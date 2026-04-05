# AutoGen Integration

Add jOutputMunch rules to any AutoGen 0.4 agent.

## Setup

Read `rules/core.md` and prepend it to your agent's system message:

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from pathlib import Path

rules = Path("rules/core.md").read_text()

agent = AssistantAgent(
    name="assistant",
    model_client=OpenAIChatCompletionClient(model="gpt-4o"),
    system_message=rules + "\n\n" + "Your custom instructions here.",
)
```

For agents that use MCP tools, also include `rules/mcp.md`:

```python
rules = Path("rules/core.md").read_text()
mcp_rules = Path("rules/mcp.md").read_text()

agent = AssistantAgent(
    name="code_navigator",
    model_client=model_client,
    workbench=workbench,
    system_message=rules + "\n" + mcp_rules,
)
```

## CrewAI, LangChain, LlamaIndex

Same principle: prepend the rule text to whatever field controls the
agent's system prompt. The rules are plain text with no dependencies.
