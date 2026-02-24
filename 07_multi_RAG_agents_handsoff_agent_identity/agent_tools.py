# Copyright (c) Microsoft. All rights reserved.

"""Domain-specific function tools for the multi-agent handoff system.

Unlike Part 5 where every specialist received the **same** tool set, each
specialist here gets a tool set **tailored to its domain**:

+---------------------+-----------------------------+-------------------------------+
| Domain              | Tool                        | Why it fits this domain       |
+---------------------+-----------------------------+-------------------------------+
| agents              | list_supported_providers    | Providers are agent-level     |
| tools               | search_github_samples       | Code samples ≈ tooling        |
| workflows           | compare_orchestrations      | Orchestration patterns live   |
|                     |                             | in the workflows docs         |
| general             | compare_concepts            | Cross-domain catch-all        |
+---------------------+-----------------------------+-------------------------------+

Each tool queries the appropriate ChromaDB collection(s) — domain-scoped
tools search their own collection; the general tool searches all four.
"""

from __future__ import annotations

from typing import Annotated, Any

import chromadb
import requests
from agent_framework import tool
from pydantic import Field

# ---------------------------------------------------------------------------
# Domain collection names (must match domain_providers.py)
# ---------------------------------------------------------------------------
_DOMAIN_COLLECTIONS = [
    "domain_agents",
    "domain_tools",
    "domain_workflows",
    "domain_general",
]


def _get_collection(
    name: str,
    persist_directory: str = ".chromadb",
) -> chromadb.Collection:
    """Return a handle to a single named ChromaDB collection."""
    client = chromadb.PersistentClient(path=persist_directory)
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _get_all_collections(
    persist_directory: str = ".chromadb",
) -> list[chromadb.Collection]:
    """Return handles to all four domain collections."""
    client = chromadb.PersistentClient(path=persist_directory)
    return [
        client.get_or_create_collection(name=n, metadata={"hnsw:space": "cosine"})
        for n in _DOMAIN_COLLECTIONS
    ]


# ═══════════════════════════════════════════════════════════════════════════
# AGENTS domain tool — list_supported_providers
# ═══════════════════════════════════════════════════════════════════════════
@tool(approval_mode="never_require")
def list_supported_providers(
    query: Annotated[
        str,
        Field(description="Optional filter query, e.g. 'Ollama' or 'local models' (pass empty string for all)"),
    ] = "",
    top_k: Annotated[
        int,
        Field(description="Number of chunks to retrieve", ge=1, le=15),
    ] = 8,
) -> str:
    """List the LLM providers supported by the Microsoft Agent Framework and
    their key configuration details.

    Searches the **agents** domain collection for provider-related documentation
    including Azure OpenAI, OpenAI, Anthropic, Ollama, GitHub Copilot, Copilot
    Studio, Azure AI Foundry, and custom providers.

    Use this tool when the user asks about supported providers, how to configure
    a specific provider, or which LLM backends are available.
    """
    col = _get_collection("domain_agents")
    if col.count() == 0:
        return "The agents domain collection is empty — run ingestion first."

    search_text = query if query else "LLM providers supported Azure OpenAI Anthropic Ollama"
    results = col.query(
        query_texts=[search_text],
        n_results=min(top_k, col.count()),
        include=["documents", "metadatas", "distances"],
    )

    if not results or not results["documents"] or not results["documents"][0]:
        return "No provider information found in the agents knowledge base."

    sections: list[str] = ["## Supported LLM Providers\n"]
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        title = meta.get("title", "")
        url = meta.get("source_url", "")
        sections.append(f"**Source:** [{title}]({url})")
        sections.append(doc)
        sections.append("")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# TOOLS domain tool — search_github_samples
# ═══════════════════════════════════════════════════════════════════════════
_GITHUB_API = "https://api.github.com"
_REPO = "microsoft/agent-framework"


