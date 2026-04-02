---
name: show-code-example
description: Provide runnable code examples with line-by-line explanations to help learners understand MAF patterns.
license: MIT
compatibility:
  - python
  - typescript
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Show Code Example Skill

## Purpose

Help learners understand Microsoft Agent Framework through well-explained, runnable code examples that they can copy and modify.

## When to Use

Activate this skill when the user asks:
- "Show me how to..."
- "Can you give me an example of..."
- "Show me code for..."
- "What does the code look like for..."
- "Give me a sample..."

## Instructions

When providing code examples:

### 1. Start with Context
- Briefly explain what the code accomplishes
- State any prerequisites (imports, environment variables)

### 2. Show Complete, Runnable Code
- Include ALL necessary imports
- Use realistic but simple values
- Add comments on non-obvious lines
- Code MUST be copy-paste runnable

### 3. Break Down Key Sections
- After the code block, explain important parts
- Number the key lines and reference them
- Explain WHY, not just WHAT

### 4. Show Expected Output
- What will the user see when they run this?
- Include sample output if helpful

### 5. Suggest Next Steps
- "To customize this, try changing..."
- "To add [feature], see [topic]"

## Output Format

```
**What this does:** [One-sentence summary]

**Prerequisites:** [What's needed before running]

```python
# Complete, runnable code
from agent_framework import Agent  # Core agent class

# Create an agent with instructions
agent = Agent(
    model_client=client,           # Your configured LLM client
    instructions="You are helpful." # System prompt
)

# Run the agent
response = await agent.run("Hello!")
print(response.content)
```

**Key points:**
1. **Line 4:** `model_client` connects the agent to your LLM
2. **Line 5:** `instructions` sets the agent's persona
3. **Line 9:** `run()` is async — use `await`

**Expected output:**
```
Hello! How can I help you today?
```

**Next steps:**
- Add a tool: see "function tools" documentation
- Add RAG: see "context providers" documentation
```

## Quality Checklist

- [ ] Code is complete and runnable (no missing imports)
- [ ] Comments explain non-obvious parts
- [ ] Key lines are explained after the block
- [ ] Expected output is shown
- [ ] Next steps guide further learning
- [ ] Sources cited if code is from documentation
