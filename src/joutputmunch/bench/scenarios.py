"""The five benchmark scenarios.

The prompts are byte-identical to the ones the published run used
(benchmarks/results.md); tests/test_scenarios.py checks that against the
harness as it stood at that run. Change a prompt and the published numbers no
longer describe this harness.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Scenario

_SPECS = {
    "code_explanation": {
        "label": "Code explanation",
        "system_baseline": "You are a helpful software engineering assistant.",
        "system_munch": "core+code",
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
        "system_baseline": "You are a helpful software engineering assistant.",
        "system_munch": "core+code",
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
        "system_baseline": "You are a helpful code reviewer.",
        "system_munch": "core+code",
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
        "system_baseline": "You are a helpful data analysis assistant.",
        "system_munch": "core",
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
        "system_baseline": "You are a helpful assistant.",
        "system_munch": "core",
        "user": (
            "Explain the difference between horizontal and vertical scaling "
            "for web applications. When should you choose one over the other?"
        ),
    },
}


RULE_SETS = {
    "core": ("core.md",),
    "core+code": ("core.md", "code-assistant.md"),
}


def default_rules_dir() -> Path:
    """`rules/` in the repository this package sits in (src/joutputmunch/bench -> repo root)."""
    return Path(__file__).resolve().parents[3] / "rules"


def load_scenarios(rules_dir: Path | None = None) -> dict[str, Scenario]:
    rules_dir = Path(rules_dir) if rules_dir else default_rules_dir()
    texts: dict[str, str] = {}
    for key, files in RULE_SETS.items():
        texts[key] = "\n".join((rules_dir / f).read_text(encoding="utf-8") for f in files)
    return {
        key: Scenario(
            key=key,
            label=spec["label"],
            user=spec["user"],
            system_baseline=spec["system_baseline"],
            system_munch=texts[spec["system_munch"]],
        )
        for key, spec in _SPECS.items()
    }
