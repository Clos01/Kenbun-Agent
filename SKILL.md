---
name: kenbun-agent
description: Standalone containerized Kenbun Agentic Swarm and FastMCP Server
---

# 🏛️ Kenbun-Agent Swarm: AI Agent Operational Guide

Welcome, Agent. You have been loaded into a **Kenbun-Agent Workspace**. 

This workspace is a standalone, decoupled, containerized environment that unifies a **FastMCP Python Swarm Server**, a **ChromaDB Vector Database**, a **Next.js Telemetry Dashboard**, and a **Jailed Sandbox Execution Container** under a secure local-first architecture.

This document serves as your **Master Skill Blueprint**. Read this fully to understand how to interact with the database, compile/run code in the sandbox jail, and execute autonomous tasks with maximum efficiency.

---

## 🛠️ 1. Workspace Topology

The workspace is organized into clean, modular folders:

```
/ (Project Root)
├── core/
│   ├── tools/
│   │   ├── audit/           # System 2: Supervisor Ensemble & Guardrail checks
│   │   ├── execution/       # System 1: Jailed Sandbox runner
│   │   ├── memory/          # System 3: ChromaDB connect & code indexers
│   │   ├── strategy/        # System 4: Token budget & decision routing
│   │   └── utils/           # Shared utilities (llm_router, paths, keys)
│   ├── brain_health/        # Telemetry logs, benchmarks, and post-mortems
│   └── tests/               # Standalone unit and integration tests (Pytest)
├── dashboard/               # Next.js 18 Telemetry visualizer UI
├── docs/
│   └── PROXMOX_PORTAINER_DEPLOYMENT.md # Proxmox VE & Portainer local home-lab guide
├── docker-compose.yml       # Unified Docker stack orchestration
├── pyproject.toml           # Modern package manifest with [ml] split
├── README.md                # General developer guide
└── SKILL.md                 # (You are here) Operational instructions for AI agents
```

---

## 🔑 2. Standalone Environment Bootstrapping

The system is configured via environment variables inside a local `.env` file (copied from `.env.example`):

1.  **Chroma Host:** ChromaDB runs in a container at `CHROMA_HOST=chromadb` inside the docker compose network, or resolves to `localhost` when queried natively.
2.  **Decoupled LLM Gateway:** All model queries route through the `llm_router.py` class, utilizing `PRIMARY_LLM_URL` (usually local Ollama `http://localhost:11434/v1` or LM Studio) and dynamically falling back to `FALLBACK_LLM_URL` on exceptions or rate limits.
3.  **Automatic Seeding:** On first boot, the config singleton dynamically creates standard directories (`core/brain_health/logs/`) and touches empty telemetry logs (`usage_stats.json`, `BENCHMARKS.json`) to guarantee error-free executions.

---

## 🧠 3. Chroma DB Vector Memory Scopes (System 3)

You have access to a namespaced ChromaDB vector memory. All embeddings must follow project filters to prevent context bleed:

*   **`kenbun.code`:** Syntactically chunked codebase nodes.
*   **`kenbun.concepts`:** Permanent architectural decisions, system rules, and design tokens.
*   **`kenbun.history`:** Swarm logs and historical post-mortems.

### Retrieval Scoping Rule:
Always query and insert using a deterministically generated `project_id` (via SHA-256 root hashing) inside your filters:
```python
where={"project_id": project_id}
```

---

## 🛡️ 4. Restricted Execution Jail (System 1)

When running shell scripts, testing code, or evaluating proposed fixes, you execute inside the `hermes_sandbox_jail` container:

1.  **Isolated User:** You run as `user: hermes_jail` (UID `2000`). You have **zero root privileges** and cannot execute `sudo` or access host files.
2.  **Resource Limits:** Docker restricts CPU and memory consumption.
3.  **Dropped Capabilities:** Linux capabilities are fully dropped (`cap_drop: [ALL]`) and privilege escalation is blocked (`no-new-privileges:true`).

---

## 🏛️ 5. The System 2 Cognitive Sign-Off Gate

> [!CAUTION]
> **MANDATORY COGNITIVE AUDIT GATE:**
> You are **FORBIDDEN** from declaring any task group or file modification as "Complete" without passing a System 2 Cognitive Audit.

Before committing changes, you must:
1.  **Format & Lint:** Run `autofix_linter` to resolve style regressions.
2.  **Verify Tests:** Trigger `PYTHONPATH=core pytest core/tests` to verify 100% green execution.
3.  **Supervisor Review:** Invoke `consult_supervisor(user_proposal, code_snippet)` to obtain consensus approval.

---

## 💡 Operational Directives

*   **Absolute Key Gating:** Never print, write, hardcode, or log any API credentials or connection keys. Route all queries through `llm_router.py` or retrieve them from the encrypted `secret_manager.py`.
*   **Decoupled Relative Paths:** Never use absolute paths pointing to specific host folders. Always discover paths dynamically starting from `__file__`.
*   **Parity Updates:** When creating, moving, or deleting files, update `core/STRUCTURE.md` and `core/FILE_GLOSSARY.md` in the same commit to keep the system map fully updated.

*You are now initialized. Build with maximum security and architectural integrity.*
