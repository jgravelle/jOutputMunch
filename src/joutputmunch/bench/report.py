"""Render a run as Markdown. It states what was measured and what was not."""

from __future__ import annotations

from .models import ScenarioResult, signed_change, summarize
from .pricing import PRICES, call_cost
from .runner import RunConfig


def _fenced(text: str) -> list[str]:
    """Fence raw output with more backticks than it contains, so its own code blocks cannot close the fence."""
    longest, run = 0, 0
    for ch in text:
        run = run + 1 if ch == "`" else 0
        longest = max(longest, run)
    fence = "`" * max(3, longest + 1)
    return [fence, text, fence]


def _cost(c, model: str) -> float | None:
    return call_cost(model, c.input_tokens, c.output_tokens)


def _cost_section(results: list[ScenarioResult]) -> list[str]:
    """Input plus output cost per arm. The rules cost input on every call, so this is the net figure."""
    lines = ["## Cost", ""]
    models = sorted({r.model for r in results})
    unpriced = [m for m in models if m not in PRICES]
    if unpriced:
        return lines + [f"Not priced: {', '.join(unpriced)} has no sourced price in `pricing.py`."]
    for m in models:
        p = PRICES[m]
        lines.append(
            f"{m}: ${p.input_per_mtok:g} input and ${p.output_per_mtok:g} output per million tokens "
            f"({p.source}, read {p.checked})."
        )
    lines += [
        "",
        "List prices, input plus output, no prompt caching. Net change is with-rules minus baseline.",
        "",
        "| Scenario | Baseline cost | With rules cost | Net change |",
        "|---|---|---|---|",
    ]
    base_total = munch_total = 0.0
    for r in results:
        b, m = _cost(r.baseline, r.model), _cost(r.munch, r.model)
        base_total += b
        munch_total += m
        lines.append(f"| {r.scenario.label} | ${b:.4f} | ${m:.4f} | {_signed_usd(m - b)} |")
    lines.append(
        f"| **Total** | **${base_total:.4f}** | **${munch_total:.4f}** | **{_signed_usd(munch_total - base_total)}** |"
    )
    return lines


def _signed_usd(delta: float) -> str:
    if round(delta, 4) == 0:
        return "$0.0000"
    return f"{'+' if delta > 0 else '-'}${abs(delta):.4f}"


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
            f"| **{signed_change(r.reduction_pct)}** | {r.baseline.latency_s}s | {r.munch.latency_s}s |"
        )
    lines += [
        f"| **Total** | **{s.baseline_tokens:,}** | **{s.munch_tokens:,}** | **{signed_change(s.aggregate_pct)}** | | |",
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
    lines += ["", *_cost_section(results), "", "## Methodology"]
    lines += [
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
        lines += [f"### {r.scenario.label}", "", "**Baseline:**", *_fenced(r.baseline.text), ""]
        lines += ["**With jOutputMunch rules:**", *_fenced(r.munch.text), ""]
    return "\n".join(lines)
