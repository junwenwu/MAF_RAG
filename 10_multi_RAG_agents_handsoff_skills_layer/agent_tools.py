# Copyright (c) Microsoft. All rights reserved.

"""Learning-focused function tools for the MAF Learning Assistant.

Each specialist gets tools **tailored to learning outcomes**:

+---------------------+-----------------------------+--------------------------------------+
| Domain              | Tool                        | Learning Purpose                     |
+---------------------+-----------------------------+--------------------------------------+
| agents              | list_supported_providers    | "What LLMs can I use?"               |
| agents              | find_getting_started        | "How do I start with agents?"        |
| tools               | search_github_samples       | Code samples from official repo      |
| tools               | find_code_examples          | Code examples from RAG (fallback)    |
| workflows           | compare_orchestrations      | "X vs Y" pattern comparisons         |
| general             | compare_concepts            | Cross-domain concept comparisons     |
| general             | find_prerequisites          | "What should I know before X?"       |
| general             | find_related_topics         | "What concepts relate to X?"         |
+---------------------+-----------------------------+--------------------------------------+

Each tool queries the appropriate ChromaDB collection(s) — domain-scoped
tools search their own collection; cross-domain tools search all four.
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


# ═══════════════════════════════════════════════════════════════════════════
# AGENTS domain tool — find_getting_started
# ═══════════════════════════════════════════════════════════════════════════
@tool(approval_mode="never_require")
def find_getting_started(
    topic: Annotated[
        str,
        Field(description="Topic to find getting started guide for (e.g. 'agents', 'tools', 'RAG')"),
    ],
    top_k: Annotated[
        int,
        Field(description="Number of chunks to retrieve", ge=1, le=10),
    ] = 5,
) -> str:
    """Find getting started, quickstart, or tutorial content for a topic.

    Searches the **agents** and **general** domain collections for introductory
    content like quickstarts, getting started guides, and basic tutorials.

    Use this tool when the user:
    - Is new to a topic and needs an entry point
    - Asks "How do I get started with X?"
    - Asks "What's the first step for X?"
    - Needs a tutorial or quickstart guide
    """
    # Search both agents and general collections for intro content
    collections = [
        _get_collection("domain_agents"),
        _get_collection("domain_general"),
    ]

    search_queries = [
        f"getting started {topic}",
        f"quickstart {topic}",
        f"tutorial {topic}",
        f"introduction {topic}",
    ]

    all_hits: list[dict[str, Any]] = []
    for col in collections:
        if col.count() == 0:
            continue
        for query in search_queries:
            results = col.query(
                query_texts=[query],
                n_results=min(3, col.count()),
                include=["documents", "metadatas", "distances"],
            )
            if results and results["documents"]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    # Dedupe by source URL
                    url = meta.get("source_url", "")
                    if not any(h["source_url"] == url for h in all_hits):
                        all_hits.append({
                            "text": doc,
                            "title": meta.get("title", ""),
                            "source_url": url,
                            "distance": dist,
                        })

    all_hits.sort(key=lambda h: h["distance"])
    hits = all_hits[:top_k]

    if not hits:
        return f"No getting started content found for '{topic}'. Try the general documentation."

    sections: list[str] = [f"## Getting Started: {topic}\n"]
    for h in hits:
        sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
        sections.append(h["text"])
        sections.append("")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# TOOLS domain tool — find_code_examples (RAG-based fallback)
# ═══════════════════════════════════════════════════════════════════════════
@tool(approval_mode="never_require")
def find_code_examples(
    topic: Annotated[
        str,
        Field(description="Topic to find code examples for (e.g. 'function tool', '@tool decorator', 'agent creation')"),
    ],
    top_k: Annotated[
        int,
        Field(description="Number of code examples to retrieve", ge=1, le=10),
    ] = 5,
) -> str:
    """Find code examples from the ingested documentation for a topic.

    Searches the **tools** and **agents** domain collections for code snippets,
    examples, and sample implementations. This is a RAG-based alternative to
    GitHub API search that uses your already-ingested documentation.

    Use this tool when the user:
    - Asks "Show me code for X"
    - Asks "How do I implement X?"
    - Needs a code example or sample
    - Wants to see syntax for a feature
    """
    collections = [
        _get_collection("domain_tools"),
        _get_collection("domain_agents"),
    ]

    search_queries = [
        f"code example {topic}",
        f"sample {topic}",
        f"how to {topic}",
        f"{topic} implementation",
    ]

    all_hits: list[dict[str, Any]] = []
    for col in collections:
        if col.count() == 0:
            continue
        for query in search_queries:
            results = col.query(
                query_texts=[query],
                n_results=min(3, col.count()),
                include=["documents", "metadatas", "distances"],
            )
            if results and results["documents"]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    # Prioritize docs that likely contain code
                    has_code = "```" in doc or "def " in doc or "class " in doc or "@tool" in doc
                    url = meta.get("source_url", "")
                    if not any(h["source_url"] == url for h in all_hits):
                        all_hits.append({
                            "text": doc,
                            "title": meta.get("title", ""),
                            "source_url": url,
                            "distance": dist if not has_code else dist * 0.8,  # Boost code-containing docs
                        })

    all_hits.sort(key=lambda h: h["distance"])
    hits = all_hits[:top_k]

    if not hits:
        return f"No code examples found for '{topic}'. Try rephrasing or check the documentation directly."

    sections: list[str] = [f"## Code Examples: {topic}\n"]
    for h in hits:
        sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
        sections.append(h["text"])
        sections.append("")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# GENERAL domain tool — find_prerequisites
# ═══════════════════════════════════════════════════════════════════════════
@tool(approval_mode="never_require")
def find_prerequisites(
    topic: Annotated[
        str,
        Field(description="Topic to find prerequisites for (e.g. 'HandoffBuilder', 'RAG', 'function tools')"),
    ],
    top_k: Annotated[
        int,
        Field(description="Number of chunks to retrieve", ge=1, le=8),
    ] = 4,
) -> str:
    """Find prerequisite knowledge or setup requirements for a topic.

    Searches ALL domain collections for information about what a learner
    should know or have set up before tackling a topic.

    Use this tool when the user:
    - Asks "What should I know before learning X?"
    - Asks "What are the prerequisites for X?"
    - Asks "What do I need to set up for X?"
    - Is confused and may be missing foundational knowledge
    """
    collections = _get_all_collections()

    search_queries = [
        f"prerequisites {topic}",
        f"before you start {topic}",
        f"requirements {topic}",
        f"setup {topic}",
        f"depends on {topic}",
    ]

    all_hits: list[dict[str, Any]] = []
    for col in collections:
        if col.count() == 0:
            continue
        for query in search_queries:
            results = col.query(
                query_texts=[query],
                n_results=min(2, col.count()),
                include=["documents", "metadatas", "distances"],
            )
            if results and results["documents"]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    url = meta.get("source_url", "")
                    if not any(h["source_url"] == url for h in all_hits):
                        all_hits.append({
                            "text": doc,
                            "title": meta.get("title", ""),
                            "source_url": url,
                            "distance": dist,
                            "collection": col.name,
                        })

    all_hits.sort(key=lambda h: h["distance"])
    hits = all_hits[:top_k]

    if not hits:
        return f"No prerequisite information found for '{topic}'. This topic may not have specific prerequisites, or you can start with the getting started guide."

    sections: list[str] = [f"## Prerequisites for: {topic}\n"]
    for h in hits:
        sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
        sections.append(h["text"])
        sections.append("")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# GENERAL domain tool — find_related_topics
# ═══════════════════════════════════════════════════════════════════════════
@tool(approval_mode="never_require")
def find_related_topics(
    topic: Annotated[
        str,
        Field(description="Topic to find related concepts for (e.g. 'context providers', 'orchestrations')"),
    ],
    top_k: Annotated[
        int,
        Field(description="Number of related topics to find", ge=1, le=10),
    ] = 6,
) -> str:
    """Find topics related to or connected with a given concept.

    Searches ALL domain collections to find concepts that relate to,
    depend on, or extend the given topic. Helps learners understand
    the broader context and connections.

    Use this tool when the user:
    - Asks "What concepts relate to X?"
    - Asks "What should I learn after X?"
    - Asks "What uses X?" or "What does X use?"
    - Wants to understand the bigger picture
    """
    collections = _get_all_collections()

    search_queries = [
        f"{topic} related to",
        f"{topic} uses",
        f"{topic} depends on",
        f"with {topic}",
        f"{topic} and",
    ]

    all_hits: list[dict[str, Any]] = []
    for col in collections:
        if col.count() == 0:
            continue
        for query in search_queries:
            results = col.query(
                query_texts=[query],
                n_results=min(2, col.count()),
                include=["documents", "metadatas", "distances"],
            )
            if results and results["documents"]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    url = meta.get("source_url", "")
                    if not any(h["source_url"] == url for h in all_hits):
                        all_hits.append({
                            "text": doc,
                            "title": meta.get("title", ""),
                            "source_url": url,
                            "distance": dist,
                            "collection": col.name,
                        })

    all_hits.sort(key=lambda h: h["distance"])
    hits = all_hits[:top_k]

    if not hits:
        return f"No related topics found for '{topic}'. Try a broader search term."

    sections: list[str] = [f"## Topics Related to: {topic}\n"]
    for h in hits:
        domain = h["collection"].replace("domain_", "")
        sections.append(f"**Source:** [{h['title']}]({h['source_url']}) (domain: {domain})")
        sections.append(h["text"])
        sections.append("")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Registry: domain name → list of tools for that specialist
# ---------------------------------------------------------------------------
DOMAIN_TOOLS: dict[str, list] = {
    "agents": [list_supported_providers, find_getting_started],
    "tools": [search_github_samples, find_code_examples],
    "workflows": [compare_orchestrations],
    "general": [compare_concepts, find_prerequisites, find_related_topics],
}
