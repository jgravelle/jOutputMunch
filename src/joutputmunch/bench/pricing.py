"""Model prices, each with its source. A model not listed here is unpriced, never guessed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float
    source: str
    checked: str


# USD per million tokens. Add a model only with a source and the date it was read.
PRICES: dict[str, Price] = {
    "claude-sonnet-4-6": Price(3.0, 15.0, "https://claude.com/pricing", "2026-10-18"),
}


def call_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """The call's cost in USD, or None when the model has no sourced price."""
    price = PRICES.get(model)
    if price is None:
        return None
    return (input_tokens * price.input_per_mtok + output_tokens * price.output_per_mtok) / 1_000_000
