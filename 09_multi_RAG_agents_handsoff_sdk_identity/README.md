# Part 9 — Agent ID for Observability on Microsoft Foundry

Multi-RAG handoff system that introduces the MAF SDK's **agent `id`** field and shows how it flows through **OpenTelemetry** into **Microsoft Foundry** for per-agent tracing, dashboards, and quality evaluation.

## What's new

| Feature | Part 8 | Part 9 |
|---|---|---|
| Agent `id` | Not used | Each agent gets `id=` passed to `Agent()` — emitted in OTel spans as `gen_ai.agent.id`, which Foundry uses as the primary agent key |
| Agent `description` | Passed as `description=` | Same, now also captured in OTel spans as `gen_ai.agent.description` |
| Foundry tracing | Not available | `--foundry` flag routes traces to Application Insights via `configure_azure_monitor()` |
| Local OTel | Not used | `--otel` flag enables local tracing (console or Aspire Dashboard) |
| Custom spans | Not used | `get_tracer()` wraps each Q&A interaction in a parent span |
| Trace IDs | Not shown | Printed to console — look up the exact trace in Foundry portal |
| Blueprint `id:` field | Not present | Required per-agent field in `blueprint.yaml` |
| Blueprint version | `1.0` | `1.1` |

## Architecture

```
blueprint.yaml (v1.1, with id: per agent)
    ↓
blueprint_loader.py → AgentIdentity(id=, name=, role=, ...)
    ↓
main.py
    ├─ configure_azure_monitor()      ← Foundry observability (--foundry)
    │   or configure_otel_providers() ← local observability (--otel)
    ├─ client.as_agent(id=, name=, description=, ...)
    │                  ↑ agent id feeds OTel spans ↑
    ├─ get_tracer().start_as_current_span("RAG Q&A")
    │                ↑ custom parent span ↑
    └─ HandoffBuilder workflow
         ├─ invoke_agent span (auto)   → gen_ai.agent.id  ← Foundry reads this
         ├─ chat span (auto)           → token usage, model
         └─ execute_tool span (auto)   → function name, args
```

## Why agent `id` matters for Foundry

The `id` is a **stable, human-readable identifier** that Microsoft Foundry uses to:

- **Correlate traces** across invocations, sessions, and deployments
- **Build per-agent dashboards** showing latency, token usage, and error rates
- **Link quality evaluations** back to a specific agent
- **Register agents** in the Foundry Agents playground

Without an explicit `id`, the SDK auto-generates a UUID that changes on every restart — making cross-run analysis impossible.

## Observability identity vs. prompt-engineering identity

| Level | Fields | Who consumes it | Purpose |
|---|---|---|---|
| **Observability identity** | `id`, `name`, `description` | Framework + Foundry | OTel spans, per-agent dashboards, agent registration |
| **Prompt-engineering identity** | `expertise`, `in_scope`, `out_of_scope`, `behavioral_rules`, `response_style`, `tool_policy` | The LLM | Shape behavior via the system prompt |

The `id` is **not** included in the system prompt — it is metadata for the observability pipeline.

## OpenTelemetry spans

When observability is enabled, the SDK auto-creates these spans:

| Span | Key attributes |
|---|---|
| `invoke_agent <name>` | `gen_ai.agent.id`, `gen_ai.agent.name`, `gen_ai.agent.description`, `gen_ai.response.id`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| `chat <model>` | `gen_ai.request.model`, prompt/response (if `ENABLE_SENSITIVE_DATA=true`) |
| `execute_tool <fn>` | `gen_ai.tool.name`, arguments/result (if `ENABLE_SENSITIVE_DATA=true`) |

Plus the custom parent span `RAG Q&A Interaction` that correlates all inner spans under a single trace.

## Quick start

```bash
# Install dependencies
pip install -r 09_multi_RAG_agents_handsoff_sdk_identity/requirements.txt

# Run without observability (same behavior as Part 8 + id)
python 09_multi_RAG_agents_handsoff_sdk_identity/main.py

# Run with local OpenTelemetry (console output)
python 09_multi_RAG_agents_handsoff_sdk_identity/main.py --otel

# Run with Foundry tracing (Azure Monitor)
APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=..." \
    python 09_multi_RAG_agents_handsoff_sdk_identity/main.py --foundry
# Open Foundry portal → Tracing to view per-agent traces

# Run with Aspire Dashboard (local Docker)
docker run --rm -d -p 18888:18888 -p 4317:18889 --name aspire mcr.microsoft.com/dotnet/aspire-dashboard:latest
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 python 09_multi_RAG_agents_handsoff_sdk_identity/main.py --otel
# Open http://localhost:18888 to view traces
```

## Foundry setup

1. Go to [Foundry portal](https://ai.azure.com) → your project → **Tracing**
2. Connect (or create) an **Application Insights** resource
3. Copy the connection string from **Manage data source**
4. Set `APPLICATIONINSIGHTS_CONNECTION_STRING` in your `.env` file
5. Run with `--foundry` — traces flow to Foundry automatically

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | (none) | Connection string for Foundry tracing via Azure Monitor |
| `ENABLE_INSTRUMENTATION` | `true` (when `--otel`) | Enable OTel instrumentation |
| `ENABLE_CONSOLE_EXPORTERS` | `true` (fallback) | Print spans to console |
| `ENABLE_SENSITIVE_DATA` | `false` | Log prompts, responses, tool args |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (none) | OTLP collector endpoint (Aspire, Jaeger, etc.) |
| `OTEL_SERVICE_NAME` | `agent_framework` | Service name in traces (use to filter in Foundry) |

## What changed from Part 8

| File | Delta |
|---|---|
| `blueprint.yaml` | Added `id:` field to triage and all specialists; bumped version to `1.1` |
| `blueprint_loader.py` | `AgentIdentity` dataclass gains `id` field; `_parse_identity()` requires and validates `id`; docstrings document Foundry observability context |
| `main.py` | Passes `id=identity.id` to `client.as_agent()`; adds `_setup_observability()` with Foundry and local paths; `--otel` and `--foundry` CLI flags; wraps Q&A in custom OTel span; prints trace IDs |
| `requirements.txt` | Adds `azure-monitor-opentelemetry` and `python-dotenv` |

## Series

| Part | Focus |
|---|---|
| 01 | Single RAG agent with ChromaDB |
| 02 | Adding function tools to RAG |
| 03 | Multi-RAG with handoff orchestration |
| 04 | Concurrent fan-out/fan-in |
| 05 | Shared function tools |
| 06 | Domain-specific tools |
| 07 | Structured agent identity (Python dataclass) |
| 08 | Declarative YAML blueprint |
| **09** | **Agent ID for observability on Microsoft Foundry** |
