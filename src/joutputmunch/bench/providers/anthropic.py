from __future__ import annotations

from ..models import Completion
from .base import timed


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, client: object | None = None):
        self.model = model
        self._client = client

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise SystemExit('pip install "joutputmunch[anthropic]"') from exc
            self._client = anthropic.Anthropic()
        return self._client

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> Completion:
        client = self._get_client()
        resp, latency = timed(
            lambda: client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        )
        text = "".join(getattr(block, "text", "") for block in resp.content)
        return Completion(
            text=text,
            output_tokens=resp.usage.output_tokens,
            input_tokens=resp.usage.input_tokens,
            latency_s=latency,
        )
