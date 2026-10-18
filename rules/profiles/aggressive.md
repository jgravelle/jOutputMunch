# jOutputMunch — Aggressive Rules (opt-in)

These rules change the shape of structured output. They save more tokens than
`rules/core.md` and they can break a consumer, so they are not part of the
default set.

**Use them only when you own the output contract**: you define the response
format and every consumer treats the omitted forms as equivalent. Do not use
them for output that must match a schema someone else defined (a JSON Schema,
an MCP tool's declared output schema, a public API).

Use alongside `rules/core.md`. Where a rule here conflicts with a contract you
do not own, the contract wins.

---

## Structure

- Omit keys whose value is `null`, an empty array, or an empty object. In
  this contract, absence means empty.
- Do not include a count field alongside the array it counts. If the
  response contains `results`, do not also include `result_count`. This
  applies only to counts of the returned array, never to a total across
  pages.
- Do not wrap data in single-key containers. `{"result": {"name": "x"}}`
  becomes `{"name": "x"}`.

## Tool results (MCP)

- Strip null values and empty collections before serializing.
- Do not include `success: true` on successful responses. In this contract,
  the absence of an `error` field means success. Include `success: false`
  only on failures.
