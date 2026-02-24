# Copyright (c) Microsoft. All rights reserved.

"""Multi-RAG agent with handoff orchestration, domain-specific tools,
and **structured agent identity**.

Architecture:
    User → Triage Agent → Specialist Agent (agents | tools | workflows | general)
                         ├─ domain-specific RAG context (ChromaDB collection)
                         ├─ domain-specific tools (tailored per specialist)
                         └─ agent identity (persona + scope + guardrails + style + tool policy)

Key difference from ``06_multi_RAG_agents_handsoff_domain_tools``:
    In Part 6, each agent's identity was scattered across three places:
        - ``AGENT_DESCRIPTIONS`` (one-liner for HandoffBuilder routing)
        - ``_TOOL_INSTRUCTIONS`` (mandatory tool rules per domain)
        - An inline instruction string in ``build_agents()``

    In Part 7, all of these are consolidated into a single ``AgentIdentity``
    dataclass per agent.  The ``build_instructions()`` function assembles
    a structured system prompt with clearly delimited sections:
        # Identity, ## Expertise, ## Scope, ## Behavioral Rules,
        ## Response Style, ## Available Tools, ## Tool Policy

    This makes each agent's responsibility explicit, auditable, and easy
    to modify without touching the orchestration code.

Usage (from repo root):
    python 07_multi_RAG_agents_handsoff_agent_identity/main.py
    python 07_multi_RAG_agents_handsoff_agent_identity/main.py --reingest
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import cast

# Ensure sibling modules are importable when run from the repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Build agents — now driven by AgentIdentity
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


def build_agents(client, providers: dict, domain_tools: dict[str, list]):
    """Create the triage agent and domain-specialist agents.

    Unlike Part 6, agent instructions are built from ``AgentIdentity``
    dataclass instances via ``build_instructions()``.  No inline strings,
    no ``AGENT_DESCRIPTIONS`` dict, no ``_TOOL_INSTRUCTIONS`` dict.

    Args:
        client: The Azure OpenAI chat client.
        providers: Domain-specific ChromaDB context providers.
        domain_tools: Mapping of domain name → list of tools for that domain.

    Returns:
        (triage, specialists_dict)  where specialists_dict maps domain name
        to agent instance.
    """
    from agent_identity import AGENT_IDENTITIES, TRIAGE_IDENTITY, build_instructions

    # Triage agent — identity-driven, no context provider, no tools
    triage = client.as_agent(
        name=TRIAGE_IDENTITY.name,
        instructions=build_instructions(TRIAGE_IDENTITY),
        description=TRIAGE_IDENTITY.role,
    )

    # Specialist agents — each with identity + context provider + domain tools
    specialists = {}
    for domain_name, provider in providers.items():
        identity = AGENT_IDENTITIES[domain_name]
        tools_for_domain = domain_tools.get(domain_name, [])
        tool_names = (
            ", ".join(t.name for t in tools_for_domain)
            if tools_for_domain
            else "(none)"
        )

        agent = client.as_agent(
            name=identity.name,
            instructions=build_instructions(identity, tool_names=tool_names),
            description=identity.role,
            context_providers=[provider],
            tools=tools_for_domain if tools_for_domain else None,
        )
        specialists[domain_name] = agent

    return triage, specialists


# ---------------------------------------------------------------------------
# Interactive loop with HandoffBuilder
# ---------------------------------------------------------------------------
async def run(reingest: bool = False) -> None:
    """Run the multi-RAG handoff workflow with agent identity."""
    from agent_framework import (
        AgentResponse,
        AgentResponseUpdate,
        Message,
        WorkflowEvent,
        WorkflowRunState,
    )
    from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

    from agent_identity import AGENT_IDENTITIES, TRIAGE_IDENTITY
    from agent_tools import DOMAIN_TOOLS
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

    # Show domain → tools mapping
    print("\n🔧 Domain-specific tools:")
    for domain_name, tools in DOMAIN_TOOLS.items():
        tool_names = ", ".join(t.name for t in tools) if tools else "(none)"
        print(f"  {domain_name}: {tool_names}")

    # Show agent identities
    print("\n🪪 Agent identities:")
    print(f"  {TRIAGE_IDENTITY.name}: {TRIAGE_IDENTITY.role}")
    for domain_name, identity in AGENT_IDENTITIES.items():
        scope_preview = identity.in_scope[:60] + "..." if len(identity.in_scope) > 60 else identity.in_scope
        print(f"  {identity.name}: {scope_preview}")

    # Create client and agents
    client = _get_client()
    triage, specialists = build_agents(client, providers, DOMAIN_TOOLS)
    all_agents = [triage] + list(specialists.values())

    def _build_workflow():
        """Build a fresh handoff workflow for each question."""
        return (
            HandoffBuilder(
                name="multi_rag_handoff_agent_identity",
                participants=all_agents,
            )
            .with_start_agent(triage)
            .build()
        )

    print("\n" + "=" * 60)
    print("  Microsoft Agent Framework – Multi-RAG Handoff + Agent Identity")
    print("  Specialists: " + ", ".join(specialists.keys()))
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

        # Build a fresh workflow per question (single-turn Q&A)
        workflow = _build_workflow()

        print("Agent: ", end="", flush=True)
        handoff_trace: list[str] = []
        tools_used: list[str] = []

        def _is_real_tool(name: str) -> bool:
            """Filter out handoff pseudo-calls (e.g. handoff_to_tools_specialist)."""
            return not name.startswith("handoff_to_")

        # Drain all events from the streaming workflow
        got_streaming_text = False
        events: list[WorkflowEvent] = []
        async for event in workflow.run(user_input, stream=True):
            events.append(event)

            # Handoff routing trace
            if event.type == "handoff_sent":
                source = event.data.source
                target = event.data.target
                handoff_trace.append(f"{source} → {target}")

            # Streaming updates (AgentResponseUpdate) — text AND tool calls
            elif event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                if event.data.text:
                    print(event.data.text, end="", flush=True)
                    got_streaming_text = True

                # Tool calls arrive as content items in the streaming update
                # Note: handoff_to_* are framework routing pseudo-calls, not real tools.
                for content in event.data.contents:
                    if content.type == "function_call" and hasattr(content, "name") and content.name:
                        if _is_real_tool(content.name) and content.name not in tools_used:
                            tools_used.append(content.name)

            # Non-streaming agent response — text and tool calls in messages
            elif event.type == "output" and isinstance(event.data, AgentResponse):
                for msg in event.data.messages:
                    if msg.text:
                        print(msg.text, end="", flush=True)
                        got_streaming_text = True
                    for content in msg.contents:
                        if content.type == "function_call" and hasattr(content, "name") and content.name:
                            if _is_real_tool(content.name) and content.name not in tools_used:
                                tools_used.append(content.name)

        # Fallback: if no streaming text was printed, check request_info events.
        if not got_streaming_text:
            for event in events:
                if event.type == "request_info" and isinstance(
                    event.data, HandoffAgentUserRequest
                ):
                    resp = event.data.agent_response
                    if resp:
                        for msg in resp.messages:
                            if msg.text:
                                print(msg.text, end="", flush=True)
                            for content in msg.contents:
                                if content.type == "function_call" and hasattr(content, "name") and content.name:
                                    if _is_real_tool(content.name) and content.name not in tools_used:
                                        tools_used.append(content.name)

        # Print routing and tool info
        if handoff_trace:
            print(f"\n  🔀 Routing: {' → '.join(handoff_trace)}")
        if tools_used:
            print(f"  🔧 Tools used: {', '.join(tools_used)}")
        else:
            print("  ℹ️  No function tools called (answered from RAG context)")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-RAG agent with handoff orchestration and agent identity.",
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
