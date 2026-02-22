# Copyright (c) Microsoft. All rights reserved.

"""RAG agent using Azure AI Search context provider with the Microsoft Agent Framework.

This module creates an agent backed by Azure AI Search for Retrieval-Augmented
Generation (RAG).  It uses the ``AzureAISearchContextProvider`` in **semantic
mode** (hybrid vector + keyword search with semantic ranking) to retrieve
relevant documents before every model invocation.

Usage:
    python rag_search_agent.py
"""

import asyncio
import os

from agent_framework import Agent
from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider
from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------------------------------------------------------------------------
# Sample queries – replace with your own
# ---------------------------------------------------------------------------
SAMPLE_QUERIES = [
    "What information is available in the knowledge base?",
    "Summarize the main topics from the documents.",
    "Find specific details about the content.",
]


async def main() -> None:
    """Run the RAG agent with Azure AI Search in semantic mode."""

    # --- Configuration from environment ---
    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    search_key = os.environ.get("AZURE_SEARCH_API_KEY")
    index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    model_deployment = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")

    # --- Azure AI Search context provider (semantic mode – fast, recommended default) ---
    search_provider = AzureAISearchContextProvider(
        source_id="search_provider",
        endpoint=search_endpoint,
        index_name=index_name,
        api_key=search_key,
        credential=AzureCliCredential() if not search_key else None,
        mode="semantic",
        top_k=3,
    )

    # --- Create the agent ---
    async with (
        search_provider,
        AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment,
            credential=AzureCliCredential(),
        ) as client,
        Agent(
            client=client,
            name="RAGSearchAgent",
            instructions=(
                "You are a knowledgeable assistant with access to a document knowledge base. "
                "Use the provided context from Azure AI Search to answer questions accurately. "
                "Always cite the source document when available. "
                "If the context does not contain the answer, say so clearly."
            ),
            context_providers=[search_provider],
        ) as agent,
    ):
        print("=" * 60)
        print("  RAG Agent with Azure AI Search (Semantic Mode)")
        print("=" * 60)

        for user_input in SAMPLE_QUERIES:
            print(f"\nUser: {user_input}")
            print("Agent: ", end="", flush=True)

            async for chunk in agent.run(user_input, stream=True):
                if chunk.text:
                    print(chunk.text, end="", flush=True)

            print("\n")


if __name__ == "__main__":
    asyncio.run(main())
