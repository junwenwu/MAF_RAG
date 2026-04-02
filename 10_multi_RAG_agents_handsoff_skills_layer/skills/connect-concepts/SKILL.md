---
name: connect-concepts
description: Help learners see how MAF concepts relate to each other and to familiar programming patterns.
license: MIT
compatibility:
  - python
  - typescript
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Connect Concepts Skill

## Purpose

Help learners build a mental model of MAF by showing how concepts connect to each other and to familiar programming patterns they already know.

## When to Use

Activate this skill when the user:
- Asks "How does X relate to Y?"
- Seems confused about how pieces fit together
- Asks "Is X like [familiar concept]?"
- Asks "What's the big picture?"
- Needs help seeing the overall architecture

## Instructions

When connecting concepts:

### 1. Identify the Concepts to Connect
- Which MAF concepts are involved?
- What familiar concepts might help?

### 2. Draw the Relationship
- Use visual diagrams when helpful
- Show how data/control flows between them

### 3. Use Familiar Analogies
- "Think of X like Y in [familiar framework]"
- "This is similar to [common pattern]"

### 4. Explain Why the Connection Matters
- How does understanding this help them?
- What can they now do that they couldn't before?

### 5. Show the Connection in Code
- Small example that shows both concepts together

## Output Format

```
# Connecting: [Concept A] and [Concept B]

## How They Relate

[Concept A] provides [what] to [Concept B].

```
┌─────────────────┐         ┌─────────────────┐
│   [Concept A]   │────────▶│   [Concept B]   │
│ [what it does]  │  [how]  │ [what it does]  │
└─────────────────┘         └─────────────────┘
```

## Familiar Analogy

**If you know [familiar concept]:** Think of [Concept A] like [analogy].

For example:
- **Context providers** are like middleware in web frameworks — they run before the main handler
- **Tools** are like API endpoints the agent can call
- **Orchestrations** are like workflow engines that coordinate multiple workers

## Why This Matters

Understanding this connection helps you:
- [Benefit 1]
- [Benefit 2]

## In Code

```python
# Example showing both concepts working together
```
```

## Common MAF Concept Connections

| If they ask about... | Connect to... | Analogy |
|---------------------|---------------|---------|
| Context providers + RAG | Context providers *use* RAG | "RAG fills the context provider's data" |
| Tools + Agents | Tools *extend* agents | "Tools are like methods an agent can call" |
| Orchestrations + Agents | Orchestrations *coordinate* agents | "Like a conductor directing musicians" |
| Identity + Instructions | Identity *informs* instructions | "Who you are shapes what you say" |

## Quality Checklist

- [ ] Concepts are clearly named
- [ ] Relationship is visualized or clearly stated
- [ ] Familiar analogy is apt and helpful
- [ ] "Why this matters" connects to learner's goals
- [ ] Code example demonstrates the connection
