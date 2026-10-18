"""The adapters pass the settings through and read native usage. No network."""

from types import SimpleNamespace

import pytest

from joutputmunch.bench.providers import DEFAULT_MODELS, make_provider
from joutputmunch.bench.providers.anthropic import AnthropicProvider
from joutputmunch.bench.providers.openai import OpenAIProvider


class _Recorder:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def test_anthropic_sends_temperature_and_reads_usage():
    resp = SimpleNamespace(
        content=[SimpleNamespace(text="hel"), SimpleNamespace(text="lo")],
        usage=SimpleNamespace(output_tokens=7, input_tokens=11),
    )
    messages = _Recorder(resp)
    p = AnthropicProvider("claude-sonnet-4-6", client=SimpleNamespace(messages=messages))
    out = p.complete("sys", "user", temperature=1.0, max_tokens=4096)
    assert messages.kwargs == {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "temperature": 1.0,
        "system": "sys",
        "messages": [{"role": "user", "content": "user"}],
    }
    assert (out.text, out.output_tokens, out.input_tokens) == ("hello", 7, 11)


def test_openai_sends_temperature_and_reads_usage():
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
        usage=SimpleNamespace(completion_tokens=3, prompt_tokens=9),
    )
    completions = _Recorder(resp)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    out = OpenAIProvider("gpt-4o", client=client).complete("sys", "u", temperature=0.5, max_tokens=10)
    assert completions.kwargs["temperature"] == 0.5
    assert completions.kwargs["messages"][0] == {"role": "system", "content": "sys"}
    assert (out.text, out.output_tokens, out.input_tokens) == ("hi", 3, 9)


def test_the_default_model_is_the_published_one():
    assert DEFAULT_MODELS["anthropic"] == "claude-sonnet-4-6"
    assert make_provider("anthropic").model == "claude-sonnet-4-6"
    assert make_provider("openai", "gpt-x").model == "gpt-x"
    with pytest.raises(ValueError):
        make_provider("nope")