@tool(approval_mode="never_require")
def search_github_samples(
    query: Annotated[
        str,
        Field(description="Search query for code samples (e.g. 'function tool decorator')"),
    ],
    language: Annotated[str, Field(description="Programming language filter")] = "Python",
    max_results: Annotated[
        int,
        Field(description="Maximum number of results to return", ge=1, le=10),
    ] = 5,
) -> str:
    """Search the microsoft/agent-framework GitHub repository for code samples.

    Use this tool when the user asks for code examples, sample implementations,
    or wants to see how a feature is used in the official repository.
    """
    search_query = f"{query} repo:{_REPO} language:{language} path:samples"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MAF-RAG-Agent/1.0",
    }

    try:
        resp = requests.get(
            f"{_GITHUB_API}/search/code",
            params={"q": search_query, "per_page": max_results},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return f"GitHub API request failed: {exc}"

    items = data.get("items", [])
    if not items:
        return f"No code samples found for '{query}' in {_REPO}."

    results: list[str] = [f"Found {len(items)} sample(s) in **{_REPO}**:\n"]

    for item in items:
        name = item.get("name", "")
        path = item.get("path", "")
        html_url = item.get("html_url", "")
        repo_name = item.get("repository", {}).get("full_name", _REPO)

        results.append(f"### [{name}]({html_url})")
        results.append(f"- **Path:** `{path}`")
        results.append(f"- **Repository:** {repo_name}")

        # Fetch a snippet of the file content (first 80 lines)
        raw_url = f"https://raw.githubusercontent.com/{repo_name}/main/{path}"
        try:
            raw_resp = requests.get(
                raw_url,
                headers={"User-Agent": "MAF-RAG-Agent/1.0"},
                timeout=10,
            )
            if raw_resp.status_code == 200:
                lines = raw_resp.text.splitlines()[:80]
                snippet = "\n".join(lines)
                results.append(f"\n```{language.lower()}\n{snippet}\n```\n")
            else:
                results.append("")
        except requests.RequestException:
            results.append("")

    return "\n".join(results)


# ═══════════════════════════════════════════════════════════════════════════
# WORKFLOWS domain tool — compare_orchestrations
# ═══════════════════════════════════════════════════════════════════════════
@tool(approval_mode="never_require")
def compare_orchestrations(
    pattern_a: Annotated[
        str,
        Field(description="First orchestration pattern (e.g. 'HandoffBuilder')"),
    ],
    pattern_b: Annotated[
        str,
        Field(description="Second orchestration pattern (e.g. 'ConcurrentBuilder')"),
    ],
    top_k: Annotated[
        int,
        Field(description="Number of chunks to retrieve per pattern", ge=1, le=10),
    ] = 4,
) -> str:
    """Retrieve workflow documentation for two orchestration patterns and
    return them side-by-side for comparison.

    Searches the **workflows** domain collection only, where all orchestration
    pattern documentation lives (Sequential, Concurrent, Handoff, Group Chat,
    Magentic).

    Use this tool when the user asks to compare, contrast, or differentiate
    two orchestration or workflow patterns.
    """
    col = _get_collection("domain_workflows")
    if col.count() == 0:
        return "The workflows domain collection is empty — run ingestion first."

    def _retrieve(query: str) -> list[dict[str, Any]]:
        results = col.query(
            query_texts=[query],
            n_results=min(top_k, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict[str, Any]] = []
        if results and results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                hits.append({
                    "text": doc,
                    "title": meta.get("title", ""),
                    "source_url": meta.get("source_url", ""),
                    "distance": dist,
                })
        return hits

    hits_a = _retrieve(pattern_a)
    hits_b = _retrieve(pattern_b)

    sections: list[str] = []
    sections.append(f"## {pattern_a}")
    if hits_a:
        for h in hits_a:
            sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
            sections.append(h["text"])
            sections.append("")
    else:
        sections.append("_No documentation found._\n")

    sections.append(f"## {pattern_b}")
    if hits_b:
        for h in hits_b:
            sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
            sections.append(h["text"])
            sections.append("")
    else:
        sections.append("_No documentation found._\n")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# GENERAL domain tool — compare_concepts (cross-domain)
# ═══════════════════════════════════════════════════════════════════════════
@tool(approval_mode="never_require")
def compare_concepts(
    concept_a: Annotated[
        str,
        Field(description="First concept to compare (e.g. 'BaseContextProvider')"),
    ],
    concept_b: Annotated[
        str,
        Field(description="Second concept to compare (e.g. 'middleware')"),
    ],
    top_k: Annotated[
        int,
        Field(description="Number of chunks to retrieve per concept", ge=1, le=10),
    ] = 3,
) -> str:
    """Retrieve documentation for two Agent Framework concepts and return
    them side-by-side for comparison.

    Queries ALL four domain collections (agents, tools, workflows, general)
    so the results span the full knowledge base.  This cross-domain search
    is ideal for the general specialist which handles broad, cross-cutting
    questions.

    Use this tool when the user asks to compare, contrast, or differentiate
    two concepts, classes, or features of the Microsoft Agent Framework.
    """
    collections = _get_all_collections()

    def _retrieve(query: str) -> list[dict[str, Any]]:
        all_hits: list[dict[str, Any]] = []
        for col in collections:
            if col.count() == 0:
                continue
            results = col.query(
                query_texts=[query],
                n_results=min(top_k, col.count()),
                include=["documents", "metadatas", "distances"],
            )
            if results and results["documents"]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    all_hits.append({
                        "text": doc,
                        "title": meta.get("title", ""),
                        "source_url": meta.get("source_url", ""),
                        "distance": dist,
                        "collection": col.name,
                    })
        all_hits.sort(key=lambda h: h["distance"])
        return all_hits[:top_k]

    hits_a = _retrieve(concept_a)
    hits_b = _retrieve(concept_b)

    sections: list[str] = []
    sections.append(f"## {concept_a}")
    if hits_a:
        for h in hits_a:
            sections.append(
                f"**Source:** [{h['title']}]({h['source_url']}) "
                f"(collection: {h['collection']})"
            )
            sections.append(h["text"])
            sections.append("")
    else:
        sections.append("_No documentation found._\n")

    sections.append(f"## {concept_b}")
    if hits_b:
        for h in hits_b:
            sections.append(
                f"**Source:** [{h['title']}]({h['source_url']}) "
                f"(collection: {h['collection']})"
            )
            sections.append(h["text"])
            sections.append("")
    else:
        sections.append("_No documentation found._\n")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Registry: domain name → list of tools for that specialist
# ---------------------------------------------------------------------------
DOMAIN_TOOLS: dict[str, list] = {
    "agents": [list_supported_providers],
    "tools": [search_github_samples],
    "workflows": [compare_orchestrations],
    "general": [compare_concepts],
}
