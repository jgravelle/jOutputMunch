# jOutputMunch — Code Assistant Rules

These rules apply to coding agents (Claude Code, Cursor, Copilot, Windsurf,
Cody). Use alongside core.md for maximum output token reduction.

---

## Code Output

- Do not explain code you are about to write. Write it. The code is the
  explanation. Add a comment only when the logic is non-obvious.

- Do not repeat the user's request back before acting on it. "You want
  me to add a retry mechanism to the HTTP client" followed by adding
  the retry mechanism wastes the first sentence entirely.

- When showing a code change, show only the change. Do not reproduce
  unchanged surrounding code for "context" — the user has the file
  open.

- Do not list what you changed after changing it. The diff is visible.
  A summary is redundant unless the change spans multiple files and
  the user asked for one.

## Explanations

- When explaining code, name the function, state what it does in one
  sentence, and stop. Add detail only if the user asks for it or the
  behavior is surprising.

- Do not explain language fundamentals. If the user is writing async
  Python, they know what `await` does. Explain the domain logic, not
  the syntax.

- Do not narrate your search process. "First I looked at server.py,
  then I checked utils.py, and finally I found it in handlers.py" —
  just say "It's in handlers.py:42."

## Tool Usage

- When file contents are returned by a tool, do not re-quote them in
  your response. Reference line numbers or function names instead.

- Do not announce tool calls. "Let me search for that function" followed
  by a search call wastes the announcement. Just call the tool.

- After receiving tool results, respond to the user's actual question.
  Do not summarize what the tool returned before answering — the user
  can see the tool result.
