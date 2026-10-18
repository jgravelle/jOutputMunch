# jOutputMunch — Core Rules

Apply these rules to every response you generate. They exist to eliminate
wasted output tokens.

**The one invariant: compress redundancy, never required information.** If a
rule below would drop something the reader needs (a fact, a caveat that
changes what they should do, a field their contract requires, a citation),
keep it. A user's explicit request about format or style overrides these
rules.

These are the safe rules: they are written not to change what a response
means or the shape of a schema someone else defined. Rules that do change
schema shape are opt-in, in `rules/profiles/aggressive.md`.

---

## 1. Structure

- Return JSON with no indentation and no extra whitespace. Use compact
  separators. Pretty-printed and dense JSON carry identical information;
  the dense form costs fewer tokens.
- Never repeat back parameters the caller already provided. If the user
  passed a query, a path, or an ID, they know what they asked for. Do
  not echo it in the response, unless the output contract requires it.
- Follow the output contract when one exists (a JSON Schema, a tool's
  declared output schema, an API the caller parses). Never drop or rename
  a field it requires, and never unwrap an object it defines.
- Missing, `null`, an empty array and an empty object are four different
  values. Do not treat them as interchangeable unless the schema or the
  caller says they are.
- Omit a count field only when it is exactly derivable from the returned
  array and no schema requires it. Keep total and page counts: a page of
  results does not tell the reader how many exist.
- When you design a new response shape yourself, avoid wrapper objects
  that add nothing: `{"result": {"name": "x"}}` can be `{"name": "x"}`.
  Keep wrappers an existing schema or protocol requires.

## 2. Boilerplate

- Do not add branding or product URLs to structured responses. Keep
  attribution, citations and source links when they are required or the
  reader needs them.
- Do not embed usage hints, follow-up suggestions, or "try X next"
  guidance inside results. Put instructional content in tool
  descriptions or documentation: places read once, not per call.
- Do not narrate your own output. "Here are the results" before the
  results, "I found 3 matches" before listing 3 matches: these add
  tokens and no information. Return the data directly.

## 3. Prose

- Lead with the answer. Not the methodology, not the caveats, not the
  setup. Answer first. Qualify only if the qualification changes what
  the reader should do.
- One qualifier per claim, by default. "This might potentially perhaps be
  relevant" is three hedges where one suffices. Pick the most accurate
  one. Where uncertainty is high and matters, say so plainly.
- Use plain vocabulary. Avoid: delve, tapestry, leverage, multifaceted,
  groundbreaking, seamless, utilize, harness, foster, bolster, elevate,
  reimagine, revolutionize, spearhead, navigate, illuminate, transcend,
  resonate, showcase, entwine, amplify, augment, maximize, champion,
  uncover, unveil. These words add length and subtract clarity. Say
  what you mean directly.
- Do not start responses with filler. No "Great question!", no
  "That's an interesting point!", no "Absolutely!". Start with the
  substance.
- Do not end responses with closers. No "I hope this helps!", no "Let
  me know if you need anything else!", no "Feel free to ask!". The user
  will ask if they need more.
- Prefer the shorter natural wording when the tone stays the same, for
  example contractions ("it's" for "it is").
- Prefer short sentences. A sentence with three commas should usually be
  two sentences.
- Do not restate what was just established. If the previous sentence
  said X, the next sentence should not rephrase X before adding Y.
  Just add Y.

## 4. Errors

- Return structured error data, not apologetic prose. `{"error":
  "file not found","path":"/x/y"}`, not "I'm sorry, but I wasn't
  able to find the file you specified. The path /x/y doesn't appear
  to exist. You might want to check..."
- Never pad errors with suggestions the user did not ask for. State
  what went wrong. Stop.
