# jOutputMunch - FREE!

**Cut your LLM output tokens. Paste one file.** In one published five-scenario run on Claude Sonnet 4.6, the rules cut output tokens from 4,520 to 1,571: a 65.2% aggregate reduction, 40.5% to 76.4% per scenario. One run per scenario, answer quality not yet measured: [the results](benchmarks/results.md) say what the run does and does not show.

jOutputMunch is a set of system prompt rules that eliminate wasted output
tokens from any LLM. No code to install. No dependencies. No API. Copy a
text file into your setup and start saving immediately.

Works with Claude, GPT, Gemini, Llama, Mistral, and anything else that
accepts a system prompt.

---

## The Problem

Every LLM produces output with the same structural waste:

- **Throat-clearing openers**: "Great question! That's a really interesting
  topic."
- **Hedge-stacking**: "This might potentially perhaps be somewhat relevant."
- **Filler vocabulary**: Delve, tapestry, leverage, multifaceted, seamless.
- **Echo fields**: Repeating back the question before answering it.
- **Self-referential closers**: "I hope this helps! Let me know if you need
  anything else!"
- **Pretty-printed JSON**: indentation and line breaks that carry no
  information.
- **Derived counts**: `result_count: 3` next to an array of 3 items.
- **Narrated data**: "Here are the results of your search" followed by the
  results.

These patterns are baked into every model's training. They appear in every
response regardless of what you ask. They cost real money at scale.

## The Fix

jOutputMunch provides rules that suppress these patterns at the system
prompt level. The model still has the same knowledge and reasoning. It just
stops wasting tokens on structural noise.

