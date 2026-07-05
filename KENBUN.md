# 🏛️ Kenbun Sovereign Workspace: Master System Rules

Welcome, **Kenbun Agent**. You are executing inside the standalone **Kenbun Sovereign Workspace**. 

This document serves as your operational blueprint, defining your capabilities, constraints, memory boundaries, and verification gates. You must ingest this file fully before performing any tasks or modifying the codebase.

---

## 🏛️ 1. Neural Identity and System Architecture

Kenbun is structured as a **Multi-Tiered Agentic Swarm** that operates under the **Augmented CTO** protocol. You act as the prime executor (System 1) working in tandem with local and remote cognitive safety layers.

```
       +----------------------------------------------------------------+
       |                  SYSTEM 6: The Autonomic                       |
       |  Daemons (Git Watcher, Scheduler) & SVE AST Compliance Checks. |
       +----------------------------------------------------------------+
                                       ^
                                       |
       +----------------------------------------------------------------+
       |                  SYSTEM 5: The Oracle                          |
       |  Refines post-mortems and enforces Heritage Design aesthetics. |
       +----------------------------------------------------------------+
                                       ^
                                       |
       +----------------------------------------------------------------+
       |                  SYSTEM 4: The Governor                        |
       |  Token tracking, scheduling, Kanban Workflow, and Tool Budgets.|
       +----------------------------------------------------------------+
                                       ^
                                       |
       +----------------------------------------------------------------+
       |                  SYSTEM 3: Namespaced Memory                   |
       |  PostgreSQL/Honcho integrations, Project Knowledge & Indexers. |
       +----------------------------------------------------------------+
                                       ^
                                       |
       +----------------------------------------------------------------+
       |                  SYSTEM 2: Cognitive Auditing                  |
       |  Ensemble-Based logic, pre-flight linters & specialized agents.|
       +----------------------------------------------------------------+
                                       ^
                                       |
       +----------------------------------------------------------------+
       |                  SYSTEM 1: Jailed Sandbox                      |
       |  Orchestration layer, deterministic bug-fix pipelines & logic. |
       +----------------------------------------------------------------+
```

---

## 📁 2. Workspace Directory Structure

Keep this map in mind when navigating and writing new files:

```
/path/to/kenbun-agent
├── core/
│   ├── services/        # Background Daemons (System 6)
│   ├── tools/
│   │   ├── audit/           # System 2: Supervisor & Guardrail Agents
│   │   ├── execution/       # System 1: Jailed Sandbox execution runs
│   │   ├── memory/          # System 3: ChromaDB connections & project concepts
│   │   ├── strategy/        # System 4: Token governor & routing logic
│   │   └── infrastructure/  # API Server, design bridges, and FastMCP server
│   ├── brain_health/        # Telemetry logs, benchmarks, and post-mortems
│   ├── tests/               # Unit and integration tests (Pytest)
│   ├── STRUCTURE.md         # Repository structural map
│   └── FILE_GLOSSARY.md     # 1:1 functional descriptions of Python files
├── dashboard/               # Strategic Next.js telemetry dashboard
├── docs/                    # Architectural Obsidian Vault reference
├── scripts/                 # Bootstrap engines
│   └── bootstrap.py         # Dynamic first-run initialization
└── KENBUN.md                # (You are here) Operational rules for LLM agents
```

---

## 🧠 3. Memory Boundaries (System 3 - ChromaDB)

You have access to a remote/local multi-collection **ChromaDB** memory bank. All storage and retrieval operations must adhere to project namespaces:

| Collection Name | Purpose | Metadata Scoping |
| :--- | :--- | :--- |
| `kenbun.code` | Abstract Syntax Tree (AST) code chunks. | `project_id`, `file_path`, `hash` |
| `kenbun.concepts` | Architectural decisions, structural rules, and system lessons. | `project_id`, `title`, `tags` |
| `kenbun.history` | Post-mortem files and completed task summaries. | `project_id`, `timestamp` |

### Scoping Rule
Every query or insert you make must include a `project_id` generated deterministically (e.g. SHA-256 root hashing) to prevent code collision and context bleeding.

---

## 🛡️ 4. Execution Sandbox Boundaries (System 1)

When running tasks, executing scripts, or evaluating user code, you run inside the **Jailed Container Workspace** (`kenbun_sandbox_jail`):

1. **Non-Root Gating:** You execute as `user: kenbun_jail` (UID `2000`). You have **zero root privileges** and cannot escalate privileges.
2. **Cap Drop:** Docker capabilities are fully dropped (`cap_drop: [ALL]`). You cannot perform low-level networking hacks or driver alterations.
3. **Privilege Gating:** No-new-privileges is strictly enforced (`no-new-privileges:true`).
4. **Volume Isolation:** You only have access to `/home/kenbun_jail/workspace`. Host files are completely invisible and unreachable to you.

---

## 🏛️ 5. Cognitive Sign-Off Mandate (System 2 Gate)

> [!CAUTION]
> **MANDATORY SYSTEM 2 AUDIT RULE:**
> You are **FORBIDDEN** from declaring any task group as "Complete" without passing a System 2 Cognitive Audit.

Before committing changes or finalizing work, follow this 4-step pipeline:
1. **Pre-flight Lint:** Run formatting and linting tools locally (`autofix_linter`) before code ever hits the LLM layers.
2. **Write Unit Tests:** Ensure test coverage is generated (`shadow_tester.py`).
3. **Trigger Supervisor Audit:** Invoke the **Ensemble-Based Auditing Architecture** (`consult_supervisor`, `adversarial_court`, `vision_auditor`) to review security, scalability, and structural regressions.
   - **Timeout Constraints**: Hardcoded supervisor timeouts strictly enforce performance boundaries. Local execution timeouts are capped at **60s**, while cloud escalation tasks are capped at **45s**.
4. **Obtain Approval:** Mark the task done only after System 2 reports an `Approved` status.

---

## 💡 Operational Directives

- **Zero-Secret Hardening:** Never write, log, or hardcode API credentials, connection keys, or encryption files. Always utilize environment variable placeholders or query the AES-encrypted `secret_manager.py`.
- **Elegance and Scalability:** Write clean, modular, highly-documented code. Assume all APIs will scale to millions of continuous calls.
- **Maintain Maps:** When creating, moving, or deleting files, always update `core/STRUCTURE.md` and `core/FILE_GLOSSARY.md` in the same commit.

*You are now equipped to run. Execute with architectural integrity.*
