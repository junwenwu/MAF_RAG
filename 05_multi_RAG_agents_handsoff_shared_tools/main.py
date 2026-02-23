# Copyright (c) Microsoft. All rights reserved.

"""Multi-RAG agent with handoff orchestration and **shared** function tools.

Architecture:
    User → Triage Agent → Specialist Agent (agents | tools | workflows | general)
                         ├─ domain-specific RAG context (ChromaDB collection)
                         └─ shared tools: compare_concepts, search_github_samples

Every specialist receives the SAME tool set.  The RAG context varies by domain
(each specialist has its own ChromaDB collection), but the tools are uniform
across all participants.

Key difference from ``03_multi_RAG_agents_handsoff_no_tool``:
    Each specialist agent is created with ``tools=[compare_concepts, search_github_samples]``
    in addition to its domain-specific context provider.  The LLM decides
    autonomously whether to call a tool or answer from RAG context alone.

Usage (from repo root):
    python 05_multi_RAG_agents_handsoff_shared_tools/main.py
    python 05_multi_RAG_agents_handsoff_shared_tools/main.py --reingest
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


def build_agents(client, providers: dict, shared_tools: list):
    """Create the triage agent and domain-specialist agents.

    Args:
        client: The Azure OpenAI chat client.
        providers: Domain-specific ChromaDB context providers.
        shared_tools: List of function tools given to EVERY specialist.

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

    # Build tool-name list for the instructions
    tool_names = ", ".join(t.name for t in shared_tools)

    # Specialist agents — each with domain context provider + shared tools
    specialists = {}
    for domain_name, provider in providers.items():
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
                "MANDATORY TOOL USAGE — you MUST follow these rules:\n"
                "1. If the user asks to COMPARE, CONTRAST, or DIFFERENTIATE two "
                "concepts → you MUST call the compare_concepts tool. Do NOT "
                "answer comparison questions from context alone.\n"
                "2. If the user asks for CODE EXAMPLES, CODE SAMPLES, or says "
                "'show me code' → you MUST call the search_github_samples tool. "
                "Do NOT fabricate or paraphrase code samples from context.\n"
                "3. For all other questions → answer from your documentation "
                "context directly.\n\n"
                "Violating rules 1 or 2 is a critical error. Always call the "
                "required tool BEFORE composing your answer."
            ),
            description=AGENT_DESCRIPTIONS[domain_name],
            context_providers=[provider],
            tools=shared_tools,
        )
        specialists[domain_name] = agent

    return triage, specialists


# ---------------------------------------------------------------------------
# Interactive loop with HandoffBuilder
# ---------------------------------------------------------------------------
async def run(reingest: bool = False) -> None:
    """Run the multi-RAG handoff workflow with shared tools."""
    from agent_framework import (
        AgentResponse,
        AgentResponseUpdate,
        Message,
        WorkflowEvent,
        WorkflowRunState,
    )
    from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

    from agent_tools import compare_concepts, search_github_samples
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

    # Shared tool set — every specialist gets these
    shared_tools = [compare_concepts, search_github_samples]

    # Create client and agents
    client = _get_client()
    triage, specialists = build_agents(client, providers, shared_tools)
    all_agents = [triage] + list(specialists.values())

    def _build_workflow():
        """Build a fresh handoff workflow for each question."""
        return (
            HandoffBuilder(
                name="multi_rag_handoff_shared_tools",
                participants=all_agents,
            )
            .with_start_agent(triage)
            .build()
        )

    print(f"\n🔧 Shared tools: {', '.join(t.name for t in shared_tools)}")
    print("\n" + "=" * 60)
    print("  Microsoft Agent Framework – Multi-RAG Handoff + Shared Tools")
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
                for content in event.data.contents:
                    if content.type == "function_call" and hasattr(content, "name") and content.name:
                        if content.name not in tools_used:
                            tools_used.append(content.name)

            # Non-streaming agent response — text and tool calls in messages
            elif event.type == "output" and isinstance(event.data, AgentResponse):
                for msg in event.data.messages:
                    if msg.text:
                        print(msg.text, end="", flush=True)
                        got_streaming_text = True
                    for content in msg.contents:
                        if content.type == "function_call" and hasattr(content, "name") and content.name:
                            if content.name not in tools_used:
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
                                    if content.name not in tools_used:
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
        description="Multi-RAG agent with handoff orchestration and shared function tools.",
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
