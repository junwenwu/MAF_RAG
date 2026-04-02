# Copyright (c) Microsoft. All rights reserved.

"""Skills layer for MAF Learning Assistant.

This module provides **learning-focused skills** that help users understand
Microsoft Agent Framework concepts through clear explanations, code examples,
and progressive tutorials.

Learning Skills (file-based in skills/ directory):
    - explain-concept:      Break down MAF concepts for beginners
    - show-code-example:    Provide runnable code with explanations
    - getting-started:      Step-by-step setup and first agent guides
    - compare-approaches:   Compare MAF patterns (orchestrations, providers)
    - deep-dive:            Detailed technical explanations
    - common-pitfalls:      Warn about mistakes and how to avoid them
    - build-incrementally:  Add features to existing code step by step
    - connect-concepts:     Show how MAF concepts relate to each other

Code-defined Skills:
    - quick-reference:      Cheat sheets for common patterns
    - environment-info:     Live runtime and configuration info

Custom Implementation:
    Since the SDK doesn't yet have SkillsProvider, this module provides a custom
    implementation using BaseContextProvider. The pattern is:
    - SkillsContextProvider extends BaseContextProvider
    - Advertises skills in the system context (~100 tokens each)
    - Provides load_skill() function tool for full skill retrieval

Usage:
    from agent_skills import build_skills_provider, list_available_skills, load_skill

    # Create provider (includes file-based + code-defined skills)
    provider = build_skills_provider()

    # Get the load_skill tool
    skill_tools = get_skill_tools()

    # Attach to agent
    agent = client.as_agent(
        name="my_agent",
        instructions="...",
        context_providers=[provider],
        tools=skill_tools,
    )
    
    # List all skills
    print(list_available_skills())
"""

from __future__ import annotations

import os
import sys
import re
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable

from agent_framework import AgentSession, BaseContextProvider, Message, SessionContext, tool
from pydantic import Field
from typing import Annotated

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


# ═══════════════════════════════════════════════════════════════════════════
# Custom Skill and SkillResource dataclasses (SDK doesn't have these yet)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SkillResource:
    """A resource attached to a skill (e.g., cheat sheet, reference data)."""
    name: str
    content: str | None = None
    description: str = ""
    _compute_fn: Callable[[], str] | None = field(default=None, repr=False)

    def get_content(self) -> str:
        """Get content, computing dynamically if needed."""
        if self._compute_fn:
            return self._compute_fn()
        return self.content or ""


@dataclass
class Skill:
    """A skill definition with optional resources."""
    name: str
    description: str
    content: str = ""
    resources: list[SkillResource] = field(default_factory=list)
    _resource_fns: dict[str, tuple[str, Callable[[], str]]] = field(default_factory=dict, repr=False)

    def resource(self, fn: Callable[[], str] = None, *, name: str = None, description: str = ""):
        """Decorator to add a dynamic resource to this skill."""
        def decorator(f: Callable[[], str]) -> Callable[[], str]:
            resource_name = name or f.__name__
            self._resource_fns[resource_name] = (description, f)
            return f
        if fn is not None:
            return decorator(fn)
        return decorator

    def get_all_resources(self) -> list[SkillResource]:
        """Get all resources including dynamic ones."""
        all_resources = list(self.resources)
        for res_name, (desc, fn) in self._resource_fns.items():
            all_resources.append(SkillResource(
                name=res_name,
                description=desc,
                _compute_fn=fn,
            ))
        return all_resources


# ═══════════════════════════════════════════════════════════════════════════
# Skills directory path
# ═══════════════════════════════════════════════════════════════════════════

SKILLS_DIR = Path(__file__).parent / "skills"


# ═══════════════════════════════════════════════════════════════════════════
# Code-defined skills — for dynamic content or programmatic definitions
# ═══════════════════════════════════════════════════════════════════════════

