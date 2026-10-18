from __future__ import annotations

from ..models import Completion
from .base import timed


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, client: object | None = None):
        self.model = model
        self._client = client

    def _get_client(self):
        if self._client is None:
            try:
                import openai
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise SystemExit('pip install "joutputmunch[openai]"') from exc
            self._client = openai.OpenAI()
        return self._client

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> Completion:
        client = self._get_client()
        resp, latency = timed(
            lambda: client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        )
        return Completion(
            text=resp.choices[0].message.content or "",
            output_tokens=resp.usage.completion_tokens,
            input_tokens=resp.usage.prompt_tokens,
            latency_s=latency,
        )
