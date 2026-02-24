# Copyright (c) Microsoft. All rights reserved.

"""Blueprint loader — reads a YAML blueprint and builds agent identities.

Extends Part 8's ``blueprint_loader.py`` with:
    - ``id`` field — a unique, stable identifier consumed by the SDK's
      ``Agent()`` constructor and emitted in OpenTelemetry spans as
      ``gen_ai.agent.id``.

Why ``id`` matters for Microsoft Foundry observability:
    When traces flow to Foundry via Azure Monitor / Application Insights,
    the ``gen_ai.agent.id`` attribute becomes the primary key that Foundry
    uses to correlate spans across invocations, sessions, and deployments.
    A stable ``id`` (vs. an auto-generated UUID) enables:
        - Per-agent performance dashboards in the Foundry portal
        - Cross-run trace correlation (same id across restarts)
        - Cost tracking and quality evaluation per agent
        - Agent registration in the Foundry Agents playground

Usage:
    from blueprint_loader import load_blueprint

    blueprint = load_blueprint("blueprint.yaml")
    triage_identity   = blueprint.triage
    specialist_ids    = blueprint.specialists   # dict[str, AgentIdentity]
    security_prompt   = blueprint.security_prompt
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ═══════════════════════════════════════════════════════════════════════════
# AgentIdentity — extended with id
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AgentIdentity:
    """Complete identity specification for one agent.

    Fields fall into two categories:

    Observability identity (consumed by the framework and Foundry):
        - ``id``   — unique, stable string passed to ``Agent(id=...)``.  Appears
          in OTel spans as ``gen_ai.agent.id`` and becomes the primary key for
          per-agent dashboards in Microsoft Foundry.
        - ``name`` — display name, appears in spans as ``gen_ai.agent.name``.
        - ``role`` — passed as ``description=`` to the Agent constructor,
          appears as ``gen_ai.agent.description``.

    Prompt-engineering identity (embedded in the system prompt):
        - ``expertise``, ``in_scope``, ``out_of_scope`` — scope the agent.
        - ``behavioral_rules`` — guardrails.
        - ``response_style`` — formatting rules.
        - ``tool_policy`` — mandatory tool-call rules.
    """

    # --- Observability identity (flows to Foundry via OTel) ---
    id: str
    """Stable agent identifier for Foundry observability.

    Passed to the SDK's Agent(id=...) constructor and emitted in every
    OTel span as gen_ai.agent.id.  Microsoft Foundry uses this attribute
    to correlate traces, build per-agent dashboards, and link quality
    evaluations back to a specific agent."""

    # --- Persona ---
    name: str
    """Display name used in HandoffBuilder and OTel spans (gen_ai.agent.name).
    Labels invoke_agent spans and Foundry trace listings."""

    role: str
    """One-line role description; passed as description= to Agent().
    Appears in Foundry traces as gen_ai.agent.description."""

    expertise: list[str]
    """Bulleted list of topics this agent is qualified to answer."""

    # --- Scope ---
    in_scope: str
    """What this agent SHOULD answer — a concise positive scope statement."""

    out_of_scope: str
    """What this agent SHOULD NOT answer — explicit exclusions."""

    # --- Behavioral rules ---
    behavioral_rules: list[str] = field(default_factory=list)
    """Ordered list of guardrails the agent must follow."""

    # --- Response style ---
    response_style: str = ""
    """Formatting, citation, and tone requirements."""

    # --- Tool policy ---
    tool_policy: str = ""
    """Mandatory tool-usage instructions (when a tool MUST be called)."""


# ═══════════════════════════════════════════════════════════════════════════
# Blueprint — the loaded result
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Blueprint:
    """Fully parsed blueprint ready to drive agent construction."""

    version: str
    security_prompt: str
    triage: AgentIdentity
    specialists: dict[str, AgentIdentity]
    tool_assignments: dict[str, list[str]]
    """Mapping of domain name → list of tool function names from the YAML."""


# ═══════════════════════════════════════════════════════════════════════════
# build_instructions — assemble a system prompt from an identity
# ═══════════════════════════════════════════════════════════════════════════

def build_instructions(
    identity: AgentIdentity,
    *,
    security_prompt: str = "",
    tool_names: str = "(none)",
) -> str:
    """Convert an ``AgentIdentity`` into a full system-prompt string.

    The ``id`` field is NOT included in the system prompt — it is passed
    to the SDK's Agent constructor and emitted in OTel spans.  Microsoft
    Foundry reads ``gen_ai.agent.id`` from these spans to build per-agent
    performance dashboards and quality evaluations.
    """
    sections: list[str] = []

    # Security — anchored at the top
    if security_prompt:
        sections.append(f"## Security\n{security_prompt}")

    # Persona
    sections.append(
        f"# Identity\n"
        f"You are **{identity.name}** — {identity.role}\n\n"
        f"## Expertise\n"
        + "\n".join(f"- {topic}" for topic in identity.expertise)
    )

    # Scope
    sections.append(
        f"## Scope\n"
        f"**IN SCOPE:** {identity.in_scope}\n\n"
        f"**OUT OF SCOPE:** {identity.out_of_scope}"
    )

    # Behavioral rules
    if identity.behavioral_rules:
        rules = "\n".join(
            f"{i}. {rule}" for i, rule in enumerate(identity.behavioral_rules, 1)
        )
        sections.append(f"## Behavioral Rules\n{rules}")

    # Response style
    if identity.response_style:
        sections.append(f"## Response Style\n{identity.response_style}")

    # Tool policy
    sections.append(f"## Available Tools\nTools: {tool_names}")
    if identity.tool_policy:
        sections.append(f"## Tool Policy — MANDATORY\n{identity.tool_policy}")

    return "\n\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# YAML loading + validation
# ═══════════════════════════════════════════════════════════════════════════

def _parse_identity(
    data: dict[str, Any],
    shared_rules: list[str] | None = None,
    shared_style: str | None = None,
) -> AgentIdentity:
    """Parse a single agent identity block from YAML.

    If ``behavioral_rules`` or ``response_style`` are absent in the YAML,
    the shared defaults are used (for specialists).  The triage agent
    always defines its own rules/style, so shared defaults are optional.
    """
    agent_id = data.get("id", "")
    if not agent_id:
        raise ValueError(f"Agent '{data.get('name', '?')}' must have an 'id' field.")

    return AgentIdentity(
        id=agent_id,
        name=data["name"],
        role=data["role"],
        expertise=data.get("expertise", []),
        in_scope=data.get("in_scope", ""),
        out_of_scope=data.get("out_of_scope", ""),
        behavioral_rules=data.get("behavioral_rules", shared_rules or []),
        response_style=data.get("response_style", shared_style or ""),
        tool_policy=data.get("tool_policy", ""),
    )


def load_blueprint(path: str | Path | None = None) -> Blueprint:
    """Load and validate a YAML blueprint file.

    Args:
        path: Path to the YAML file.  Defaults to ``blueprint.yaml`` in the
              same directory as this module.

    Returns:
        A fully parsed ``Blueprint`` instance.

    Raises:
        FileNotFoundError: If the blueprint file does not exist.
        ValueError: If required fields are missing or the schema version
                    is unsupported.
    """
    if path is None:
        path = Path(os.path.dirname(os.path.abspath(__file__))) / "blueprint.yaml"
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Blueprint not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    # --- Version check ---
    version = str(raw.get("version", ""))
    if not version:
        raise ValueError("Blueprint must specify a 'version' field.")

    # --- Shared config ---
    shared = raw.get("shared", {})
    shared_rules: list[str] = shared.get("behavioral_rules", [])
    shared_style: str = shared.get("response_style", "")
    security_prompt: str = shared.get("security_prompt", "")

    # --- Triage ---
    triage_data = raw.get("triage")
    if not triage_data:
        raise ValueError("Blueprint must define a 'triage' agent.")
    triage = _parse_identity(triage_data)

    # --- Specialists ---
    specialists_data: dict[str, Any] = raw.get("specialists", {})
    if not specialists_data:
        raise ValueError("Blueprint must define at least one specialist.")

    specialists: dict[str, AgentIdentity] = {}
    tool_assignments: dict[str, list[str]] = {}

    for domain_name, spec_data in specialists_data.items():
        specialists[domain_name] = _parse_identity(
            spec_data,
            shared_rules=shared_rules,
            shared_style=shared_style,
        )
        tool_assignments[domain_name] = spec_data.get("tools", [])

    return Blueprint(
        version=version,
        security_prompt=security_prompt,
        triage=triage,
        specialists=specialists,
        tool_assignments=tool_assignments,
    )
