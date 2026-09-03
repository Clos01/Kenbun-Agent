---
name: "codebase-cognitive-explainer"
description: "Autonomously parses code files, components, and functions into Plain-English Variable/Function Dictionaries and Visual Mental Models designed for ADHD and neurodivergent operators."
version: "1.0.0"
license: "MIT"
---

# Codebase Cognitive Explainer (ADHD Code Translator)

Autonomous Variable, Function, & Architecture Deconstructor.

Version: 1.0.0  
License: MIT

## Purpose

This skill deconstructs complex code into 3 simple, zero-friction layers:
1. **The 1-Sentence Purpose**: What this file or function actually achieves.
2. **The Variable & Function Dictionary**: A clean table translating variables into plain-English meanings.
3. **The Data Flow Map**: A Mermaid diagram showing where data enters, transforms, and outputs.

---

## CLI Tool Usage (`bin/code-clarity`)

```bash
# Deconstruct any code file into plain English
bin/code-clarity /path/to/component.tsx

# Example on active Next.js app:
bin/code-clarity /Users/carlosrivas/Dev/Projects/eko-veritas-prod/src/components/ui/unified-prompt-diff.tsx
```
