# Multi-RAG Agents – Handoff Orchestration with Shared Tools

Multi-agent handoff orchestration where **every specialist agent receives the
same function tools** alongside its domain-specific RAG context provider.

## Architecture

```
User → Triage Agent → Specialist (agents | tools | workflows | general)
                       ├─ domain-specific ChromaDB collection (RAG context)
                       └─ shared tools: compare_concepts, search_github_samples
```

### What's shared vs. domain-specific

| Aspect        | Shared / Per-specialist |
|---------------|-------------------------|
| RAG context   | Per-specialist (4 ChromaDB collections) |
| Function tools | **Shared** (same 2 tools for all) |
| Instructions  | Per-specialist (domain-aware prompt) |

## Shared tools

1. **`compare_concepts`** — Queries *all four* domain collections, retrieves
   documentation for two concepts, and presents them side-by-side.  This
   cross-domain search is the key adaptation from the single-agent version.

2. **`search_github_samples`** — Searches the `microsoft/agent-framework`
   GitHub repository for code samples.  Domain-agnostic by nature.

## Running

```bash
# From the repo root (assumes .venv is activated and .env is configured)
python 05_multi_RAG_agents_handsoff_shared_tools/main.py

# Re-scrape all documentation pages
python 05_multi_RAG_agents_handsoff_shared_tools/main.py --reingest
```

## Example questions

- "Compare BaseContextProvider and middleware" → triage → general_specialist → `compare_concepts` tool
- "Show me code samples for the @tool decorator" → triage → tools_specialist → `search_github_samples` tool
- "How do I create a declarative agent?" → triage → agents_specialist → RAG context only (no tool needed)

## Key delta from `03_multi_RAG_agents_handsoff_no_tool`

1. Added `agent_tools.py` with shared function tools
2. `build_agents()` now accepts a `shared_tools` list and passes it to every specialist via `tools=shared_tools`
3. The event loop tracks `function_call` content types and prints which tools were used
4. `compare_concepts` queries across all 4 domain collections (cross-domain merge + rank by distance)
