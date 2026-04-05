"""
jOutputMunch Benchmark Harness

Measures output token reduction when jOutputMunch rules are applied.
Runs each scenario twice (baseline vs. with rules) and compares:
  - Output token count
  - Response latency
  - Answer correctness (manual review column)

Requirements:
    pip install anthropic openai tiktoken

Usage:
    python benchmarks/harness.py                    # run all scenarios
    python benchmarks/harness.py --scenario code    # run one scenario
    python benchmarks/harness.py --save             # write results.md
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import tiktoken
except ImportError:
    sys.exit("pip install tiktoken")


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


# ---------------------------------------------------------------------------
# Model clients (lazy import)
# ---------------------------------------------------------------------------

def call_anthropic(system: str, user: str, model: str = "claude-sonnet-4-20250514") -> dict:
    import anthropic
    client = anthropic.Anthropic()
    t0 = time.perf_counter()
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    latency = time.perf_counter() - t0
    text = resp.content[0].text
    return {
        "text": text,
        "tokens_out": resp.usage.output_tokens,
        "tokens_out_tiktoken": count_tokens(text),
        "latency_s": round(latency, 2),
    }


def call_openai(system: str, user: str, model: str = "gpt-4o") -> dict:
    import openai
    client = openai.OpenAI()
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    latency = time.perf_counter() - t0
    text = resp.choices[0].message.content
    return {
        "text": text,
        "tokens_out": resp.usage.completion_tokens,
        "tokens_out_tiktoken": count_tokens(text),
        "latency_s": round(latency, 2),
    }


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"

CORE_RULES = (RULES_DIR / "core.md").read_text(encoding="utf-8")
CODE_RULES = (RULES_DIR / "code-assistant.md").read_text(encoding="utf-8")


SCENARIOS = {
    "code_explanation": {
        "label": "Code explanation",
        "model_fn": "anthropic",
        "system_baseline": "You are a helpful software engineering assistant.",
        "system_munch": CORE_RULES + "\n" + CODE_RULES,
        "user": (
            "Explain what this function does, how it handles edge cases, and "
            "any potential issues:\n\n"
            "```python\n"
            "def retry(fn, max_attempts=3, backoff=1.0, exceptions=(Exception,)):\n"
            "    last_err = None\n"
            "    for attempt in range(1, max_attempts + 1):\n"
            "        try:\n"
            "            return fn()\n"
            "        except exceptions as e:\n"
            "            last_err = e\n"
            "            if attempt < max_attempts:\n"
            "                time.sleep(backoff * (2 ** (attempt - 1)))\n"
            "    raise last_err\n"
            "```"
        ),
    },
    "bug_diagnosis": {
        "label": "Bug diagnosis",
        "model_fn": "anthropic",
        "system_baseline": "You are a helpful software engineering assistant.",
        "system_munch": CORE_RULES + "\n" + CODE_RULES,
        "user": (
            "This test is failing. Why?\n\n"
            "```python\n"
            "def test_cache_expiry():\n"
            "    cache = LRUCache(max_size=2, ttl_seconds=1)\n"
            "    cache.set('a', 1)\n"
            "    cache.set('b', 2)\n"
            "    time.sleep(1.1)\n"
            "    cache.set('c', 3)\n"
            "    assert cache.get('a') is None  # expired\n"
            "    assert cache.get('b') is None  # expired\n"
            "    assert cache.get('c') == 3\n"
            "    assert len(cache) == 1  # FAILS: len is 3\n"
            "```\n\n"
            "```\n"
            "AssertionError: assert 3 == 1\n"
            "```"
        ),
    },
    "pr_review": {
        "label": "PR review",
        "model_fn": "anthropic",
        "system_baseline": "You are a helpful code reviewer.",
        "system_munch": CORE_RULES + "\n" + CODE_RULES,
        "user": (
            "Review this diff for correctness, performance, and style:\n\n"
            "```diff\n"
            "--- a/src/auth.py\n"
            "+++ b/src/auth.py\n"
            "@@ -12,8 +12,15 @@\n"
            " def verify_token(token: str) -> dict:\n"
            "-    payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])\n"
            "-    return payload\n"
            "+    try:\n"
            "+        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])\n"
            "+        user = db.query(User).filter(User.id == payload['sub']).first()\n"
            "+        if user is None:\n"
            "+            raise AuthError('User not found')\n"
            "+        if user.is_banned:\n"
            "+            raise AuthError('Account suspended')\n"
            "+        payload['user'] = user\n"
            "+        return payload\n"
            "+    except jwt.ExpiredSignatureError:\n"
            "+        raise AuthError('Token expired')\n"
            "+    except jwt.InvalidTokenError:\n"
            "+        raise AuthError('Invalid token')\n"
            "```"
        ),
    },
    "data_summary": {
        "label": "Data summary",
        "model_fn": "openai",
        "system_baseline": "You are a helpful data analysis assistant.",
        "system_munch": CORE_RULES,
        "user": (
            "Summarize this dataset schema and suggest three analyses:\n\n"
            "```json\n"
            + json.dumps({
                "dataset": "sales_2024",
                "rows": 148203,
                "columns": [
                    {"name": "order_id", "type": "int", "nulls": 0},
                    {"name": "customer_id", "type": "int", "nulls": 0},
                    {"name": "product_name", "type": "str", "nulls": 12},
                    {"name": "category", "type": "str", "nulls": 0,
                     "unique": 8},
                    {"name": "quantity", "type": "int", "nulls": 0,
                     "min": 1, "max": 500},
                    {"name": "unit_price", "type": "float", "nulls": 0,
                     "min": 0.99, "max": 4999.99},
                    {"name": "order_date", "type": "date", "nulls": 0,
                     "min": "2024-01-01", "max": "2024-12-31"},
                    {"name": "region", "type": "str", "nulls": 3,
                     "unique": 5},
                    {"name": "discount_pct", "type": "float", "nulls": 89102,
                     "min": 0.0, "max": 0.40},
                ],
            }, indent=2)
            + "\n```"
        ),
    },
    "general_question": {
        "label": "General question",
        "model_fn": "openai",
        "system_baseline": "You are a helpful assistant.",
        "system_munch": CORE_RULES,
        "user": (
            "Explain the difference between horizontal and vertical scaling "
            "for web applications. When should you choose one over the other?"
        ),
    },
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_scenario(name: str, scenario: dict) -> dict:
    call = call_anthropic if scenario["model_fn"] == "anthropic" else call_openai
    model = (
        "claude-sonnet-4-20250514"
        if scenario["model_fn"] == "anthropic"
        else "gpt-4o"
    )

    print(f"  [{name}] baseline ...", end=" ", flush=True)
    baseline = call(scenario["system_baseline"], scenario["user"], model)
    print(f"{baseline['tokens_out']} tokens, {baseline['latency_s']}s")

    print(f"  [{name}] with rules ...", end=" ", flush=True)
    munched = call(scenario["system_munch"], scenario["user"], model)
    print(f"{munched['tokens_out']} tokens, {munched['latency_s']}s")

    reduction = baseline["tokens_out"] - munched["tokens_out"]
    pct = (reduction / baseline["tokens_out"] * 100) if baseline["tokens_out"] else 0

    return {
        "scenario": scenario["label"],
        "model": model,
        "baseline_tokens": baseline["tokens_out"],
        "munch_tokens": munched["tokens_out"],
        "reduction": reduction,
        "reduction_pct": round(pct, 1),
        "baseline_latency": baseline["latency_s"],
        "munch_latency": munched["latency_s"],
        "baseline_text": baseline["text"],
        "munch_text": munched["text"],
    }


def write_results(results: list[dict], output_path: Path):
    lines = [
        "# jOutputMunch Benchmark Results\n",
        "",
        "Same prompt, same model, same temperature. Only difference: "
        "jOutputMunch rules in the system prompt.\n",
        "",
        "| Scenario | Model | Baseline tokens | With rules | Reduction | Baseline latency | With rules latency |",
        "|---|---|---|---|---|---|---|",
    ]
    total_base = 0
    total_munch = 0
    for r in results:
        total_base += r["baseline_tokens"]
        total_munch += r["munch_tokens"]
        lines.append(
            f"| {r['scenario']} | {r['model']} "
            f"| {r['baseline_tokens']:,} "
            f"| {r['munch_tokens']:,} "
            f"| **-{r['reduction_pct']}%** "
            f"| {r['baseline_latency']}s "
            f"| {r['munch_latency']}s |"
        )

    total_reduction = total_base - total_munch
    total_pct = round(total_reduction / total_base * 100, 1) if total_base else 0
    lines.append(
        f"| **Total** | | **{total_base:,}** | **{total_munch:,}** "
        f"| **-{total_pct}%** | | |"
    )

    lines.extend([
        "",
        "## Methodology",
        "",
        "- Token counts are from the model's native usage reporting",
        "- Each scenario runs once with a generic system prompt (baseline) "
        "and once with jOutputMunch core + code-assistant rules",
        "- No cherry-picking: every run is recorded as-is",
        "- Latency measured wall-clock, single run (indicative, not statistical)",
        "",
        "## Raw Output",
        "",
    ])

    for r in results:
        lines.extend([
            f"### {r['scenario']} ({r['model']})",
            "",
            "**Baseline:**",
            "```",
            r["baseline_text"],
            "```",
            "",
            "**With jOutputMunch rules:**",
            "```",
            r["munch_text"],
            "```",
            "",
        ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nResults written to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="jOutputMunch benchmark harness")
    parser.add_argument(
        "--scenario", "-s",
        help="Run a single scenario by key (e.g. code_explanation)",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Write results to benchmarks/results.md",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available scenarios",
    )
    args = parser.parse_args()

    if args.list:
        for key, s in SCENARIOS.items():
            print(f"  {key:25s} {s['label']} ({s['model_fn']})")
        return

    # Check API keys
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    scenarios = SCENARIOS
    if args.scenario:
        if args.scenario not in SCENARIOS:
            sys.exit(f"Unknown scenario: {args.scenario}. Use --list.")
        scenarios = {args.scenario: SCENARIOS[args.scenario]}

    # Filter to runnable scenarios
    runnable = {}
    for key, s in scenarios.items():
        if s["model_fn"] == "anthropic" and not has_anthropic:
            print(f"  Skipping {key} (no ANTHROPIC_API_KEY)")
        elif s["model_fn"] == "openai" and not has_openai:
            print(f"  Skipping {key} (no OPENAI_API_KEY)")
        else:
            runnable[key] = s

    if not runnable:
        sys.exit("No scenarios to run. Set ANTHROPIC_API_KEY and/or OPENAI_API_KEY.")

    print(f"Running {len(runnable)} scenario(s)...\n")
    results = []
    for key, scenario in runnable.items():
        results.append(run_scenario(key, scenario))

    # Summary
    print("\n--- Summary ---")
    for r in results:
        print(
            f"  {r['scenario']:25s} "
            f"{r['baseline_tokens']:>5} -> {r['munch_tokens']:>5} "
            f"(-{r['reduction_pct']}%)"
        )

    if args.save:
        out = Path(__file__).resolve().parent / "results.md"
        write_results(results, out)


if __name__ == "__main__":
    main()
