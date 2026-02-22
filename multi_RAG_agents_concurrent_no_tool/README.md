# Multi-RAG Agent with Concurrent Orchestration (No Function Tools)

This project demonstrates **multiple domain-specialist RAG agents** running **in parallel** using the [ConcurrentBuilder](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/concurrent) orchestration pattern from the Microsoft Agent Framework.

## Architecture

```
User Question
     │
     ▼
┌─────────────────────────────────────────────────┐
│           Fan-out (parallel dispatch)           │
│                                                 │
│  ┌───────────┐  ┌───────────┐                   │
│  │  Agents   │  │   Tools   │                   │
│  │ Specialist│  │ Specialist│                   │
│  │ (16 pages)│  │ (8 pages) │                   │
│  └─────┬─────┘  └─────┬─────┘                   │
│  ┌───────────┐  ┌───────────┐                   │
│  │ Workflows │  │  General  │                   │
│  │ Specialist│  │ Specialist│                   │
│  │ (20 pages)│  │ (53 pages)│                   │
│  └─────┬─────┘  └─────┬─────┘                   │
│        │    │    │     │                         │
│        └────┼────┘     │                         │
│             ▼          ▼                         │
│       Fan-in (aggregator)                        │
│    LLM synthesises consolidated answer           │
└─────────────────────────────────────────────────┘
```

## Key Concepts

| Concept | Description |
|---|---|
| **ConcurrentBuilder** | Fan-out/fan-in: dispatches the same prompt to all participants in parallel, then aggregates results |
| **No triage agent** | Every specialist answers every question simultaneously — no routing decision needed |
| **Custom aggregator** | An LLM-based callback discards irrelevant responses and synthesises the useful ones into a single answer |
| **`NO_RELEVANT_CONTEXT`** | Specialists that lack context return this sentinel; the aggregator filters them out |
| **Domain split** | Same 4-domain split as the handoff project: agents, tools, workflows, general |
| **No function tools** | Specialists answer purely from their RAG context — no `@tool`-decorated functions |

## Handoff vs Concurrent

| Aspect | Handoff (previous project) | Concurrent (this project) |
|---|---|---|
| **Routing** | Triage agent routes to one specialist | All specialists answer in parallel |
| **Latency** | Sequential: triage then specialist | Parallel: all run simultaneously |
| **Cost** | 1 triage call + 1 specialist call | 4 specialist calls + 1 aggregation call |
| **Answer quality** | Single specialist perspective | Multi-perspective synthesised answer |
| **Best for** | Clear-domain questions | Cross-domain or ambiguous questions |

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
pip install -r multi_RAG_agents_concurrent_no_tool/requirements.txt

# First run will scrape and index all 97 pages into 4 ChromaDB collections
python multi_RAG_agents_concurrent_no_tool/main.py

# Force re-scrape
python multi_RAG_agents_concurrent_no_tool/main.py --reingest
```

## Example Session

```
You: How do I create a function tool?
Agent: [all 4 specialists answer in parallel, aggregator synthesises]
  ⚡ Parallel: agents_specialist, tools_specialist, workflows_specialist, general_specialist

You: What orchestration patterns are available?
Agent: [synthesised answer from workflows + general specialists]
  ⚡ Parallel: agents_specialist, tools_specialist, workflows_specialist, general_specialist
```

## Files

| File | Description |
|---|---|
| `main.py` | ConcurrentBuilder workflow + custom LLM aggregator + interactive loop |
| `domain_urls.py` | URL lists split by domain (shared with handoff project) |
| `domain_providers.py` | `ChromaWebContextProvider` per domain (shared with handoff project) |
| `web_loader.py` | Web scraping + chunking (shared across all projects) |
| `requirements.txt` | Python dependencies |

## How the Aggregator Works

1. All 4 specialists receive the question simultaneously
2. Each specialist queries its own ChromaDB collection for RAG context
3. Specialists with no relevant context respond with `NO_RELEVANT_CONTEXT`
4. The custom aggregator:
   - Filters out `NO_RELEVANT_CONTEXT` responses
   - If only one specialist answered → returns that answer directly
   - If multiple specialists answered → sends their combined output to the LLM to synthesise a single consolidated answer

## Series

1. **single_RAG_agent_no_tool** — Single agent RAG over the full docs
2. **single_RAG_agent_with_tool** — Same agent plus function tools
3. **multi_RAG_agents_handsoff_no_tool** — Multiple specialists with handoff orchestration
4. **multi_RAG_agents_concurrent_no_tool** — Multiple specialists with concurrent orchestration ← you are here