# Example: A code-defined skill with static resources
quick_reference_skill = Skill(
    name="quick-reference",
    description="Quick reference cards for common Agent Framework patterns. Use when the user asks for a cheat sheet, quick reference, or needs a concise command/pattern list.",
    content=dedent("""\
        # Quick Reference Skill

        Use this skill to provide concise reference cards for common patterns.

        When providing a quick reference:
        1. Keep it scannable — use tables or bullet lists
        2. Include the most common use cases first
        3. Show minimal working examples
        4. Link to full documentation for details
    """),
    resources=[
        SkillResource(
            name="agent-patterns",
            content=dedent("""\
                # Agent Creation Patterns

                | Pattern | Code | Use Case |
                |---------|------|----------|
                | Basic agent | `client.as_agent(name="x")` | Simple chat |
                | With tools | `client.as_agent(tools=[t])` | Function calling |
                | With RAG | `client.as_agent(context_providers=[p])` | Knowledge grounded |
                | With ID | `client.as_agent(id="x", name="y")` | Foundry tracing |
            """),
        ),
        SkillResource(
            name="tool-patterns",
            content=dedent("""\
                # Tool Definition Patterns

                | Pattern | Code |
                |---------|------|
                | Basic tool | `@tool()\\ndef func(): ...` |
                | With description | `@tool(description="...")` |
                | Auto approval | `@tool(approval_mode="never_require")` |
                | Always approve | `@tool(approval_mode="always_require")` |
                | Typed params | `query: Annotated[str, Field(description="...")]` |
            """),
        ),
        SkillResource(
            name="orchestration-patterns",
            content=dedent("""\
                # Orchestration Patterns

                | Pattern | Builder | Use Case |
                |---------|---------|----------|
                | Handoff | `HandoffBuilder` | Route to specialists |
                | Concurrent | `ConcurrentBuilder` | Fan-out/fan-in |
                | Sequential | `SequentialBuilder` | Pipeline |
                | Group Chat | `GroupChatBuilder` | Multi-agent discussion |
            """),
        ),
    ],
)


# Example: A skill with a dynamic resource (computed at read time)
environment_skill = Skill(
    name="environment-info",
    description="Current environment and configuration information. Use when the user asks about the current setup, environment variables, or runtime configuration.",
    content=dedent("""\
        # Environment Information Skill

        Use this skill to provide information about the current environment.
        The environment resource returns live data about the runtime context.
    """),
)


@environment_skill.resource
def runtime() -> str:
    """Get current runtime environment details."""
    import os
    import sys

    return dedent(f"""\
        # Runtime Environment

        - Python: {sys.version}
        - Platform: {sys.platform}
        - Working directory: {os.getcwd()}
        - AZURE_OPENAI_ENDPOINT: {'set' if os.environ.get('AZURE_OPENAI_ENDPOINT') else 'not set'}
        - APPLICATIONINSIGHTS_CONNECTION_STRING: {'set' if os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING') else 'not set'}
    """)


