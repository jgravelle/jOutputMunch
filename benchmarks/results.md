# jOutputMunch Benchmark Results

Same prompt, same model, same temperature. Only difference: jOutputMunch rules in the system prompt.

All runs: **claude-sonnet-4-6** via Anthropic API, one run per cell.

The script that produced this run was not committed. The harness committed
with these results (cac4bad) routed two scenarios to OpenAI, named another
Claude model and writes a different report, so it is not that script. It set
no temperature (the API default is 1.0) and max 4096 output tokens. The
harness's defaults now are this file's model and those settings, with 1.0 set
explicitly.

| Scenario | Baseline tokens | With rules | Reduction | Baseline latency | With rules latency |
|---|---|---|---|---|---|
| Code explanation | 650 | 193 | **-70.3%** | 12.34s | 5.93s |
| Bug diagnosis | 405 | 158 | **-61.0%** | 7.46s | 4.88s |
| PR review | 698 | 351 | **-49.7%** | 12.62s | 8.56s |
| Data summary | 602 | 358 | **-40.5%** | 13.79s | 8.84s |
| General question | 2,165 | 511 | **-76.4%** | 39.09s | 12.14s |
| **Total** | **4,520** | **1,571** | **-65.2%** | | |

65.2% aggregate output-token reduction across the 5 scenarios (total over
total). The unweighted mean of the five scenario reductions is 59.6%.

## What this run does and does not show

- Token counts are the Anthropic API's native `usage.output_tokens`.
- Each scenario: generic system prompt (baseline) vs. `rules/core.md`
  (+ `rules/code-assistant.md` for coding scenarios).
- OpenAI runs were abandoned when the quota ran out, and those scenarios
  were rerun on Claude. The raw outputs were not kept, so which runs were
  recorded cannot be checked.
- One run per cell. Latency is wall-clock: indicative, not statistical. There
  are no repetitions and no confidence intervals.
- Answer quality was not measured. The raw outputs of this run were not kept
  with this file, so the reduction cannot be checked against what was lost.
- Input tokens were not recorded. The rules lengthen the system prompt, so on
  a short answer they can cost more input than they save in output.
- The committed `rules/` at cac4bad, which added these results, are identical
  to the initial commit and unchanged through d46c99c. The run's own working
  tree was not committed, so the exact rule text it used cannot be confirmed.
  `core.md` has since been split into a safe default and an opt-in aggressive
  profile (`rules/profiles/aggressive.md`); the safe default has not been
  benchmarked yet.

## Notes on the General Question result

The 76.4% reduction on the horizontal/vertical scaling question is the largest
because the baseline model produced an extensive multi-section essay with
headers, subheaders, a comparison table, and a conclusion paragraph. The rules
version answered in four direct paragraphs. Whether those paragraphs kept
everything the essay said was judged by reading them, not measured.

## Reproduce

Every run calls the Anthropic API (10 calls for all five scenarios).

```bash
pip install -e ".[anthropic]"
export ANTHROPIC_API_KEY=...
python benchmarks/harness.py --save
```

The defaults are this file's model and the committed harness's settings:
`claude-sonnet-4-6`, temperature 1.0, max 4096 output tokens. `--save`
overwrites this file with the new run's numbers, settings, input tokens and
raw outputs; pass `--output` to keep it.
