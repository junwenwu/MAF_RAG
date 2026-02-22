# Adding Function Tools to a RAG Agent with Microsoft Agent Framework

*Part 2 of the MAF Series*

---

In [Part 1](../single_RAG_agent_no_tool/blog-01-building-rag-with-maf.md), I built a RAG prototype that answers questions grounded in the Agent Framework documentation. It works well for general Q&A, but it has a limitation: every answer comes from the same retrieval pipeline. Ask it to *compare* two concepts, and it retrieves chunks for the combined query rather than each concept independently. Ask for *code samples*, and it can only quote documentation text — it can't search a real repository.

In this post, I extend the RAG agent with **function tools** — custom Python functions that the LLM can call on its own when the question warrants it. The agent decides *automatically* which tool to use (or whether to skip tools entirely) based on the user's intent.

The full source code is available on [GitHub](https://github.com/junwenwu/MAF_RAG).

## What changes from Part 1

The Part 1 agent has a single path: retrieve context from ChromaDB, then answer. The Part 2 agent keeps that path but adds two more:

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
       ┌───────┼────────┐
       ▼       ▼        ▼
  Direct    Compare   Search
  answer    concepts  GitHub
```

The LLM sees the tool definitions alongside the injected context and decides the best route. No if-else routing. No intent classifier. The model handles it.

## The `@tool` decorator

Microsoft Agent Framework provides a `@tool` decorator that turns any Python function into something the LLM can call. The decorator does three things automatically:

1. **Generates a JSON schema** from the function signature and type annotations
2. **Extracts the docstring** as the tool description (the LLM reads this to decide when to call it)
3. **Wires up invocation** so the framework handles the call-and-return cycle

Here's the minimal pattern:

```python
from agent_framework import tool

@tool(approval_mode="never_require")
def my_tool(query: str) -> str:
    """Description the LLM reads to decide when to call this tool."""
    return "result"
```

The `approval_mode="never_require"` flag tells the framework to execute the tool without asking the user for permission. For production agents handling sensitive operations, you'd set this to `"always_require"` or use middleware for approval flows.

### Type annotations drive the schema

The `@tool` decorator uses `Annotated` types with Pydantic `Field` to generate richer schemas:

```python
from typing import Annotated
from pydantic import Field

@tool(approval_mode="never_require")
def compare_concepts(
    concept_a: Annotated[str, Field(description="First concept to compare")],
    concept_b: Annotated[str, Field(description="Second concept to compare")],
    top_k: Annotated[int, Field(description="Chunks per concept", ge=1, le=10)] = 3,
) -> str:
    """Retrieve documentation for two concepts and return them side-by-side."""
    ...
```

The LLM sees a schema like:

```json
{
  "name": "compare_concepts",
  "description": "Retrieve documentation for two concepts and return them side-by-side.",
  "parameters": {
    "concept_a": { "type": "string", "description": "First concept to compare" },
    "concept_b": { "type": "string", "description": "Second concept to compare" },
    "top_k": { "type": "integer", "description": "Chunks per concept", "default": 3 }
  }
}
```

Good descriptions here make the difference between the LLM calling the right tool and hallucinating an answer. The docstring tells the LLM *when* to call the tool; the field descriptions tell it *what* to pass.

## Tool 1: compare_concepts

A common question pattern is "What's the difference between X and Y?" The base RAG agent handles this by retrieving chunks for the combined query "X and Y," which often returns mixed or irrelevant results. The `compare_concepts` tool solves this by querying ChromaDB *separately* for each concept:

```python
@tool(approval_mode="never_require")
def compare_concepts(
    concept_a: Annotated[str, Field(description="First concept to compare")],
    concept_b: Annotated[str, Field(description="Second concept to compare")],
    top_k: Annotated[int, Field(description="Chunks per concept", ge=1, le=10)] = 3,
) -> str:
    """Retrieve documentation for two Agent Framework concepts and return them
    side-by-side for comparison."""
    collection = _get_collection()

    def _retrieve(query: str) -> list[dict]:
        results = collection.query(
            query_texts=[query], n_results=top_k,
            include=["documents", "metadatas"],
        )
        hits = []
        if results and results["documents"]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                hits.append({
                    "text": doc,
                    "title": meta.get("title", ""),
                    "source_url": meta.get("source_url", ""),
                })
        return hits

    hits_a = _retrieve(concept_a)
    hits_b = _retrieve(concept_b)

    # Format as side-by-side Markdown sections
    sections = []
    sections.append(f"## {concept_a}")
    for h in hits_a:
        sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
        sections.append(h["text"])
    sections.append(f"## {concept_b}")
    for h in hits_b:
        sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
        sections.append(h["text"])

    return "\n".join(sections)
```

The tool reuses the same ChromaDB collection that the `BaseContextProvider` already populated — no duplicate data, no extra embedding calls. The `_get_collection()` helper opens the persisted collection in read-only mode:

```python
def _get_collection(
    persist_directory: str = ".chromadb",
    collection_name: str = "web_docs",
) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=persist_directory)
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
```

## Tool 2: search_github_samples

Documentation explains concepts. Code shows how to use them. The `search_github_samples` tool bridges that gap by searching the official `microsoft/agent-framework` GitHub repository for real sample code:

```python
@tool(approval_mode="never_require")
def search_github_samples(
    query: Annotated[str, Field(description="Search query for code samples")],
    language: Annotated[str, Field(description="Programming language filter")] = "Python",
    max_results: Annotated[int, Field(description="Maximum results", ge=1, le=10)] = 5,
) -> str:
    """Search the microsoft/agent-framework GitHub repository for code samples."""
    search_query = f"{query} repo:{_REPO} language:{language} path:samples"

    resp = requests.get(
        "https://api.github.com/search/code",
        params={"q": search_query, "per_page": max_results},
        headers={"Accept": "application/vnd.github.v3+json"},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])

    results = []
    for item in items:
        html_url = item.get("html_url", "")
        path = item.get("path", "")
        results.append(f"### [{item['name']}]({html_url})")
        results.append(f"- **Path:** `{path}`")

        # Fetch a code snippet (first 80 lines)
        raw_url = f"https://raw.githubusercontent.com/{_REPO}/main/{path}"
        raw_resp = requests.get(raw_url, timeout=10)
        if raw_resp.status_code == 200:
            snippet = "\n".join(raw_resp.text.splitlines()[:80])
            results.append(f"\n```python\n{snippet}\n```\n")

    return "\n".join(results)
