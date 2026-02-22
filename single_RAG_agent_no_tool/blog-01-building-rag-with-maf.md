# Building a RAG Application with Microsoft Agent Framework

*Part 1 of the MAF Series*

---

Microsoft recently released the [Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) — a unified Python and .NET SDK that brings together the best of AutoGen and Semantic Kernel into a single framework for building agentic AI applications. In this first post of the series, I walk through building a **Retrieval-Augmented Generation (RAG)** prototype that answers questions grounded in real documentation.

The full source code is available on [GitHub](https://github.com/junwenwu/MAF_RAG).

## What we're building

A conversational agent that:

1. Scrapes the entire Agent Framework documentation (~97 pages) from learn.microsoft.com
2. Chunks and embeds the content into a local vector store
3. Retrieves relevant passages at query time
4. Generates grounded answers with source citations via Azure OpenAI

No Azure AI Search required. No proprietary data. Just a local prototype that runs with a single command.

## Architecture

```
User Question
      │
      ▼
┌─────────────────────────────┐
│   BaseContextProvider       │
│   (before_run hook)         │
│   ┌───────────────────────┐ │
│   │ Query ChromaDB for    │ │
│   │ top-k similar chunks  │ │
│   └───────────┬───────────┘ │
└───────────────┼─────────────┘
                │ inject context
                ▼
┌─────────────────────────────┐
│   Agent (Azure OpenAI)      │
│   Instructions + Context    │──▶ Grounded Answer
│   + User Question           │    with source URLs
└─────────────────────────────┘
```

The key insight is that MAF's `BaseContextProvider` gives you a clean hook to inject retrieved context before every model invocation — no prompt engineering gymnastics needed.

## The RAG pipeline in four steps

### Step 1: Scrape and extract text

The web loader fetches each documentation page and extracts clean text using BeautifulSoup. One important detail: link URLs are inlined into the text so the agent can cite them later.

```python
# web_loader.py
from bs4 import BeautifulSoup

def fetch_page_text(url: str) -> tuple[str, str]:
    response = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(response.text, "lxml")

    # Remove noise
    for tag in soup.find_all(["script", "style", "nav", "footer"]):
        tag.decompose()

    # Inline link URLs so they survive get_text()
    # <a href="https://github.com/...">repo</a> → "repo (https://github.com/...)"
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        link_text = a_tag.get_text(strip=True)
        if link_text and href.startswith("http"):
            a_tag.replace_with(f"{link_text} ({href})")

    main = soup.find("main") or soup.find("article") or soup.find("body")
    title = soup.title.string.strip()
    text = main.get_text(separator="\n", strip=True)
    return title, text
```

Without the URL inlining step, BeautifulSoup's `get_text()` discards all `href` attributes, and the agent loses the ability to provide source links.

### Step 2: Chunk the text

Text is split into ~1000-character overlapping chunks. The overlap ensures that information at paragraph boundaries isn't lost.

```python
def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks
```

### Step 3: Embed and store in ChromaDB

ChromaDB handles embedding automatically using its built-in `all-MiniLM-L6-v2` model from Sentence Transformers. This runs entirely locally — no API calls for embedding.

```python
import chromadb

client = chromadb.PersistentClient(path=".chromadb")
collection = client.get_or_create_collection(
    name="web_docs",
    metadata={"hnsw:space": "cosine"},
)

# ChromaDB embeds the documents automatically on upsert
collection.upsert(
    ids=[chunk.id for chunk in chunks],
    documents=[chunk.text for chunk in chunks],
    metadatas=[{"source_url": chunk.source_url, "title": chunk.title} for chunk in chunks],
)
```

A few things to note about this approach:

- **`upsert`** (not `add`) means re-ingesting the same pages won't create duplicates
- **`all-MiniLM-L6-v2`** produces 384-dimensional vectors and truncates at ~256 tokens — longer chunks still get retrieved correctly, but only the first ~200 words influence the similarity score
- **Cosine similarity** is configured via `{"hnsw:space": "cosine"}` for normalized distance comparison
- The `.chromadb/` directory persists embeddings to disk, so subsequent runs skip ingestion entirely

### Step 4: Wire it into MAF with BaseContextProvider

This is where Microsoft Agent Framework shines. Instead of manually stitching prompts together, you implement `BaseContextProvider` and let the framework handle the rest.

```python
from agent_framework import BaseContextProvider, Message, SessionContext

class ChromaWebContextProvider(BaseContextProvider):
    source_id: str = "chroma_web"

    async def before_run(self, *, agent, session, context, state):
        # Extract the user's question
        query = " ".join(
            msg.text for msg in context.input_messages if msg and msg.text
        )

        # Retrieve top-k chunks from ChromaDB
        results = self._collection.query(
            query_texts=[query], n_results=5,
            include=["documents", "metadatas", "distances"],
        )

        # Inject them as context messages
        context_messages = [
            Message(role="user", text="Use the following context to answer:"),
        ]
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            context_messages.append(
                Message(role="user", text=f"[Source: {meta['title']}]({meta['source_url']})\n{doc}")
            )
        context.extend_messages(self.source_id, context_messages)
```

The framework calls `before_run()` before every LLM invocation. The retrieved chunks appear as additional context messages in the conversation, and the model sees them alongside the user's question.

### Putting it all together

Creating the agent takes just a few lines:

```python
from agent_framework.azure import AzureOpenAIChatClient

client = AzureOpenAIChatClient(api_key=os.environ["AZURE_OPENAI_API_KEY"])

agent = client.as_agent(
    name="WebRAGAgent",
    instructions=(
        "You are a knowledgeable assistant for the Microsoft Agent Framework. "
        "Answer questions using the provided documentation context. "
        "Always cite the source URL when available."
    ),
    context_providers=[ChromaWebContextProvider()],
)

# Interactive loop
async for chunk in agent.run("How do I create my first agent?", stream=True):
    print(chunk.text, end="")
```

## What the data source looks like

The prototype scrapes 97 pages across the full Agent Framework documentation:

| Section | Pages | Topics |
|---|---|---|
| Overview & Landing | 2 | GitHub repo, samples, introduction |
| Get Started | 7 | First agent, tools, multi-turn, memory, workflows, hosting |
| Agents | 7 | Running agents, multimodal, structured output, RAG, declarative |
| Tools | 8 | Function tools, code interpreter, file search, web search, MCP tools |
| Conversations & Memory | 4 | Sessions, context providers, storage |
| Middleware | 9 | Defining middleware, termination, exception handling, shared state |
| Providers | 9 | Azure OpenAI, OpenAI, Foundry, Anthropic, Ollama, Copilot Studio |
| Workflows | 13 | Executors, edges, orchestrations (sequential, concurrent, handoff) |
| Integrations | 14 | Azure Functions, A2A, AG-UI protocol |
| DevUI, Migration, Support | 17 | Tracing, migration from AutoGen/Semantic Kernel, FAQ |

All pages are fetched with the Python language pivot. On first run, ingestion takes a few minutes. After that, the ChromaDB cache makes startup instant.

## Lessons learned

**Link URLs matter for RAG.** The default `get_text()` in BeautifulSoup strips all HTML attributes, including `href`. Without explicitly inlining URLs into the text, the agent can say "check the GitHub repository" but can't provide the actual link. A small scraping fix made a big difference in answer quality.

**Broad queries need fallback retrieval.** Keyword-based search returns nothing for questions like "What do you know?" — there's no keyword overlap. Vector similarity search (ChromaDB) handles this naturally because semantic embeddings capture meaning, not just words.

**ChromaDB's built-in embeddings are good enough for prototyping.** `all-MiniLM-L6-v2` runs locally, requires no API keys, and produces reasonable results. For production, you'd likely switch to Azure OpenAI embeddings (`text-embedding-3-large`) for better multilingual support and longer context windows.

**`BaseContextProvider` keeps the code clean.** Without it, you'd be manually concatenating retrieved text into prompts, managing token budgets, and handling the retrieval lifecycle yourself. The framework's `before_run()` hook gives you a single, well-defined place to inject context.

## Running it yourself

```bash
git clone https://github.com/junwenwu/MAF_RAG.git
cd MAF_RAG
python -m venv .venv && source .venv/bin/activate
pip install -r single_RAG_agent_no_tool/requirements.txt

# Option A: Azure CLI auth (recommended)
az login

# Option B: API key auth
# Set AZURE_OPENAI_API_KEY in .env

cp .env.example .env
# Edit .env with your endpoint and deployment name

python single_RAG_agent_no_tool/main.py
```

## What's next

This is the first installment in a series exploring Microsoft Agent Framework. In upcoming posts, I'll cover:

- **Adding function tools** to give the agent capabilities beyond Q&A
- **Multi-agent for multiple RAGs** — coordinating specialized agents across different knowledge sources
- **Workflows and orchestrations** for multi-agent collaboration
- **Agent Identity** — configuring agent personas and behavioral boundaries
- **Agent Blueprint** — declarative agent definitions for reproducible deployments

The full source code is on [GitHub](https://github.com/junwenwu/MAF_RAG). Questions or feedback? Open an issue or reach out.

---

*Built with [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) | [ChromaDB](https://docs.trychroma.com/) | [Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/)*
