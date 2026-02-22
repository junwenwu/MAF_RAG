# Copyright (c) Microsoft. All rights reserved.

"""Interactive RAG chat – the main entry point for the MAF RAG application.

Run this script to start an interactive loop where you can ask questions
and the agent answers by retrieving context from web documentation via ChromaDB.

Usage (from repo root):
    python single_RAG_agent_single_tool/main.py
    python single_RAG_agent_single_tool/main.py --mode custom
    python single_RAG_agent_single_tool/main.py --mode search
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Ensure sibling modules are importable when run from the repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Web docs mode (ChromaDB – default, no Azure AI Search needed)
# ---------------------------------------------------------------------------
async def run_web_mode() -> None:
    """Interactive chat with web-scraped docs in ChromaDB."""
    from agent_framework.azure import AzureOpenAIChatClient

    from rag_web_agent import ChromaWebContextProvider

    provider = ChromaWebContextProvider()

    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if api_key:
        client = AzureOpenAIChatClient(api_key=api_key)
    else:
        from azure.identity import AzureCliCredential
        client = AzureOpenAIChatClient(credential=AzureCliCredential())

    agent = client.as_agent(
        name="WebRAGAgent",
        instructions=(
            "You are a knowledgeable assistant for the Microsoft Agent Framework. "
            "Answer questions using the provided documentation context. "
            "Always cite the source URL when available. "
            "If the context does not contain the answer, say so clearly."
        ),
        context_providers=[provider],
    )

    print(f"\nLoaded {provider._collection.count()} chunks from web docs into ChromaDB.")
    await _interactive_loop(agent)


# ---------------------------------------------------------------------------
# Azure AI Search mode
# ---------------------------------------------------------------------------
async def run_search_mode() -> None:
    """Interactive chat with the Azure AI Search RAG agent."""
    from agent_framework import Agent
    from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider
    from azure.identity.aio import AzureCliCredential

    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    search_key = os.environ.get("AZURE_SEARCH_API_KEY")
    index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    model_deployment = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")

    search_provider = AzureAISearchContextProvider(
        source_id="search_provider",
        endpoint=search_endpoint,
        index_name=index_name,
        api_key=search_key,
        credential=AzureCliCredential() if not search_key else None,
        mode="semantic",
        top_k=3,
    )

    async with (
        search_provider,
        AzureAIAgentClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment,
            credential=AzureCliCredential(),
        ) as client,
        Agent(
            client=client,
            name="RAGAgent",
            instructions=(
                "You are a knowledgeable assistant with access to a document knowledge base. "
                "Use the provided context from Azure AI Search to answer questions accurately. "
                "Always cite the source document when available. "
                "If the context does not contain the answer, say so clearly."
            ),
            context_providers=[search_provider],
        ) as agent,
    ):
        print("\nConnected to Azure AI Search index:", index_name)
        _interactive_loop(agent)


# ---------------------------------------------------------------------------
# Custom local provider mode
# ---------------------------------------------------------------------------
async def run_custom_mode() -> None:
    """Interactive chat with the custom local RAG provider."""
    from agent_framework.azure import AzureOpenAIChatClient
    from azure.identity import AzureCliCredential

    from rag_custom_provider import TextSearchContextProvider

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

    print("\nUsing custom local text-search provider with built-in Contoso Outdoors knowledge base.")
    await _interactive_loop(agent)


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------
async def _interactive_loop(agent) -> None:
    """Run an interactive Q&A loop with the given agent."""
    print("Type your question and press Enter.  Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        print("Agent: ", end="", flush=True)
        async for chunk in agent.run(user_input, stream=True):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Interactive RAG chat powered by the Microsoft Agent Framework.",
    )
    parser.add_argument(
        "--mode",
        choices=["web", "custom", "search"],
        default="web",
        help="RAG backend: 'web' = web docs via ChromaDB (default), 'custom' = local Contoso data, 'search' = Azure AI Search.",
    )
    return parser.parse_args()


async def main() -> None:
    """Entry point."""
    args = parse_args()

    print("=" * 60)
    print("  Microsoft Agent Framework – RAG Chat")
    print("=" * 60)

    if args.mode == "custom":
        await run_custom_mode()
    elif args.mode == "search":
        await run_search_mode()
    else:
        await run_web_mode()


if __name__ == "__main__":
    asyncio.run(main())
