---
name: build-incrementally
description: Guide learners to add features to existing MAF code step by step.
license: MIT
compatibility:
  - python
  - typescript
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Build Incrementally Skill

## Purpose

Help learners extend their existing MAF code by adding new features incrementally, showing exactly what to add and where.

## When to Use

Activate this skill when the user:
- Has working code and wants to add a feature
- Asks "How do I add [feature] to my agent?"
- Says "I have X, now I want Y"
- Asks "What's the next step after [basic example]?"

## Instructions

When guiding incremental building:

### 1. Acknowledge Their Starting Point
- Reference what they have
- "Building on your basic agent..."

### 2. Show Before and After
- "Before" = their current code (simplified)
- "After" = code with the new feature
- Highlight additions with comments

### 3. Explain Each Addition
- What line(s) were added?
- Why is each addition needed?

### 4. Show It Working
- Expected new behavior
- Sample interaction demonstrating the feature

### 5. Suggest Next Increments
- What could they add after this?
- Progressive complexity path

## Output Format

```
# Adding [Feature] to Your Agent

**Starting from:** Basic agent with [what they have]

## Before (Your Current Code)
```python
agent = Agent(
    model_client=client,
    instructions="You are helpful."
)
```

## After (With [Feature])
```python
from agent_framework import tool  # NEW: Import tool decorator

@tool  # NEW: Mark function as a tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""  # NEW: Docstring becomes description
    return f"Weather in {city}: Sunny, 72°F"

agent = Agent(
    model_client=client,
    instructions="You are helpful.",
    tools=[get_weather],  # NEW: Add tools list
)
```

## What Changed

| Addition | Purpose |
|----------|---------|
| `from agent_framework import tool` | Import the decorator |
| `@tool` | Marks function as callable by the agent |
| `tools=[get_weather]` | Registers the tool with the agent |

## Try It

```python
response = await agent.run("What's the weather in Seattle?")
# Agent will call get_weather("Seattle") and include the result
```

## Next Steps

Now that you have tools, you can:
- **Add multiple tools:** `tools=[tool1, tool2]`
- **Add tool approval:** Set `approval_mode="always_require"`
- **Add RAG context:** See "context providers" guide
```

## Quality Checklist

- [ ] Starting point is acknowledged
- [ ] Before/after code is clear
- [ ] New lines are marked with comments
- [ ] Each addition is explained
- [ ] Working example shows new behavior
- [ ] Next steps continue the learning path
