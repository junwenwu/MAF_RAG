# Copyright (c) Microsoft. All rights reserved.

"""Multi-RAG agent with concurrent orchestration — no function tools.

Architecture:
    User Question
         │
    ┌────┴────┐   fan-out (parallel)
    ▼    ▼    ▼    ▼
  agents tools workflows general   ← 4 domain specialists
    │    │    │    │
    └────┬────┘   fan-in
         ▼
    Aggregator  → synthesised answer

All four domain specialists answer every question in parallel.  A custom
aggregator then uses the LLM to synthesise one consolidated answer from the
relevant responses.

Usage (from repo root):
    python multi_RAG_agents_concurrent_no_tool/main.py
    python multi_RAG_agents_concurrent_no_tool/main.py --reingest
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

# Ensure sibling modules are importable when run from the repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Agent descriptions
# ---------------------------------------------------------------------------
AGENT_DESCRIPTIONS = {
    "agents": (
        "Specialist for core agent concepts: creating agents, running agents, "
        "multimodal, structured output, RAG, declarative agents, observability, "
        "and LLM provider configuration."
    ),
    "tools": (
        "Specialist for agent tooling: function tools, the @tool decorator, "
        "tool approval, code interpreter, file search, web search, and MCP tools."
    ),
    "workflows": (
        "Specialist for multi-agent workflows and orchestrations: executors, edges, "
        "events, human-in-the-loop, checkpoints, state management, and orchestration "
        "patterns (sequential, concurrent, handoff, group chat, magentic)."
    ),
    "general": (
        "Specialist for general Agent Framework topics: overview, getting started, "
        "conversations and memory, sessions, context providers, middleware, "
        "integrations, migration guides, DevUI, FAQ, and troubleshooting."
    ),
}


# ---------------------------------------------------------------------------
# Build agents
# ---------------------------------------------------------------------------
def _get_client():
    """Create the Azure OpenAI chat client."""
    from agent_framework.azure import AzureOpenAIChatClient

    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if api_key:
        return AzureOpenAIChatClient(api_key=api_key)
    else:
        from azure.identity import AzureCliCredential

        return AzureOpenAIChatClient(credential=AzureCliCredential())


def build_specialists(client, providers: dict) -> dict:
    """Create one specialist agent per domain, each with its own RAG provider.

    Returns:
        {domain_name: agent}
    """
    specialists = {}
    for domain_name, provider in providers.items():
        agent = client.as_agent(
            name=f"{domain_name}_specialist",
            instructions=(
                f"You are a specialist for {domain_name}-related topics in the "
                "Microsoft Agent Framework.  Answer questions using the provided "
                "documentation context from your knowledge base.  "
                "Always cite the source URL when available.  "
                "If the context does not contain the answer, respond with exactly: "
                "'NO_RELEVANT_CONTEXT' — nothing else."
            ),
            description=AGENT_DESCRIPTIONS[domain_name],
            context_providers=[provider],
        )
        specialists[domain_name] = agent
    return specialists


# ---------------------------------------------------------------------------
# Custom aggregator callback
# ---------------------------------------------------------------------------
def _make_aggregator(client):
    """Return an async aggregator callback that uses the LLM to synthesise
    the parallel specialist responses into a single consolidated answer."""

    async def aggregate(results: list) -> str:
        """Receive list[AgentExecutorResponse] and return a summary string."""
        from agent_framework import Message

        sections: list[str] = []
        for r in results:
            agent_name = r.agent_response.messages[-1].author_name or "unknown"
            text = r.agent_response.messages[-1].text or ""
            # Skip specialists that had no relevant context
            if "NO_RELEVANT_CONTEXT" in text:
                continue
            sections.append(f"### {agent_name}\n{text}")

        if not sections:
            return "I could not find relevant information across any domain."

        # If only one specialist answered, return directly (no extra LLM call)
        if len(sections) == 1:
            return sections[0].split("\n", 1)[1]  # strip the header

        # Multiple specialists contributed → synthesise with LLM
        combined = "\n\n".join(sections)
        prompt_text = (
            "Below are answers from multiple domain specialists about the "
            "Microsoft Agent Framework.  Synthesise them into a single, clear, "
            "well-structured answer.  Keep all source URLs.  Omit duplicate info.\n\n"
            f"{combined}"
        )
        resp = await client.get_response([Message(role="user", text=prompt_text)])
        return resp.messages[-1].text or combined

    return aggregate


# ---------------------------------------------------------------------------
# Interactive loop with ConcurrentBuilder
# ---------------------------------------------------------------------------
async def run(reingest: bool = False) -> None:
    """Run the multi-RAG concurrent workflow."""
    from agent_framework import (
        AgentResponse,
        AgentResponseUpdate,
        Message,
    )
    from agent_framework.orchestrations import ConcurrentBuilder

    from domain_providers import build_domain_providers, reingest_all

    # Build (or rebuild) domain providers
    if reingest:
        print("🔄 Re-ingesting all domain collections...")
        reingest_all()

    providers = build_domain_providers()

    # Show collection stats
    print("\n📊 Domain collections:")
    for domain_name, prov in providers.items():
        print(f"  {domain_name}: {prov._collection.count()} chunks")

    # Create client and agents
    client = _get_client()
    specialists = build_specialists(client, providers)
    participant_list = list(specialists.values())

    # Custom aggregator that synthesises the parallel answers via LLM
    aggregator = _make_aggregator(client)

    def _build_workflow():
        """Build a fresh concurrent workflow for each question."""
        return (
            ConcurrentBuilder(
                participants=participant_list,
                intermediate_outputs=True,
            )
            .with_aggregator(aggregator)
            .build()
        )

    print("\n" + "=" * 60)
    print("  Microsoft Agent Framework – Multi-RAG Concurrent")
    print("  Specialists (parallel): " + ", ".join(specialists.keys()))
    print("=" * 60)
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

        workflow = _build_workflow()

        print("Agent: ", end="", flush=True)

        # Collect outputs — the custom aggregator yields a single string
        answer = ""
        responded_specialists: list[str] = []

        async for event in workflow.run(user_input, stream=True):
            # Intermediate outputs — streaming text from individual specialists
            if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                pass  # suppress per-specialist streaming; we show the aggregated answer

            # Intermediate outputs — full response from individual specialists
            elif event.type == "output" and isinstance(event.data, AgentResponse):
                for msg in event.data.messages:
                    if msg.author_name:
                        responded_specialists.append(msg.author_name)

            # Final aggregated output (string from our custom callback)
            elif event.type == "output" and isinstance(event.data, str):
                answer = event.data

            # Default output: list[Message] when no custom aggregator
            elif event.type == "output" and isinstance(event.data, list):
                for item in event.data:
                    if isinstance(item, Message) and item.text:
                        answer += item.text + "\n"

        print(answer)

        # Show which specialists contributed
        if responded_specialists:
            names = sorted(set(responded_specialists))
            print(f"  ⚡ Parallel: {', '.join(names)}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-RAG agent with concurrent orchestration.",
    )
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="Delete all domain collections and re-scrape from the web.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    await run(reingest=args.reingest)


if __name__ == "__main__":
    asyncio.run(main())