```

The tool uses GitHub's code search API scoped to the `samples/` directory. For each result, it fetches the first 80 lines of source code so the LLM can include actual snippets in its response — not just links.

Note: GitHub's unauthenticated API allows roughly 10 requests per minute. For heavier use, you'd add a `GITHUB_TOKEN` header.

## Registering tools with the agent

With both functions defined, registering them is a single parameter:

```python
from agent_tools import compare_concepts, search_github_samples

agent = client.as_agent(
    name="WebRAGAgent",
    instructions=(
        "You are a knowledgeable assistant for the Microsoft Agent Framework. "
        "Answer questions using the provided documentation context. "
        "Always cite the source URL when available.\n\n"
        "You have access to tools:\n"
        "- compare_concepts: Use when the user asks to compare or contrast two concepts.\n"
        "- search_github_samples: Use when the user asks for code examples from the official repo.\n\n"
        "Choose the right tool automatically based on the user's question. "
        "For general questions, just use the documentation context directly."
    ),
    context_providers=[provider],
    tools=[compare_concepts, search_github_samples],
)
```

The `tools=[]` parameter accepts any list of `@tool`-decorated functions. The framework auto-generates the tool schemas and includes them in every LLM request. The agent instructions provide guidance on *when* to use each tool, but the LLM ultimately decides.

## Tracking which tools were used

A natural question arises: did the agent actually call a tool, or did it just answer from context? I added tool usage tracking by inspecting the finalized response after streaming:

```python
stream = agent.run(user_input, stream=True)
async for chunk in stream:
    if chunk.text:
        print(chunk.text, end="", flush=True)