@environment_skill.resource(name="vector-store", description="Vector store status")
def get_vector_store_status() -> str:
    """Return ChromaDB collection status."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=".chromadb")
        collections = client.list_collections()
        lines = ["# Vector Store Status", ""]
        for col in collections:
            lines.append(f"- {col.name}: {col.count()} chunks")
        return "\n".join(lines) if collections else "No collections found."
    except Exception as e:
        return f"Error reading vector store: {e}"


# Collect all code-defined skills
CODE_DEFINED_SKILLS: list[Skill] = [
    quick_reference_skill,
    environment_skill,
]


# ═══════════════════════════════════════════════════════════════════════════
# Domain-to-skills mapping (for blueprint reference)
# ═══════════════════════════════════════════════════════════════════════════

# Maps domain names to skill names most relevant for that domain.
# All skills are available to all agents; this is for documentation
# and helps the LLM prioritize skills by domain.
#
# Learning-focused skill design:
# - explain-concept: Always useful for "what is X?" questions
# - show-code-example: Core for agents/tools domains
# - getting-started: Entry point for any domain
# - compare-approaches: Critical for workflows domain
# - deep-dive: For advanced questions in any domain
# - common-pitfalls: Important for tools domain (errors are common)
# - build-incrementally: When users have working code
# - connect-concepts: For architectural understanding
DOMAIN_SKILL_NAMES: dict[str, list[str]] = {
    "agents": [
        "explain-concept",      # "What is an agent?"
        "show-code-example",    # "Show me how to create an agent"
        "getting-started",      # "Get started with agents"
        "compare-approaches",   # "Compare ChatClientAgent vs as_agent"
        "build-incrementally",  # "Add tools to my agent"
        "quick-reference",      # "Agent cheat sheet"
    ],
    "tools": [
        "explain-concept",      # "What is the @tool decorator?"
        "show-code-example",    # "Show me a tool example"
        "getting-started",      # "Get started with tools"
        "common-pitfalls",      # "Why isn't my tool being called?"
        "build-incrementally",  # "Add a tool to my agent"
        "quick-reference",      # "Tool patterns cheat sheet"
    ],
    "workflows": [
        "explain-concept",      # "What is HandoffBuilder?"
        "compare-approaches",   # "Compare Handoff vs Concurrent"
        "deep-dive",            # "How does handoff work internally?"
        "getting-started",      # "Get started with orchestrations"
        "connect-concepts",     # "How do orchestrations relate to agents?"
        "quick-reference",      # "Orchestration cheat sheet"
    ],
    "general": [
        "explain-concept",      # "What is a context provider?"
        "getting-started",      # "Get started with MAF"
        "connect-concepts",     # "How do these pieces fit together?"
        "deep-dive",            # "MAF architecture deep dive"
        "common-pitfalls",      # "Common MAF mistakes"
        "environment-info",     # "What's my current setup?"
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# Custom SkillsContextProvider (SDK doesn't have SkillsProvider yet)
# ═══════════════════════════════════════════════════════════════════════════

# Global registry of all skills (populated by build_skills_provider)
_SKILL_REGISTRY: dict[str, Skill] = {}


def _load_skill_from_file(skill_path: Path) -> Skill | None:
    """Load a skill from a SKILL.md file."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    content = skill_md.read_text()

    # Parse YAML frontmatter
    name = skill_path.name
    description = ""

    # Extract frontmatter between --- markers
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2].strip()

            # Extract name and description from frontmatter
            for line in frontmatter.strip().split("\n"):
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"\'')
        else:
            body = content
    else:
        body = content

    return Skill(
        name=name,
        description=description or f"Skill loaded from {skill_path.name}",
        content=body,
    )


class SkillsContextProvider(BaseContextProvider):
    """Custom context provider that advertises available skills.

    This provides progressive disclosure:
    - Advertises skill names and descriptions in context (~100 tokens each)
    - Full skill content is loaded via the load_skill tool when needed
    """

    source_id: str = "skills"

    def __init__(
        self,
        skills: list[Skill] | None = None,
        skill_paths: Path | list[Path] | None = None,
    ) -> None:
        super().__init__(source_id="skills")
        self._skills: dict[str, Skill] = {}

        # Load file-based skills
        if skill_paths:
            paths = [skill_paths] if isinstance(skill_paths, Path) else skill_paths
            for base_path in paths:
                if base_path.exists():
                    for skill_dir in base_path.iterdir():
                        if skill_dir.is_dir():
                            skill = _load_skill_from_file(skill_dir)
                            if skill:
                                self._skills[skill.name] = skill

        # Add code-defined skills
        if skills:
            for skill in skills:
                self._skills[skill.name] = skill

        # Update global registry
        global _SKILL_REGISTRY
        _SKILL_REGISTRY = self._skills

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """List all available skill names."""
        return sorted(self._skills.keys())

    @override
    async def get_content(
        self,
        session: AgentSession,
        context: SessionContext,
    ) -> list[Message]:
        """Return skill advertisements as context."""
        if not self._skills:
            return []

        # Build skill catalog for the LLM
        lines = [
            "## Available Skills",
            "",
            "Use the `load_skill` tool to get full instructions for any skill.",
            "",
            "| Skill | Description |",
            "|-------|-------------|",
        ]

        for name in sorted(self._skills.keys()):
            skill = self._skills[name]
            # Truncate long descriptions
            desc = skill.description[:80] + "..." if len(skill.description) > 80 else skill.description
            lines.append(f"| `{name}` | {desc} |")

        return [Message.system("\n".join(lines))]


