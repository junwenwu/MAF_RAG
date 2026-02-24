# Multi-RAG Agents – Handoff Orchestration with Domain-Specific Tools

Multi-agent handoff orchestration where **each specialist agent receives
tools tailored to its domain** — unlike Part 5 where every specialist
shared the same tool set.

## Architecture

```
User → Triage Agent → Specialist (agents | tools | workflows | general)
                       ├─ domain-specific ChromaDB collection (RAG context)
                       └─ domain-specific tools (unique per specialist)
```

### Tool assignment

| Specialist | Tool | Scope |
|---|---|---|
| agents | `list_supported_providers` | Queries agents collection for provider info |
| tools | `search_github_samples` | Searches GitHub repo for code samples |
| workflows | `compare_orchestrations` | Queries workflows collection for pattern comparison |
| general | `compare_concepts` | Cross-domain comparison across all 4 collections |

### What's shared vs. domain-specific

| Aspect | Shared / Per-specialist |
|---|---|
| RAG context | Per-specialist (4 ChromaDB collections) |
| Function tools | **Per-specialist** (different tools per domain) |
| Instructions | Per-specialist (domain-aware + tool-specific rules) |

## Running

```bash
# From the repo root (assumes .venv is activated and .env is configured)
python 06_multi_RAG_agents_handsoff_domain_tools/main.py

# Re-scrape all documentation pages
python 06_multi_RAG_agents_handsoff_domain_tools/main.py --reingest
```

## Example questions

- "What providers does the framework support?" → triage → agents_specialist → `list_supported_providers`
- "Show me code samples for the @tool decorator" → triage → tools_specialist → `search_github_samples`
- "Compare HandoffBuilder and ConcurrentBuilder" → triage → workflows_specialist → `compare_orchestrations`
- "Compare BaseContextProvider and middleware" → triage → general_specialist → `compare_concepts`
- "How do I create a declarative agent?" → triage → agents_specialist → RAG context only

## Key delta from `05_multi_RAG_agents_handsoff_shared_tools`

1. `agent_tools.py` defines four tools organised in a `DOMAIN_TOOLS` registry mapping domain → tool list
2. `build_agents()` reads from `DOMAIN_TOOLS` instead of accepting a flat `shared_tools` list
3. `_TOOL_INSTRUCTIONS` dict provides domain-specific mandatory tool-usage rules
4. Each specialist sees only the tools relevant to its domain — no unused tool definitions in the prompt
5. `compare_orchestrations` is a new domain-scoped tool that queries only the workflows collection
6. `list_supported_providers` is a new domain-scoped tool that queries only the agents collection
