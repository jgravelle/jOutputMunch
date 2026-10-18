import pytest

from joutputmunch.bench.models import (
    Completion,
    Scenario,
    ScenarioResult,
    reduction_pct,
    summarize,
)
from joutputmunch.bench.report import render
from joutputmunch.bench.runner import RunConfig, run_scenario
from joutputmunch.bench.scenarios import load_scenarios


def _result(base, munch, label="x"):
    s = Scenario(key=label, label=label, user="u", system_baseline="b", system_munch="m")
    return ScenarioResult(s, "anthropic", "m", Completion("", base, 0, 1.0), Completion("", munch, 0, 1.0))


def test_the_published_numbers_give_both_summaries():
    """benchmarks/results.md: 65.2% is the aggregate; the plain mean is 59.6%."""
    published = [(650, 193), (405, 158), (698, 351), (602, 358), (2165, 511)]
    s = summarize([_result(b, m, str(i)) for i, (b, m) in enumerate(published)])
    assert (s.baseline_tokens, s.munch_tokens) == (4520, 1571)
    assert s.aggregate_pct == 65.2
    assert s.mean_pct == 59.6


def test_reduction_handles_a_zero_baseline_and_growth():
    assert reduction_pct(0, 5) == 0.0
    assert reduction_pct(100, 120) == -20.0


def test_summarize_refuses_nothing():
    with pytest.raises(ValueError):
        summarize([])


def test_both_arms_get_the_same_prompt_temperature_and_limit(fake_provider):
    scenario = load_scenarios()["general_question"]
    result = run_scenario(scenario, fake_provider, RunConfig(temperature=0.3, max_tokens=123))
    base, munch = fake_provider.calls
    assert base["system"] == scenario.system_baseline and munch["system"] == scenario.system_munch
    assert base["user"] == munch["user"] == scenario.user
    assert {c["temperature"] for c in fake_provider.calls} == {0.3}
    assert {c["max_tokens"] for c in fake_provider.calls} == {123}
    assert result.reduction_pct == 60.0


def test_the_report_names_its_settings_and_its_limits(fake_provider):
    config = RunConfig(temperature=1.0, max_tokens=4096)
    results = [run_scenario(s, fake_provider, config) for s in load_scenarios().values()]
    text = render(results, config)
    assert "anthropic/fake-model" in text
    assert "Temperature: **1.0** (set explicitly)" in text
    assert "Aggregate output-token reduction: 60.0%" in text
    assert "Unweighted mean of the 5 scenario reductions: 60.0%" in text
    assert "Answer quality is not measured" in text
    assert "| General question | 30 | 900 |" in text
