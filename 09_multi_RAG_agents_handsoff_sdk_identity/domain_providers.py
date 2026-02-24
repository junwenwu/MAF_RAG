# Copyright (c) Microsoft. All rights reserved.

"""Domain-specific ChromaDB context providers for the multi-RAG agent system.

Each domain (agents, tools, workflows, general) gets its own:
- ChromaDB collection  (e.g. ``domain_agents``, ``domain_tools``)
- ``ChromaWebContextProvider`` instance that ingests only the URLs for that domain

The providers can be used stand-alone or attached to specialist agents in a
HandoffBuilder workflow.
"""

from __future__ import annotations

import sys
from typing import Any

import chromadb
from agent_framework import AgentSession, BaseContextProvider, Message, SessionContext

from domain_urls import DOMAIN_REGISTRY
from web_loader import load_and_chunk_urls

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


# ---------------------------------------------------------------------------
# ChromaDB context provider — one instance per domain
# ---------------------------------------------------------------------------
class ChromaWebContextProvider(BaseContextProvider):
    """Retrieve relevant web-page chunks from a domain-specific ChromaDB collection.

    On first use the provider fetches the configured URLs, chunks the content,
    and upserts the chunks into ChromaDB.  Subsequent runs reuse the persisted
    collection.
    """

    source_id: str = "chroma_web"

    def __init__(
        self,
        urls: list[str],
        collection_name: str,
        persist_directory: str = ".chromadb",
        top_k: int = 5,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        source_id: str | None = None,
    ) -> None:
        super().__init__(source_id=source_id or f"chroma_{collection_name}")
        self._urls = urls
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._top_k = top_k
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

        # Initialise ChromaDB (persisted to disk so re-runs are instant)
        self._client = chromadb.PersistentClient(path=self._persist_directory)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # Ingest if the collection is empty
        if self._collection.count() == 0:
            self._ingest()

    # --- Ingestion ----------------------------------------------------------
    def _ingest(self) -> None:
        """Fetch URLs, chunk text, and upsert into ChromaDB."""
        print(f"\n📥 Ingesting [{self._collection_name}] — {len(self._urls)} pages...")
        chunks = load_and_chunk_urls(
            self._urls,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
        )
        if not chunks:
            print("  No chunks produced — check the URLs.")
            return

        self._collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {"source_url": c.source_url, "title": c.title, "chunk_index": c.chunk_index}
                for c in chunks
            ],
        )
        print(f"  ✅ Stored {len(chunks)} chunks in [{self._collection_name}].\n")

    # --- Query --------------------------------------------------------------
    def _query(self, query: str) -> list[dict[str, Any]]:
        """Search ChromaDB for the most relevant chunks."""
        results = self._collection.query(
            query_texts=[query],
            n_results=self._top_k,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict[str, Any]] = []
        if results and results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                hits.append({"text": doc, "metadata": meta, "distance": dist})
        return hits

    # --- BaseContextProvider hook -------------------------------------------
    @override
    async def before_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """Retrieve relevant chunks and inject them into the agent context."""
        query = " ".join(
            msg.text for msg in context.input_messages if msg and msg.text
        ).strip()

        if not query:
            return

        hits = self._query(query)
        if not hits:
            return

        context_messages = [
            Message(
                role="user",
                text=(
                    f"Use the following context from the [{self._collection_name}] "
                    "knowledge base to answer the question:"
                ),
            ),
        ]
        for hit in hits:
            title = hit["metadata"].get("title", "")
            url = hit["metadata"].get("source_url", "")
            context_messages.append(
                Message(
                    role="user",
                    text=f"[Source: {title}]({url})\n{hit['text']}",
                )
            )

        context.extend_messages(self.source_id, context_messages)


# ---------------------------------------------------------------------------
# Factory: build all domain providers at once
# ---------------------------------------------------------------------------
def build_domain_providers(
    persist_directory: str = ".chromadb",
    top_k: int = 5,
) -> dict[str, ChromaWebContextProvider]:
    """Create one ``ChromaWebContextProvider`` per registered domain.

    Returns a ``{domain_name: provider}`` dict, e.g.::

        {"agents": <provider>, "tools": <provider>, ...}
    """
    providers: dict[str, ChromaWebContextProvider] = {}
    for domain_name, urls in DOMAIN_REGISTRY.items():
        providers[domain_name] = ChromaWebContextProvider(
            urls=urls,
            collection_name=f"domain_{domain_name}",
            persist_directory=persist_directory,
            top_k=top_k,
        )
    return providers


# ---------------------------------------------------------------------------
# Convenience: re-ingest all domains
# ---------------------------------------------------------------------------
def reingest_all(persist_directory: str = ".chromadb") -> None:
    """Delete all domain collections and re-ingest from scratch."""
    client = chromadb.PersistentClient(path=persist_directory)
    for domain_name in DOMAIN_REGISTRY:
        col_name = f"domain_{domain_name}"
        try:
            client.delete_collection(col_name)
            print(f"  Deleted collection '{col_name}'.")
        except Exception:
            pass
    build_domain_providers(persist_directory=persist_directory)
