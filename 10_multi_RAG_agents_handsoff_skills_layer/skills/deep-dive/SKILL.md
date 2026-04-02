---
name: deep-dive
description: Provide detailed technical explanations for advanced MAF topics with architecture insights.
license: MIT
compatibility:
  - python
  - typescript
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Deep Dive Skill

## Purpose

Provide thorough technical explanations for learners who want to understand MAF internals, architecture decisions, or advanced patterns.

## When to Use

Activate this skill when the user asks:
- "How does [X] work internally?"
- "Explain the architecture of..."
- "Deep dive into..."
- "Technical details of..."
- "What happens when..."
- "Under the hood of..."

## Instructions

When providing a deep dive:

### 1. Set Expectations
- Who is this for? (intermediate/advanced)
- What will they learn?
- What should they know first?

### 2. Explain the Architecture
- Components involved
- How they interact
- Data flow diagram if helpful

### 3. Walk Through the Lifecycle
- Step-by-step: what happens when X occurs?
- Include internal details (classes, methods)
- Note where extension points exist

### 4. Discuss Design Decisions
- Why was it built this way?
- What trade-offs were made?
- How does this compare to alternatives?

### 5. Show Advanced Usage
- Examples that leverage the internals
- When would you customize at this level?

## Output Format

```
# Deep Dive: [Topic]

**Audience:** [Intermediate/Advanced learners who already understand X]

## Overview

[2-3 sentence summary of what we'll cover]

## Architecture

[Component diagram or description]

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Component A │───▶│ Component B │───▶│ Component C │
└─────────────┘    └─────────────┘    └─────────────┘
```

## Lifecycle Walkthrough

When [action] happens:

1. **Step 1:** [What happens, which class/method]
2. **Step 2:** [Next step]
3. **Step 3:** [Next step]

## Design Decisions

**Why [design choice]?**
- [Reason 1]
- [Reason 2]
- Trade-off: [What was sacrificed]

## Advanced Example

```python
# Example leveraging internal knowledge
```

**When to use this:** [Specific scenario]
```

## Quality Checklist

- [ ] Prerequisites clearly stated
- [ ] Architecture is visualized or clearly described
- [ ] Lifecycle covers internal steps
- [ ] Design decisions are explained
- [ ] Advanced example demonstrates practical use
- [ ] Sources cited from documentation
