# Copyright (c) Microsoft. All rights reserved.

"""Multi-RAG agent with handoff orchestration, **agent ID for observability**,
and **Microsoft Foundry tracing integration**.

Architecture:
    blueprint.yaml  →  blueprint_loader.py  →  AgentIdentity objects (with id)
                                              ↓
    User → Triage Agent → Specialist Agent (agents | tools | workflows | general)
                         ├─ domain-specific RAG context (ChromaDB collection)
                         ├─ domain-specific tools (resolved by name from registry)
                         ├─ agent identity (loaded from YAML)
                         └─ Observability identity (id=, name=, description=)
                              └─ OpenTelemetry → Foundry: gen_ai.agent.id

Key differences from ``08_multi_RAG_agents_handsoff_agent_blueprint``:
    1. **id field**: Each agent gets a unique ``id`` passed to the SDK's
       ``Agent(id=...)`` constructor.  This ``id`` appears automatically in
       OpenTelemetry spans as ``gen_ai.agent.id``, which Microsoft Foundry
       uses to build per-agent dashboards and quality evaluations.

    2. **Foundry observability**: ``configure_otel_providers()`` enables
       OpenTelemetry tracing, metrics, and logging.  When
       ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set, traces flow to
       Azure Monitor / Application Insights, where Foundry reads them.
       The SDK auto-creates spans for:
       - ``invoke_agent <agent_name>``  (top-level agent invocation)
       - ``chat <model_name>``          (LLM inference call)
       - ``execute_tool <function_name>`` (function tool execution)

    3. **Custom spans**: ``get_tracer()`` wraps each Q&A interaction in a
       scenario-level span so all inner agent/tool spans are correlated
       under a single trace in the Foundry portal.

    4. **Trace IDs**: Printed to the console so the user can look up the
       exact trace in Foundry's Tracing view.

Usage (from repo root):
    python 09_multi_RAG_agents_handsoff_sdk_identity/main.py
    python 09_multi_RAG_agents_handsoff_sdk_identity/main.py --reingest
    python 09_multi_RAG_agents_handsoff_sdk_identity/main.py --blueprint custom.yaml
    python 09_multi_RAG_agents_handsoff_sdk_identity/main.py --otel
    python 09_multi_RAG_agents_handsoff_sdk_identity/main.py --otel --foundry
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
# Observability setup
# ---------------------------------------------------------------------------
def _setup_observability(*, foundry: bool = False) -> None:
    """Enable OpenTelemetry tracing, metrics, and logging.

    Two modes:
        - **Local** (default): Uses ``configure_otel_providers()`` with
          console exporters or an OTLP endpoint (e.g. Aspire Dashboard).
        - **Foundry** (``--foundry``): Uses ``configure_azure_monitor()``
          to send traces to Azure Application Insights, where Microsoft
          Foundry reads ``gen_ai.agent.id`` to build per-agent dashboards.

    Spans auto-created by the SDK:
        - ``invoke_agent <agent_name>``
        - ``chat <model_name>``
        - ``execute_tool <function_name>``

    Span attributes auto-populated from Agent(id=, name=, description=):
        - ``gen_ai.agent.id``       ← Foundry uses this as the agent key
        - ``gen_ai.agent.name``
        - ``gen_ai.agent.description``
        - ``gen_ai.response.id``
        - ``gen_ai.usage.input_tokens``
        - ``gen_ai.usage.output_tokens``
    """
    if foundry:
        # --- Foundry path: export to Azure Monitor / Application Insights ---
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
            # Tell the SDK to emit gen_ai.* spans (invoke_agent, chat, etc.).
            # configure_azure_monitor sets up the TracerProvider and exporters,
            # but the SDK only generates its own spans when instrumentation is
            # explicitly enabled.
            enable_instrumentation()
            print("📡 Foundry observability enabled (Azure Monitor)")
            print("   Traces will appear in Foundry portal → Tracing")
            return

    # --- Local path: console or OTLP endpoint ---
    # IMPORTANT: Set env vars BEFORE importing the observability module.
    # The module reads ENABLE_CONSOLE_EXPORTERS at import time to decide
    # whether to create a ConsoleSpanExporter.  If the var isn't set when
    # the module loads, no exporter is created → NoOp tracer → zero trace IDs.
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        os.environ.setdefault("ENABLE_CONSOLE_EXPORTERS", "true")
    os.environ.setdefault("ENABLE_INSTRUMENTATION", "true")

    from agent_framework.observability import configure_otel_providers

    # Pass a ConsoleSpanExporter explicitly as a fallback — this guarantees
    # a real TracerProvider is created even if the module's env-var detection
    # fails (e.g. when OBSERVABILITY_SETTINGS was initialised before the
    # env vars were set).
    extra_exporters = None
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        extra_exporters = [ConsoleSpanExporter()]

    configure_otel_providers(exporters=extra_exporters)
    print("📡 OpenTelemetry observability enabled (local)")


# ---------------------------------------------------------------------------
# Build agents — blueprint-driven with SDK id
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


def build_agents(client, providers: dict, blueprint, tool_registry: dict[str, list]):
    """Create the triage agent and domain-specialist agents from a blueprint.

    Key difference from Part 8: each agent now receives ``id=identity.id``
    which the SDK uses for:
        - OpenTelemetry span attribute ``gen_ai.agent.id`` — the primary
          key that Microsoft Foundry uses for per-agent tracing
        - Orchestration tracking (``resolve_agent_id()`` in the SDK)
        - Foundry agent registration and quality evaluation

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

    # Triage agent — identity from blueprint, with SDK id
    triage = client.as_agent(
        id=blueprint.triage.id,
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
            id=identity.id,
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
# Interactive loop with HandoffBuilder + observability
# ---------------------------------------------------------------------------
async def run(
    reingest: bool = False,
    blueprint_path: str | None = None,
    enable_otel: bool = False,
    foundry: bool = False,
) -> None:
    """Run the multi-RAG handoff workflow with agent ID and Foundry observability."""
    from agent_framework import (
        AgentResponse,
        AgentResponseUpdate,
        WorkflowEvent,
    )
    from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

    from agent_tools import DOMAIN_TOOLS
    from blueprint_loader import load_blueprint
    from domain_providers import build_domain_providers, reingest_all

    # Observability (optional)
    if enable_otel:
        _setup_observability(foundry=foundry)

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

    # Show SDK agent identities from blueprint (id + name + role)
    print("\n🪪 SDK agent identities (from blueprint):")
    print(f"  id={blueprint.triage.id}  name={blueprint.triage.name}  role={blueprint.triage.role}")
    for domain_name, identity in blueprint.specialists.items():
        print(f"  id={identity.id}  name={identity.name}  role={identity.role[:60]}...")

    # Create client and agents
    client = _get_client()
    triage, specialists = build_agents(client, providers, blueprint, DOMAIN_TOOLS)
    all_agents = [triage] + list(specialists.values())

    def _build_workflow():
        """Build a fresh handoff workflow for each question."""
        return (
            HandoffBuilder(
                name="multi_rag_handoff_sdk_identity",
                participants=all_agents,
            )
            .with_start_agent(triage)
            .build()
        )

    print("\n" + "=" * 60)
    print("  Microsoft Agent Framework – Multi-RAG + Agent ID for Foundry")
    print("  Specialists: " + ", ".join(specialists.keys()))
    print(f"  Blueprint: v{blueprint.version}")
    if enable_otel and foundry:
        print("  Observability: Foundry (Azure Monitor)")
    elif enable_otel:
        print("  Observability: OpenTelemetry ENABLED (local)")
    else:
        print("  Observability: disabled (use --otel to enable)")
    print("=" * 60)
    print("Type your question and press Enter.  Type 'quit' or 'exit' to stop.\n")

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
                # Set gen_ai.* attributes so Foundry Tracing can identify
                # this as an AI agent interaction.  These are the semantic
                # convention attributes that Foundry filters on.
                span.set_attribute("gen_ai.system", "openai")
                span.set_attribute("gen_ai.operation.name", "chat")
                span.set_attribute("gen_ai.agent.id", blueprint.triage.id)
                span.set_attribute("gen_ai.agent.name", blueprint.triage.name)
                span.set_attribute("gen_ai.request.model", os.environ.get(
                    "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4.1"))
                trace_id = format_trace_id(span.get_span_context().trace_id)
                await _process_events(workflow, user_input)
                # Print trace info after the answer
                print()
                if handoff_trace:
                    print(f"  🔀 Routing: {' → '.join(handoff_trace)}")
                if tools_used:
                    print(f"  🔧 Tools used: {', '.join(tools_used)}")
                else:
                    print("  ℹ️  No function tools called (answered from RAG context)")
                print(f"  🔍 Trace ID: {trace_id}")
        else:
            await _process_events(workflow, user_input)
            print()
            if handoff_trace:
                print(f"  🔀 Routing: {' → '.join(handoff_trace)}")
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
        description=(
            "Multi-RAG agent with handoff orchestration, "
            "agent ID for observability, and Microsoft Foundry tracing."
        ),
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
    parser.add_argument(
        "--otel",
        action="store_true",
        help=(
            "Enable OpenTelemetry observability (tracing, metrics, logging).  "
            "Spans are printed to the console by default.  "
            "Set OTEL_EXPORTER_OTLP_ENDPOINT to send to Aspire Dashboard or another collector."
        ),
    )
    parser.add_argument(
        "--foundry",
        action="store_true",
        help=(
            "Route traces to Microsoft Foundry via Azure Monitor.  "
            "Requires APPLICATIONINSIGHTS_CONNECTION_STRING.  "
            "Implies --otel."
        ),
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    # --foundry implies --otel
    enable_otel = args.otel or args.foundry
    try:
        await run(
            reingest=args.reingest,
            blueprint_path=args.blueprint,
            enable_otel=enable_otel,
            foundry=args.foundry,
        )
    finally:
        # Flush pending telemetry so traces reach Application Insights
        # before the process exits.  The Azure Monitor exporter batches
        # spans and sends them asynchronously — without an explicit flush
        # the program may exit before the batch is transmitted.
        if enable_otel:
            _flush_telemetry()


def _flush_telemetry() -> None:
    """Force-flush the global TracerProvider so all spans are exported.

    ``configure_azure_monitor()`` installs a ``BatchSpanProcessor`` that
    accumulates spans in memory and sends them in periodic batches.  If
    the process exits before a batch fires, traces appear in the console
    (trace ID is printed) but never arrive in Application Insights.

    Calling ``force_flush()`` blocks until the current batch is sent,
    then ``shutdown()`` releases resources cleanly.
    """
    import opentelemetry.trace as ot_trace

    provider = ot_trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        print("\n⏳ Flushing telemetry to Application Insights …")
        provider.force_flush(timeout_millis=10_000)
        print("✅ Telemetry flushed.")
    if hasattr(provider, "shutdown"):
        provider.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
