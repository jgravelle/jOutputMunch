"""Render a run as Markdown. It states what was measured and what was not."""

from __future__ import annotations

from .models import ScenarioResult, summarize
from .runner import RunConfig


def render(results: list[ScenarioResult], config: RunConfig) -> str:
    s = summarize(results)
    models = sorted({f"{r.provider}/{r.model}" for r in results})
    lines = [
        "# jOutputMunch Benchmark Results",
        "",
        "Same prompt, same model, same temperature. Only difference: jOutputMunch rules in the system prompt.",
        "",
        (
            f"Model: **{', '.join(models)}**. Temperature: **{config.temperature}** (set explicitly). "
            f"Max output tokens: {config.max_tokens}. One run per cell."
        ),
        "",
        "| Scenario | Baseline tokens | With rules | Reduction | Baseline latency | With rules latency |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario.label} | {r.baseline.output_tokens:,} | {r.munch.output_tokens:,} "
            f"| **-{r.reduction_pct}%** | {r.baseline.latency_s}s | {r.munch.latency_s}s |"
        )
    lines += [
        f"| **Total** | **{s.baseline_tokens:,}** | **{s.munch_tokens:,}** | **-{s.aggregate_pct}%** | | |",
        "",
        (
            f"Aggregate output-token reduction: {s.aggregate_pct}% (total over total). "
            f"Unweighted mean of the {s.scenarios} scenario reductions: {s.mean_pct}%."
        ),
        "",
        "## Input tokens",
        "",
        "The rules make the system prompt longer. Provider-reported input tokens per call:",
        "",
        "| Scenario | Baseline input | With rules input |",
        "|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r.scenario.label} | {r.baseline.input_tokens:,} | {r.munch.input_tokens:,} |")
    lines += [
        "",
        "## Methodology",
        "",
        "- Token counts are the provider's native usage figures.",
        (
            "- Each scenario runs once with a generic system prompt (baseline) and once with "
            "`rules/core.md` (plus `rules/code-assistant.md` for coding scenarios)."
        ),
        "- Every run is recorded as-is.",
        "- Latency is wall-clock, one run per cell: indicative, not statistical.",
        "- Answer quality is not measured. Compare the raw outputs below yourself.",
        "",
        "## Raw output",
        "",
    ]
    for r in results:
        lines += [
            f"### {r.scenario.label}",
            "",
            "**Baseline:**",
            "```",
            r.baseline.text,
            "```",
            "",
            "**With jOutputMunch rules:**",
            "```",
            r.munch.text,
            "```",
            "",
        ]
    return "\n".join(lines)
