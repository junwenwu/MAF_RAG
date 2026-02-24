# Multi-RAG Agents – Handoff Orchestration with Agent Identity

Part 7 of the MAF learning series. Builds on [Part 6 (domain-specific tools)](../06_multi_RAG_agents_handsoff_domain_tools/) by adding **structured agent identity** — a dataclass that captures each agent's persona, scope, behavioral rules, response style, and tool policy in one place.

## Architecture

```
User
  │
  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Triage Agent (identity: route-only, no RAG, no tools)             │
│  Identity: name, role, scope, behavioral_rules, response_style     │
└──────────┬────────────┬──────────────┬───────────────┬─────────────┘
           │            │              │               │
    ┌──────▼──────┐  ┌──▼──────────┐  ┌▼────────────┐ ┌▼──────────────┐
    │ agents      │  │ tools       │  │ workflows   │ │ general       │
    │ identity    │  │ identity    │  │ identity    │ │ identity      │
    │ + RAG       │  │ + RAG       │  │ + RAG       │ │ + RAG         │
    │ + domain    │  │ + domain    │  │ + domain    │ │ + domain      │
    │   tool      │  │   tool      │  │   tool      │ │   tool        │
    └─────────────┘  └─────────────┘  └─────────────┘ └───────────────┘
```

## Key delta from Part 6

In Part 6, each agent's "identity" was scattered across three places:

| Part 6 location | What it held |
|---|---|
| `AGENT_DESCRIPTIONS` dict | One-liner for HandoffBuilder routing |
| `_TOOL_INSTRUCTIONS` dict | Mandatory tool-usage rules per domain |
| Inline string in `build_agents()` | Instructions, citations, behavioral hints |

In Part 7, all of these are consolidated into a single `AgentIdentity` dataclass:

```python
@dataclass(frozen=True)
class AgentIdentity:
    name: str              # e.g. "agents_specialist"
    role: str              # one-liner for routing
    expertise: list[str]   # bulleted topic list
    in_scope: str          # what the agent SHOULD answer
    out_of_scope: str      # what the agent SHOULD NOT answer
    behavioral_rules: list[str]  # ordered guardrails
    response_style: str    # formatting/citation/tone
    tool_policy: str       # mandatory tool-usage rules
```

The `build_instructions()` function assembles a structured system prompt with clearly delimited sections:

```
# Identity
You are **agents_specialist** — Specialist for core agent concepts...

## Expertise
- Creating and configuring agents
- Running agents and processing responses
- ...

## Scope
**IN SCOPE:** Questions about agent creation, configuration...
**OUT OF SCOPE:** Questions about function tools (→ tools_specialist)...

## Behavioral Rules
1. Answer ONLY from the provided documentation context...
2. Always cite the source URL...
3. ...

## Response Style
Use clear, concise language. Prefer bullet points...

## Available Tools
Tools: list_supported_providers

## Tool Policy — MANDATORY
If the user asks about SUPPORTED PROVIDERS...
```

## Files

| File | New/Changed | Purpose |
|---|---|---|
| `agent_identity.py` | **NEW** | `AgentIdentity` dataclass + `build_instructions()` + per-agent identity definitions |
| `main.py` | Changed | `build_agents()` reads from `AgentIdentity` instead of inline strings |
| `agent_tools.py` | Unchanged | Same `DOMAIN_TOOLS` registry from Part 6 |
| `domain_urls.py` | Unchanged | Same URL splits |
| `domain_providers.py` | Unchanged | Same `ChromaWebContextProvider` per domain |
| `web_loader.py` | Unchanged | Same scraping + chunking |

## Identity components

| Component | Purpose | Example (agents specialist) |
|---|---|---|
| **name** | Agent name in HandoffBuilder | `agents_specialist` |
| **role** | One-line description for routing | "Specialist for core agent concepts..." |
| **expertise** | Bulleted topics the agent can answer | Creating agents, providers, multimodal... |
| **in_scope** | Positive scope statement | "Questions about agent creation, configuration..." |
| **out_of_scope** | Explicit exclusions with redirect | "Questions about function tools (→ tools_specialist)" |
| **behavioral_rules** | Ordered guardrails | "Answer ONLY from context", "Always cite sources"... |
| **response_style** | Formatting requirements | "Use clear, concise language. Prefer bullet points." |
| **tool_policy** | Mandatory tool-usage rules | "If user asks about PROVIDERS → MUST call list_supported_providers" |

## Running

```bash
cd MAF_RAG
python -m venv .venv && source .venv/bin/activate
pip install -r 07_multi_RAG_agents_handsoff_agent_identity/requirements.txt

# Azure CLI auth (recommended)
az login

# Or set AZURE_OPENAI_API_KEY in .env
cp .env.example .env

python 07_multi_RAG_agents_handsoff_agent_identity/main.py
```

## Example prompts

```
What LLM providers does the framework support?
Show me code samples for the @tool decorator
Compare HandoffBuilder and ConcurrentBuilder
Compare BaseContextProvider and middleware
How do I create a declarative agent?
```

## Series

| # | Project | Focus |
|---|---|---|
| 01 | [single_RAG_agent_no_tool](../01_single_RAG_agent_no_tool/) | Single agent, single collection, no tools |
| 02 | [single_RAG_agent_with_tool](../02_single_RAG_agent_with_tool/) | Same agent + function tools |
| 03 | [multi_RAG_agents_handsoff_no_tool](../03_multi_RAG_agents_handsoff_no_tool/) | Handoff orchestration, no tools |
| 04 | [multi_RAG_agents_concurrent_no_tool](../04_multi_RAG_agents_concurrent_no_tool/) | Concurrent fan-out/fan-in |
| 05 | [multi_RAG_agents_handsoff_shared_tools](../05_multi_RAG_agents_handsoff_shared_tools/) | Handoff + shared tools |
| 06 | [multi_RAG_agents_handsoff_domain_tools](../06_multi_RAG_agents_handsoff_domain_tools/) | Handoff + domain-specific tools |
| **07** | **multi_RAG_agents_handsoff_agent_identity** | **Handoff + agent identity** ← you are here |
