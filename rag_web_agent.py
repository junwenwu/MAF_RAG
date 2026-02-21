# Copyright (c) Microsoft. All rights reserved.

"""ChromaDB-backed context provider for the Microsoft Agent Framework.

This module:
1. Fetches web pages and chunks them (via web_loader).
2. Stores chunks in a local ChromaDB collection with embeddings.
3. Implements ``BaseContextProvider`` to retrieve relevant chunks before every
   agent invocation — giving the model grounded context (RAG).

No Azure AI Search required — everything runs locally.

Usage:
    python rag_web_agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import chromadb
from agent_framework import AgentSession, BaseContextProvider, Message, SessionContext
from agent_framework.azure import AzureOpenAIChatClient
from dotenv import load_dotenv

from web_loader import DEFAULT_URLS, TextChunk, load_and_chunk_urls

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

# Load environment variables from .env file
load_dotenv()


# ---------------------------------------------------------------------------
# ChromaDB context provider
# ---------------------------------------------------------------------------
class ChromaWebContextProvider(BaseContextProvider):
    """Retrieve relevant web-page chunks from a local ChromaDB collection.

    On first use the provider fetches the configured URLs, chunks the content,
    and upserts the chunks into ChromaDB.  Subsequent runs reuse the persisted
    collection.
    """

    source_id: str = "chroma_web"

    def __init__(
        self,
        urls: list[str] | None = None,
        collection_name: str = "web_docs",
        persist_directory: str = ".chromadb",
        top_k: int = 5,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        source_id: str = "chroma_web",
    ) -> None:
        super().__init__(source_id=source_id)
        self._urls = urls or DEFAULT_URLS
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
        print("\n📥 Ingesting web pages into ChromaDB...")
        chunks = load_and_chunk_urls(
            self._urls,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
        )
        if not chunks:
            print("  No chunks produced — check the URLs.")
            return

        # ChromaDB handles embedding via its built-in default model
        self._collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {"source_url": c.source_url, "title": c.title, "chunk_index": c.chunk_index}
                for c in chunks
            ],
        )
        print(f"  ✅ Stored {len(chunks)} chunks in ChromaDB.\n")

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
                text="Use the following context retrieved from documentation to answer the question:",
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
# Convenience: re-ingest (delete + rebuild)
# ---------------------------------------------------------------------------
def reingest(
    urls: list[str] | None = None,
    collection_name: str = "web_docs",
    persist_directory: str = ".chromadb",
) -> None:
    """Delete the existing collection and re-ingest from scratch."""
    client = chromadb.PersistentClient(path=persist_directory)
    try:
        client.delete_collection(collection_name)
        print(f"Deleted collection '{collection_name}'.")
    except Exception:
        pass
    ChromaWebContextProvider(urls=urls, collection_name=collection_name, persist_directory=persist_directory)


# ---------------------------------------------------------------------------
# Main — standalone demo
# ---------------------------------------------------------------------------
async def main() -> None:
    """Run an interactive RAG agent backed by web-scraped ChromaDB docs."""

    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")

    provider = ChromaWebContextProvider()

    agent = AzureOpenAIChatClient(api_key=api_key).as_agent(
        name="WebRAGAgent",
        instructions=(
            "You are a knowledgeable assistant for the Microsoft Agent Framework. "
            "Answer questions using the provided documentation context. "
            "Always cite the source URL when available. "
            "If the context does not contain the answer, say so clearly."
        ),
        context_providers=[provider],
    )

    print("=" * 60)
    print("  RAG Agent — Web Docs via ChromaDB (Local)")
    print("=" * 60)

    queries = [
        "What is the Microsoft Agent Framework?",
        "How do I create my first agent?",
        "What types of tools does the framework support?",
        "How do I add a function tool to an agent?",
    ]

    for user_input in queries:
        print(f"\nUser: {user_input}")
        result = await agent.run(user_input)
        print(f"Agent: {result}")


if __name__ == "__main__":
    asyncio.run(main())
