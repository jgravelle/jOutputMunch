"""Command line for the benchmark harness.

Every run calls a paid API: two calls per scenario.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .models import summarize
from .providers import DEFAULT_MODELS, KEY_ENV, make_provider
from .report import render
from .runner import RunConfig, run_scenario
from .scenarios import default_rules_dir, load_scenarios

# Anthropic's and OpenAI's documented default. The published run relied on the
# default without setting it; the harness now sets it, so the value is on record.
DEFAULT_TEMPERATURE = 1.0
DEFAULT_MAX_TOKENS = 4096


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
    return p


def main(argv: list[str] | None = None, *, provider_factory=make_provider, environ=None) -> int:
    args = build_parser().parse_args(argv)
    environ = os.environ if environ is None else environ
    rules_dir = args.rules_dir or default_rules_dir()
    if not (rules_dir / "core.md").is_file():
        print(
            f"No rules at {rules_dir}. Run from a checkout (pip install -e .) or pass --rules-dir.",
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

    if not environ.get(KEY_ENV[args.provider]):
        print(f"Set {KEY_ENV[args.provider]} to run against {args.provider}.", file=sys.stderr)
        return 2

    provider = provider_factory(args.provider, args.model)
    config = RunConfig(temperature=args.temperature, max_tokens=args.max_tokens)
    print(f"Running {len(scenarios)} scenario(s) on {provider.name}/{provider.model}, temperature {config.temperature}\n")
    results = [run_scenario(s, provider, config, progress=print) for s in scenarios.values()]

    summary = summarize(results)
    print("\n--- Summary ---")
    for r in results:
        print(f"  {r.scenario.label:25s} {r.baseline.output_tokens:>5} -> {r.munch.output_tokens:>5} (-{r.reduction_pct}%)")
    print(f"  aggregate -{summary.aggregate_pct}%, unweighted mean -{summary.mean_pct}%")

    if args.save:
        args.output.write_text(render(results, config), encoding="utf-8")
        print(f"\nResults written to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
