---
name: explain-concept
description: Break down Microsoft Agent Framework concepts for learners with clear definitions and practical context.
license: MIT
compatibility:
  - python
  - typescript
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Explain Concept Skill

## Purpose

Help learners understand Microsoft Agent Framework concepts by providing clear, structured explanations that build understanding progressively.

## When to Use

Activate this skill when the user asks:
- "What is [concept]?"
- "Explain [concept]"
- "What does [term] mean?"
- "Help me understand [topic]"
- "Define [component]"

## Instructions

When explaining a MAF concept:

### 1. Start with a One-Sentence Definition
- Lead with what it IS, not what it does
- Use simple, jargon-free language
- Example: "A **context provider** is a component that supplies additional information to an agent before it responds."

### 2. Explain Why It Exists
- What problem does it solve?
- Why would a developer need this?
- Example: "Context providers exist because agents need domain knowledge beyond their training data."

### 3. Show Where It Fits
- How does it relate to other MAF components?
- Simple diagram or hierarchy if helpful
- Example: "Context providers sit between RAG systems and the agent, formatting retrieved data for the prompt."

### 4. Provide a Minimal Example
- Show the simplest possible working code
- Keep it under 10 lines if possible
- Add inline comments explaining each part

### 5. Connect to What They Know
- Relate to familiar programming concepts
- "Think of it like..." analogies help

## Output Format

```
**[Concept Name]**

[One-sentence definition]

**Why it matters:** [Problem it solves]

**Where it fits:** [Relationship to other components]

**Minimal example:**
```python
[Simple code with comments]
```

**Think of it like:** [Familiar analogy]
```

## Quality Checklist

- [ ] Definition is clear without jargon
- [ ] "Why" is explained before "how"
- [ ] Code example is minimal and runnable
- [ ] Connected to familiar concepts
- [ ] Sources cited from documentation
