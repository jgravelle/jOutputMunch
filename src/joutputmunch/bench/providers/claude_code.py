"""Run each call through headless Claude Code (`claude -p`) on the user's own login.

jjg's ruling (2026-10-18): the benchmark uses his Claude login, not an API key.
This provider never reads, copies or prints a credential. It starts the
`claude` executable, which authenticates itself. It removes the API-key and
provider-switch variables it knows (every ANTHROPIC_* variable and the
Bedrock, Vertex and Foundry switches) from the child's environment, so the
CLI does not take them up instead of the login.

The executable, never a shell shim. On Windows an npm install puts a
`claude.cmd` first on PATH. cmd.exe would run it, and cmd.exe ends an argument
at a newline, so a multi-line system prompt would be cut short and every flag
after it lost. A shim is resolved to the `claude.exe` beside it or refused.

Fairness. Claude Code normally adds its own context: the user's CLAUDE.md,
hooks, MCP servers and tools. Any of that in the baseline arm would shorten the
baseline and shrink the measured reduction. `--bare` would drop it but never
reads OAuth, so the flags below turn each part off. `check_pair()` then
measures what got through, from the usage block.

What this path cannot do, and the report says so:
- set the temperature (Claude Code has no flag for it);
- confirm that thinking is off (it is requested off in --settings, and the
  usage block does not split thinking tokens out of output_tokens);
- confirm from its help that `--setting-sources ""` loads no settings: the
  guard measures the effect instead;
- price a call in dollars: it is subscription usage.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from ..models import Completion
from .base import timed

# Over the prompt's own estimated size, the most input one call may report. The
# user's global CLAUDE.md alone is about 1,500 tokens (6,059 bytes, measured
# 2026-10-18), so a leak of it lands well past this.
CONTAMINATION_MARGIN_TOKENS = 750
# How far the rules arm's overhead may sit from the baseline's. A context both arms
# get equally shifts both; a difference is what biases the reduction. The range is
# lopsided because the estimate overshoots the rules text by about 90 tokens
# (tiktoken cl100k as a proxy), so a clean run sits near -90.
ARM_GAP_LOW_TOKENS = -250
ARM_GAP_HIGH_TOKENS = 150
# A call that reports this much LESS input than its own prompt's estimate did not
# receive its prompt: a system prompt cut short, or a user prompt never read from stdin.
UNDER_LIMIT_TOKENS = 400

# The flags, all from `claude --help` (2.1.301). Each one is pinned in tests.
FIXED_FLAGS = [
    "--output-format", "json",
    "--tools", "",                       # no tools in either arm
    "--strict-mcp-config",               # no MCP servers (no --mcp-config is given)
    "--setting-sources", "",             # load no user, project or local settings (so no user hooks)
    "--no-session-persistence",          # help: sessions "will not be saved to disk and cannot be resumed"
    "--settings", json.dumps({"alwaysThinkingEnabled": False}),
]

# Variables that would point the CLI at a key or another provider instead of the login.
_STRIPPED_ENV_PREFIXES = ("ANTHROPIC_",)
_STRIPPED_ENV = {"CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDECODE"}
_SHIMS = {".cmd", ".bat", ".ps1"}


def estimate_tokens(text: str) -> int:
    """A rough count, four characters a token. Only the guard uses it."""
    return max(1, len(text) // 4)


def overhead(system: str, user: str, input_tokens: int) -> int:
    """Reported input beyond the prompt's own estimated size."""
    return input_tokens - estimate_tokens(system) - estimate_tokens(user)


def contamination(system: str, user: str, input_tokens: int) -> int:
    """Tokens over the one-call limit (0 = clean)."""
    return max(0, overhead(system, user, input_tokens) - CONTAMINATION_MARGIN_TOKENS)


def check_pair(key: str, user: str, base_system: str, base_input: int, rules_system: str, rules_input: int) -> list[str]:
    """What makes one scenario's two calls an unfair comparison. Empty means clean."""
    problems = []
    for arm, system, n in (("baseline", base_system, base_input), ("rules", rules_system, rules_input)):
        extra = contamination(system, user, n)
        if extra:
            problems.append(f"{key} {arm}: {n:,} input tokens, {extra:,} over the limit")
        if overhead(system, user, n) < -UNDER_LIMIT_TOKENS:
            problems.append(f"{key} {arm}: {n:,} input tokens, less than its own prompt; the prompt did not arrive")
    gap = overhead(rules_system, user, rules_input) - overhead(base_system, user, base_input)
    if not ARM_GAP_LOW_TOKENS <= gap <= ARM_GAP_HIGH_TOKENS:
        problems.append(
            f"{key}: the arms' overheads differ by {gap:+,} tokens "
            f"(allowed {ARM_GAP_LOW_TOKENS:+,} to {ARM_GAP_HIGH_TOKENS:+,})"
        )
    return problems


def resolve_executable(found: str | None) -> str:
    """The real claude executable. A shell shim is resolved to the exe beside it, or refused."""
    if not found:
        raise SystemExit("The claude CLI is not on PATH. Install Claude Code and sign in first.")
    path = Path(found)
    # On Windows an extensionless `claude` is npm's sh script, not something CreateProcess can run.
    is_shim = path.suffix.lower() in _SHIMS or (os.name == "nt" and not path.suffix)
    if not is_shim:
        return str(path)
    exe = path.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    if exe.is_file():
        return str(exe)
    raise SystemExit(
        f"{path} is a shell shim, and a shell would cut the system prompt at its first newline. "
        f"Expected the executable at {exe}."
    )


def child_env(environ: dict[str, str], max_tokens: int) -> dict[str, str]:
    env = {
        k: v for k, v in environ.items()
        if not k.startswith(_STRIPPED_ENV_PREFIXES) and k not in _STRIPPED_ENV
    }
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_tokens)
    return env


class ClaudeCodeProvider:
    name = "claude-code"
    sets_temperature = False
    priced_in_dollars = False

    def __init__(self, model: str, run: Callable[..., subprocess.CompletedProcess] | None = None,
                 executable: str | None = None):
        self.model = model
        self._run = run or subprocess.run
        self._exe = executable

    def command(self, system: str) -> list[str]:
        exe = self._exe or resolve_executable(shutil.which("claude"))
        return [exe, "-p", "--model", self.model, "--system-prompt", system, *FIXED_FLAGS]

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int) -> Completion:
        argv = self.command(system)
        env = child_env(dict(os.environ), max_tokens)
        # An empty folder, so no project CLAUDE.md or settings are found, removed afterwards.
        with tempfile.TemporaryDirectory(prefix="joutputmunch-") as cwd:
            try:
                proc, latency = timed(
                    lambda: self._run(
                        argv, input=user, capture_output=True, text=True,
                        encoding="utf-8", cwd=cwd, env=env, timeout=600, check=False,
                    )
                )
            except subprocess.TimeoutExpired:
                # Its message repeats the whole argv; the type is enough.
                raise TimeoutError("claude -p took longer than 600 s") from None
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
