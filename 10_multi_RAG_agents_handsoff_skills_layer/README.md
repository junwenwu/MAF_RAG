# Part 10: Learning-Focused Skills with Official SkillsProvider

This project extends [Part 9](../09_multi_RAG_agents_handsoff_sdk_identity/) by introducing **learning-focused skills** — using the official `SkillsProvider` API to help users learn about Microsoft Agent Framework through clear explanations, code examples, and progressive tutorials.

## What's New in Part 10

| Feature | Part 9 | Part 10 |
| ------- | ------ | ------- |
| Tools | Domain-specific function tools | Same |
| Identity | Full agent identity (id, name, role, expertise, scope) | Same |
| **Skills** | ❌ | ✅ Learning-focused skills via SkillsProvider |
| **SKILL.md Files** | ❌ | ✅ 8 learning-focused skill definitions |
| **Progressive Disclosure** | ❌ | ✅ Advertise → Load → Read resources |
| **Skills Tools** | ❌ | ✅ `load_skill`, `read_skill_resource` |

## Skills vs Tools vs Identity

Understanding the three layers that shape agent behavior:

| Layer | Purpose | Example |
| ----- | ------- | ------- |
| **Identity** | WHO the agent is | "You are agents_specialist — expert in agent creation" |
| **Skills** | HOW the agent teaches | "When explaining a concept, start with a one-sentence definition..." |
| **Tools** | WHAT actions the agent can take | `list_supported_providers()` function |

### Why Learning-Focused Skills

The use case is **helping users learn about Microsoft Agent Framework** through RAG-powered documentation. Generic skills like "summarize" don't fit this context. Instead, we use:

1. **Learning-Optimized Skills**: Each skill is designed for educational outcomes
2. **Progressive Disclosure**: Skills advertise briefly (~100 tokens), load full instructions on demand
3. **Structured Outputs**: Skills produce consistent, learner-friendly formats
4. **Question-Type Matching**: Skills match common learner question patterns

## Official SkillsProvider Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        SkillsProvider                                    │
│  • Scans skills/ directory for SKILL.md files                           │
│  • Advertises skills in prompt (short descriptions only)                │
│  • Provides tools: load_skill, read_skill_resource, run_skill_script    │
└─────────────────────────────────────────────────────────────────────────┘
         │
         │ discovers
         ▼
┌──────────────────┐ ┌──────────────────┐ ┌─────────────────────┐
│ explain-concept/ │ │ show-code-      │ │ getting-started/    │
│   SKILL.md       │ │   example/      │ │   SKILL.md          │
└──────────────────┘ │   SKILL.md      │ └─────────────────────┘
                    └──────────────────┘
```

## SKILL.md Format

Each skill is a directory with a `SKILL.md` file:

```markdown
---
name: explain-concept
description: Break down MAF concepts for learners with clear definitions.
license: MIT
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Explain Concept Skill

## When to Use
Activate when the user asks: "What is [concept]?", "Explain [topic]"

