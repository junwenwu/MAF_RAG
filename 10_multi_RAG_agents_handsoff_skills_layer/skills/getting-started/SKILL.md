---
name: getting-started
description: Guide learners through their first steps with MAF features using progressive, numbered tutorials.
license: MIT
compatibility:
  - python
  - typescript
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Getting Started Skill

## Purpose

Guide learners through their first experience with a MAF feature, from installation to a working example, using clear step-by-step instructions.

## When to Use

Activate this skill when the user asks:
- "How do I get started with..."
- "Tutorial for..."
- "Walk me through..."
- "First steps for..."
- "How do I set up..."
- "Beginner guide for..."

## Instructions

When creating a getting-started guide:

### 1. State the Goal
- What will they have at the end?
- How long will it take? (estimate)
- Example: "By the end, you'll have a working agent that answers questions. (~5 minutes)"

### 2. List Prerequisites
- Required installations (Python version, packages)
- Required accounts or API keys
- Keep this minimal — don't overwhelm beginners

### 3. Number Each Step Clearly
- One action per step
- Include the exact command or code
- Add "Why this step" for non-obvious ones

### 4. Verify Success
- How do they know each step worked?
- Include expected output or verification commands

### 5. Celebrate and Point Forward
- Congratulate them on completion
- Suggest what to learn next

## Output Format

```
# Getting Started: [Feature Name]

**Goal:** [What they'll achieve]  
**Time:** [Estimate]

## Prerequisites
- [ ] Python 3.10+ installed
- [ ] Azure OpenAI API key (or OpenAI API key)

## Steps

### Step 1: Install the SDK
```bash
pip install agent-framework-azure-ai --pre
```
**Verify:** Run `pip show agent-framework` — you should see version info.

### Step 2: Set Up Credentials
```bash
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com"
```
**Why:** The SDK reads these environment variables automatically.

### Step 3: Create Your First Agent
```python
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework import Agent

client = AzureOpenAIChatClient()
agent = Agent(model_client=client, instructions="You are a helpful assistant.")

response = await agent.run("What can you help me with?")
print(response.content)
```

**Verify:** You should see the agent's response printed.

## 🎉 Success!

You now have a working MAF agent. Next:
- **Add a tool:** See "function tools" guide
- **Add memory:** See "context providers" guide
```

## Quality Checklist

- [ ] Goal is clear and achievable
- [ ] Prerequisites are minimal
- [ ] Each step is one action
- [ ] Verification included for key steps
- [ ] Commands are copy-paste ready
- [ ] Next steps guide continued learning
