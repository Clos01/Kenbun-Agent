# 🏛️ KENBUN: THE NEURAL HIERARCHY

This is the master map of the Kenbun system, a Twelve-Factor, Sovereign Intelligence engine designed for infinite scalability and total observability.

## 🌌 The Six Systems of Intelligence

Kenbun is organized into a nested hierarchy of reasoning, from immediate reflexes to long-term architectural planning.

### 🧘 System 1: The Reflex (Immediate Action)
- **Component**: `core/tools/infrastructure/server.py` & Orchestration Layer
- **Function**: Immediate tool execution, file manipulation, and deterministic `bug_fix` pipelines.
- **Goal**: Execution latency < 100ms.

### 🧠 System 2: The Supervisor (Reasoning & Ethics)
- **Component**: `core/tools/audit/` (Ensemble-Based Auditing Architecture)
- **Function**: Audits System 1's proposals via specialized agents (e.g. `adversarial_court`, `guardrail_agent`, `vision_auditor`) and pre-flight linters.
- **Goal**: Zero "Draft Quality" code in production.

### 🐝 System 3: The Hivemind (Short-Term Memory)
- **Component**: `core/tools/memory/` (PostgreSQL / Honcho)
- **Function**: Context ingestion (`code_indexer`, `digester`, `pdf_ingestor`, `knowledge_manager`) and cross-agent memory management.
- **Goal**: Total codebase awareness and robust knowledge retrieval.

### ⚖️ System 4: The Governor (Bayesian Intelligence)
- **Component**: `core/tools/strategy/`
- **Function**: Token tracking, atomic file locks, scheduling, Kanban Workflow Logic (`kanban_tools.py`, `delegation_tool.py`), and Neural Evaluation.
- **Goal**: Cost-efficient, high-probability execution paths and efficient task distribution.

### 🔮 System 5: The Oracle (Architectural Vision)
- **Component**: `core/tools/design/oracle.py` & `core/tools/audit/gemini_reviewer.py`
- **Function**: Long-term planning, research, and deep architectural audits. Grounded in official documentation and the **Heritage** Design System (DESIGN.md).
- **Goal**: Maintaining the Heritage aesthetic and architectural integrity.

### 🌌 System 6: The Autonomic (Self-Healing & SVE)
- **Component**: `core/services/` (Daemons) & `core/tools/autonomic/` (Correctors)
- **Function**: Monitors the system via `sve_pulse.py`, `git_push_watcher_daemon.py`, and `scheduler_daemon.py`. The **Sovereign Verification Engine (SVE)** enforces AST structural laws project-wide.
- **Goal**: Infinite system stability, task scheduling, and total architectural grounding.

---

## 📂 Repository Structure

```text
Kenbun/
├── core/                       # The Intelligence Core (Twelve-Factor, Modular)
│   ├── services/               # Background Daemons (System 6)
│   ├── tools/                  # The Toolbelt (Systems 1-5)
│   │   ├── audit/              # Supervisor & Oracle logic
│   │   ├── design/             # Design Oracle & UI Rules
│   │   ├── execution/          # Worker Nodes & Sandbox
│   │   ├── infrastructure/     # API Server, Config, Orchestrator
│   │   ├── memory/             # Hivemind & Vector Store
│   │   ├── strategy/           # Bayesian Governor & Token Logic
│   │   └── utils/              # Pathing, Telemetry, Shims
│   └── STRUCTURE.md            # Technical Master Map (Local)
├── dashboard/                  # The Observatory (Next.js 16, Heritage)
│   ├── src/
│   │   ├── app/                # Next.js App Router
│   │   ├── components/         # Galaxy Map, Fleet View, Kanban
│   │   └── lib/                # UI Config & API Hooks
│   ├── brain_health/               # Live Telemetry, Benchmarks & Logs
├── docs/                       # Kenbun Obsidian Vault (Complete System Docs)
├── scripts/                    # Setup, Guided Bootstrap & User CLI Entry Points
│   ├── bootstrap.py            # Interactive guided onboarding setup & stack manager
│   ├── terminal_chat.py        # Kenbun Cognitive interactive terminal shell (termchat)
│   ├── full_audit_scan.py      # Autonomic codebase compliance & quality scanner
│   └── agent_bus.py            # Real-time event-bus channels for async agents
├── DESIGN.md                   # Heritage Design System (Source of Truth)
├── LEGION_SPECULATIVE_RUN.md   # System 2 Speculative Server Blueprint
└── STRUCTURE.md                # Root System Map (Synchronized)
```

## 🛠️ Operating Protocols

1.  **Twelve-Factor Compliance**: All configuration must be in `core/tools/infrastructure/config.py` or `.env`. No hardcoded paths.
2.  **Heritage Design**: All UI components must adhere to the tokenized palette (Limestone/Boston Clay) and the radii defined in the root `DESIGN.md`.
3.  **Absolute Imports**: All internal imports must use the `from tools.*` scheme.
4.  **Sovereign Verification (SVE)**: Core logic must be decorated with `@sovereign_logic` or verified by the `sve_pulse.py` to ensure it is grounded in the project's architectural source of truth.
4.  **TDD Mandate**: Code without tests is "Draft Quality" and will be rejected by the Supervisor.

---

*“Stability through constant correction.”* — The Kenbun Autonomic
