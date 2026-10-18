"""Run each call through headless Claude Code (`claude -p`) on the user's own login.

jjg's ruling (2026-10-18): the benchmark uses his Claude login, not an API key.
This provider never reads, copies or prints a credential. It starts the
`claude` CLI, which authenticates itself, and removes ANTHROPIC_API_KEY from
the child's environment so the CLI cannot fall back to a key.

Fairness. Claude Code normally adds its own context: the user's CLAUDE.md,
hooks, MCP servers, tools and per-machine prompt sections. Any of that in the
baseline arm would shorten the baseline and shrink the measured reduction.
`--bare` would drop it all but never reads OAuth, so the flags below turn
each part off, and `contamination()` checks the result from the usage block.

What this path cannot do, and the report says so:
- set the temperature (Claude Code exposes no flag);
- confirm that thinking is off (it is requested off in --settings; the usage
  block does not split thinking tokens out of output_tokens);
- price a call in dollars: it is subscription usage.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable

from ..models import Completion
from .base import timed

# Over the prompt's own estimated size, the most input a call may report. The
# user's global CLAUDE.md alone is about 1,500 tokens (6,059 bytes, measured
# 2026-10-18), so a leak of it lands well past this. Claude Code's own fixed
# overhead is unmeasured; the dry check reports it before any full run.
CONTAMINATION_MARGIN_TOKENS = 750

# The flags, all from `claude --help` (2.1.301). Each one is pinned in tests.
FIXED_FLAGS = [
    "--output-format", "json",
    "--tools", "",                       # no tools in either arm
    "--strict-mcp-config",               # no MCP servers (no --mcp-config is given)
    "--setting-sources", "",             # no user, project or local settings: drops hooks
    "--exclude-dynamic-system-prompt-sections",
    "--no-session-persistence",          # nothing left in the user's session list
    "--settings", json.dumps({"alwaysThinkingEnabled": False}),
]


def estimate_tokens(text: str) -> int:
    """A rough count, four characters a token. Only the contamination guard uses it."""
    return max(1, len(text) // 4)


def contamination(system: str, user: str, input_tokens: int) -> int:
    """How many reported input tokens exceed the prompt's estimate plus the margin (0 = clean)."""
    return max(0, input_tokens - (estimate_tokens(system) + estimate_tokens(user) + CONTAMINATION_MARGIN_TOKENS))


class ClaudeCodeProvider:
    name = "claude-code"
    sets_temperature = False
    priced_in_dollars = False

    def __init__(self, model: str, run: Callable[..., subprocess.CompletedProcess] | None = None,
                 executable: str | None = None):
        self.model = model
        self._run = run or subprocess.run
        self._exe = executable

    def _executable(self) -> str:
        exe = self._exe or shutil.which("claude")
        if not exe:
            raise SystemExit("The claude CLI is not on PATH. Install Claude Code and sign in first.")
        return exe

    def command(self, system: str) -> list[str]:
        return [self._executable(), "-p", "--model", self.model, "--system-prompt", system, *FIXED_FLAGS]

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> Completion:
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_tokens)
        # An empty folder, so no project CLAUDE.md or settings are found, removed afterwards.
        with tempfile.TemporaryDirectory(prefix="joutputmunch-") as cwd:
            proc, latency = timed(
                lambda: self._run(
                    self.command(system), input=user, capture_output=True, text=True,
                    encoding="utf-8", cwd=cwd, env=env, timeout=600, check=False,
                )
            )
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p exited {proc.returncode}")
        data = json.loads(proc.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude -p reported an error ({data.get('subtype', 'unknown')})")
        usage = data["usage"]
        input_tokens = (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
        return Completion(
            text=data.get("result", ""),
            output_tokens=usage["output_tokens"],
            input_tokens=input_tokens,
            latency_s=latency,
        )
