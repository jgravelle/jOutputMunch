"""Command line for the benchmark harness.

Every run calls a paid API: two calls per scenario.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from .models import signed_change, summarize
from .pricing import call_cost
from .providers import DEFAULT_MODELS, KEY_ENV, make_provider
from .records import RunRecorder
from .report import render
from .runner import RunConfig, run_scenario
from .scenarios import RULE_SETS, default_rules_dir, load_scenarios

# Anthropic's and OpenAI's documented default. The harness committed with the
# published results set no temperature, so it relied on this; it is explicit now.
DEFAULT_TEMPERATURE = 1.0
DEFAULT_MAX_TOKENS = 4096


def default_records_dir() -> Path:
    """benchmarks/runs/ in the checkout (gitignored), or under the working folder when installed."""
    root = Path(__file__).resolve().parents[3]
    if not (root / "pyproject.toml").is_file():
        root = Path.cwd()
    return root / "benchmarks" / "runs"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="joutputmunch-bench", description="jOutputMunch benchmark harness")
    p.add_argument("--scenario", "-s", help="run one scenario by key (see --list)")
    p.add_argument("--list", action="store_true", help="list the scenarios and exit")
    p.add_argument("--provider", choices=sorted(DEFAULT_MODELS), default="anthropic")
    p.add_argument("--model", help="model id (default: the provider's entry in DEFAULT_MODELS)")
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--rules-dir", type=Path, default=None, help="directory holding core.md and code-assistant.md")
    p.add_argument("--save", action="store_true", help="write the report to --output")
    p.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "benchmarks" / "results.md",
        help="report path for --save (default: benchmarks/results.md)",
    )
    p.add_argument(
        "--records",
        type=Path,
        default=None,
        help="JSONL file that gets one line per call, written as each call ends "
        "(default: benchmarks/runs/<run id>.jsonl, gitignored)",
    )
    p.add_argument("--record-text", action="store_true", help="also keep each answer's text in the records")
    return p


def main(argv: list[str] | None = None, *, provider_factory=make_provider, environ=None) -> int:
    args = build_parser().parse_args(argv)
    environ = os.environ if environ is None else environ
    rules_dir = args.rules_dir or default_rules_dir()
    needed = sorted({f for files in RULE_SETS.values() for f in files})
    missing = [f for f in needed if not (rules_dir / f).is_file()]
    if missing:
        print(
            f"No {', '.join(missing)} in {rules_dir}. Run from a checkout (pip install -e .) or pass --rules-dir.",
            file=sys.stderr,
        )
        return 2
    scenarios = load_scenarios(rules_dir)

    if args.list:
        for key, s in scenarios.items():
            print(f"  {key:25s} {s.label}")
        return 0

    if args.scenario:
        if args.scenario not in scenarios:
            print(f"Unknown scenario: {args.scenario}. Use --list.", file=sys.stderr)
            return 2
        scenarios = {args.scenario: scenarios[args.scenario]}

    # Every paid call happens below, so a report that cannot be written must stop us here.
    if args.save and not args.output.parent.is_dir():
        print(f"Cannot write {args.output}: no such folder. Pass --output.", file=sys.stderr)
        return 2

    if not environ.get(KEY_ENV[args.provider]):
        print(f"Set {KEY_ENV[args.provider]} to run against {args.provider}.", file=sys.stderr)
        return 2

    # A random suffix: two runs must never share a file or an id, whatever the clock's resolution.
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"
    records = args.records or default_records_dir() / f"{run_id}.jsonl"
    try:
        records.parent.mkdir(parents=True, exist_ok=True)
        # Open it once now: a records file that cannot be written must stop the run before the first paid call.
        with records.open("a", encoding="utf-8"):
            pass
    except OSError:
        print(f"Cannot write {records}. Pass --records.", file=sys.stderr)
        return 2

    provider = provider_factory(args.provider, args.model)
    config = RunConfig(temperature=args.temperature, max_tokens=args.max_tokens)
    recorder = RunRecorder(
        records,
        run_id=run_id,
        provider=provider.name,
        model=provider.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        record_text=args.record_text,
    )
    print(f"Running {len(scenarios)} scenario(s) on {provider.name}/{provider.model}, temperature {config.temperature}")
    print(f"Records: {records}\n")
    results = [run_scenario(s, provider, config, progress=print, recorder=recorder) for s in scenarios.values()]

    summary = summarize(results)
    print("\n--- Summary ---")
    for r in results:
        print(f"  {r.scenario.label:25s} {r.baseline.output_tokens:>5} -> {r.munch.output_tokens:>5} ({signed_change(r.reduction_pct)})")
    print(f"  aggregate {signed_change(summary.aggregate_pct)}, unweighted mean {signed_change(summary.mean_pct)}")
    costs = [call_cost(provider.model, c.input_tokens, c.output_tokens) for r in results for c in (r.baseline, r.munch)]
    if None in costs:
        print(f"  cost: not priced ({provider.model} has no sourced price in pricing.py)")
    else:
        print(f"  cost: ${sum(costs):.4f} for {len(costs)} calls")

    if args.save:
        args.output.write_text(render(results, config), encoding="utf-8")
        print(f"\nResults written to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
