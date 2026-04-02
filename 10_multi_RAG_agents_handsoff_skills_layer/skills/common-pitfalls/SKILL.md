---
name: common-pitfalls
description: Warn learners about common MAF mistakes and how to avoid them.
license: MIT
compatibility:
  - python
  - typescript
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Common Pitfalls Skill

## Purpose

Help learners avoid common mistakes when working with MAF by explaining what goes wrong, why, and how to fix it.

## When to Use

Activate this skill when the user:
- Is about to do something that commonly fails
- Asks about errors or unexpected behavior
- Asks "Why isn't my [X] working?"
- Asks "What should I watch out for?"
- Mentions symptoms of common issues

## Instructions

When highlighting pitfalls:

### 1. Name the Pitfall Clearly
- Short, memorable name
- Example: "Forgetting to await async calls"

### 2. Show What Goes Wrong
- The broken code or bad pattern
- The error message or unexpected behavior

### 3. Explain Why It Fails
- Root cause, not just symptoms
- Connect to how MAF works

### 4. Show the Fix
- Corrected code
- Highlight what changed

### 5. Give Prevention Tips
- How to avoid this in the future
- IDE/linter settings that help

## Output Format

```
## ⚠️ Pitfall: [Name]

**What goes wrong:**
```python
# Broken code
agent.run("Hello")  # Missing await!
```
**Error:** `RuntimeWarning: coroutine 'run' was never awaited`

**Why this happens:**
[Explanation of root cause — e.g., "agent.run() is async and returns a coroutine, not a result"]

**The fix:**
```python
# Corrected code
response = await agent.run("Hello")  # Add await
```

**Prevention:**
- Use `async def main()` and `asyncio.run(main())`
- Enable "no-await-in-loop" linter rules
- VS Code shows warnings for unawaited coroutines
```

## Common MAF Pitfalls to Know

When relevant, mention these frequent issues:

1. **Forgetting await** — Agent methods are async
2. **Missing @tool decorator** — Functions aren't recognized as tools
3. **Wrong return type** — Tools must return strings
4. **Missing API keys** — Environment variables not set
5. **Token limits exceeded** — Context too large for model
6. **Approval mode confusion** — Tools not executing

## Quality Checklist

- [ ] Pitfall has a clear, memorable name
- [ ] Broken code is realistic
- [ ] Error message or symptom shown
- [ ] Root cause explained (not just "do this instead")
- [ ] Fixed code is correct
- [ ] Prevention tips are actionable
