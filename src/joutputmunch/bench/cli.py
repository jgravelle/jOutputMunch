"""Command line for the benchmark harness.

Every run makes two calls per scenario: a paid API call, or usage on a Claude
plan with --provider claude-code.
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
    p.add_argument(
        "--dry-check",
        action="store_true",
        help="claude-code only: the floor probe plus both arms of ONE scenario (3 calls); checks what Claude Code added",
    )
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

    key = KEY_ENV[args.provider]
    if key and not environ.get(key):
        print(f"Set {key} to run against {args.provider}.", file=sys.stderr)
        return 2
    if args.dry_check and args.provider != "claude-code":
        print("--dry-check is for --provider claude-code.", file=sys.stderr)
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
    sets_temperature = getattr(provider, "sets_temperature", True)
    recorder = RunRecorder(
        records,
        run_id=run_id,
        provider=provider.name,
        model=provider.model,
        temperature=config.temperature if sets_temperature else None,
        max_tokens=config.max_tokens,
        record_text=args.record_text,
        priced_in_dollars=getattr(provider, "priced_in_dollars", True),
    )
    floor = None
    if not getattr(provider, "priced_in_dollars", True):
        floor = _probe_floor(provider, config, recorder)
        if floor is None:
            return 3
    if args.dry_check:
        return _dry_check(next(iter(scenarios.values())), provider, config, recorder, records, floor)
    temp = config.temperature if sets_temperature else "not set (provider default)"
    print(f"Running {len(scenarios)} scenario(s) on {provider.name}/{provider.model}, temperature {temp}")
    print(f"Records: {records}\n")
    results = [run_scenario(s, provider, config, progress=print, recorder=recorder) for s in scenarios.values()]

    summary = summarize(results)
    print("\n--- Summary ---")
    for r in results:
        print(f"  {r.scenario.label:25s} {r.baseline.output_tokens:>5} -> {r.munch.output_tokens:>5} ({signed_change(r.reduction_pct)})")
    print(f"  aggregate {signed_change(summary.aggregate_pct)}, unweighted mean {signed_change(summary.mean_pct)}")
    if not getattr(provider, "priced_in_dollars", True):
        calls = [c for r in results for c in (r.baseline, r.munch)]
        print(
            f"  usage: {sum(c.input_tokens for c in calls):,} input and {sum(c.output_tokens for c in calls):,} "
            f"output tokens over {len(calls)} calls (subscription, not priced in dollars)"
        )
        dirty = _contaminated(results, floor)
        if dirty:
            print("\nRefused: Claude Code added context to these calls, so the comparison is not fair:", file=sys.stderr)
            for line in dirty:
                print(f"  {line}", file=sys.stderr)
            print(f"No report written. The records are in {records}.", file=sys.stderr)
            return 3
    else:
        costs = [call_cost(provider.model, c.input_tokens, c.output_tokens) for r in results for c in (r.baseline, r.munch)]
        if None in costs:
            print(f"  cost: not priced ({provider.model} has no sourced price in pricing.py)")
        else:
            print(f"  cost: ${sum(costs):.4f} for {len(costs)} calls")

    if args.save:
        args.output.write_text(render(results, config, floor=floor), encoding="utf-8")
        print(f"\nResults written to {args.output}")
    return 0


def _probe_floor(provider, config, recorder) -> int | None:
    """One near-empty call: what Claude Code adds to every call. None when it is too much to trust."""
    from .models import Scenario
    from .providers.claude_code import (
        FLOOR_PROBE_SYSTEM,
        FLOOR_PROBE_USER,
        floor_of,
        floor_problems,
    )

    probe = Scenario(key="floor_probe", label="Floor probe", user=FLOOR_PROBE_USER,
                     system_baseline=FLOOR_PROBE_SYSTEM, system_munch=FLOOR_PROBE_SYSTEM)
    print("Floor probe: one near-empty call to measure what Claude Code adds to every call")
    try:
        c = provider.complete(FLOOR_PROBE_SYSTEM, FLOOR_PROBE_USER, temperature=config.temperature,
                              max_tokens=config.max_tokens)
    except BaseException as exc:
        recorder.failed(probe, "probe", FLOOR_PROBE_SYSTEM, exc)
        raise
    recorder.completed(probe, "probe", FLOOR_PROBE_SYSTEM, c)
    floor = floor_of(c.input_tokens)
    print(f"  floor: {floor:,} tokens\n")
    problems = floor_problems(floor)
    if problems:
        for p in problems:
            print(f"Refused: {p}. Something besides Claude Code's own context reached the call.", file=sys.stderr)
        return None
    return floor


def _contaminated(results, floor: int) -> list[str]:
    from .providers.claude_code import check_pair

    out = []
    for r in results:
        s = r.scenario
        out += check_pair(s.key, s.user, s.system_baseline, r.baseline.input_tokens, s.system_munch,
                          r.munch.input_tokens, floor)
    return out


def _dry_check(scenario, provider, config, recorder, records, floor: int) -> int:
    """The floor probe plus both arms of one scenario: does Claude Code add more than its floor?"""
    from .providers.claude_code import EXCESS_LIMIT_TOKENS, check_pair, excess

    print(f"Dry check: both arms of one scenario ({scenario.key}), 2 calls after the probe, on "
          f"{provider.name}/{provider.model}")
    r = run_scenario(scenario, provider, config, progress=print, recorder=recorder)
    for arm, system, c in (("baseline", scenario.system_baseline, r.baseline), ("rules", scenario.system_munch, r.munch)):
        print(f"  {arm}: reported input {c.input_tokens:,} tokens, {excess(system, scenario.user, c.input_tokens, floor):,} "
              f"beyond the floor")
    print(f"  limit: {EXCESS_LIMIT_TOKENS} beyond the floor per call, and the arms within the gap limit")
    print(f"  records: {records}")
    problems = check_pair(scenario.key, scenario.user, scenario.system_baseline, r.baseline.input_tokens,
                          scenario.system_munch, r.munch.input_tokens, floor)
    if problems:
        for p in problems:
            print(f"  REFUSE: {p}")
        print("  A full run would be refused.")
        return 3
    print("  CLEAN: a full run would pass the guard.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
