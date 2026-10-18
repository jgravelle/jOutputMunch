from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from ..models import Completion


class Provider(Protocol):
    name: str
    model: str

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> Completion: ...


def timed(call: Callable[[], object]) -> tuple[object, float]:
    """Run `call` and return its result with the wall-clock seconds it took."""
    t0 = time.perf_counter()
    result = call()
    return result, round(time.perf_counter() - t0, 2)
