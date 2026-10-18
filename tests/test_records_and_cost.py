"""Every call is on disk before the next one, and cost is net of the rules' input."""

import json

import pytest
from conftest import FakeProvider

from joutputmunch.bench import cli
from joutputmunch.bench.pricing import PRICES, call_cost
from joutputmunch.bench.records import SCHEMA, read_records
from joutputmunch.bench.report import render
from joutputmunch.bench.runner import RunConfig, run_scenario
from joutputmunch.bench.scenarios import load_scenarios


def _factory(fake):
    def make(name, model):
        fake.name, fake.model = name, model or "fake-model"
        return fake

    return make


def test_the_sourced_price_and_the_cost_arithmetic():
    p = PRICES["claude-sonnet-4-6"]
    assert (p.input_per_mtok, p.output_per_mtok) == (3.0, 15.0)
    assert p.source.startswith("https://") and p.checked
    assert call_cost("claude-sonnet-4-6", 1_000_000, 0) == 3.0
    assert call_cost("claude-sonnet-4-6", 8000, 6091) == pytest.approx(0.024 + 0.091365)
    assert call_cost("not-a-priced-model", 10, 10) is None


def test_one_line_per_call_with_the_settings_and_no_text_by_default(tmp_path, capsys):
    records = tmp_path / "r.jsonl"
    fake = FakeProvider()
    key = "sk-test-not-a-real-key-456"
    rc = cli.main(["--records", str(records)], provider_factory=_factory(fake), environ={"ANTHROPIC_API_KEY": key})
    assert rc == 0
    rows = read_records(records)
    assert len(rows) == 10 == len(fake.calls)
    assert {r["arm"] for r in rows} == {"baseline", "rules"}
    for r in rows:
        assert r["schema"] == SCHEMA
        assert (r["temperature"], r["max_tokens"], r["model"]) == (1.0, 4096, "fake-model")
        assert "text" not in r and r["cost_usd"] is None
    raw = records.read_text(encoding="utf-8")
    assert key not in raw and key not in capsys.readouterr().out


def test_text_is_kept_only_when_asked(tmp_path):
    records = tmp_path / "r.jsonl"
    cli.main(["-s", "general_question", "--records", str(records), "--record-text"],
             provider_factory=_factory(FakeProvider()), environ={"ANTHROPIC_API_KEY": "k"})
    assert {r["text"] for r in read_records(records)} == {"short", "a much longer answer"}


class _DiesOnThirdCall(FakeProvider):
    def complete(self, system, user, *, temperature, max_tokens):
        if len(self.calls) == 2:
            raise TimeoutError("request id abc123 timed out")
        return super().complete(system, user, temperature=temperature, max_tokens=max_tokens)


def test_a_failed_call_keeps_the_calls_already_paid_for(tmp_path):
    records = tmp_path / "r.jsonl"
    with pytest.raises(TimeoutError):
        cli.main(["--records", str(records)], provider_factory=_factory(_DiesOnThirdCall()),
                 environ={"ANTHROPIC_API_KEY": "k"})
    rows = read_records(records)
    assert [("error" in r) for r in rows] == [False, False, True]
    assert rows[2]["error"] == "TimeoutError"
    assert "abc123" not in records.read_text(encoding="utf-8"), "an SDK message can carry request details"


def test_a_record_reaches_disk_before_the_next_call(tmp_path):
    records = tmp_path / "r.jsonl"
    seen = []

    class Watching(FakeProvider):
        def complete(self, system, user, *, temperature, max_tokens):
            seen.append(len(records.read_text(encoding="utf-8").splitlines()) if records.exists() else 0)
            return super().complete(system, user, temperature=temperature, max_tokens=max_tokens)

    cli.main(["-s", "pr_review", "--records", str(records)], provider_factory=_factory(Watching()),
             environ={"ANTHROPIC_API_KEY": "k"})
    assert seen == [0, 1]


def test_an_unwritable_records_path_stops_before_any_call(tmp_path, capsys):
    blocker = tmp_path / "a-file"
    blocker.write_text("x", encoding="utf-8")
    fake = FakeProvider()
    rc = cli.main(["--records", str(blocker / "r.jsonl")], provider_factory=_factory(fake),
                  environ={"ANTHROPIC_API_KEY": "k"})
    assert rc == 2 and fake.calls == []
    assert "--records" in capsys.readouterr().err


def test_the_report_prices_both_arms_and_the_net_change():
    fake = FakeProvider(model="claude-sonnet-4-6")
    config = RunConfig(temperature=1.0, max_tokens=4096)
    results = [run_scenario(s, fake, config) for s in load_scenarios().values()]
    text = render(results, config)
    assert "$3 input and $15 output per million tokens" in text
    # baseline: 30 in + 100 out; rules: 900 in + 40 out, per scenario
    base = call_cost("claude-sonnet-4-6", 30, 100)
    munch = call_cost("claude-sonnet-4-6", 900, 40)
    assert f"| General question | ${base:.4f} | ${munch:.4f} |" in text
    assert f"**${5 * base:.4f}**" in text and f"**${5 * munch:.4f}**" in text


def test_an_unpriced_model_says_so_instead_of_inventing_a_figure(fake_provider):
    config = RunConfig(temperature=1.0, max_tokens=4096)
    text = render([run_scenario(load_scenarios()["general_question"], fake_provider, config)], config)
    assert "Not priced: fake-model" in text
    assert "Baseline cost" not in text


def test_records_are_valid_json_lines(tmp_path):
    records = tmp_path / "r.jsonl"
    cli.main(["-s", "bug_diagnosis", "--records", str(records)], provider_factory=_factory(FakeProvider()),
             environ={"ANTHROPIC_API_KEY": "k"})
    for line in records.read_text(encoding="utf-8").splitlines():
        json.loads(line)
