"""The claude-code provider, against a faked `claude` CLI. Nothing here starts the real one."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from joutputmunch.bench import cli
from joutputmunch.bench.providers import KEY_ENV, make_provider
from joutputmunch.bench.providers.claude_code import (
    ARM_GAP_HIGH_TOKENS,
    ARM_GAP_LOW_TOKENS,
    CONTAMINATION_MARGIN_TOKENS,
    FIXED_FLAGS,
    UNDER_LIMIT_TOKENS,
    ClaudeCodeProvider,
    check_pair,
    child_env,
    contamination,
    estimate_tokens,
    resolve_executable,
)
from joutputmunch.bench.records import read_records
from joutputmunch.bench.scenarios import load_scenarios


class FakeClaude:
    """Stands in for subprocess.run. Reports input = the prompt's estimate + that arm's overhead."""

    def __init__(self, base_overhead=0, rules_overhead=None, returncode=0, is_error=False):
        self.base_overhead = base_overhead
        self.rules_overhead = base_overhead if rules_overhead is None else rules_overhead
        self.returncode = returncode
        self.is_error = is_error
        self.calls = []

    def __call__(self, argv, *, input, cwd, env, **kwargs):
        system = argv[argv.index("--system-prompt") + 1]
        self.calls.append({"argv": argv, "input": input, "cwd": cwd, "env": env, "cwd_empty": not os.listdir(cwd),
                           "kwargs": kwargs})
        rules = "jOutputMunch" in system
        extra = self.rules_overhead if rules else self.base_overhead
        body = {
            "type": "result",
            "is_error": self.is_error,
            "result": "short" if rules else "a much longer answer",
            "usage": {
                "input_tokens": estimate_tokens(system) + estimate_tokens(input) + extra - 3,
                "cache_creation_input_tokens": 2,
                "cache_read_input_tokens": 1,
                "output_tokens": 40 if rules else 100,
            },
            "total_cost_usd": 0.5,
        }
        return subprocess.CompletedProcess(argv, self.returncode, stdout=json.dumps(body), stderr="")


def _factory(fake):
    return lambda name, model: ClaudeCodeProvider(model or "claude-sonnet-4-6", run=fake, executable="claude")


def _run(args, fake, tmp_path, **kw):
    return cli.main(["--provider", "claude-code", "--records", str(tmp_path / "r.jsonl"), *args],
                    provider_factory=_factory(fake), environ={}, **kw)


# --- the command line ----------------------------------------------------------


def test_it_needs_no_key_and_defaults_to_the_published_model():
    assert KEY_ENV["claude-code"] is None
    assert make_provider("claude-code").model == "claude-sonnet-4-6"


def test_every_isolating_flag_is_passed_and_the_user_prompt_goes_by_stdin():
    fake = FakeClaude()
    ClaudeCodeProvider("claude-sonnet-4-6", run=fake, executable="claude").complete(
        "SYS", "USER PROMPT", temperature=1.0, max_tokens=123)
    argv = fake.calls[0]["argv"]
    assert argv[:2] == ["claude", "-p"]
    assert argv[argv.index("--model") + 1] == "claude-sonnet-4-6"
    assert argv[argv.index("--system-prompt") + 1] == "SYS"
    for flag in ("--no-session-persistence", "--strict-mcp-config"):
        assert flag in argv, flag
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--output-format") + 1] == "json"
    assert json.loads(argv[argv.index("--settings") + 1]) == {"alwaysThinkingEnabled": False}
    assert "--mcp-config" not in argv and "--bare" not in argv
    assert "USER PROMPT" not in argv and fake.calls[0]["input"] == "USER PROMPT"
    assert argv[-len(FIXED_FLAGS):] == FIXED_FLAGS


def test_the_real_rules_text_survives_a_real_process_boundary():
    """The defect a faked runner cannot see: the argv a process RECEIVES, with the actual rules text.

    python.exe is a stand-in for claude.exe, whose own argument parser is not checked here; the
    guard's under-limit and gap checks are the backstop if the two ever differ.
    """
    rules = load_scenarios()["code_explanation"].system_munch
    assert "\\n" not in rules and "\n" in rules  # multi-line, which is what a .cmd shim breaks
    sent = ClaudeCodeProvider("claude-sonnet-4-6", executable="claude").command(rules)[1:]
    echo = "import json,sys; sys.stdout.write(json.dumps(sys.argv[1:]))"
    proc = subprocess.run([sys.executable, "-c", echo, *sent], capture_output=True, text=True,
                          encoding="utf-8", timeout=60, check=True)
    assert json.loads(proc.stdout) == sent


@pytest.mark.parametrize("suffix", [".cmd", ".CMD", ".bat", ".ps1"])
def test_a_shell_shim_is_resolved_to_the_exe_beside_it(tmp_path, suffix):
    shim = tmp_path / f"claude{suffix}"
    shim.write_text("@echo off", encoding="utf-8")
    exe = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert resolve_executable(str(shim)) == str(exe)


def test_a_shim_with_no_exe_beside_it_is_refused(tmp_path):
    shim = tmp_path / "claude.cmd"
    shim.write_text("@echo off", encoding="utf-8")
    with pytest.raises(SystemExit, match="shell shim"):
        resolve_executable(str(shim))


@pytest.mark.skipif(os.name != "nt", reason="npm's extensionless sh script is a shim only on Windows")
def test_an_extensionless_claude_is_a_shim_on_windows(tmp_path):
    with pytest.raises(SystemExit, match="shell shim"):
        resolve_executable(str(tmp_path / "claude"))


def test_an_executable_is_used_as_found_and_a_missing_one_is_refused(tmp_path):
    assert resolve_executable(str(tmp_path / "claude.exe")) == str(tmp_path / "claude.exe")
    if os.name != "nt":
        assert resolve_executable("/usr/local/bin/claude") == str(Path("/usr/local/bin/claude"))
    with pytest.raises(SystemExit, match="not on PATH"):
        resolve_executable(None)


def test_a_missing_cli_stops_before_any_call(monkeypatch):
    monkeypatch.setattr("joutputmunch.bench.providers.claude_code.shutil.which", lambda _name: None)
    fake = FakeClaude()
    with pytest.raises(SystemExit, match="not on PATH"):
        ClaudeCodeProvider("m", run=fake).complete("s", "u", temperature=1.0, max_tokens=10)
    assert fake.calls == []


# --- the environment and the folder -----------------------------------------------


def test_no_key_or_provider_switch_reaches_the_cli_and_the_output_limit_does():
    env = child_env({
        "ANTHROPIC_API_KEY": "sk-test-not-a-real-key-789",
        "ANTHROPIC_AUTH_TOKEN": "t",
        "ANTHROPIC_BASE_URL": "https://example.invalid",
        "CLAUDE_CODE_USE_BEDROCK": "1",
        "CLAUDE_CODE_USE_VERTEX": "1",
        "CLAUDE_CODE_USE_FOUNDRY": "1",
        "CLAUDECODE": "1",
        "PATH": "p",
    }, max_tokens=4096)
    assert env == {"PATH": "p", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "4096"}


def test_the_provider_passes_the_stripped_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key-789")
    fake = FakeClaude()
    ClaudeCodeProvider("m", run=fake, executable="claude").complete("s", "u", temperature=1.0, max_tokens=4096)
    env = fake.calls[0]["env"]
    assert "ANTHROPIC_API_KEY" not in env and env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "4096"


def test_each_call_runs_in_an_empty_folder_that_is_gone_afterwards():
    fake = FakeClaude()
    ClaudeCodeProvider("m", run=fake, executable="claude").complete("s", "u", temperature=1.0, max_tokens=10)
    call = fake.calls[0]
    assert call["cwd_empty"] and not Path(call["cwd"]).exists()
    assert call["kwargs"]["timeout"] > 0 and call["kwargs"]["check"] is False


# --- parsing and failures -------------------------------------------------------


def test_usage_counts_cache_tokens_as_input_and_ignores_the_dollar_figure():
    c = ClaudeCodeProvider("m", run=FakeClaude(), executable="claude").complete(
        "s" * 40, "u" * 40, temperature=1.0, max_tokens=10)
    assert c.input_tokens == estimate_tokens("s" * 40) + estimate_tokens("u" * 40)
    assert c.output_tokens == 100 and c.text == "a much longer answer"


@pytest.mark.parametrize("fake", [FakeClaude(returncode=1), FakeClaude(is_error=True)])
def test_a_failing_cli_raises_and_is_recorded_by_type(fake, tmp_path):
    with pytest.raises(RuntimeError):
        _run(["-s", "bug_diagnosis"], fake, tmp_path)
    assert [r["error"] for r in read_records(tmp_path / "r.jsonl")] == ["RuntimeError"]


def test_a_timeout_does_not_repeat_the_argv():
    def slow(argv, **kw):
        raise subprocess.TimeoutExpired(argv, 600)

    with pytest.raises(TimeoutError) as info:
        ClaudeCodeProvider("m", run=slow, executable="claude").complete("SECRETISH SYSTEM TEXT", "u",
                                                                        temperature=1.0, max_tokens=10)
    assert "SECRETISH" not in str(info.value) and info.value.__cause__ is None


# --- the guard ------------------------------------------------------------------


def test_the_guard_sits_below_a_leaked_claude_md():
    assert CONTAMINATION_MARGIN_TOKENS < 6059 // 4
    at_limit = estimate_tokens("s") + estimate_tokens("u") + CONTAMINATION_MARGIN_TOKENS
    assert contamination("s", "u", at_limit) == 0 and contamination("s", "u", at_limit + 1) == 1


def test_check_pair_names_each_kind_of_problem():
    s, u = "s" * 40, "u" * 40
    clean = estimate_tokens(s) + estimate_tokens(u)
    assert check_pair("k", u, s, clean, s, clean) == []
    assert check_pair("k", u, s, clean, s, clean + 1500)[0].startswith("k rules:")
    allowed = f"(allowed {ARM_GAP_LOW_TOKENS:+,} to {ARM_GAP_HIGH_TOKENS:+,})"
    high = check_pair("k", u, s, clean, s, clean + ARM_GAP_HIGH_TOKENS + 1)
    assert high == [f"k: the arms' overheads differ by +{ARM_GAP_HIGH_TOKENS + 1:,} tokens {allowed}"]
    assert check_pair("k", u, s, clean, s, clean + ARM_GAP_HIGH_TOKENS) == []
    # The negative side is what a cut-short rules prompt looks like.
    low = check_pair("k", u, s, clean, s, clean + ARM_GAP_LOW_TOKENS - 1)
    assert low == [f"k: the arms' overheads differ by {ARM_GAP_LOW_TOKENS - 1:+,} tokens {allowed}"]
    assert check_pair("k", u, s, clean, s, clean + ARM_GAP_LOW_TOKENS) == []
    # A prompt that never arrived reports less input than the prompt itself, in either arm.
    lost = check_pair("k", u, s, clean - UNDER_LIMIT_TOKENS - 1, s, clean - UNDER_LIMIT_TOKENS - 1)
    assert [p for p in lost if "did not arrive" in p] == [
        f"k baseline: {clean - UNDER_LIMIT_TOKENS - 1:,} input tokens, less than its own prompt; the prompt did not arrive",
        f"k rules: {clean - UNDER_LIMIT_TOKENS - 1:,} input tokens, less than its own prompt; the prompt did not arrive",
    ]


def test_a_clean_run_writes_a_report_that_says_it_is_a_new_series(tmp_path):
    out = tmp_path / "results.md"
    fake = FakeClaude(base_overhead=700)
    assert _run(["--save", "--output", str(out)], fake, tmp_path) == 0 and len(fake.calls) == 10
    report = out.read_text(encoding="utf-8")
    assert report.split("\n", 3)[2].startswith("**A new series. Not comparable with the published API run.**")
    assert "Same prompt, same model. Only difference" in report and "same temperature" not in report
    assert "Temperature: **not set**" in report
    assert "Subscription usage, not priced in dollars" in report
    assert "| General question | 700 | 700 |" in report
    assert "$" not in report.split("## Usage")[1].split("## Methodology")[0]
    for r in read_records(tmp_path / "r.jsonl"):
        assert r["temperature"] is None and r["cost_usd"] is None


@pytest.mark.parametrize(("fake", "names"), [
    (FakeClaude(base_overhead=1500), "bug_diagnosis baseline"),
    (FakeClaude(base_overhead=0, rules_overhead=1500), "bug_diagnosis rules"),
    (FakeClaude(base_overhead=0, rules_overhead=400), "bug_diagnosis: the arms' overheads differ"),
    # The shim defect: a rules prompt cut to its first line reports far less input than it should.
    (FakeClaude(base_overhead=0, rules_overhead=-1400), "bug_diagnosis rules: "),
])
def test_a_contaminated_run_writes_no_report_and_keeps_its_records(tmp_path, capsys, fake, names):
    out = tmp_path / "results.md"
    assert _run(["--save", "--output", str(out)], fake, tmp_path) == 3 and not out.exists()
    assert len(read_records(tmp_path / "r.jsonl")) == 10
    err = capsys.readouterr().err
    assert "Refused" in err and names in err


@pytest.mark.parametrize(("fake", "rc", "verdict"), [
    (FakeClaude(base_overhead=100), 0, "CLEAN"),
    (FakeClaude(base_overhead=1500), 3, "REFUSE"),
    (FakeClaude(base_overhead=100, rules_overhead=1500), 3, "REFUSE"),
])
def test_the_dry_check_runs_both_arms_of_one_scenario(tmp_path, capsys, fake, rc, verdict):
    assert _run(["--dry-check"], fake, tmp_path) == rc
    assert len(fake.calls) == 2
    systems = [c["argv"][c["argv"].index("--system-prompt") + 1] for c in fake.calls]
    assert "jOutputMunch" not in systems[0] and "jOutputMunch" in systems[1]
    assert verdict in capsys.readouterr().out
    assert [r["arm"] for r in read_records(tmp_path / "r.jsonl")] == ["baseline", "rules"]


def test_the_dry_check_is_only_for_claude_code(capsys):
    assert cli.main(["--dry-check"], environ={"ANTHROPIC_API_KEY": "k"}) == 2
    assert "claude-code" in capsys.readouterr().err
