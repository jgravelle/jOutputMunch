"""The claude-code provider, against a faked `claude` CLI. Nothing here starts the real one."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from joutputmunch.bench import cli
from joutputmunch.bench.providers import KEY_ENV, make_provider
from joutputmunch.bench.providers.claude_code import (
    CONTAMINATION_MARGIN_TOKENS,
    FIXED_FLAGS,
    ClaudeCodeProvider,
    contamination,
    estimate_tokens,
)
from joutputmunch.bench.records import read_records


class FakeClaude:
    """Stands in for subprocess.run. Reports input = the prompt's estimate + `overhead`."""

    def __init__(self, overhead=0, returncode=0, is_error=False):
        self.overhead = overhead
        self.returncode = returncode
        self.is_error = is_error
        self.calls = []

    def __call__(self, argv, *, input, cwd, env, **kwargs):
        system = argv[argv.index("--system-prompt") + 1]
        self.calls.append({"argv": argv, "input": input, "cwd": cwd, "env": env, "cwd_empty": not os.listdir(cwd),
                           "kwargs": kwargs})
        rules = "jOutputMunch" in system
        body = {
            "type": "result",
            "is_error": self.is_error,
            "result": "short" if rules else "a much longer answer",
            "usage": {
                "input_tokens": estimate_tokens(system) + estimate_tokens(input) + self.overhead - 3,
                "cache_creation_input_tokens": 2,
                "cache_read_input_tokens": 1,
                "output_tokens": 40 if rules else 100,
            },
            "total_cost_usd": 0.5,
        }
        return subprocess.CompletedProcess(argv, self.returncode, stdout=json.dumps(body), stderr="")


def _factory(fake):
    return lambda name, model: ClaudeCodeProvider(model or "claude-sonnet-4-6", run=fake, executable="claude")


def test_it_needs_no_key_and_defaults_to_the_published_model():
    assert KEY_ENV["claude-code"] is None
    assert make_provider("claude-code").model == "claude-sonnet-4-6"


def test_every_isolating_flag_is_passed_and_the_user_prompt_goes_by_stdin():
    fake = FakeClaude()
    p = ClaudeCodeProvider("claude-sonnet-4-6", run=fake, executable="claude")
    p.complete("SYS", "USER PROMPT", temperature=1.0, max_tokens=123)
    argv = fake.calls[0]["argv"]
    assert argv[:2] == ["claude", "-p"]
    assert argv[argv.index("--model") + 1] == "claude-sonnet-4-6"
    assert argv[argv.index("--system-prompt") + 1] == "SYS"
    for flag in ("--no-session-persistence", "--strict-mcp-config", "--exclude-dynamic-system-prompt-sections"):
        assert flag in argv, flag
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--output-format") + 1] == "json"
    assert json.loads(argv[argv.index("--settings") + 1]) == {"alwaysThinkingEnabled": False}
    assert "--mcp-config" not in argv and "--bare" not in argv
    assert "USER PROMPT" not in argv and fake.calls[0]["input"] == "USER PROMPT"
    assert argv[-len(FIXED_FLAGS):] == FIXED_FLAGS


