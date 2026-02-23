# Copyright (c) Microsoft. All rights reserved.

"""Interactive RAG chat with function tools.

This demo extends the single-tool RAG agent with additional function tools
that the LLM can call directly:

* **compare_concepts** – Retrieve and compare two Agent Framework concepts.
* **search_github_samples** – Search the official repo for code samples.

The agent automatically decides which tool to use based on the user's question.

Usage (from repo root):
    python 02_single_RAG_agent_with_tool/main.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure sibling modules are importable when run from the repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Web docs mode with function tools
# ---------------------------------------------------------------------------
async def run() -> None:
    """Interactive chat with ChromaDB RAG + function tools.

    The agent automatically decides when to call tools based on the question.
    """
    from agent_framework.azure import AzureOpenAIChatClient

    from agent_tools import compare_concepts, search_github_samples
    from rag_web_agent import ChromaWebContextProvider

    provider = ChromaWebContextProvider()
    tools = [compare_concepts, search_github_samples]

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
            "If the context does not contain the answer, say so clearly.\n\n"
            "You have access to tools:\n"
            "- compare_concepts: Use when the user asks to compare or contrast two concepts.\n"
            "- search_github_samples: Use when the user asks for code examples from the official repo.\n\n"
            "Choose the right tool automatically based on the user's question. "
            "For general questions, just use the documentation context directly."
        ),
        context_providers=[provider],
        tools=tools,
    )

    print(f"\nLoaded {provider._collection.count()} chunks from web docs into ChromaDB.")
    print(f"Tools available: {', '.join(t.name for t in tools)}")
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
        stream = agent.run(user_input, stream=True)
        async for chunk in stream:
            if chunk.text:
                print(chunk.text, end="", flush=True)

        # After streaming completes, inspect the final response for tool usage
        response = await stream.get_final_response()
        tools_used: list[str] = []
        for msg in response.messages:
            for content in msg.contents:
                if content.type == "function_call" and hasattr(content, "name") and content.name:
                    if content.name not in tools_used:
                        tools_used.append(content.name)
                elif content.type == "function_result":
                    # function_result has call_id but not always name;
                    # the matching function_call already captured the name.
                    pass

        if tools_used:
            print(f"\n  🔧 Tools used: {', '.join(tools_used)}")
        else:
            print("\n  ℹ️  No function tools called (answered from RAG context)")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main() -> None:
    """Entry point."""
    print("=" * 60)
    print("  Microsoft Agent Framework – RAG Chat + Tools")
    print("=" * 60)
    await run()


if __name__ == "__main__":
    asyncio.run(main())
