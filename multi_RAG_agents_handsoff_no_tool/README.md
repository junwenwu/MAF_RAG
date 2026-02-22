# Multi-RAG Agent with Handoff Orchestration (No Function Tools)

This project demonstrates **multiple domain-specialist RAG agents** coordinated by a **triage agent** using the [HandoffBuilder](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff) orchestration pattern from the Microsoft Agent Framework.

## Architecture

```
User Question
     │
     ▼
┌────────────┐
│   Triage   │  No RAG — just routes
│   Agent    │
└─────┬──────┘
      │  handoff_to_<specialist>
      ▼
┌─────────────────────────────────────────┐
│  Specialist Agents (one per domain)     │
│                                         │
│  ┌───────────┐  ┌───────────┐           │
│  │  Agents   │  │   Tools   │           │
│  │ Specialist│  │ Specialist│           │
│  │ (16 pages)│  │ (8 pages) │           │
│  └───────────┘  └───────────┘           │
│  ┌───────────┐  ┌───────────┐           │
│  │ Workflows │  │  General  │           │
│  │ Specialist│  │ Specialist│           │
│  │ (20 pages)│  │ (53 pages)│           │
│  └───────────┘  └───────────┘           │
│                                         │
│  Each specialist has its own ChromaDB   │
│  collection + BaseContextProvider       │
└─────────────────────────────────────────┘
```

## Key Concepts

| Concept | Description |
|---|---|
| **HandoffBuilder** | Assembles agents in a mesh topology where agents transfer control to each other via tool calls |
| **Triage agent** | A routing agent with no RAG — analyzes the user's question and hands off to the right specialist |
| **Specialist agents** | Each has a domain-specific `BaseContextProvider` backed by its own ChromaDB collection |
| **Domain split** | The ~97 Agent Framework doc pages are split into 4 domains: agents, tools, workflows, general |
| **No function tools** | Specialists answer purely from their RAG context — no `@tool`-decorated functions |

## Domain Split

| Domain | Collection | Pages | Topics |
|---|---|---|---|
| **agents** | `domain_agents` | 16 | Core agent concepts, running agents, multimodal, structured output, RAG, providers |
| **tools** | `domain_tools` | 8 | Function tools, @tool decorator, tool approval, code interpreter, MCP tools |
| **workflows** | `domain_workflows` | 20 | Executors, edges, events, orchestrations (handoff, sequential, concurrent, group chat) |
| **general** | `domain_general` | 53 | Overview, getting started, conversations, middleware, integrations, migration, support |

## Quick Start

```bash
# From the repo root
pip install -r multi_RAG_agents_handsoff_no_tool/requirements.txt

# First run will scrape and index all 97 pages into 4 ChromaDB collections
python multi_RAG_agents_handsoff_no_tool/main.py

# Force re-scrape
python multi_RAG_agents_handsoff_no_tool/main.py --reingest
```

## Example Session

```
You: How do I create a function tool?
Agent: [triage routes to tools_specialist]
  🔀 Routing: triage_agent → tools_specialist

You: What orchestration patterns are available?
Agent: [triage routes to workflows_specialist]
  🔀 Routing: triage_agent → workflows_specialist

You: How do I get started with the Agent Framework?
Agent: [triage routes to general_specialist]
  🔀 Routing: triage_agent → general_specialist
```

## How It Works

1. **Domain URLs** ([domain_urls.py](domain_urls.py)) — Splits the full URL list into 4 domains
2. **Domain Providers** ([domain_providers.py](domain_providers.py)) — Creates one `ChromaWebContextProvider` per domain, each with its own ChromaDB collection
3. **Handoff Workflow** ([main.py](main.py)) — Wires everything together:
   - Creates a triage agent (no RAG, just routing instructions)
   - Creates 4 specialist agents (each with their domain's context provider)
   - Uses `HandoffBuilder` to build a workflow where triage hands off to specialists
   - Streams responses and shows the routing trace

## Files

| File | Description |
|---|---|
| [main.py](main.py) | Entry point — builds HandoffBuilder workflow, interactive loop |
| [domain_urls.py](domain_urls.py) | URL lists split by domain |
| [domain_providers.py](domain_providers.py) | `ChromaWebContextProvider` per domain + factory |
| [web_loader.py](web_loader.py) | Web scraping + chunking (shared logic) |
| [requirements.txt](requirements.txt) | Python dependencies |

## Progression

This is project 3 in the learning series:

1. **single_RAG_agent_no_tool** — Single agent, single ChromaDB collection, no tools
2. **single_RAG_agent_with_tool** — Single agent + function tools
3. **multi_RAG_agents_handsoff_no_tool** — Multiple specialist agents with handoff orchestration ← you are here
