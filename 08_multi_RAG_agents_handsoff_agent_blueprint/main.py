# Copyright (c) Microsoft. All rights reserved.

"""Multi-RAG agent with handoff orchestration driven by a **declarative
YAML blueprint**.

Architecture:
    blueprint.yaml  →  blueprint_loader.py  →  AgentIdentity objects
                                              ↓
    User → Triage Agent → Specialist Agent (agents | tools | workflows | general)
                         ├─ domain-specific RAG context (ChromaDB collection)
                         ├─ domain-specific tools (resolved by name from registry)
                         └─ agent identity (loaded from YAML, not Python code)

Key difference from ``07_multi_RAG_agents_handsoff_agent_identity``:
    In Part 7, agent identities are defined as Python dataclass instances
    in ``agent_identity.py`` (~300 lines of code).  Adding or modifying an
    agent means editing Python.

    In Part 8, the same information lives in ``blueprint.yaml``.  The Python
    code reads the YAML, builds ``AgentIdentity`` objects, and generates
    system prompts — no Python changes needed to modify agent behavior.

Usage (from repo root):
    python 08_multi_RAG_agents_handsoff_agent_blueprint/main.py
    python 08_multi_RAG_agents_handsoff_agent_blueprint/main.py --reingest
    python 08_multi_RAG_agents_handsoff_agent_blueprint/main.py --blueprint custom.yaml
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
# Build agents — now driven by the blueprint
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


def _resolve_tools(tool_names: list[str], tool_registry: dict[str, list]) -> list:
    """Resolve tool function names from the blueprint to actual tool objects.

    The blueprint YAML lists tools by name (e.g. ``list_supported_providers``).
    This function looks them up in the ``DOMAIN_TOOLS`` registry from
    ``agent_tools.py`` and returns the matching callable objects.
    """
    # Build a flat name → tool-object mapping from the registry
    name_to_tool: dict = {}
    for tools in tool_registry.values():
        for t in tools:
            name_to_tool[t.name] = t

    resolved = []
    for name in tool_names:
        if name in name_to_tool:
            resolved.append(name_to_tool[name])
        else:
            print(f"  ⚠️  Tool '{name}' referenced in blueprint but not found in registry")
    return resolved


def build_agents(client, providers: dict, blueprint, tool_registry: dict[str, list]):
    """Create the triage agent and domain-specialist agents from a blueprint.

    Args:
        client: The Azure OpenAI chat client.
        providers: Domain-specific ChromaDB context providers.
        blueprint: A loaded ``Blueprint`` instance from ``blueprint_loader.py``.
        tool_registry: The ``DOMAIN_TOOLS`` dict from ``agent_tools.py``.

    Returns:
        (triage, specialists_dict)  where specialists_dict maps domain name
        to agent instance.
    """
    from blueprint_loader import build_instructions

    # Triage agent — identity from blueprint, no context provider, no tools
    triage = client.as_agent(
        name=blueprint.triage.name,
        instructions=build_instructions(
            blueprint.triage,
            security_prompt=blueprint.security_prompt,
        ),
        description=blueprint.triage.role,
    )

    # Specialist agents
    specialists = {}
    for domain_name, provider in providers.items():
        identity = blueprint.specialists.get(domain_name)
        if identity is None:
            print(f"  ⚠️  Domain '{domain_name}' has a provider but no blueprint entry — skipping")
            continue

        # Resolve tools by name from the blueprint
        tool_name_list = blueprint.tool_assignments.get(domain_name, [])
        tools_for_domain = _resolve_tools(tool_name_list, tool_registry)
        tool_names_str = (
            ", ".join(t.name for t in tools_for_domain)
            if tools_for_domain
            else "(none)"
        )

        agent = client.as_agent(
            name=identity.name,
            instructions=build_instructions(
                identity,
                security_prompt=blueprint.security_prompt,
                tool_names=tool_names_str,
            ),
            description=identity.role,
            context_providers=[provider],
            tools=tools_for_domain if tools_for_domain else None,
        )
        specialists[domain_name] = agent

    return triage, specialists


# ---------------------------------------------------------------------------
# Interactive loop with HandoffBuilder
# ---------------------------------------------------------------------------
async def run(reingest: bool = False, blueprint_path: str | None = None) -> None:
    """Run the multi-RAG handoff workflow driven by a YAML blueprint."""
    from agent_framework import (
        AgentResponse,
        AgentResponseUpdate,
        WorkflowEvent,
    )
    from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

    from agent_tools import DOMAIN_TOOLS
    from blueprint_loader import load_blueprint
    from domain_providers import build_domain_providers, reingest_all

    # Load blueprint
    blueprint = load_blueprint(blueprint_path)
    print(f"\n📘 Blueprint loaded: v{blueprint.version}")

    # Build (or rebuild) domain providers
    if reingest:
        print("🔄 Re-ingesting all domain collections...")
        reingest_all()

    providers = build_domain_providers()

    # Show collection stats
    print("\n📊 Domain collections:")
    for domain_name, prov in providers.items():
        print(f"  {domain_name}: {prov._collection.count()} chunks")

    # Show blueprint → tool resolution
    print("\n🔧 Blueprint tool assignments:")
    for domain_name, tool_names in blueprint.tool_assignments.items():
        names_str = ", ".join(tool_names) if tool_names else "(none)"
        print(f"  {domain_name}: {names_str}")

    # Show agent identities from blueprint
    print("\n🪪 Agent identities (from blueprint):")
    print(f"  {blueprint.triage.name}: {blueprint.triage.role}")
    for domain_name, identity in blueprint.specialists.items():
        scope_preview = (
            identity.in_scope[:60] + "..."
            if len(identity.in_scope) > 60
            else identity.in_scope
        )
        print(f"  {identity.name}: {scope_preview}")

    # Create client and agents
    client = _get_client()
    triage, specialists = build_agents(client, providers, blueprint, DOMAIN_TOOLS)
    all_agents = [triage] + list(specialists.values())

    def _build_workflow():
        """Build a fresh handoff workflow for each question."""
        return (
            HandoffBuilder(
                name="multi_rag_handoff_blueprint",
                participants=all_agents,
            )
            .with_start_agent(triage)
            .build()
        )

    print("\n" + "=" * 60)
    print("  Microsoft Agent Framework – Multi-RAG Handoff + Blueprint")
    print("  Specialists: " + ", ".join(specialists.keys()))
    print(f"  Blueprint: v{blueprint.version}")
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

            # Streaming updates
            elif event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                if event.data.text:
                    print(event.data.text, end="", flush=True)
                    got_streaming_text = True

                for content in event.data.contents:
                    if content.type == "function_call" and hasattr(content, "name") and content.name:
                        if _is_real_tool(content.name) and content.name not in tools_used:
                            tools_used.append(content.name)

            # Non-streaming agent response
            elif event.type == "output" and isinstance(event.data, AgentResponse):
                for msg in event.data.messages:
                    if msg.text:
                        print(msg.text, end="", flush=True)
                        got_streaming_text = True
                    for content in msg.contents:
                        if content.type == "function_call" and hasattr(content, "name") and content.name:
                            if _is_real_tool(content.name) and content.name not in tools_used:
                                tools_used.append(content.name)

        # Fallback: check request_info events
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
        description="Multi-RAG agent with handoff orchestration driven by a YAML blueprint.",
    )
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="Delete all domain collections and re-scrape from the web.",
    )
    parser.add_argument(
        "--blueprint",
        type=str,
        default=None,
        help="Path to a custom blueprint YAML file (default: blueprint.yaml in this directory).",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    await run(reingest=args.reingest, blueprint_path=args.blueprint)


if __name__ == "__main__":
    asyncio.run(main())