## Instructions
1. Start with a one-sentence definition
2. Explain why it exists (what problem it solves)
3. Show where it fits in the architecture
4. Provide a minimal code example
5. Connect to familiar concepts
...
```

## Learning-Focused Skills

Skills are designed for common learner question patterns:

| Skill | Question Pattern | Example Trigger |
| ----- | ---------------- | --------------- |
| `explain-concept` | "What is X?" | "What is a context provider?" |
| `show-code-example` | "Show me how to..." | "Show me how to create an agent" |
| `getting-started` | "How do I start with..." | "Get started with tools" |
| `compare-approaches` | "X vs Y" | "HandoffBuilder vs ConcurrentBuilder" |
| `deep-dive` | "How does X work internally?" | "How does handoff work?" |
| `common-pitfalls` | "Why isn't X working?" | "Why isn't my tool being called?" |
| `build-incrementally` | "I have X, add Y" | "Add tools to my agent" |
| `connect-concepts` | "How does X relate to Y?" | "How do orchestrations relate to agents?" |

## How Skills Work at Runtime

```text
User: "What is a context provider?"
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ LLM sees skill advertisements in context:                                │
│   "explain-concept: Break down MAF concepts for learners."               │
│   "show-code-example: Provide runnable code with explanations."          │
│                                                                          │
│ LLM decides: "User wants to understand a concept — load explain-concept" │
└──────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼ calls load_skill("explain-concept")
┌──────────────────────────────────────────────────────────────────────────┐
│ SkillsProvider returns full SKILL.md instructions:                       │
│   "Start with a one-sentence definition..."                              │
│   "Explain why it exists..."                                             │
│   "Provide a minimal code example..."                                    │
└──────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼ LLM applies skill guidelines
┌──────────────────────────────────────────────────────────────────────────┐
│ Agent response follows skill format:                                     │
│   **Context Provider**                                                   │
│   A context provider supplies additional information to an agent...      │
│   **Why it matters:** RAG data, user history, external context...        │
│   **Minimal example:** `class MyProvider(BaseContextProvider)...`        │
└──────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```text
10_multi_RAG_agents_handsoff_skills_layer/
├── main.py                 # Entry point with SkillsProvider integration
├── blueprint.yaml          # Agent definitions (skills via SDK)
├── blueprint_loader.py     # Simplified (no skill parsing)
├── agent_skills.py         # SkillsProvider + code-defined skills
├── agent_tools.py          # Domain-specific function tools (from Part 9)
├── domain_providers.py     # ChromaDB context providers (from Part 9)
├── domain_urls.py          # URL groups per domain (from Part 9)
├── web_loader.py           # Web scraping utilities (from Part 9)
├── requirements.txt        # Dependencies
└── skills/                 # Learning-focused SKILL.md files
    ├── explain-concept/    # "What is X?" questions
    │   └── SKILL.md
    ├── show-code-example/  # "Show me how..." requests
    │   └── SKILL.md
    ├── getting-started/    # "Get started with..." tutorials
    │   └── SKILL.md
    ├── compare-approaches/ # "X vs Y" comparisons
    │   └── SKILL.md
    ├── deep-dive/          # "How does X work?" internals
    │   └── SKILL.md
    ├── common-pitfalls/    # "Why isn't X working?" debugging
    │   └── SKILL.md
    ├── build-incrementally/ # "Add Y to my code" guides
    │   └── SKILL.md
    └── connect-concepts/   # "How does X relate to Y?" architecture
        └── SKILL.md
```

## Key Code: SkillsProvider Integration

```python
from agent_framework import SkillsProvider

# Create SkillsProvider from skills/ directory
skills_provider = SkillsProvider(
    path="./skills",
    name="agent_framework_skills"
)

# Build agent with skills as context provider
agent = build_agent(
    model_client=client,
    identity=identity,
    tools=[...],
    context_providers=[rag_provider, skills_provider],  # Skills provided here
)
```

## Usage

```bash
# Run with skills layer
python 10_multi_RAG_agents_handsoff_skills_layer/main.py

# Re-ingest documentation
python 10_multi_RAG_agents_handsoff_skills_layer/main.py --reingest

# Enable observability
python 10_multi_RAG_agents_handsoff_skills_layer/main.py --otel

# Send to Foundry
python 10_multi_RAG_agents_handsoff_skills_layer/main.py --otel --foundry
```

## Example Interaction

```text
Available skills: explain-concept, show-code-example, getting-started, compare-approaches, ...

You: What is a context provider?
Agent: [LLM calls load_skill("explain-concept")]

**Context Provider**

A context provider supplies additional information to an agent before it responds.

**Why it matters:** Agents need domain knowledge beyond their training data. 
Context providers inject RAG results, user history, or external data into the prompt.

**Where it fits:**
```text
┌──────────────┐    ┌──────────────────┐    ┌─────────┐
│ RAG/Database │───▶│ Context Provider │───▶│  Agent  │
└──────────────┘    └──────────────────┘    └─────────┘
```

**Minimal example:**
```python
class MyProvider(BaseContextProvider):
    async def get_context(self, request):
        return [SystemMessage(content="You know about X")]
