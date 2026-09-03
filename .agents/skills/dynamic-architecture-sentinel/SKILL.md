---
name: "dynamic-architecture-sentinel"
description: "Enforces zero-hardcoding dynamic plugin architectures and transparent black-box observability across all codebases. Guarantees code scales infinitely without manual switch/case or registry maintenance."
version: "1.0.0"
license: "MIT"
---

# Dynamic Architecture Sentinel (Black-Box Illumination Protocol)

Autonomous Dynamic Architecture & Observability Standard for Sovereign Agentic Systems.

Version: 1.0.0  
License: MIT

## Purpose

AI systems thrive when bound by **strict schema contracts** while remaining **infinitely dynamic in execution**.

This skill enforces two non-negotiable laws across all codebases (Kenbun, Eko Veritas, NeverMiss, etc.):
1. **Zero-Hardcoding Law**: No static switch/case routers or hardcoded list arrays. Everything must auto-discover dynamically from directory structures, schemas, or configs.
2. **Black-Box Illumination Law**: Every autonomous decision made by an agent must output structured, plain-English telemetry explaining *what* was evaluated, *why* this path was chosen, and *what* happens next.

---

## The 4 Pillars of Dynamic Architecture

```mermaid
flowchart TD
    Contract["1. Strict Schema Contract\n(TypeScript Interface / Pydantic Model)"] --> Discovery["2. Dynamic Auto-Discovery\n(Hot-reloads directories & configs without code edits)"]
    Discovery --> Decision["3. Autonomous Path Selection\n(Agent evaluates state & picks optimal route)"]
    Decision --> Illumination["4. Black-Box Illumination\n(Transparent plain-English telemetry rendered to operator)"]
```

---

## Verification & CLI Tool

```bash
# Audit a codebase for hardcoded static anti-patterns:
bin/dynamic-audit /path/to/project
```
