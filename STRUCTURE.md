# 🏛️ KENBUN: THE NEURAL HIERARCHY

This is the master map of the Kenbun system, a Twelve-Factor, Sovereign Intelligence engine designed for infinite scalability and total observability.

## 🌌 The Six Systems of Intelligence

Kenbun is organized into a nested hierarchy of reasoning, from immediate reflexes to long-term architectural planning.

### 🧘 System 1: The Reflex (Immediate Action)
- **Component**: `FastMCP` / `server.py`
- **Function**: Immediate tool execution and file manipulation.
- **Goal**: Execution latency < 100ms.

### 🧠 System 2: The Supervisor (Reasoning & Ethics)
- **Component**: `supervisor_agent.py` / `LM Studio (Local)`
- **Function**: Audits System 1's proposals for security, design consistency, and logic errors.
- **Goal**: Zero "Draft Quality" code in production.

### 🐝 System 3: The Hivemind (Short-Term Memory)
- **Component**: `chroma_db_connect.py` / `repo_mapper.py`
- **Function**: Semantic indexing of the current repository. Maps all "Neural Signals" (functions, variables, logic) into a vector space.
- **Goal**: Total codebase awareness.

### ⚖️ System 4: The Governor (Bayesian Intelligence)
- **Component**: `strategy_manager.py` / `token_governor.py`
- **Function**: Tracks tool performance (Success/Failure) using Bayesian alpha/beta weights. Manages financial budgets and API rate limits.
- **Goal**: Cost-efficient, high-probability execution paths.

### 🔮 System 5: The Oracle (Architectural Vision)
- **Component**: `oracle.py` / `gemini_reviewer.py`
- **Function**: Long-term planning, research, and deep architectural audits. Grounded in official documentation and the **Heritage** Design System (DESIGN.md).
- **Goal**: Maintaining the Heritage aesthetic and architectural integrity.

### 🌌 System 6: The Autonomic (Self-Healing & SVE)
- **Component**: `swarm_daemon.py` / `sve_pulse.py` (System 5.1)
- **Function**: Monitors the system for regressions, technical debt, and logical hallucinations. The **Sovereign Verification Engine (SVE)** enforces AST structural laws and logical provenance project-wide.
- **Goal**: Infinite system stability and total architectural grounding.

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
