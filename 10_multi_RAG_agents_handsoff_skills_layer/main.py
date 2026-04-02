# Copyright (c) Microsoft. All rights reserved.

"""Multi-RAG agent with handoff orchestration, **skills layer**, and Foundry tracing.

Architecture:
    skills/                         <- File-based skills (SKILL.md format)
    ├── summarize-content/SKILL.md
    ├── step-by-step/SKILL.md
    └── ...

    agent_skills.py                 <- Code-defined skills + SkillsProvider factory

    blueprint.yaml  →  blueprint_loader.py  →  AgentIdentity objects
                                              ↓
    User → Triage Agent → Specialist Agent (agents | tools | workflows | general)
                         ├─ domain-specific RAG context (ChromaDB collection)
                         ├─ domain-specific tools (resolved by name from registry)
                         ├─ SkillsProvider (discovers skills, provides load_skill tool)
                         ├─ agent identity (loaded from YAML)
                         └─ Observability identity (id=, name=, description=)

Key differences from ``09_multi_RAG_agents_handsoff_sdk_identity``:
    1. **SkillsProvider**: Uses the official SDK ``SkillsProvider`` class to
       discover and serve skills to agents via progressive disclosure.

    2. **File-based skills**: Skills are defined in SKILL.md files following
       the Agent Skills specification (https://agentskills.io/).

    3. **Progressive disclosure**: Skills advertise (name + description),
       then agents call ``load_skill`` to get full instructions, and
       ``read_skill_resource`` for supplementary files.

    4. **Code-defined skills**: Can define skills in Python with dynamic
       resources using ``@skill.resource`` decorator.

    5. **Skill tools**: SkillsProvider adds tools: ``load_skill``,
       ``read_skill_resource``, ``run_skill_script``.

Usage (from repo root):
    python 10_multi_RAG_agents_handsoff_skills_layer/main.py
    python 10_multi_RAG_agents_handsoff_skills_layer/main.py --reingest
    python 10_multi_RAG_agents_handsoff_skills_layer/main.py --blueprint custom.yaml
    python 10_multi_RAG_agents_handsoff_skills_layer/main.py --otel
    python 10_multi_RAG_agents_handsoff_skills_layer/main.py --otel --foundry
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
# Observability setup (same as Part 9)
# ---------------------------------------------------------------------------
def _setup_observability(*, foundry: bool = False) -> None:
    """Enable OpenTelemetry tracing, metrics, and logging.

    Two modes:
        - **Local** (default): Uses ``configure_otel_providers()`` with
          console exporters or an OTLP endpoint (e.g. Aspire Dashboard).
        - **Foundry** (``--foundry``): Uses ``configure_azure_monitor()``
          to send traces to Azure Application Insights.
    """
    if foundry:
        conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
        if not conn_str:
            print(
                "⚠️  --foundry requires APPLICATIONINSIGHTS_CONNECTION_STRING.\n"
                "   Get it from Foundry portal → Tracing → Manage data source.\n"
                "   Falling back to local OTel exporters."
            )
        else:
            from azure.monitor.opentelemetry import configure_azure_monitor
            from agent_framework.observability import enable_instrumentation

            configure_azure_monitor(connection_string=conn_str)
            enable_instrumentation()
            print("📡 Foundry observability enabled (Azure Monitor)")
            print("   Traces will appear in Foundry portal → Tracing")
            return

    # Local path: console or OTLP endpoint
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        os.environ.setdefault("ENABLE_CONSOLE_EXPORTERS", "true")
    os.environ.setdefault("ENABLE_INSTRUMENTATION", "true")

    from agent_framework.observability import configure_otel_providers

    extra_exporters = None
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        extra_exporters = [ConsoleSpanExporter()]

    configure_otel_providers(exporters=extra_exporters)
    print("📡 OpenTelemetry observability enabled (local)")


# ---------------------------------------------------------------------------
# Build agents — blueprint-driven with skills layer
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
    """Resolve tool function names from the blueprint to actual tool objects."""
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


def build_agents(
    client,
    providers: dict,
    blueprint,
    tool_registry: dict[str, list],
    skills_provider,
    skill_tools: list,
):
    """Create the triage agent and domain-specialist agents from a blueprint.

    Key difference from Part 9: each agent now receives **skills** via a
    custom ``SkillsContextProvider`` that advertises available skills and
    provides ``load_skill`` and ``read_skill_resource`` function tools.

    The SkillsContextProvider:
        - Discovers SKILL.md files from the skills/ directory
        - Provides progressive disclosure (advertise → load → read resources)
        - Skills tools: load_skill, read_skill_resource
        - Can include code-defined skills with dynamic resources

    Architecture:
        skills/                      <- File-based skills (SKILL.md format)
        ├── summarize-content/
        ├── step-by-step/
        └── ...

        agent_skills.py              <- Code-defined skills + SkillsContextProvider factory

    Args:
        client: The Azure OpenAI chat client.
        providers: Domain-specific ChromaDB context providers.
        blueprint: A loaded ``Blueprint`` instance from ``blueprint_loader.py``.
        tool_registry: The ``DOMAIN_TOOLS`` dict from ``agent_tools.py``.
        skills_provider: A ``SkillsContextProvider`` instance for skill discovery.
        skill_tools: List of skill-related tools (load_skill, read_skill_resource).

    Returns:
        (triage, specialists_dict)  where specialists_dict maps domain name
        to agent instance.
    """
    from blueprint_loader import build_instructions

    # Triage agent — no skills (just routes)
    triage = client.as_agent(
        id=blueprint.triage.id,
        name=blueprint.triage.name,
        instructions=build_instructions(
            blueprint.triage,
            security_prompt=blueprint.security_prompt,
            shared_behavioral_rules=[],  # Triage doesn't use shared rules
            shared_response_style="",
        ),
        description=blueprint.triage.role,
    )

    # Specialist agents — with RAG context provider + skills provider
    specialists = {}
    for domain_name, rag_provider in providers.items():
        identity = blueprint.specialists.get(domain_name)
        if identity is None:
            print(f"  ⚠️  Domain '{domain_name}' has a provider but no blueprint entry — skipping")
            continue

        # Resolve tools by name from the blueprint
        tool_name_list = blueprint.specialist_tools.get(domain_name, [])
        tools_for_domain = _resolve_tools(tool_name_list, tool_registry)
        tool_names_str = (
            ", ".join(t.name for t in tools_for_domain)
            if tools_for_domain
            else "(none)"
        )

        # Combine domain tools with skill tools
        # Every specialist gets load_skill and read_skill_resource
        all_tools = list(skill_tools)  # Start with skill tools
        if tools_for_domain:
            all_tools.extend(tools_for_domain)

        # Each specialist gets both RAG context and skills
        agent = client.as_agent(
            id=identity.id,
            name=identity.name,
            instructions=build_instructions(
                identity,
                security_prompt=blueprint.security_prompt,
                shared_behavioral_rules=blueprint.behavioral_rules,
                shared_response_style=blueprint.response_style,
            ),
            description=identity.role,
            context_providers=[rag_provider, skills_provider],
            tools=all_tools if all_tools else None,
        )
        specialists[domain_name] = agent

    return triage, specialists


# ---------------------------------------------------------------------------
# Interactive loop with HandoffBuilder + observability
# ---------------------------------------------------------------------------
async def run(
    reingest: bool = False,
    blueprint_path: str | None = None,
    enable_otel: bool = False,
    foundry: bool = False,
) -> None:
    """Run the multi-RAG handoff workflow with skills layer."""
    from agent_framework import (
        AgentResponse,
        AgentResponseUpdate,
        WorkflowEvent,
    )
    from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

    from agent_skills import build_skills_provider, list_available_skills, get_skill_tools
    from agent_tools import DOMAIN_TOOLS
    from blueprint_loader import load_blueprint
    from domain_providers import build_domain_providers, reingest_all

    # Observability (optional)
    if enable_otel:
        _setup_observability(foundry=foundry)

    # Load blueprint
    blueprint = load_blueprint(blueprint_path)
    print(f"\n📘 Blueprint loaded: v{blueprint.version}")

    # Build skills provider (discovers skills from skills/ directory + code-defined)
    skills_provider = build_skills_provider(include_code_skills=True)
    skill_tools = get_skill_tools()  # load_skill, read_skill_resource
    available_skills = list_available_skills()
    print(f"\n🎯 Skills provider initialized: {len(available_skills)} skills available")
    for skill_name in available_skills:
        print(f"  - {skill_name}")

    # Build (or rebuild) domain providers
    if reingest:
        print("\n🔄 Re-ingesting all domain collections...")
        reingest_all()

    providers = build_domain_providers()

    # Show collection stats
    print("\n📊 Domain collections:")
    for domain_name, prov in providers.items():
        print(f"  {domain_name}: {prov._collection.count()} chunks")

    # Show blueprint → tool resolution
    print("\n🔧 Blueprint tool assignments:")
    for domain_name, tool_names in blueprint.specialist_tools.items():
        names_str = ", ".join(tool_names) if tool_names else "(none)"
        print(f"  {domain_name}: {names_str}")

    # Show SDK agent identities from blueprint (id + name + role)
    print("\n🪪 SDK agent identities (from blueprint):")
    print(f"  id={blueprint.triage.id}  name={blueprint.triage.name}  role={blueprint.triage.role}")
    for domain_name, identity in blueprint.specialists.items():
        print(f"  id={identity.id}  name={identity.name}  role={identity.role[:60]}...")

    # Create client and agents
    client = _get_client()
    triage, specialists = build_agents(
        client, providers, blueprint, DOMAIN_TOOLS, skills_provider, skill_tools
    )
    all_agents = [triage] + list(specialists.values())

    def _build_workflow():
        """Build a fresh handoff workflow for each question."""
        return (
            HandoffBuilder(
                name="multi_rag_handoff_skills_layer",
                participants=all_agents,
            )
            .with_start_agent(triage)
            .build()
        )

    print("\n" + "=" * 60)
    print("  Microsoft Agent Framework – Multi-RAG + Skills Layer")
    print("  Specialists: " + ", ".join(specialists.keys()))
    print(f"  Blueprint: v{blueprint.version}")
    print(f"  Skills: {len(available_skills)} available (via SkillsProvider)")
    if enable_otel and foundry:
        print("  Observability: Foundry (Azure Monitor)")
    elif enable_otel:
        print("  Observability: OpenTelemetry ENABLED (local)")
    else:
        print("  Observability: disabled (use --otel to enable)")
    print("=" * 60)
    print("Type your question and press Enter.  Type 'quit' or 'exit' to stop.\n")
    print("Tip: Agents can now use 'load_skill' and 'read_skill_resource' tools.\n")

    # Import tracer only if observability is enabled
    get_tracer = None
    format_trace_id = None
    SpanKind = None
    if enable_otel:
        from agent_framework.observability import get_tracer as _get_tracer
        from opentelemetry.trace import SpanKind as _SpanKind
        from opentelemetry.trace.span import format_trace_id as _format_trace_id

        get_tracer = _get_tracer
        format_trace_id = _format_trace_id
        SpanKind = _SpanKind

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

        async def _process_events(workflow, user_input):
            """Run the workflow and collect handoff/tool traces."""
            nonlocal handoff_trace, tools_used

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

        # Run with or without OTel span
        if enable_otel and get_tracer and format_trace_id and SpanKind:
            with get_tracer().start_as_current_span(
                "RAG Q&A Interaction",
                kind=SpanKind.CLIENT,
            ) as span:
                span.set_attribute("gen_ai.system", "openai")
                span.set_attribute("gen_ai.operation.name", "chat")
                span.set_attribute("gen_ai.agent.id", blueprint.triage.id)
                span.set_attribute("gen_ai.agent.name", blueprint.triage.name)
                span.set_attribute("gen_ai.request.model", os.environ.get(
                    "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4.1"))
                trace_id = format_trace_id(span.get_span_context().trace_id)
                await _process_events(workflow, user_input)
                print()
                if handoff_trace:
                    print(f"  🔀 Routing: {' → '.join(handoff_trace)}")
                if tools_used:
                    print(f"  🔧 Tools used: {', '.join(tools_used)}")
                else:
                    print("  ℹ️  No function tools called (answered from RAG context + skills)")
                print(f"  🔍 Trace ID: {trace_id}")
        else:
            await _process_events(workflow, user_input)
            print()
            if handoff_trace:
                print(f"  🔀 Routing: {' → '.join(handoff_trace)}")
            if tools_used:
                print(f"  🔧 Tools used: {', '.join(tools_used)}")
            else:
                print("  ℹ️  No function tools called (answered from RAG context + skills)")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Multi-RAG agent with handoff orchestration, skills layer, "
            "and Foundry observability."
        )
    )
    parser.add_argument(
        "--reingest",
        action="store_true",
        help="Re-ingest all domain collections from scratch.",
    )
    parser.add_argument(
        "--blueprint",
        type=str,
        default=None,
        help="Path to a custom blueprint YAML file.",
    )
    parser.add_argument(
        "--otel",
        action="store_true",
        help="Enable OpenTelemetry observability (local exporters).",
    )
    parser.add_argument(
        "--foundry",
        action="store_true",
        help="Send traces to Azure Monitor / Foundry (requires --otel).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(
        run(
            reingest=args.reingest,
            blueprint_path=args.blueprint,
            enable_otel=args.otel,
            foundry=args.foundry,
        )
    )


if __name__ == "__main__":
    main()