def test_no_api_key_reaches_the_cli_and_the_output_limit_does(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key-789")
    fake = FakeClaude()
    ClaudeCodeProvider("m", run=fake, executable="claude").complete("s", "u", temperature=1.0, max_tokens=4096)
    env = fake.calls[0]["env"]
    assert "ANTHROPIC_API_KEY" not in env
    assert env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "4096"


def test_each_call_runs_in_an_empty_folder_that_is_gone_afterwards():
    fake = FakeClaude()
    ClaudeCodeProvider("m", run=fake, executable="claude").complete("s", "u", temperature=1.0, max_tokens=10)
    call = fake.calls[0]
    assert call["cwd_empty"]
    assert not Path(call["cwd"]).exists()
    assert call["kwargs"]["timeout"] > 0 and call["kwargs"]["check"] is False


def test_usage_counts_cache_tokens_as_input_and_ignores_the_dollar_figure():
    fake = FakeClaude()
    c = ClaudeCodeProvider("m", run=fake, executable="claude").complete("s" * 40, "u" * 40, temperature=1.0, max_tokens=10)
    assert c.input_tokens == estimate_tokens("s" * 40) + estimate_tokens("u" * 40)
    assert c.output_tokens == 100 and c.text == "a much longer answer"


@pytest.mark.parametrize("fake", [FakeClaude(returncode=1), FakeClaude(is_error=True)])
def test_a_failing_cli_raises_and_is_recorded_by_type(fake, tmp_path):
    records = tmp_path / "r.jsonl"
    with pytest.raises(RuntimeError):
        cli.main(["--provider", "claude-code", "-s", "bug_diagnosis", "--records", str(records)],
                 provider_factory=_factory(fake), environ={})
    assert [r["error"] for r in read_records(records)] == ["RuntimeError"]


def test_a_missing_cli_stops_before_any_call(monkeypatch):
    monkeypatch.setattr("joutputmunch.bench.providers.claude_code.shutil.which", lambda _name: None)
    with pytest.raises(SystemExit, match="not on PATH"):
        ClaudeCodeProvider("m", run=FakeClaude()).complete("s", "u", temperature=1.0, max_tokens=10)


def test_a_clean_run_writes_a_report_that_says_it_is_a_new_series(tmp_path):
    out = tmp_path / "results.md"
    records = tmp_path / "r.jsonl"
    fake = FakeClaude(overhead=CONTAMINATION_MARGIN_TOKENS)
    rc = cli.main(["--provider", "claude-code", "--save", "--output", str(out), "--records", str(records)],
                  provider_factory=_factory(fake), environ={})
    assert rc == 0 and len(fake.calls) == 10
    report = out.read_text(encoding="utf-8")
    first = report.split("\n", 3)[2]
    assert first.startswith("**A new series. Not comparable with the published API run (65.2%).**")
    assert "Temperature: **not set**" in report
    assert "Subscription usage, not priced in dollars" in report
    assert "$" not in report.split("## Usage")[1].split("## Methodology")[0]
    for r in read_records(records):
        assert r["temperature"] is None and r["cost_usd"] is None


def test_a_contaminated_run_writes_no_report_and_keeps_its_records(tmp_path, capsys):
    out = tmp_path / "results.md"
    records = tmp_path / "r.jsonl"
    # A leaked global CLAUDE.md is about 1,500 tokens.
    fake = FakeClaude(overhead=1500)
    rc = cli.main(["--provider", "claude-code", "--save", "--output", str(out), "--records", str(records)],
                  provider_factory=_factory(fake), environ={})
    assert rc == 3 and not out.exists()
    assert len(read_records(records)) == 10
    err = capsys.readouterr().err
    assert "Refused" in err and "bug_diagnosis baseline" in err


def test_the_guard_sits_below_a_leaked_claude_md():
    assert CONTAMINATION_MARGIN_TOKENS < 6059 // 4
    assert contamination("s", "u", estimate_tokens("s") + estimate_tokens("u") + CONTAMINATION_MARGIN_TOKENS) == 0
    assert contamination("s", "u", estimate_tokens("s") + estimate_tokens("u") + CONTAMINATION_MARGIN_TOKENS + 1) == 1


@pytest.mark.parametrize(("overhead", "rc", "verdict"), [(100, 0, "CLEAN"), (1500, 3, "REFUSE")])
def test_the_dry_check_makes_one_baseline_call(tmp_path, capsys, overhead, rc, verdict):
    fake = FakeClaude(overhead=overhead)
    records = tmp_path / "r.jsonl"
    assert cli.main(["--provider", "claude-code", "--dry-check", "--records", str(records)],
                    provider_factory=_factory(fake), environ={}) == rc
    assert len(fake.calls) == 1
    assert "jOutputMunch" not in fake.calls[0]["argv"][fake.calls[0]["argv"].index("--system-prompt") + 1]
    out = capsys.readouterr().out
    assert verdict in out and f"overhead: {overhead:,} tokens" in out
    assert [r["arm"] for r in read_records(records)] == ["baseline"]


def test_the_dry_check_is_only_for_claude_code(capsys):
    assert cli.main(["--dry-check"], environ={"ANTHROPIC_API_KEY": "k"}) == 2
    assert "claude-code" in capsys.readouterr().err
