"""Run each scenario once without the rules and once with them."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import Scenario, ScenarioResult
from .providers import Provider


@dataclass(frozen=True)
class RunConfig:
    temperature: float
    max_tokens: int


def run_scenario(
    scenario: Scenario,
    provider: Provider,
    config: RunConfig,
    progress: Callable[[str], None] | None = None,
) -> ScenarioResult:
    say = progress or (lambda _msg: None)
    calls = {}
    for arm, system in (("baseline", scenario.system_baseline), ("with rules", scenario.system_munch)):
        say(f"  [{scenario.key}] {arm} ...")
        calls[arm] = provider.complete(
            system, scenario.user, temperature=config.temperature, max_tokens=config.max_tokens
        )
        say(f"  [{scenario.key}] {arm}: {calls[arm].output_tokens} tokens, {calls[arm].latency_s}s")
    return ScenarioResult(
        scenario=scenario,
        provider=provider.name,
        model=provider.model,
        baseline=calls["baseline"],
        munch=calls["with rules"],
    )
