# Copyright (c) Microsoft. All rights reserved.

"""Domain-specific URL groups for the Microsoft Agent Framework docs.

The full set of ~97 documentation pages is split into four specialist domains
so that each RAG agent can operate over a focused subset of knowledge.
"""

from __future__ import annotations

_BASE = "https://learn.microsoft.com/en-us/agent-framework"
_PIVOT = "?pivots=programming-language-python"

# ---------------------------------------------------------------------------
# Domain 1: Agents — core agent concepts, providers, identity
# ---------------------------------------------------------------------------
AGENTS_URLS = [
    f"{_BASE}/agents/{_PIVOT}",
    f"{_BASE}/agents/running-agents{_PIVOT}",
    f"{_BASE}/agents/multimodal{_PIVOT}",
    f"{_BASE}/agents/structured-output{_PIVOT}",
    f"{_BASE}/agents/background-responses{_PIVOT}",
    f"{_BASE}/agents/rag{_PIVOT}",
    f"{_BASE}/agents/declarative{_PIVOT}",
    f"{_BASE}/agents/observability{_PIVOT}",
    # Providers (how to connect agents to LLM backends)
    f"{_BASE}/agents/providers/{_PIVOT}",
    f"{_BASE}/agents/providers/azure-openai{_PIVOT}",
    f"{_BASE}/agents/providers/openai{_PIVOT}",
    f"{_BASE}/agents/providers/azure-ai-foundry{_PIVOT}",
    f"{_BASE}/agents/providers/anthropic{_PIVOT}",
    f"{_BASE}/agents/providers/ollama{_PIVOT}",
    f"{_BASE}/agents/providers/github-copilot{_PIVOT}",
    f"{_BASE}/agents/providers/copilot-studio{_PIVOT}",
    f"{_BASE}/agents/providers/custom{_PIVOT}",
]

# ---------------------------------------------------------------------------
# Domain 2: Tools — function tools, code interpreter, MCP, etc.
# ---------------------------------------------------------------------------
TOOLS_URLS = [
    f"{_BASE}/agents/tools/{_PIVOT}",
    f"{_BASE}/agents/tools/function-tools{_PIVOT}",
    f"{_BASE}/agents/tools/tool-approval{_PIVOT}",
    f"{_BASE}/agents/tools/code-interpreter{_PIVOT}",
    f"{_BASE}/agents/tools/file-search{_PIVOT}",
    f"{_BASE}/agents/tools/web-search{_PIVOT}",
    f"{_BASE}/agents/tools/hosted-mcp-tools{_PIVOT}",
    f"{_BASE}/agents/tools/local-mcp-tools{_PIVOT}",
]

# ---------------------------------------------------------------------------
# Domain 3: Workflows — orchestration patterns, handoffs, events
# ---------------------------------------------------------------------------
WORKFLOWS_URLS = [
    f"{_BASE}/workflows/{_PIVOT}",
    f"{_BASE}/workflows/executors{_PIVOT}",
    f"{_BASE}/workflows/edges{_PIVOT}",
    f"{_BASE}/workflows/events{_PIVOT}",
    f"{_BASE}/workflows/workflows{_PIVOT}",
    f"{_BASE}/workflows/agents-in-workflows{_PIVOT}",
    f"{_BASE}/workflows/human-in-the-loop{_PIVOT}",
    f"{_BASE}/workflows/state{_PIVOT}",
    f"{_BASE}/workflows/checkpoints{_PIVOT}",
    f"{_BASE}/workflows/declarative{_PIVOT}",
    f"{_BASE}/workflows/observability{_PIVOT}",
    f"{_BASE}/workflows/as-agents{_PIVOT}",
    f"{_BASE}/workflows/visualization{_PIVOT}",
    # Orchestrations (high-level patterns)
    f"{_BASE}/workflows/orchestrations/{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/sequential{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/concurrent{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/handoff{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/group-chat{_PIVOT}",
    f"{_BASE}/workflows/orchestrations/magentic{_PIVOT}",
]

