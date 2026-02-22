# Copyright (c) Microsoft. All rights reserved.

"""Custom function tools for the RAG agent.

These tools extend the agent's capabilities beyond simple Q&A by letting the
LLM call Python functions directly.  Each function is decorated with
``@tool`` so the Agent Framework auto-generates input schemas and wires up
invocation.

Tools
-----
* **compare_concepts** – Retrieve and compare two Agent Framework concepts
  side-by-side using the ChromaDB knowledge base.
* **search_github_samples** – Search the ``microsoft/agent-framework`` GitHub
  repository for code samples matching a query.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import chromadb
import requests
from agent_framework import tool
from pydantic import Field


# ---------------------------------------------------------------------------
# Shared ChromaDB handle (reuse the same persisted collection as the RAG
# context provider so we don't duplicate data)
# ---------------------------------------------------------------------------
def _get_collection(
    persist_directory: str = ".chromadb",
    collection_name: str = "web_docs",
) -> chromadb.Collection:
    """Return the existing ChromaDB collection (read-only)."""
    client = chromadb.PersistentClient(path=persist_directory)
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Tool 1 – Compare two Agent Framework concepts
# ---------------------------------------------------------------------------
@tool(approval_mode="never_require")
def compare_concepts(
    concept_a: Annotated[str, Field(description="First concept to compare (e.g. 'BaseContextProvider')")],
    concept_b: Annotated[str, Field(description="Second concept to compare (e.g. 'middleware')")],
    top_k: Annotated[int, Field(description="Number of chunks to retrieve per concept", ge=1, le=10)] = 3,
) -> str:
    """Retrieve documentation for two Agent Framework concepts and return them side-by-side for comparison.

    Use this tool when the user asks to compare, contrast, or differentiate two
    concepts, classes, or features of the Microsoft Agent Framework.
    """
    collection = _get_collection()

    def _retrieve(query: str) -> list[dict[str, Any]]:
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas"],
        )
        hits: list[dict[str, Any]] = []
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

    sections: list[str] = []

    sections.append(f"## {concept_a}")
    if hits_a:
        for h in hits_a:
            sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
            sections.append(h["text"])
            sections.append("")
    else:
        sections.append("_No documentation found._\n")

    sections.append(f"## {concept_b}")
    if hits_b:
        for h in hits_b:
            sections.append(f"**Source:** [{h['title']}]({h['source_url']})")
            sections.append(h["text"])
            sections.append("")
    else:
        sections.append("_No documentation found._\n")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Tool 2 – Search GitHub samples in microsoft/agent-framework
# ---------------------------------------------------------------------------
_GITHUB_API = "https://api.github.com"
_REPO = "microsoft/agent-framework"


@tool(approval_mode="never_require")
def search_github_samples(
    query: Annotated[str, Field(description="Search query for code samples (e.g. 'function tool decorator')")],
    language: Annotated[str, Field(description="Programming language filter")] = "Python",
    max_results: Annotated[int, Field(description="Maximum number of results to return", ge=1, le=10)] = 5,
) -> str:
    """Search the microsoft/agent-framework GitHub repository for code samples.

    Use this tool when the user asks for code examples, sample implementations,
    or wants to see how a feature is used in the official repository.
    """
    # GitHub code search API
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
            raw_resp = requests.get(raw_url, headers={"User-Agent": "MAF-RAG-Agent/1.0"}, timeout=10)
            if raw_resp.status_code == 200:
                lines = raw_resp.text.splitlines()[:80]
                snippet = "\n".join(lines)
                results.append(f"\n```{language.lower()}\n{snippet}\n```\n")
            else:
                results.append("")
        except requests.RequestException:
            results.append("")

    return "\n".join(results)
