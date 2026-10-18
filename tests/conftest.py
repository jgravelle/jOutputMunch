from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from joutputmunch.bench.models import Completion

REPO = Path(__file__).resolve().parents[1]


@dataclass
class FakeProvider:
    """Answers from a script instead of an API. Records every call."""

    name: str = "anthropic"
    model: str = "fake-model"
    calls: list[dict] = field(default_factory=list)

    def complete(self, system, user, *, temperature, max_tokens):
        self.calls.append({"system": system, "user": user, "temperature": temperature, "max_tokens": max_tokens})
        rules = "jOutputMunch" in system
        return Completion(
            text="short" if rules else "a much longer answer",
            output_tokens=40 if rules else 100,
            input_tokens=900 if rules else 30,
            latency_s=0.5,
        )


@pytest.fixture(autouse=True)
def _records_stay_out_of_the_repo(tmp_path, monkeypatch):
    """No test may write run records into the checkout."""
    from joutputmunch.bench import cli

    monkeypatch.setattr(cli, "default_records_dir", lambda: tmp_path / "runs")


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def repo():
    return REPO
