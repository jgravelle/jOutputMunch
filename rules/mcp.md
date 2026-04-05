# jOutputMunch — MCP Tool Response Rules

These rules apply specifically to Model Context Protocol tool responses.
Use alongside core.md for maximum output token reduction.

---

## Tool Results

- Tool descriptions teach. Tool results report. All usage hints,
  workflow suggestions, and "you might also try" guidance belongs in
  the tool's description field (read once at session start), not in
  every result payload (read on every call).

- Return structured data, never narrated data. The model consuming
  your result will parse JSON — it does not need a prose introduction
  explaining what the JSON contains.

- When returning multiple items, use a flat array. Do not add per-item
  commentary, per-item status messages, or interstitial text between
  items.

- Omit metadata envelopes when they contain nothing actionable. A
  `_meta` object with only `powered_by` and `timing_ms` costs tokens
  on every call. If the consumer never acts on it, stop sending it.

- Error responses are data, not conversation. Return
  `{"error":"not_found"}` — not `"I was unable to locate the
  requested resource. Please verify the identifier and try again."`.

## Serialization

- Use `json.dumps(result, separators=(',',':'))` — no `indent`.
  Pretty-printed JSON exists for human readability. MCP results are
  consumed by models. Dense JSON is equally parseable and 15-25%
  smaller.

- Strip null values and empty collections before serializing. Every
  `"field": null` or `"items": []` is 3-5 tokens of transmitted
  nothingness.

- Do not include a `success: true` field on successful responses.
  Success is the default — the absence of an error field implies it.
  Only include `success: false` on failures.
