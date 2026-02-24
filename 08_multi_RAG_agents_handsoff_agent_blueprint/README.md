# 08 — Agent Blueprint (Declarative Multi-Agent Definitions)

Multi-agent handoff system where the entire agent configuration — identities,
scopes, behavioral rules, tool assignments, and security prompts — is defined
in a **YAML blueprint** instead of Python code.

## What changed from Part 7

| Aspect | Part 7 (Python identity) | Part 8 (YAML blueprint) |
|---|---|---|
| Identity location | `agent_identity.py` (~300 lines of Python) | `blueprint.yaml` (~230 lines of YAML) |
| Format | Frozen dataclass instances in source code | Declarative YAML — no Python knowledge needed |
| Modification workflow | Edit Python → test → deploy | Edit YAML → test → deploy |
| Schema validation | Compile-time (Python type system) | Load-time (`blueprint_loader.py` validates) |
| Tool assignment | Hard-coded in `DOMAIN_TOOLS` and `AgentIdentity` | Declared by name in YAML, resolved at load time |
| Security prompt | Hard-coded in `build_instructions()` | Field in `shared:` section, configurable |
| Custom blueprints | N/A — one hard-coded configuration | `--blueprint custom.yaml` CLI flag |

## Architecture

```
blueprint.yaml
    │
    ▼
blueprint_loader.py  ──→  Blueprint(triage, specialists, tool_assignments, ...)
    │                          │
    │                          ├── AgentIdentity (triage)
    │                          ├── AgentIdentity (agents_specialist)
    │                          ├── AgentIdentity (tools_specialist)
    │                          ├── AgentIdentity (workflows_specialist)
    │                          └── AgentIdentity (general_specialist)
    │
    ▼
main.py
    ├── _resolve_tools()    ← maps tool names from YAML to callable objects
    ├── build_agents()      ← creates agents from Blueprint + providers
    └── run()               ← HandoffBuilder workflow + streaming event loop
```

## Blueprint schema

```yaml
version: "1.0"

shared:
  behavioral_rules: [...]   # Applied to all specialists
  response_style: "..."     # Applied to all specialists
  security_prompt: "..."    # Anchored at top of every system prompt

triage:
  name: triage_agent
  role: "..."
  expertise: [...]
  in_scope: "..."
  out_of_scope: "..."
  behavioral_rules: [...]   # Triage-specific (overrides shared)
  response_style: "..."     # Triage-specific (overrides shared)

specialists:
  agents:
    name: agents_specialist
    role: "..."
    expertise: [...]
    in_scope: "..."
    out_of_scope: "..."
    tools: [list_supported_providers]   # Resolved by name from registry
    tool_policy: "..."
  tools: { ... }
  workflows: { ... }
  general: { ... }
```

## Key files

| File | Purpose |
|---|---|
| `blueprint.yaml` | **NEW** — Declarative agent system definition |
| `blueprint_loader.py` | **NEW** — Loads YAML, validates, builds `AgentIdentity` + `Blueprint` |
| `main.py` | Simplified — reads from blueprint instead of hard-coded identities |
| `agent_tools.py` | Same tool registry from Part 7 |
| `domain_urls.py` | Same URL splits |
| `domain_providers.py` | Same ChromaDB providers |
| `web_loader.py` | Same scraping + chunking |

## Running

```bash
# From repo root
python -m venv .venv && source .venv/bin/activate
pip install -r 08_multi_RAG_agents_handsoff_agent_blueprint/requirements.txt

# Azure CLI auth
az login

# Default blueprint
python 08_multi_RAG_agents_handsoff_agent_blueprint/main.py

# Custom blueprint
python 08_multi_RAG_agents_handsoff_agent_blueprint/main.py --blueprint path/to/custom.yaml

# Re-ingest all domain collections
python 08_multi_RAG_agents_handsoff_agent_blueprint/main.py --reingest
```

## Series

1. [01\_single\_RAG\_agent\_no\_tool](../01_single_RAG_agent_no_tool/) — Single agent, single ChromaDB collection
2. [02\_single\_RAG\_agent\_with\_tool](../02_single_RAG_agent_with_tool/) — Same agent plus function tools
3. [03\_multi\_RAG\_agents\_handsoff\_no\_tool](../03_multi_RAG_agents_handsoff_no_tool/) — Handoff orchestration
4. [04\_multi\_RAG\_agents\_concurrent\_no\_tool](../04_multi_RAG_agents_concurrent_no_tool/) — Concurrent fan-out/fan-in
5. [05\_multi\_RAG\_agents\_handsoff\_shared\_tools](../05_multi_RAG_agents_handsoff_shared_tools/) — Shared function tools
6. [06\_multi\_RAG\_agents\_handsoff\_domain\_tools](../06_multi_RAG_agents_handsoff_domain_tools/) — Domain-specific tools
7. [07\_multi\_RAG\_agents\_handsoff\_agent\_identity](../07_multi_RAG_agents_handsoff_agent_identity/) — Structured agent identity
8. **08\_multi\_RAG\_agents\_handsoff\_agent\_blueprint** — Declarative YAML blueprint ← you are here
