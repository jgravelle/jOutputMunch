"""Provider adapters. Each SDK is imported only when its provider is used."""

from __future__ import annotations

from .base import Provider

DEFAULT_MODELS = {
    # The published results were measured on this model (benchmarks/results.md).
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    # Runs on the user's own Claude login through `claude -p`, never an API key (jjg, 2026-10-18).
    "claude-code": "claude-sonnet-4-6",
}

# The environment variable each provider needs. None: the provider brings its own login.
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "claude-code": None}


def make_provider(name: str, model: str | None = None) -> Provider:
    if name not in DEFAULT_MODELS:
        raise ValueError(f"unknown provider: {name}")
    model = model or DEFAULT_MODELS[name]
    if name == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(model)
    if name == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(model)
    if name == "claude-code":
        from .claude_code import ClaudeCodeProvider

        return ClaudeCodeProvider(model)
    raise ValueError(f"unknown provider: {name}")


__all__ = ["DEFAULT_MODELS", "KEY_ENV", "Provider", "make_provider"]
