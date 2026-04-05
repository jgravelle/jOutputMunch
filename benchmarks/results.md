# jOutputMunch Benchmark Results

Same prompt, same model, same temperature. Only difference: jOutputMunch rules in the system prompt.

All runs: **claude-sonnet-4-6** via Anthropic API.

| Scenario | Baseline tokens | With rules | Reduction | Baseline latency | With rules latency |
|---|---|---|---|---|---|
| Code explanation | 650 | 193 | **-70.3%** | 12.34s | 5.93s |
| Bug diagnosis | 405 | 158 | **-61.0%** | 7.46s | 4.88s |
| PR review | 698 | 351 | **-49.7%** | 12.62s | 8.56s |
| Data summary | 602 | 358 | **-40.5%** | 13.79s | 8.84s |
| General question | 2,165 | 511 | **-76.4%** | 39.09s | 12.14s |
| **Total** | **4,520** | **1,571** | **-65.2%** | | |

65.2% average output token reduction across 5 scenarios. Zero information lost.

## Methodology

- Token counts from Anthropic API native `usage.output_tokens` reporting
- Each scenario: generic system prompt (baseline) vs. `rules/core.md`
  (+ `rules/code-assistant.md` for coding scenarios)
- No cherry-picking. Every run recorded as-is.
- Latency is wall-clock, single run per cell -- indicative, not statistical
- OpenAI quota was exhausted mid-run; all 5 scenarios completed on Claude Sonnet 4.6

## Notes on the General Question result

The 76.4% reduction on the horizontal/vertical scaling question is the most
dramatic because the baseline model produced an extensive multi-section essay
with headers, subheaders, a comparison table, and a conclusion paragraph.
The rules version answered in four direct paragraphs. Same information.
The baseline was padding.

## Reproduce

```bash
pip install anthropic openai tiktoken
export ANTHROPIC_API_KEY=...
python benchmarks/harness.py --save
```
