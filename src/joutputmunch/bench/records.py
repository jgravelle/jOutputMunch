"""One JSON line per provider call, on disk before the next call starts.

A run that dies on its eighth call keeps the seven it paid for. Raw model text
is left out unless asked for, because a benchmark prompt or answer can be
something its owner would not commit.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .. import __version__
from .models import Completion, Scenario
from .pricing import call_cost

SCHEMA = "joutputmunch.run/v1"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RunRecorder:
    def __init__(self, path: Path, *, run_id: str, provider: str, model: str, temperature: float | None,
                 max_tokens: int, record_text: bool = False, priced_in_dollars: bool = True):
        self.path = Path(path)
        self.base = {
            "schema": SCHEMA,
            "run_id": run_id,
            "harness_version": __version__,
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        self.record_text = record_text
        self.priced_in_dollars = priced_in_dollars

    def _write(self, row: dict) -> None:
        line = json.dumps({**self.base, **row}, ensure_ascii=False, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _row(self, scenario: Scenario, arm: str, system: str) -> dict:
        return {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scenario": scenario.key,
            "arm": arm,
            "system_sha256": _sha256(system),
            "user_sha256": _sha256(scenario.user),
        }

    def completed(self, scenario: Scenario, arm: str, system: str, c: Completion) -> None:
        row = self._row(scenario, arm, system) | {
            "input_tokens": c.input_tokens,
            "output_tokens": c.output_tokens,
            "latency_s": c.latency_s,
            "cost_usd": (
                call_cost(self.base["model"], c.input_tokens, c.output_tokens) if self.priced_in_dollars else None
            ),
        }
        if self.record_text:
            row["text"] = c.text
        self._write(row)

    def failed(self, scenario: Scenario, arm: str, system: str, exc: BaseException) -> None:
        # The exception's type only: an SDK message can carry request details.
        self._write(self._row(scenario, arm, system) | {"error": type(exc).__name__})


def read_records(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
