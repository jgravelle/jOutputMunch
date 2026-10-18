"""Plain data passed between providers, the runner and the report."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Completion:
    """One provider call. Token counts are the provider's own usage figures."""

    text: str
    output_tokens: int
    input_tokens: int
    latency_s: float


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    user: str
    system_baseline: str
    system_munch: str


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    provider: str
    model: str
    baseline: Completion
    munch: Completion

    @property
    def reduction_pct(self) -> float:
        """Output-token reduction for this scenario, in percent (one decimal)."""
        return reduction_pct(self.baseline.output_tokens, self.munch.output_tokens)


def signed_change(pct: float) -> str:
    """A reduction as a signed change: 60.0 -> '-60.0%', -20.0 (growth) -> '+20.0%'."""
    if pct == 0:
        return "0.0%"
    return f"{-pct:+.1f}%"


def reduction_pct(baseline: int, munch: int) -> float:
    if baseline <= 0:
        return 0.0
    return round((baseline - munch) / baseline * 100, 1)


@dataclass(frozen=True)
class Summary:
    baseline_tokens: int
    munch_tokens: int
    aggregate_pct: float
    """Token-weighted: total reduction over total baseline tokens."""
    mean_pct: float
    """Unweighted mean of the per-scenario reductions."""
    scenarios: int


def summarize(results: list[ScenarioResult]) -> Summary:
    if not results:
        raise ValueError("no results to summarize")
    base = sum(r.baseline.output_tokens for r in results)
    munch = sum(r.munch.output_tokens for r in results)
    mean = round(sum(r.reduction_pct for r in results) / len(results), 1)
    return Summary(base, munch, reduction_pct(base, munch), mean, len(results))
