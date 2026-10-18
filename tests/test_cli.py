import subprocess
import sys

from joutputmunch.bench import cli


def _factory(fake):
    def make(name, model):
        fake.name, fake.model = name, model or "fake-model"
        return fake

    return make


def test_list_needs_no_key(capsys):
    assert cli.main(["--list"], environ={}) == 0
    assert "general_question" in capsys.readouterr().out


def test_a_missing_key_stops_before_any_call(fake_provider, capsys):
    assert cli.main([], provider_factory=_factory(fake_provider), environ={}) == 2
    assert fake_provider.calls == []
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_an_unknown_scenario_is_refused(fake_provider):
    assert cli.main(["-s", "nope"], provider_factory=_factory(fake_provider), environ={"ANTHROPIC_API_KEY": "k"}) == 2


def test_the_defaults_match_the_committed_harness_and_the_published_model():
    args = cli.build_parser().parse_args([])
    assert (args.provider, args.model, args.temperature, args.max_tokens) == ("anthropic", None, 1.0, 4096)


def test_save_writes_the_report_and_never_the_key(fake_provider, tmp_path, capsys):
    out = tmp_path / "results.md"
    key = "sk-test-not-a-real-key-123"
    rc = cli.main(
        ["--save", "--output", str(out), "-s", "bug_diagnosis"],
        provider_factory=_factory(fake_provider),
        environ={"ANTHROPIC_API_KEY": key},
    )
    assert rc == 0
    report = out.read_text(encoding="utf-8")
    assert "Bug diagnosis" in report and "Temperature: **1.0**" in report
    assert key not in report and key not in capsys.readouterr().out
    assert len(fake_provider.calls) == 2


def test_the_old_entry_point_still_works(repo):
    proc = subprocess.run(
        [sys.executable, str(repo / "benchmarks" / "harness.py"), "--list"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "code_explanation" in proc.stdout


def test_a_missing_rules_dir_is_named_not_a_traceback(tmp_path, capsys):
    assert cli.main(["--list", "--rules-dir", str(tmp_path)], environ={}) == 2
    err = capsys.readouterr().err
    assert str(tmp_path) in err and "--rules-dir" in err


def test_save_to_a_missing_folder_stops_before_any_paid_call(fake_provider, tmp_path, capsys):
    out = tmp_path / "no-such-dir" / "results.md"
    rc = cli.main(["--save", "--output", str(out)], provider_factory=_factory(fake_provider), environ={"ANTHROPIC_API_KEY": "k"})
    assert rc == 2 and fake_provider.calls == []
    assert "--output" in capsys.readouterr().err


def test_each_missing_rule_file_is_named(tmp_path, capsys):
    (tmp_path / "core.md").write_text("rules", encoding="utf-8")
    assert cli.main(["--list", "--rules-dir", str(tmp_path)], environ={}) == 2
    assert "code-assistant.md" in capsys.readouterr().err
