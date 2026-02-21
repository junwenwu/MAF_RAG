# Copyright (c) Microsoft. All rights reserved.

"""Custom text-search context provider for offline / local RAG scenarios.

This module shows how to build your own ``BaseContextProvider`` that performs a
keyword-based search against a simple in-memory document store.  You can swap
the search implementation with any backend (Azure AI Search, FAISS, Chroma,
Postgres, etc.) while keeping the same agent integration.

Usage:
    python rag_custom_provider.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from agent_framework import AgentSession, BaseContextProvider, Message, SessionContext
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

# Load environment variables from .env file
load_dotenv()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Document:
    """A searchable document with metadata."""

    id: str
    title: str
    content: str
    source: str
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sample knowledge base – replace with your own documents / data source
# ---------------------------------------------------------------------------
KNOWLEDGE_BASE: list[Document] = [
    Document(
        id="doc-1",
        title="Contoso Outdoors Return Policy",
        content=(
            "Contoso Outdoors offers a 60-day return policy for all products purchased "
            "online or in-store. Items must be in original condition with tags attached. "
            "Refunds are processed within 5-7 business days after the returned item is "
            "received at our warehouse. Clearance items are final sale and cannot be returned."
        ),
        source="https://contoso.com/policies/returns",
        tags=["policy", "returns", "refund"],
    ),
    Document(
        id="doc-2",
        title="Contoso Outdoors Shipping Information",
        content=(
            "Standard shipping takes 5-7 business days and is free for orders over $50. "
            "Express shipping (2-3 business days) is available for $12.99. Overnight shipping "
            "is available for $24.99. All orders are shipped via trusted carriers with "
            "tracking numbers provided via email."
        ),
        source="https://contoso.com/shipping",
        tags=["shipping", "delivery"],
    ),
    Document(
        id="doc-3",
        title="TrailRunner X3 Tent Care Guide",
        content=(
            "The TrailRunner X3 tent features a ripstop nylon body with 3000mm waterproof "
            "rating. To maintain the tent fabric: (1) Always air-dry the tent completely "
            "before storage. (2) Clean with mild soap and lukewarm water – never use "
            "detergent. (3) Apply seam sealer annually. (4) Store loosely rolled in a "
            "cool, dry place. (5) Avoid prolonged UV exposure when not in use."
        ),
        source="https://contoso.com/products/trailrunner-x3/care",
        tags=["product", "tent", "care", "maintenance"],
    ),
    Document(
        id="doc-4",
        title="Alpine Explorer 40L Backpack Features",
        content=(
            "The Alpine Explorer 40L backpack is designed for multi-day hikes. Key features "
            "include an adjustable torso length (15-21 inches), ventilated back panel, "
            "integrated rain cover, hydration sleeve, and multiple organization pockets. "
            "Weight: 2.8 lbs. Made from recycled 210D nylon with a lifetime warranty."
        ),
        source="https://contoso.com/products/alpine-explorer-40l",
        tags=["product", "backpack", "features"],
    ),
]


# ---------------------------------------------------------------------------
# Custom context provider
# ---------------------------------------------------------------------------
class TextSearchContextProvider(BaseContextProvider):
    """Search a local document collection and inject results into the agent context.

    This provider runs a simple keyword search before every agent invocation,
    finds matching documents, and adds them as extra context messages so the
    model can ground its answers.
    """

    source_id: str = "text_search"

    def __init__(
        self,
        documents: list[Document] | None = None,
        top_k: int = 3,
        source_id: str = "text_search",
    ) -> None:
        super().__init__(source_id=source_id)
        self._documents = documents or KNOWLEDGE_BASE
        self._top_k = top_k

    # --- Core hook ----------------------------------------------------------
    @override
    async def before_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """Search the knowledge base and inject relevant documents into context."""
        # Combine input messages into a single query string
        query = " ".join(
            msg.text for msg in context.input_messages if msg and msg.text
        ).lower()

        if not query.strip():
            return

        # Simple keyword matching – replace with vector similarity in production
        scored: list[tuple[float, Document]] = []
        for doc in self._documents:
            score = self._score(query, doc)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_docs = [doc for _, doc in scored[: self._top_k]]

        if not top_docs:
            return

        # Build context messages
        context_messages = [
            Message(role="user", text="Use the following context to answer the question:"),
        ]
        for doc in top_docs:
            context_messages.append(
                Message(
                    role="user",
                    text=f"[Source: {doc.title}]({doc.source})\n{doc.content}",
                )
            )

        context.extend_messages(self.source_id, context_messages)

    # --- Scoring ------------------------------------------------------------
    @staticmethod
    def _score(query: str, doc: Document) -> float:
        """Score a document against a query with simple keyword matching."""
        score = 0.0
        searchable = f"{doc.title} {doc.content} {' '.join(doc.tags)}".lower()
        words = set(query.split())
        for word in words:
            if len(word) > 2 and word in searchable:
                score += 1.0
        # Boost for tag matches
        for tag in doc.tags:
            if tag in query:
                score += 2.0
        return score


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    """Run the RAG agent with a custom text-search context provider."""

    credential = AzureCliCredential()
    agent = AzureOpenAIChatClient(credential=credential).as_agent(
        name="SupportSpecialist",
        instructions=(
            "You are a helpful support specialist for Contoso Outdoors. "
            "Answer questions using the provided context and cite the source "
            "document when available. If the context does not contain the "
            "answer, say so clearly."
        ),
        context_providers=[TextSearchContextProvider()],
    )

    print("=" * 60)
    print("  RAG Agent with Custom Text Search Provider")
    print("=" * 60)

    queries = [
        "What is the return policy?",
        "How long does standard shipping take?",
        "How should I care for the TrailRunner tent fabric?",
        "Tell me about the Alpine Explorer backpack.",
    ]

    for user_input in queries:
        print(f"\nUser: {user_input}")
        result = await agent.run(user_input)
        print(f"Agent: {result}")


if __name__ == "__main__":
    asyncio.run(main())
