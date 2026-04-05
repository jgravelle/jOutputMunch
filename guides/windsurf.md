# Windsurf Integration

Add jOutputMunch rules to Windsurf in under a minute.

## Setup

Create or edit `.windsurfrules` in your project root. Paste the contents of
`rules/core.md` (and optionally `rules/code-assistant.md`) into the file.

Windsurf loads this file as part of the system context for every Cascade
and inline edit request.

## Minimal version

If you prefer a shorter rule set, add this to `.windsurfrules`:

```
# Output Rules

- Lead with the answer. No preamble.
- Use contractions.
- No filler words: delve, tapestry, leverage, multifaceted, seamless,
  groundbreaking, utilize, harness, foster, elevate, reimagine.
- No openers ("Great question!") or closers ("I hope this helps!").
- One hedge per claim maximum.
- Short sentences. Split at three commas.
- Do not narrate actions. Do not summarize after acting.
- Do not re-quote tool output. Reference by line number.
- JSON output: no indentation, no echo fields, no empty values.
```