# Inspect the final response for tool calls
response = await stream.get_final_response()
tools_used = []
for msg in response.messages:
    for content in msg.contents:
        if content.type == "function_call" and hasattr(content, "name"):
            if content.name not in tools_used:
                tools_used.append(content.name)

if tools_used:
    print(f"\n  🔧 Tools used: {', '.join(tools_used)}")
else:
    print("\n  ℹ️  No function tools called (answered from RAG context)")
```

The key insight: during streaming, `function_call` content chunks may arrive with partial or empty `name` fields. The reliable approach is to call `get_final_response()` after the stream completes, which returns fully accumulated messages with complete function call records.

## Example session

```
You: Compare context providers and function tools

Agent: Here's a comparison of context providers and function tools...

  **Context Providers** inject data into the conversation before the
  model runs. They manage memory, history, and session state via the
  `before_run()` hook.

  **Function Tools** let the agent execute actions during a conversation.
  They're defined with `@tool` and registered via `tools=[]`.

  Context providers enrich context; function tools extend capabilities.

  🔧 Tools used: compare_concepts
```

```
You: What is the Agent Framework?

Agent: The Microsoft Agent Framework is a unified Python and .NET SDK
  that brings together the best of AutoGen and Semantic Kernel...

  ℹ️  No function tools called (answered from RAG context)
```

The agent routes "compare X and Y" to `compare_concepts` and uses direct RAG context for general questions — no explicit routing code required.

## Lessons learned

**Tool descriptions are prompts.** The docstring and field descriptions are the only information the LLM has when deciding which tool to call. Vague descriptions lead to tools being ignored or misused. Being explicit about *when* to use a tool (in both the docstring and the agent instructions) dramatically improves routing accuracy.

**Reuse your vector store.** The `compare_concepts` tool queries the same ChromaDB collection that the context provider already maintains. This avoids duplicating data and embedding costs. Any tool that needs domain knowledge can tap into the same persisted collection.

**Inspect the final response, not streaming chunks.** During streaming, `function_call` content arrives in partial chunks — the `name` field may be empty in early chunks. Calling `get_final_response()` after the stream completes gives you the fully assembled messages with complete tool call information.

**`approval_mode` controls execution safety.** Setting `"never_require"` is fine for read-only tools like search and retrieval. For tools that modify state (write to databases, call external APIs with side effects), use `"always_require"` to add a human-in-the-loop approval step.

**The context provider and tools are complementary, not competing.** The context provider runs on every request and ensures the agent always has relevant documentation. Tools activate only when the LLM decides they're needed. Together, they give the agent a baseline of knowledge plus specialized capabilities.

## Running it yourself

```bash
git clone https://github.com/junwenwu/MAF_RAG.git
cd MAF_RAG
python -m venv .venv && source .venv/bin/activate
pip install -r single_RAG_agent_with_tool/requirements.txt

# Option A: Azure CLI auth (recommended)
az login

# Option B: API key auth
# Set AZURE_OPENAI_API_KEY in .env

cp .env.example .env
# Edit .env with your endpoint and deployment name

python single_RAG_agent_with_tool/main.py
```

### Example prompts to try

```
Compare BaseContextProvider and middleware
Show me code samples for function tools
What's the difference between sequential and concurrent orchestration?
Find examples of the @tool decorator in the official repo
```

## What's next

This is the second installment in the series. Coming up:

- **Multi-agent for multiple RAGs** — coordinating specialized agents across different knowledge sources
- **Workflows and orchestrations** for multi-agent collaboration
- **Agent Identity** — configuring agent personas and behavioral boundaries
- **Agent Blueprint** — declarative agent definitions for reproducible deployments

The full source code is on [GitHub](https://github.com/junwenwu/MAF_RAG). Questions or feedback? Open an issue or reach out.

---

*Built with [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) | [ChromaDB](https://docs.trychroma.com/) | [Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/)*
