# OpenAI / ChatGPT Integration

Add jOutputMunch rules to any OpenAI API call or custom GPT.

## API usage

Prepend the contents of `rules/core.md` to your system message:

```python
import openai

rules = open("rules/core.md").read()

response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": rules},
        {"role": "user", "content": "Your prompt here"},
    ],
)
```

## Custom GPTs

1. Go to ChatGPT > Explore GPTs > Create
2. In the Instructions field, paste the contents of `rules/core.md`
3. Save

Every conversation with that GPT will follow the output rules.

## Minimal system message

If you want the shortest possible version:

```
Rules for every response:
- Lead with the answer. No preamble.
- Use contractions. Short sentences.
- No filler: delve, tapestry, leverage, multifaceted, seamless, utilize.
- No openers ("Great question!") or closers ("Hope this helps!").
- One hedge per claim max. Do not restate what was just said.
- JSON: no indentation, no echo fields, no nulls, no derived counts.
```
