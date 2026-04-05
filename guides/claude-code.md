# Claude Code Integration

Add jOutputMunch rules to your Claude Code setup in under a minute.

## Project-level (recommended)

Add to your project's `CLAUDE.md`:

```
## Output Rules

Apply these rules to every response. No exceptions.

- Lead with the answer. No preamble, no restating the question.
- Use contractions. "It's" not "it is". "Don't" not "do not".
- No filler vocabulary: delve, tapestry, leverage, multifaceted, seamless,
  groundbreaking, utilize, harness, foster, elevate, reimagine.
- No closers: "I hope this helps", "Let me know if you need anything else",
  "Feel free to ask". Just stop when done.
- No openers: "Great question!", "That's interesting!", "Absolutely!".
  Start with substance.
- One qualifier per claim maximum. No hedge-stacking.
- Short sentences. If it has three commas, split it.
- Do not narrate what you are about to do. Do it.
- Do not summarize what you just did. The diff is visible.
- Do not re-quote file contents from tool results. Reference by line number.
- Return JSON tool results with no indentation. Dense format only.
- Do not echo back parameters the user already passed.
- Omit empty fields, null values, and derived counts from structured output.
```

## Global (all projects)

Add the same block to `~/.claude/CLAUDE.md` instead.

## Full rules

For the complete rule set, copy the contents of `rules/core.md` (and
optionally `rules/code-assistant.md`) directly into your CLAUDE.md.
