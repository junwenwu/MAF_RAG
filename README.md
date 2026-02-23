# MAF RAG — Learning Microsoft Agent Framework

A hands-on series exploring the [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) through practical projects, starting with Retrieval-Augmented Generation (RAG).

## Projects

| Folder | Description |
|---|---|
| [01_single_RAG_agent_no_tool/](01_single_RAG_agent_no_tool/) | Single agent with ChromaDB-backed RAG over the full Agent Framework docs (~97 pages) |
| [02_single_RAG_agent_with_tool/](02_single_RAG_agent_with_tool/) | Same RAG agent plus function tools: concept comparison and GitHub sample search |
| [03_multi_RAG_agents_handsoff_no_tool/](03_multi_RAG_agents_handsoff_no_tool/) | Multiple domain-specialist RAG agents with handoff orchestration (no function tools) |
| [04_multi_RAG_agents_concurrent_no_tool/](04_multi_RAG_agents_concurrent_no_tool/) | Multiple domain-specialist RAG agents with concurrent fan-out/fan-in orchestration (no function tools) |

## Planned

- **Multi-agent with function tools** — specialist agents enhanced with domain-specific tools
- **Workflows and orchestrations** — multi-agent collaboration patterns
- **Agent Identity** — configuring agent personas and behavioral boundaries
- **Agent Blueprint** — declarative agent definitions for reproducible deployments

## Quick start

```bash
git clone https://github.com/junwenwu/MAF_RAG.git
cd MAF_RAG
python -m venv .venv && source .venv/bin/activate
pip install -r 01_single_RAG_agent_no_tool/requirements.txt

cp .env.example .env
# Edit .env with your Azure OpenAI endpoint and deployment name

# Option A: Azure CLI auth (recommended)
az login

# Option B: API key auth — set AZURE_OPENAI_API_KEY in .env

python 01_single_RAG_agent_no_tool/main.py
```

## Prerequisites

- Python 3.10+
- An Azure OpenAI resource with a chat deployment (e.g., `gpt-4.1`)
- Azure CLI (`az login`) or an API key

## Repository layout

```
MAF_RAG/
├── .env.example                          # Environment variable template
├── .gitignore
├── README.md                             # ← you are here
├── 01_single_RAG_agent_no_tool/
│   ├── README.md                         # Detailed project docs
│   ├── main.py                           # CLI entry point (3 modes)
│   ├── web_loader.py                     # Web scraping + chunking
│   ├── rag_web_agent.py                  # ChromaDB context provider
│   ├── rag_custom_provider.py            # In-memory keyword search demo
│   ├── rag_search_agent.py               # Azure AI Search version (optional)
│   └── requirements.txt                  # Python dependencies
├── 02_single_RAG_agent_with_tool/
│   ├── README.md                         # Project docs
│   ├── main.py                           # CLI entry point with tools
│   ├── agent_tools.py                    # compare_concepts + search_github_samples
│   ├── web_loader.py                     # Web scraping + chunking
│   ├── rag_web_agent.py                  # ChromaDB context provider
│   └── requirements.txt                  # Python dependencies
├── 03_multi_RAG_agents_handsoff_no_tool/
│   ├── README.md                         # Project docs
│   ├── main.py                           # HandoffBuilder workflow + interactive loop
│   ├── domain_urls.py                    # URL lists split by domain
│   ├── domain_providers.py               # ChromaWebContextProvider per domain
│   ├── web_loader.py                     # Web scraping + chunking
│   └── requirements.txt                  # Python dependencies
├── 04_multi_RAG_agents_concurrent_no_tool/
│   ├── README.md                         # Project docs
│   ├── main.py                           # ConcurrentBuilder workflow + LLM aggregator
│   ├── domain_urls.py                    # URL lists split by domain
│   ├── domain_providers.py               # ChromaWebContextProvider per domain
│   ├── web_loader.py                     # Web scraping + chunking
│   └── requirements.txt                  # Python dependencies
└── 05_multi_RAG_agents_handsoff_shared_tools/
    ├── README.md                         # Project docs
    ├── main.py                           # HandoffBuilder workflow + shared tools
    ├── agent_tools.py                    # compare_concepts + search_github_samples
    ├── domain_urls.py                    # URL lists split by domain
    ├── domain_providers.py               # ChromaWebContextProvider per domain
    └── web_loader.py                     # Web scraping + chunking
```

## License

This project is for learning purposes.