[H/T: https://www.youtube.com/@CraigdoesAI for doing a lot of legwork on this.]

---

## Quick Start

**1. Pick your platform:**

| Platform | Guide |
|----------|-------|
| Claude Code | [guides/claude-code.md](guides/claude-code.md) |
| Cursor | [guides/cursor.md](guides/cursor.md) |
| Windsurf | [guides/windsurf.md](guides/windsurf.md) |
| OpenAI / ChatGPT | [guides/openai-system-prompt.md](guides/openai-system-prompt.md) |
| AutoGen / CrewAI / LangChain | [guides/autogen.md](guides/autogen.md) |

**2. Copy the rules into your system prompt.** That's it. No install, no
config, no package.

The full rule set is in [`rules/core.md`](rules/core.md). Specialized
variants for [MCP tools](rules/mcp.md) and
[code assistants](rules/code-assistant.md) are also available.

---

## Before / After

**Prompt**: "Explain the difference between horizontal and vertical scaling."

An illustrative example, not a benchmark output.

### Without jOutputMunch (287 tokens)

> Great question! Horizontal and vertical scaling are two fundamental
> approaches to scaling web applications, and understanding the difference
> between them is crucial for making informed architectural decisions.
>
> **Horizontal scaling** (also known as "scaling out") involves adding more
> machines to your infrastructure. This is a really powerful approach
> because it allows you to distribute the workload across multiple servers,
> which can help improve both performance and reliability. [...]
>
> I hope this helps! Let me know if you'd like me to dive deeper into any
> of these concepts.

### With jOutputMunch (168 tokens)

> **Horizontal scaling** adds more machines. You go from one server to ten,
> each handling a slice of traffic. Good for stateless services. Harder
> when you need shared state (sessions, locks).
>
> **Vertical scaling** makes one machine bigger. More RAM, faster CPU,
> bigger disk. Simpler to reason about. Hits a ceiling when you max out
> the hardware.
>
> Use vertical first when you're small. Switch to horizontal when a single
> machine can't keep up or when you need redundancy. Most production
> systems end up doing both.

**41% fewer tokens in this example.**

---

## Rule Files

| File | Scope | Use when |
|------|-------|----------|
| [rules/core.md](rules/core.md) | Universal | Any LLM, any task |
| [rules/mcp.md](rules/mcp.md) | MCP tools | Your agent calls MCP tools |
| [rules/code-assistant.md](rules/code-assistant.md) | Coding agents | Claude Code, Cursor, Copilot, etc. |
| [rules/profiles/aggressive.md](rules/profiles/aggressive.md) | Opt-in | You own the output format and want nulls, counts and wrappers dropped too |

Use `core.md` alone for general use. Stack `mcp.md` or `code-assistant.md`
on top for specialized workflows.

`core.md` is the safe set: it never changes what a response means or the
shape of a schema someone else defined. `profiles/aggressive.md` drops null and
empty fields, derived counts and wrapper objects. That breaks a consumer that
tells missing from `null` or reads a wrapper, so use it only for output whose
format you own.

---

## Benchmarks

Run the benchmark harness yourself. It calls a paid API: two calls per
scenario, ten for the full set.

```bash
pip install -e ".[anthropic]"
export ANTHROPIC_API_KEY=...
python benchmarks/harness.py --save
```

The defaults reproduce the published run: `claude-sonnet-4-6`, temperature
1.0, max 4096 output tokens. `--provider openai`, `--model` and
`--temperature` change them. The harness runs each scenario twice (baseline
vs. with rules) and writes `benchmarks/results.md` with output and input
token counts, latency, the settings used and the full output text.

The harness is the only part of jOutputMunch with code. The rules need none.

Published results: [benchmarks/results.md](benchmarks/results.md)

---

## The jMunch Ecosystem: Both Sides of the Token Bill

jOutputMunch cuts what the model **generates**. That's one half of your
token cost.

The other half is what you **send in** — file contents, search results,
database dumps, documentation pages. That's where input tokens pile up,
and where the [jMunch MCP suite](https://github.com/jgravelle/jcodemunch-mcp)
attacks the problem from the other direction.

Benchmarked on real production codebases (165–951 files):

| Tool | What it replaces | Token reduction |
|------|-----------------|-----------------|
| [jCodemunch](https://github.com/jgravelle/jcodemunch-mcp) | Reading raw source files | **99.6% avg** (up to 531×) |
| [jDocMunch](https://github.com/jgravelle/jdocmunch-mcp) | Loading full doc files | Search by section instead |
| [jDataMunch](https://github.com/jgravelle/jdatamunch-mcp) | Scanning full datasets | ~25,000× on 1M-row CSVs |

Instead of dumping a 700k-token codebase into context, jCodemunch lets the
model navigate by symbol — looking up only the function, class, or reference
it actually needs. Same answer. Fraction of the tokens.

**Paired together:** jOutputMunch cut output tokens 65.2% (aggregate) in its
one published run.
jCodemunch eliminates ~99.6% of the input side. On code-heavy workloads,
that's the entire token budget on both ends of the conversation.

They're complementary, not overlapping. jOutputMunch is a system prompt
you paste. jCodemunch is an MCP server your agent calls. They work the
same day, with the same model, with no changes to your workflow.

---

## How It Works

LLMs default to verbose, hedged, narrated output because that's what
dominates their training data. These patterns are consistent and
predictable across models.

jOutputMunch rules override these defaults at the system prompt level:

1. **Structure rules** strip whitespace and echo fields from structured
   output and follow the output schema when there is one. Dropping nulls,
   counts and wrappers is opt-in.
2. **Boilerplate rules** eliminate attribution strings, usage hints, and
   meta-commentary that add tokens without adding information.
3. **Prose rules** cut filler vocabulary, hedge-stacking, throat-clearing
   openers, and self-referential closers.
4. **Error rules** replace apologetic prose errors with structured data.

The model retains all its knowledge and reasoning capability. It just
stops padding the output.

---

## FAQ

**Does this hurt answer quality?**

Not measured yet. The published run recorded tokens and latency, not
answer quality. The rules are written to cut redundancy and keep required
information, and `core.md` says so as its first rule. A benchmark that
checks quality is planned.

**Does this work with every model?**

The rules are plain text, so any model that takes a system prompt can use
them. The published measurement covers Claude Sonnet 4.6 only. The
harness can run the same scenarios on OpenAI models (`--provider openai`).

**Can I customize the rules?**

Yes. The rule files are plain text. Remove rules you disagree with,
add your own, adjust the banned word list. Fork and make it yours.

**How is this different from just saying "be concise"?**

"Be concise" is one instruction and leaves the model to guess what to cut.
jOutputMunch names the specific patterns to cut, and says what must stay.

---

## License

MIT. Forever. Use it, fork it, share it.

Made by [J. Gravelle](https://github.com/jgravelle).