# ═══════════════════════════════════════════════════════════════════════════
# Skill tools (load_skill, read_skill_resource)
# ═══════════════════════════════════════════════════════════════════════════

@tool(approval_mode="never_require")
def load_skill(
    skill_name: Annotated[
        str,
        Field(description="Name of the skill to load (e.g., 'explain-concept', 'getting-started')"),
    ],
) -> str:
    """Load full instructions for a skill by name.

    Use this tool when you need detailed guidance on how to respond
    to a particular type of question. The skill content provides
    formatting rules, output templates, and teaching strategies.

    Available skills:
    - explain-concept: How to explain MAF concepts
    - show-code-example: How to provide code with explanations
    - getting-started: How to create step-by-step tutorials
    - compare-approaches: How to compare different patterns
    - deep-dive: How to explain internal architecture
    - common-pitfalls: How to explain errors and fixes
    - build-incrementally: How to add features to existing code
    - connect-concepts: How to show concept relationships
    - quick-reference: How to provide cheat sheets
    - environment-info: Current runtime environment
    """
    skill = _SKILL_REGISTRY.get(skill_name)
    if not skill:
        available = ", ".join(sorted(_SKILL_REGISTRY.keys()))
        return f"Skill '{skill_name}' not found. Available skills: {available}"

    # Build full skill content
    lines = [
        f"# Skill: {skill.name}",
        "",
        f"**Description:** {skill.description}",
        "",
        "## Instructions",
        "",
        skill.content,
    ]

    # Add resources if any
    resources = skill.get_all_resources()
    if resources:
        lines.append("")
        lines.append("## Resources")
        lines.append("")
        for res in resources:
            lines.append(f"### {res.name}")
            if res.description:
                lines.append(f"*{res.description}*")
            lines.append("")
            lines.append(res.get_content())
            lines.append("")

    return "\n".join(lines)


@tool(approval_mode="never_require")
def read_skill_resource(
    skill_name: Annotated[
        str,
        Field(description="Name of the skill containing the resource"),
    ],
    resource_name: Annotated[
        str,
        Field(description="Name of the resource to read"),
    ],
) -> str:
    """Read a specific resource from a skill.

    Resources are additional content like cheat sheets, reference data,
    or dynamic information that supplements the main skill instructions.
    """
    skill = _SKILL_REGISTRY.get(skill_name)
    if not skill:
        available = ", ".join(sorted(_SKILL_REGISTRY.keys()))
        return f"Skill '{skill_name}' not found. Available skills: {available}"

    resources = skill.get_all_resources()
    for res in resources:
        if res.name == resource_name:
            return res.get_content()

    available_resources = [r.name for r in resources]
    return f"Resource '{resource_name}' not found in skill '{skill_name}'. Available: {available_resources}"


def get_skill_tools() -> list:
    """Get the skill-related tools to attach to agents."""
    return [load_skill, read_skill_resource]


# ═══════════════════════════════════════════════════════════════════════════
# SkillsProvider factory
# ═══════════════════════════════════════════════════════════════════════════

def build_skills_provider(
    *,
    include_code_skills: bool = True,
    skill_paths: list[Path] | Path | None = None,
) -> SkillsContextProvider:
    """Create a SkillsContextProvider with file-based and optional code-defined skills.

    Args:
        include_code_skills: Whether to include code-defined skills from this module.
        skill_paths: Custom skill paths. Defaults to the skills/ directory.

    Returns:
        A configured SkillsContextProvider ready to attach to agents.
    """
    if skill_paths is None:
        skill_paths = SKILLS_DIR

    return SkillsContextProvider(
        skills=CODE_DEFINED_SKILLS if include_code_skills else None,
        skill_paths=skill_paths,
    )


def list_available_skills() -> list[str]:
    """List all available skill names (file-based + code-defined)."""
    skill_names = []

    # File-based skills
    if SKILLS_DIR.exists():
        for skill_dir in SKILLS_DIR.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_names.append(skill_dir.name)

    # Code-defined skills
    for skill in CODE_DEFINED_SKILLS:
        if skill.name not in skill_names:
            skill_names.append(skill.name)

    return sorted(skill_names)
