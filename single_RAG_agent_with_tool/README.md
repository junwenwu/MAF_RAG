# Single RAG Agent with Function Tool(s)

Extends the [no-tool RAG agent](../single_RAG_agent_no_tool/) by adding
**function tools** that the LLM can call during a conversation.

## Tools

| Tool | Description |
|---|---|
| `compare_concepts` | Retrieve and compare two Agent Framework concepts side-by-side using the ChromaDB knowledge base |
| `search_github_samples` | Search the `microsoft/agent-framework` GitHub repo for code samples matching a query |

Both tools are defined with the `@tool` decorator from the Agent Framework,
which auto-generates JSON schemas from the function signatures and wires up
invocation automatically.

## Architecture

```
User Question
      │
      ▼
┌─────────────────────────────────────┐
│  BaseContextProvider (before_run)   │
│  → query ChromaDB for top-k chunks │
└──────────────┬──────────────────────┘
               │ inject context
               ▼
┌─────────────────────────────────────┐
│  Agent (Azure OpenAI)              │
│  Instructions + Context + Question │
│                                     │
│  Tools:                             │
│   • compare_concepts                │
│   • search_github_samples           │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
  Direct answer    Tool call(s)
                   → compare concepts
                   → search GitHub
                   → return results → final answer
```

## How it differs from the single-tool version

| Aspect | single_RAG_agent_no_tool | single_RAG_agent_with_tool |
|---|---|---|
| Context injection | ChromaDB via `BaseContextProvider` | Same |
| Function tools | None | `compare_concepts`, `search_github_samples` |
| Agent capabilities | Q&A only | Q&A + concept comparison + code sample lookup |

## Running

```bash
# From the repo root
python single_RAG_agent_with_tool/main.py
```

### Example prompts

```
Compare BaseContextProvider and middleware
Show me code samples for function tools
What's the difference between sequential and concurrent orchestration?
Find examples of the @tool decorator in the official repo
```

## Files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point with tools integrated |
| `agent_tools.py` | `compare_concepts` and `search_github_samples` tool definitions |
| `web_loader.py` | Web scraping and chunking (shared with single-tool version) |
| `rag_web_agent.py` | ChromaDB context provider (shared with single-tool version) |
| `requirements.txt` | Python dependencies |
