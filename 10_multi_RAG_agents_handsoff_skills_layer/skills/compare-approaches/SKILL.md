---
name: compare-approaches
description: Compare MAF patterns, orchestrations, and providers to help learners make informed decisions.
license: MIT
compatibility:
  - python
  - typescript
metadata:
  author: MAF Learning System
  version: "1.0"
  domain: learning
---

# Compare Approaches Skill

## Purpose

Help learners understand the differences between MAF options (orchestrations, providers, patterns) so they can choose the right approach for their needs.

## When to Use

Activate this skill when the user asks:
- "Compare X and Y"
- "What's the difference between..."
- "X vs Y"
- "Should I use X or Y?"
- "When would I choose..."
- "Pros and cons of..."

## Instructions

When comparing MAF approaches:

### 1. State What's Being Compared
- Name both options clearly
- Briefly note what category they're in

### 2. Create a Comparison Table
- Use clear criteria relevant to the decision
- Keep to 4-6 rows max
- Use ✅/❌ or clear values

### 3. Explain the Key Difference
- What's the ONE main distinction?
- Make this memorable

### 4. Give Decision Guidance
- "Choose A when..." / "Choose B when..."
- Tie to specific use cases

### 5. Show Minimal Code for Each
- Side-by-side if possible
- Just enough to see the API difference

## Output Format

```
# Comparing: [Option A] vs [Option B]

Both are [category]. Here's how they differ:

| Criteria | [Option A] | [Option B] |
|----------|------------|------------|
| [Criterion 1] | [Value] | [Value] |
| [Criterion 2] | [Value] | [Value] |
| [Criterion 3] | [Value] | [Value] |
| [Criterion 4] | [Value] | [Value] |

**Key difference:** [One-sentence summary of the main distinction]

## When to Choose

**Choose [Option A] when:**
- [Use case 1]
- [Use case 2]

**Choose [Option B] when:**
- [Use case 1]
- [Use case 2]

## Code Comparison

**[Option A]:**
```python
# Minimal example
```

**[Option B]:**
```python
# Minimal example
```
```

## Quality Checklist

- [ ] Both options clearly named
- [ ] Table has relevant criteria (not filler)
- [ ] Key difference is memorable
- [ ] Decision guidance is actionable
- [ ] Code shows the API difference
- [ ] Sources cited from documentation
