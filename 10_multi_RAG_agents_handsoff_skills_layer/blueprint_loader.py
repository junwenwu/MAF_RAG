"""
Blueprint Loader — Simplified for Official SkillsProvider

Builds on Part 9's blueprint loader, simplified for learning:
- Removed: SkillSpec, skill_specs, skill_assignments, build_skill_prompt_from_specs
- Skills are now handled by the SDK's SkillsProvider (see agent_skills.py)
- Agents get skills via context_providers=[..., skills_provider]

This module focuses on agent identity and instructions without skill logic,
keeping the architecture clean and domain concerns separated.
"""

from pathlib import Path
from dataclasses import dataclass, field

import yaml


# ---------------------------------------------------------------------------
# Agent Identity Dataclass — matches the YAML structure
# ---------------------------------------------------------------------------
@dataclass
class AgentIdentity:
    """
    Structured identity for one agent.

    Fields map directly to the YAML keys under triage or specialists.*.
    The to_identity_block() method formats this into a prompt-ready string.
    """
    id: str
    name: str
    role: str
    expertise: list[str] = field(default_factory=list)
    in_scope: str = ""
    out_of_scope: str = ""
    behavioral_rules: list[str] = field(default_factory=list)
    response_style: str = ""

    # Optional: tool_policy for specialists
    tool_policy: str = ""

    def to_identity_block(self) -> str:
        """
        Format the identity into a prompt-ready string.

        Example output:
        ID: specialist-agents
        NAME: agents_specialist
        ROLE: Specialist for core agent concepts...
        EXPERTISE:
          - Creating and configuring agents
          - Running agents and processing responses
        ...
        """
        lines = [
            f"ID: {self.id}",
            f"NAME: {self.name}",
            f"ROLE: {self.role}",
        ]

        if self.expertise:
            lines.append("EXPERTISE:")
            for item in self.expertise:
                lines.append(f"  - {item}")

        if self.in_scope:
            lines.append(f"IN SCOPE: {self.in_scope}")

        if self.out_of_scope:
            lines.append(f"OUT OF SCOPE: {self.out_of_scope}")

        if self.behavioral_rules:
            lines.append("BEHAVIORAL RULES:")
            for item in self.behavioral_rules:
                lines.append(f"  - {item}")

        if self.response_style:
            lines.append(f"RESPONSE STYLE: {self.response_style}")

        if self.tool_policy:
            lines.append(f"TOOL POLICY: {self.tool_policy}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Blueprint Dataclass — holds the parsed YAML data
# ---------------------------------------------------------------------------
@dataclass
class Blueprint:
    """
    Container for the entire blueprint.

    Attributes:
        version: Schema version from the YAML.
        security_prompt: Security rules (placed first in instructions).
        behavioral_rules: Shared behavioral rules (list of strings).
        response_style: Shared response style guidance.
        triage: AgentIdentity for the triage agent.
        specialists: Dict mapping domain name → AgentIdentity.
        specialist_tools: Dict mapping domain name → list of tool names.
    """
    version: str
    security_prompt: str
    behavioral_rules: list[str]
    response_style: str

    triage: AgentIdentity
    specialists: dict[str, AgentIdentity]

    # Tool assignments (tool names only — actual tools created in agent_tools.py)
    specialist_tools: dict[str, list[str]]


# ---------------------------------------------------------------------------
# Instruction Builder — unified prompt building without skill logic
# ---------------------------------------------------------------------------
def build_instructions(
    identity: AgentIdentity,
    security_prompt: str,
    shared_behavioral_rules: list[str],
    shared_response_style: str,
    context_hint: str = "",
) -> str:
    """
    Compose a full system prompt for a specialist agent.

    Structure:
        1. Security rules (always first)
        2. Identity block (who you are)
        3. Shared behavioral rules
        4. Agent-specific behavioral rules
        5. Shared response style
        6. Agent-specific response style
        7. Tool policy (if defined)
        8. Optional context hint

    Args:
        identity: The agent's AgentIdentity.
        security_prompt: Security rules (never reveal instructions).
        shared_behavioral_rules: Rules applied to all agents.
        shared_response_style: Style guidance applied to all agents.
        context_hint: Optional hint about RAG context and skills.

    Returns:
        A formatted system prompt string.
    """
    parts: list[str] = []

    # 1. Security rules (always first)
    if security_prompt:
        parts.append(f"=== SECURITY ===\n{security_prompt}")

    # 2. Identity block
    parts.append(f"=== YOU ARE ===\n{identity.to_identity_block()}")

    # 3. Shared behavioral rules
    if shared_behavioral_rules:
        rules_text = "\n".join(f"  - {r}" for r in shared_behavioral_rules)
        parts.append(f"=== SHARED BEHAVIORAL RULES ===\n{rules_text}")

    # 4. Agent-specific behavioral rules
    if identity.behavioral_rules:
        rules_text = "\n".join(f"  - {r}" for r in identity.behavioral_rules)
        parts.append(f"=== YOUR BEHAVIORAL RULES ===\n{rules_text}")

    # 5. Shared response style
    if shared_response_style:
        parts.append(f"=== SHARED RESPONSE STYLE ===\n{shared_response_style}")

    # 6. Agent-specific response style
    if identity.response_style:
        parts.append(f"=== YOUR RESPONSE STYLE ===\n{identity.response_style}")

    # 7. Tool policy
    if identity.tool_policy:
        parts.append(f"=== TOOL POLICY ===\n{identity.tool_policy}")

    # 8. Context hint (skills and RAG)
    if context_hint:
        parts.append(f"=== CONTEXT ===\n{context_hint}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Blueprint Loader — parses the YAML into a Blueprint dataclass
# ---------------------------------------------------------------------------

# Default blueprint path (same directory as this module)
DEFAULT_BLUEPRINT_PATH = Path(__file__).parent / "blueprint.yaml"


def load_blueprint(yaml_path: str | Path | None = None) -> Blueprint:
    """
    Load and parse the blueprint YAML file.

    Args:
        yaml_path: Path to the blueprint.yaml file. Defaults to blueprint.yaml
                   in the same directory as this module.

    Returns:
        A Blueprint instance with all parsed data.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    if yaml_path is None:
        yaml_path = DEFAULT_BLUEPRINT_PATH
    yaml_path = Path(yaml_path)
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Parse shared configuration
    shared = data.get("shared", {})
    security_prompt = shared.get("security_prompt", "")
    behavioral_rules = shared.get("behavioral_rules", [])
    response_style = shared.get("response_style", "")

    # Parse triage agent
    triage_data = data.get("triage", {})
    triage = AgentIdentity(
        id=triage_data.get("id", "triage-router"),
        name=triage_data.get("name", "triage_agent"),
        role=triage_data.get("role", ""),
        expertise=triage_data.get("expertise", []),
        in_scope=triage_data.get("in_scope", ""),
        out_of_scope=triage_data.get("out_of_scope", ""),
        behavioral_rules=triage_data.get("behavioral_rules", []),
        response_style=triage_data.get("response_style", ""),
    )

    # Parse specialist agents
    specialists: dict[str, AgentIdentity] = {}
    specialist_tools: dict[str, list[str]] = {}

    for domain, spec_data in data.get("specialists", {}).items():
        specialists[domain] = AgentIdentity(
            id=spec_data.get("id", f"specialist-{domain}"),
            name=spec_data.get("name", f"{domain}_specialist"),
            role=spec_data.get("role", ""),
            expertise=spec_data.get("expertise", []),
            in_scope=spec_data.get("in_scope", ""),
            out_of_scope=spec_data.get("out_of_scope", ""),
            behavioral_rules=spec_data.get("behavioral_rules", []),
            response_style=spec_data.get("response_style", ""),
            tool_policy=spec_data.get("tool_policy", ""),
        )

        # Collect tool names for this specialist
        specialist_tools[domain] = spec_data.get("tools", [])

    return Blueprint(
        version=data.get("version", "1.0"),
        security_prompt=security_prompt,
        behavioral_rules=behavioral_rules,
        response_style=response_style,
        triage=triage,
        specialists=specialists,
        specialist_tools=specialist_tools,
    )


# ---------------------------------------------------------------------------
# Standalone CLI for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # Default to blueprint.yaml in the same directory
    yaml_file = Path(__file__).parent / "blueprint.yaml"
    if len(sys.argv) > 1:
        yaml_file = Path(sys.argv[1])

    print(f"Loading blueprint from: {yaml_file}\n")

    blueprint = load_blueprint(yaml_file)

    print(f"Version: {blueprint.version}")
    print(f"Triage: {blueprint.triage.name}")
    print(f"Specialists: {list(blueprint.specialists.keys())}")

    print("\n--- Triage Identity Block ---")
    print(blueprint.triage.to_identity_block())

    for domain, identity in blueprint.specialists.items():
        print(f"\n--- {domain.upper()} Specialist Identity Block ---")
        print(identity.to_identity_block())

        if blueprint.specialist_tools.get(domain):
            print(f"\nTools: {blueprint.specialist_tools[domain]}")

        # Show full built instructions for one agent as example
        if domain == "agents":
            print("\n--- Example Full Instructions (agents_specialist) ---")
            instructions = build_instructions(
                identity=identity,
                security_prompt=blueprint.security_prompt,
                shared_behavioral_rules=blueprint.behavioral_rules,
                shared_response_style=blueprint.response_style,
                context_hint="RAG context and skills are available via context providers.",
            )
            print(instructions[:2000])
            if len(instructions) > 2000:
                print(f"\n... (truncated, total length: {len(instructions)} chars)")