```

**Think of it like:** Middleware in web frameworks — runs before the main handler.

  🔀 Routing: triage_agent → general_specialist
  🎯 Skills used: explain-concept
  ℹ️  No function tools called (answered from RAG context + skill guidance)
```

## Environment Variables

Same as Part 9 — see [09 README](../09_multi_RAG_agents_handsoff_sdk_identity/README.md#environment-variables).

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      User Question                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     Triage Agent                             │
│  • Routes to appropriate specialist                          │
│  • No skills (routing only)                                  │
└─────────────────────────┬───────────────────────────────────┘
                          │ handoff
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│    Agents Specialist          │ │    Tools Specialist           │
├───────────────────────────────┤ ├───────────────────────────────┤
│ Identity (WHO)                │ │ Identity (WHO)                │
│ - name, role                  │ │ - name, role                  │
│ - expertise                   │ │ - expertise                   │
├───────────────────────────────┤ ├───────────────────────────────┤
│ Context Providers             │ │ Context Providers             │
│ ┌───────────────────────────┐ │ │ ┌───────────────────────────┐ │
│ │ RAG Provider (ChromaDB)   │ │ │ │ RAG Provider (ChromaDB)   │ │
│ └───────────────────────────┘ │ │ └───────────────────────────┘ │
│ ┌───────────────────────────┐ │ │ ┌───────────────────────────┐ │
│ │ SkillsProvider            │ │ │ │ SkillsProvider            │ │
│ │ - advertises skills       │ │ │ │ - advertises skills       │ │
│ │ - load_skill tool         │ │ │ │ - load_skill tool         │ │
│ │ - read_skill_resource     │ │ │ │ - read_skill_resource     │ │
│ └───────────────────────────┘ │ │ └───────────────────────────┘ │
├───────────────────────────────┤ ├───────────────────────────────┤
│ Function Tools                │ │ Function Tools                │
│ - list_supported_providers    │ │ - search_github_samples       │
└───────────────────────────────┘ └───────────────────────────────┘
```

## Skills, Tools, and Agents Mapping

### The Three-Layer Architecture

Each specialist agent has three complementary layers:

| Layer | What It Provides | Mechanism |
| ----- | ---------------- | --------- |
| **Function Tools** | Actions (data retrieval) | `@tool` decorator, explicit per agent |
| **SkillsProvider** | Teaching strategies | Context provider, shared by all |
| **RAG Provider** | Documentation knowledge | ChromaDB, domain-specific |

### Complete Agent-Tool-Skill Mapping

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                 ALL AGENTS                                          │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  SkillsProvider (context provider, shared by all specialists)                 │  │
│  │  Provides tools: load_skill, read_skill_resource                              │  │
│  │  Advertises all 10 skills (8 file-based + 2 code-defined)                     │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│      AGENTS SPECIALIST          │  │       TOOLS SPECIALIST          │
├─────────────────────────────────┤  ├─────────────────────────────────┤
│ Function Tools:                 │  │ Function Tools:                 │
│   • list_supported_providers    │  │   • search_github_samples       │
│   • find_getting_started        │  │   • find_code_examples          │
├─────────────────────────────────┤  ├─────────────────────────────────┤
│ Recommended Skills:             │  │ Recommended Skills:             │
│   • explain-concept             │  │   • show-code-example           │
│   • show-code-example           │  │   • common-pitfalls             │
│   • getting-started             │  │   • build-incrementally         │
│   • compare-approaches          │  │   • getting-started             │
│   • build-incrementally         │  │   • quick-reference             │
│   • quick-reference             │  │                                 │
└─────────────────────────────────┘  └─────────────────────────────────┘

┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│     WORKFLOWS SPECIALIST        │  │      GENERAL SPECIALIST         │
├─────────────────────────────────┤  ├─────────────────────────────────┤
│ Function Tool:                  │  │ Function Tools:                 │
│   • compare_orchestrations      │  │   • compare_concepts            │
│                                 │  │   • find_prerequisites          │
│                                 │  │   • find_related_topics         │
├─────────────────────────────────┤  ├─────────────────────────────────┤
│ Recommended Skills:             │  │ Recommended Skills:             │
│   • compare-approaches          │  │   • explain-concept             │
│   • deep-dive                   │  │   • getting-started             │
│   • connect-concepts            │  │   • connect-concepts            │
│   • getting-started             │  │   • common-pitfalls             │
│   • quick-reference             │  │   • deep-dive                   │
│                                 │  │   • environment-info            │
└─────────────────────────────────┘  └─────────────────────────────────┘
```

### Learning-Focused Tools

Each tool is designed for specific learning questions:

| Tool | Domain | Learning Purpose | Example Question |
| ---- | ------ | ---------------- | ---------------- |
| `list_supported_providers` | agents | "What LLMs can I use?" | "Show me available providers" |
| `find_getting_started` | agents | Entry point guidance | "How do I start with agents?" |
| `search_github_samples` | tools | Official code samples | "Show me @tool examples" |
| `find_code_examples` | tools | RAG-based code search (fallback) | "How do I create a tool?" |
| `compare_orchestrations` | workflows | Pattern comparisons | "Sequential vs handoff" |
| `compare_concepts` | general | Cross-domain comparisons | "Agent vs workflow" |
| `find_prerequisites` | general | Foundation building | "What should I know before RAG?" |
| `find_related_topics` | general | Connected learning | "What relates to context providers?" |

### How Tool Policies Reference Skills

Each agent's `tool_policy` in the blueprint guides when to use skills:

| Agent | Function Tools | Skill Guidance in Policy |
| ----- | -------------- | ------------------------ |
| `agents_specialist` | `list_supported_providers`, `find_getting_started` | `explain-concept`, `show-code-example`, `getting-started`, `compare-approaches` |
| `tools_specialist` | `search_github_samples`, `find_code_examples` | `show-code-example`, `common-pitfalls`, `build-incrementally` |
| `workflows_specialist` | `compare_orchestrations` | `compare-approaches`, `deep-dive`, `connect-concepts` |
| `general_specialist` | `compare_concepts`, `find_prerequisites`, `find_related_topics` | `explain-concept`, `getting-started`, `connect-concepts`, `common-pitfalls` |

### How Skills and Tools Work Together

Skills and tools are **separate complementary layers** — skills don't "use" tools, they shape how tool results are presented.

| Layer | Purpose | Example |
| ----- | ------- | ------- |
| **Tool** | Retrieves RAW DATA from RAG | `find_getting_started("agents")` → quickstart docs |
| **Skill** | Teaches HOW TO FORMAT that data | `getting-started` → numbered steps, verification |

**Example: "How do I get started with agents?"**

```text
User: "How do I get started with agents?"
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│ 1. LLM calls load_skill("getting-started")              │
│    → Gets formatting rules:                              │
│      • State the goal & time estimate                    │
│      • List prerequisites as checklist                   │
│      • Number each step clearly                          │
│      • Include verification commands                     │
└──────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│ 2. LLM calls find_getting_started("agents")             │
│    → Gets RAG data:                                      │
│      • Quickstart docs                                   │
│      • Installation instructions                         │
│      • Code examples                                     │
└──────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│ 3. LLM combines:                                         │
│    SKILL format + TOOL data = Structured tutorial        │
└──────────────────────────────────────────────────────────┘
```

**Why both?**

- Without the **tool**: The skill tells *how* to format, but has no documentation content
- Without the **skill**: The tool returns raw docs, but no pedagogy (numbered steps, verification, etc.)

### Key Design Decision: Shared Skills, Domain Tools

**All agents can use ALL skills** (SkillsProvider is shared). But:

- The **tool_policy** in the blueprint suggests which skills fit each domain
- The **DOMAIN_SKILL_NAMES** mapping in [agent_skills.py](agent_skills.py) documents recommended skills per domain
- The LLM decides to call `load_skill("explain-concept")` based on the question pattern

This means a `tools_specialist` can still use `explain-concept` if the user asks "What is the @tool decorator?" — the skill isn't restricted, just recommended.

## Next Steps

- **Part 11**: Dynamic skill activation based on user input analysis
- **Part 12**: Skill chaining and composition patterns
- **Part 13**: Custom skill scripts with `run_skill_script`
