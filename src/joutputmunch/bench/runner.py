"""Run each scenario once without the rules and once with them."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import Scenario, ScenarioResult
from .providers import Provider
from .records import RunRecorder


@dataclass(frozen=True)
class RunConfig:
    temperature: float
    max_tokens: int


def run_scenario(
    scenario: Scenario,
    provider: Provider,
    config: RunConfig,
    progress: Callable[[str], None] | None = None,
    recorder: RunRecorder | None = None,
) -> ScenarioResult:
    say = progress or (lambda _msg: None)
    calls = {}
    for arm, system in (("baseline", scenario.system_baseline), ("rules", scenario.system_munch)):
        say(f"  [{scenario.key}] {arm} ...")
        try:
            calls[arm] = provider.complete(
                system, scenario.user, temperature=config.temperature, max_tokens=config.max_tokens
            )
        except Exception as exc:
            if recorder:
                recorder.failed(scenario, arm, system, exc)
            raise
        if recorder:
            recorder.completed(scenario, arm, system, calls[arm])
        say(f"  [{scenario.key}] {arm}: {calls[arm].output_tokens} tokens, {calls[arm].latency_s}s")
    return ScenarioResult(
        scenario=scenario,
        provider=provider.name,
        model=provider.model,
        baseline=calls["baseline"],
        munch=calls["rules"],
    )