# ---------------------------------------------------------------------------
# Domain 4: General — overview, getting-started, conversations, middleware,
#            integrations, migration, support, DevUI
# ---------------------------------------------------------------------------
GENERAL_URLS = [
    # Landing + overview
    f"{_BASE}/",
    f"{_BASE}/overview/{_PIVOT}",
    # Getting started
    f"{_BASE}/get-started/{_PIVOT}",
    f"{_BASE}/get-started/your-first-agent{_PIVOT}",
    f"{_BASE}/get-started/add-tools{_PIVOT}",
    f"{_BASE}/get-started/multi-turn{_PIVOT}",
    f"{_BASE}/get-started/memory{_PIVOT}",
    f"{_BASE}/get-started/workflows{_PIVOT}",
    f"{_BASE}/get-started/hosting{_PIVOT}",
    # Conversations & Memory
    f"{_BASE}/agents/conversations/{_PIVOT}",
    f"{_BASE}/agents/conversations/session{_PIVOT}",
    f"{_BASE}/agents/conversations/context-providers{_PIVOT}",
    f"{_BASE}/agents/conversations/storage{_PIVOT}",
    # Middleware
    f"{_BASE}/agents/middleware/{_PIVOT}",
    f"{_BASE}/agents/middleware/defining-middleware{_PIVOT}",
    f"{_BASE}/agents/middleware/chat-middleware{_PIVOT}",
    f"{_BASE}/agents/middleware/agent-vs-run-scope{_PIVOT}",
    f"{_BASE}/agents/middleware/termination{_PIVOT}",
    f"{_BASE}/agents/middleware/result-overrides{_PIVOT}",
    f"{_BASE}/agents/middleware/exception-handling{_PIVOT}",
    f"{_BASE}/agents/middleware/shared-state{_PIVOT}",
    f"{_BASE}/agents/middleware/runtime-context{_PIVOT}",
    # Integrations
    f"{_BASE}/integrations/{_PIVOT}",
    f"{_BASE}/integrations/azure-functions{_PIVOT}",
    f"{_BASE}/integrations/openai-endpoints{_PIVOT}",
    f"{_BASE}/integrations/purview{_PIVOT}",
    f"{_BASE}/integrations/m365{_PIVOT}",
    f"{_BASE}/integrations/a2a{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/getting-started{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/backend-tool-rendering{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/frontend-tools{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/security-considerations{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/human-in-the-loop{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/state-management{_PIVOT}",
    f"{_BASE}/integrations/ag-ui/testing-with-dojo{_PIVOT}",
    # DevUI
    f"{_BASE}/devui/{_PIVOT}",
    f"{_BASE}/devui/directory-discovery{_PIVOT}",
    f"{_BASE}/devui/api-reference{_PIVOT}",
    f"{_BASE}/devui/tracing{_PIVOT}",
    f"{_BASE}/devui/security{_PIVOT}",
    f"{_BASE}/devui/samples{_PIVOT}",
    # Migration Guide
    f"{_BASE}/migration-guide/{_PIVOT}",
    f"{_BASE}/migration-guide/from-autogen/{_PIVOT}",
    f"{_BASE}/migration-guide/from-semantic-kernel/{_PIVOT}",
    f"{_BASE}/migration-guide/from-semantic-kernel/samples{_PIVOT}",
    # Support
    f"{_BASE}/support/{_PIVOT}",
    f"{_BASE}/support/faq{_PIVOT}",
    f"{_BASE}/support/troubleshooting{_PIVOT}",
    f"{_BASE}/support/upgrade/{_PIVOT}",
    f"{_BASE}/support/upgrade/requests-and-responses-upgrade-guide-python{_PIVOT}",
    f"{_BASE}/support/upgrade/typed-options-guide-python{_PIVOT}",
    f"{_BASE}/support/upgrade/python-2026-significant-changes{_PIVOT}",
]


# ---------------------------------------------------------------------------
# Registry: domain name → URLs
# ---------------------------------------------------------------------------
DOMAIN_REGISTRY: dict[str, list[str]] = {
    "agents": AGENTS_URLS,
    "tools": TOOLS_URLS,
    "workflows": WORKFLOWS_URLS,
    "general": GENERAL_URLS,
}
