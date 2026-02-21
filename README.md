# Microsoft Agent Framework — RAG Application

A Retrieval-Augmented Generation (RAG) prototype built with the
[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/)
that uses **web pages** (e.g. learn.microsoft.com) as the knowledge source — no
Azure AI Search required.

## Architecture

```
Web Pages (learn.microsoft.com, ...)
    │  fetched & chunked at startup
    ▼
┌──────────────────────────────────┐
│  ChromaDB (local vector store)   │
│  stores text chunks + embeddings │
└──────────┬───────────────────────┘
           │  top-k similarity search
           ▼
┌──────────────────────────────────┐
│  Microsoft Agent Framework       │
│  ┌────────────────────────────┐  │
│  │  ChromaWebContextProvider  │  │
│  │  (BaseContextProvider)     │──┼──▶ ChromaDB query
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │  Agent (gpt-4o)            │  │
│  │  + RAG instructions        │──┼──▶ Azure OpenAI
│  └────────────────────────────┘  │
└──────────────────────────────────┘
           │
           ▼
      Grounded Answer (with source citations)
```

## Modes

| File | Mode | Description |
|---|---|---|
| `rag_web_agent.py` | **Web docs (default)** | Fetches web pages → chunks → ChromaDB → RAG |
| `rag_custom_provider.py` | Custom local | In-memory keyword search against sample Contoso docs |
| `rag_search_agent.py` | Azure AI Search | Semantic search via Azure AI Search (requires setup) |
| `main.py` | Interactive CLI | Interactive Q&A loop supporting all modes |

## Prerequisites

- Python 3.10+
- **Azure OpenAI** deployment (e.g. `gpt-4o`) with an Azure subscription
- Azure CLI installed and authenticated (`az login`)
- Internet access (to fetch web pages on first run)

**Not** required: Azure AI Search, Azure AI Foundry project, or your own data.

## Setup

1. **Enter the directory:**

   ```bash
   cd MAF_RAG
   ```

2. **Create a virtual environment and install dependencies:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   ```

3. **Authenticate with Azure:**

   ```bash
   az login
   ```

   The agent uses `AzureCliCredential` to connect to your default Azure OpenAI
   resource. No `.env` changes needed for the default web mode.

## Usage

### Interactive chat (web docs — recommended)

```bash
python main.py
```

On first run the app fetches pages from learn.microsoft.com, chunks them, and
stores the embeddings in a local `.chromadb/` folder. Subsequent runs reuse the
cached data instantly.

### Run sample queries

```bash
python rag_web_agent.py
```

### Custom Contoso sample data (no web fetch)

```bash
python main.py --mode custom
```

### Re-ingest web pages

If you want to refresh the cached content:

```python
from rag_web_agent import reingest
reingest()  # deletes and re-fetches all pages
```

### Add your own URLs

Edit the `DEFAULT_URLS` list in [web_loader.py](web_loader.py) or pass custom
URLs programmatically:

```python
from rag_web_agent import ChromaWebContextProvider

provider = ChromaWebContextProvider(urls=[
    "https://learn.microsoft.com/en-us/agent-framework/overview/",
    "https://your-docs-site.com/getting-started",
])
```

## Project structure

```
MAF_RAG/
├── main.py                  # Interactive CLI entry point
├── web_loader.py            # Fetch web pages, extract text, chunk
├── rag_web_agent.py         # ChromaDB context provider + demo agent
├── rag_custom_provider.py   # In-memory keyword search provider
├── rag_search_agent.py      # Azure AI Search provider (optional)
├── requirements.txt         # Python dependencies
├── .env                     # Environment config (minimal for web mode)
├── .env.example             # Full template with Azure AI Search vars
└── README.md                # This file
```

## Key concepts

### How the RAG pipeline works

1. **Fetch** — `web_loader.py` downloads web pages and extracts text with BeautifulSoup
2. **Chunk** — Text is split into ~1000-char overlapping chunks
3. **Embed & Store** — Chunks are upserted into ChromaDB (uses its built-in embedding model)
4. **Retrieve** — `ChromaWebContextProvider.before_run()` queries ChromaDB for top-k similar chunks
5. **Generate** — The agent receives the chunks as context and produces a grounded answer

### Context providers

The Microsoft Agent Framework uses **context providers** to inject external
knowledge into the agent's prompt. The framework calls `before_run()` on each
provider before every model invocation.

- **`ChromaWebContextProvider`** — local ChromaDB-backed provider (this project)
- **`AzureAISearchContextProvider`** — first-party Azure AI Search integration
- **`BaseContextProvider`** — abstract base class for building custom providers

## References

- [Microsoft Agent Framework docs](https://learn.microsoft.com/en-us/agent-framework/)
- [Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [ChromaDB documentation](https://docs.trychroma.com/)
