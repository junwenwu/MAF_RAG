# Copyright (c) Microsoft. All rights reserved.

"""Multi-RAG agent with handoff orchestration and **domain-specific** function tools.

Architecture:
    User → Triage Agent → Specialist Agent (agents | tools | workflows | general)
                         ├─ domain-specific RAG context (ChromaDB collection)
                         └─ domain-specific tools (tailored per specialist)

Unlike Part 5 where every specialist received the SAME tool set, each
specialist here gets tools **tailored to its domain**:

    agents     → list_supported_providers   (queries agents collection)
    tools      → search_github_samples      (searches GitHub repo)
    workflows  → compare_orchestrations     (queries workflows collection)
    general    → compare_concepts           (queries all 4 collections)

Key difference from ``05_multi_RAG_agents_handsoff_shared_tools``:
    ``build_agents()`` reads from ``DOMAIN_TOOLS`` registry to give each
    specialist a **different** tool set.  The specialist instructions are
    dynamically generated based on the tools assigned to that domain.

Usage (from repo root):
    python 06_multi_RAG_agents_handsoff_domain_tools/main.py
    python 06_multi_RAG_agents_handsoff_domain_tools/main.py --reingest
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
# Agent descriptions — used by HandoffBuilder for routing
# ---------------------------------------------------------------------------
AGENT_DESCRIPTIONS = {
    "agents": (
        "Specialist for core agent concepts: creating agents, running agents, "
        "multimodal, structured output, RAG, declarative agents, observability, "
        "and LLM provider configuration (Azure OpenAI, OpenAI, Anthropic, Ollama, etc.)."
    ),
    "tools": (
        "Specialist for agent tooling: function tools, the @tool decorator, "
        "tool approval, code interpreter, file search, web search, and MCP tools "
        "(hosted and local)."
    ),
    "workflows": (
        "Specialist for multi-agent workflows and orchestrations: executors, edges, "
        "events, human-in-the-loop, checkpoints, state management, and orchestration "
        "patterns (sequential, concurrent, handoff, group chat, magentic)."
    ),
    "general": (
        "Specialist for general Agent Framework topics: overview, getting started, "
        "conversations and memory, sessions, context providers, middleware, "
        "integrations (Azure Functions, OpenAI endpoints, AG-UI, A2A), "
        "migration guides, DevUI, FAQ, and troubleshooting."
    ),
}


# ---------------------------------------------------------------------------
# Domain-specific tool-usage instructions
# ---------------------------------------------------------------------------

_TOOL_INSTRUCTIONS: dict[str, str] = {
    "agents": (
        "MANDATORY TOOL USAGE — you MUST follow these rules:\n"
        "1. If the user asks about SUPPORTED PROVIDERS, which LLMS or MODELS "
        "are available, or how to CONFIGURE a provider → you MUST call the "
        "list_supported_providers tool.\n"
        "2. For all other questions → answer from your documentation context "
        "directly.\n\n"
        "Violating rule 1 is a critical error. Always call the required tool "
        "BEFORE composing your answer."
    ),
    "tools": (
        "MANDATORY TOOL USAGE — you MUST follow these rules:\n"
        "1. If the user asks for CODE EXAMPLES, CODE SAMPLES, or says "
        "'show me code' → you MUST call the search_github_samples tool. "
        "Do NOT fabricate or paraphrase code samples from context.\n"
        "2. For all other questions → answer from your documentation context "
        "directly.\n\n"
        "Violating rule 1 is a critical error. Always call the required tool "
        "BEFORE composing your answer."
    ),
    "workflows": (
        "MANDATORY TOOL USAGE — you MUST follow these rules:\n"
        "1. If the user asks to COMPARE, CONTRAST, or DIFFERENTIATE two "
        "orchestration patterns or workflow concepts → you MUST call the "
        "compare_orchestrations tool. Do NOT answer comparison questions "
        "from context alone.\n"
        "2. For all other questions → answer from your documentation context "
        "directly.\n\n"
        "Violating rule 1 is a critical error. Always call the required tool "
        "BEFORE composing your answer."
    ),
    "general": (
        "MANDATORY TOOL USAGE — you MUST follow these rules:\n"
        "1. If the user asks to COMPARE, CONTRAST, or DIFFERENTIATE two "
        "concepts → you MUST call the compare_concepts tool. Do NOT "
        "answer comparison questions from context alone.\n"
        "2. For all other questions → answer from your documentation context "
        "directly.\n\n"
        "Violating rule 1 is a critical error. Always call the required tool "
        "BEFORE composing your answer."
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


def build_agents(client, providers: dict, domain_tools: dict[str, list]):
    """Create the triage agent and domain-specialist agents.

    Args:
        client: The Azure OpenAI chat client.
        providers: Domain-specific ChromaDB context providers.
        domain_tools: Mapping of domain name → list of tools for that domain.

    Returns:
        (triage, specialists_dict)  where specialists_dict maps domain name
        to agent instance.
    """
    # Triage agent — no context provider, no tools, just routes
    triage = client.as_agent(
        name="triage_agent",
        instructions=(
            "You are a triage agent for the Microsoft Agent Framework documentation. "
            "Your ONLY job is to determine which specialist agent should handle the "
            "user's question and hand off to them immediately.\n\n"
            "Available specialists:\n"
            "- agents_specialist: Questions about creating/running agents, providers, "
            "multimodal, structured output, RAG, declarative agents, observability.\n"
            "- tools_specialist: Questions about function tools, @tool decorator, "
            "code interpreter, file search, web search, MCP tools.\n"
            "- workflows_specialist: Questions about workflows, orchestrations, "
            "executors, edges, events, handoffs, group chat, state management.\n"
            "- general_specialist: Questions about overview, getting started, "
            "conversations, memory, middleware, integrations, migration, DevUI, FAQ.\n\n"
            "Analyze the question and immediately hand off to the most relevant "
            "specialist. Do NOT try to answer the question yourself."
        ),
        description="Routes user questions to the appropriate domain specialist.",
    )

    # Specialist agents — each with domain context provider + domain-specific tools
    specialists = {}
    for domain_name, provider in providers.items():
        tools_for_domain = domain_tools.get(domain_name, [])
        tool_names = ", ".join(t.name for t in tools_for_domain) if tools_for_domain else "(none)"
        tool_instructions = _TOOL_INSTRUCTIONS.get(domain_name, "")

        agent = client.as_agent(
            name=f"{domain_name}_specialist",
            instructions=(
                f"You are a specialist for {domain_name}-related topics in the "
                "Microsoft Agent Framework. Answer questions using the provided "
                "documentation context from your knowledge base. "
                "Always cite the source URL when available. "
                "If the context does not contain the answer, say so clearly. "
                "After providing your answer, do NOT hand off to another agent.\n\n"
                f"You have access to tools: {tool_names}.\n\n"
                f"{tool_instructions}"
            ),
            description=AGENT_DESCRIPTIONS[domain_name],
            context_providers=[provider],
            tools=tools_for_domain if tools_for_domain else None,
        )
        specialists[domain_name] = agent

    return triage, specialists


# ---------------------------------------------------------------------------
# Interactive loop with HandoffBuilder
# ---------------------------------------------------------------------------
async def run(reingest: bool = False) -> None:
    """Run the multi-RAG handoff workflow with domain-specific tools."""
    from agent_framework import (
        AgentResponse,
        AgentResponseUpdate,
        Message,
        WorkflowEvent,
        WorkflowRunState,
    )
    from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

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

    # Create client and agents
    client = _get_client()
    triage, specialists = build_agents(client, providers, DOMAIN_TOOLS)
    all_agents = [triage] + list(specialists.values())

    def _build_workflow():
        """Build a fresh handoff workflow for each question."""
        return (
            HandoffBuilder(
                name="multi_rag_handoff_domain_tools",
                participants=all_agents,
            )
            .with_start_agent(triage)
            .build()
        )

    print("\n" + "=" * 60)
    print("  Microsoft Agent Framework – Multi-RAG Handoff + Domain Tools")
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
        description="Multi-RAG agent with handoff orchestration and domain-specific function tools.",
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
