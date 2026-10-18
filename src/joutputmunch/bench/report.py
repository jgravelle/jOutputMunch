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


CLAUDE_CODE = "claude-code"


def _usage_section(results: list[ScenarioResult]) -> list[str]:
    from .providers.claude_code import overhead

    calls = [c for r in results for c in (r.baseline, r.munch)]
    lines = [
        "## Usage",
        "",
        (
            f"Subscription usage, not priced in dollars: {sum(c.input_tokens for c in calls):,} input and "
            f"{sum(c.output_tokens for c in calls):,} output tokens over {len(calls)} calls."
        ),
        "",
        "Input each call reported beyond its prompt's estimated size (four characters a token):",
        "",
        "| Scenario | Baseline overhead | With rules overhead |",
        "|---|---|---|",
    ]
    for r in results:
        s = r.scenario
        lines.append(
            f"| {s.label} | {overhead(s.system_baseline, s.user, r.baseline.input_tokens):,} "
            f"| {overhead(s.system_munch, s.user, r.munch.input_tokens):,} |"
        )
    return lines


def render(results: list[ScenarioResult], config: RunConfig) -> str:
    s = summarize(results)
    models = sorted({f"{r.provider}/{r.model}" for r in results})
    via_claude_code = any(r.provider == CLAUDE_CODE for r in results)
    lines = [
        "# jOutputMunch Benchmark Results",
        "",
    ]
    if via_claude_code:
        lines += [
            (
                "**A new series. Not comparable with the published API run.** These calls ran "
                "through Claude Code (`claude -p`) on a subscription login, a different path to the model "
                "from the API calls that produced the published figures."
            ),
            "",
        ]
    lines += [
        (
            "Same prompt, same model. Only difference: jOutputMunch rules in the system prompt."
            if via_claude_code
            else "Same prompt, same model, same temperature. Only difference: jOutputMunch rules in the system prompt."
        ),
        "",
        (
            f"Model: **{', '.join(models)}**. "
            + (
                "Temperature: **not set** (Claude Code has no temperature flag; its default applies). "
                if via_claude_code
                else f"Temperature: **{config.temperature}** (set explicitly). "
            )
            + f"Max output tokens: {config.max_tokens}. One run per cell."
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
    lines += ["", *(_usage_section(results) if via_claude_code else _cost_section(results)), "", "## Methodology"]
    if via_claude_code:
        lines += [
            "",
            (
                "- Claude Code ran with its own context switched off as far as its flags allow: the system "
                "prompt replaced, no tools, no MCP servers, no user, project or local settings files "
                "requested, no session saved to disk, and each call in an empty folder. Managed settings "
                "still apply. Whether anything else reached the model is checked only by the guard, and "
                "only above its limits: each call's reported input against its prompt's estimated size "
                "(over by 750, or under by 400), and the two arms' overheads against each other (-250 to "
                "+150). Smaller additions pass unseen. A run that fails any check writes no report."
            ),
            (
                "- Thinking was requested off. The usage block does not split thinking tokens out of output "
                "tokens, so that cannot be confirmed here."
            ),
        ]
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
