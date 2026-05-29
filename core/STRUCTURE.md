# 🏗️ Kenbun/core: Master System Map

This is the definitive technical documentation for the Kenbun Professional Architecture

The system is segmented into two primary domains to ensure infinite scalability and professional separation of concerns.

## 📂 Project Hierarchy

* **kenbun/core/**: The "Brain" and "Engine" of the system.
  * **tools/**: All MCP tools, strategy logic, and the API server.
  * **brain_health/**: Pure telemetry stream (JSON, JSONL, Logs).
  * **benchmarks/**: Performance and reliability testing scripts.
  * **ingestion/**: Knowledge processing logic.
* **kenbun/dashboard/**: The "Observatory" (Next.js 16).
  * **src/**: Real-time telemetry visualization and Intelligence Stream.

## 🏛️ The Neural Hierarchy (Systems 1-5)

| Layer | Component | Location | Responsibility |
| :--- | :--- | :--- | :--- |
| **System 6** | Sensory | `tools/infrastructure/` | Transcription, voice commands, async native ears, and remote feedback. |
| **System 5** | Design Discovery | `tools/infrastructure/` | Strategic briefing, Open Design parity, and Skill Protocols. |
| **System 5** | Reflection | `tools/audit/` | Distilling experience into long-term Hivemind knowledge. |
| **System 4** | Strategy | `tools/strategy/` | Bayesian routing, token governance, and decision logic. |
| **System 3** | Memory | `tools/memory/` | Semantic retrieval (ChromaDB) for namespaced project concepts. |
| **System 2** | Audit | `tools/audit/` | Executive code review and high-fidelity verification. |
| **System 2c** | Guardrail | `tools/audit/` | Fast, deterministic security and style constraints. |
| **System 1** | Execution | `tools/execution/` | Sandboxed code testing, repo scanning, and research. |

---

## 📂 Detailed File Directory

### 🧠 System 4 & 5: Strategy & Reflection
*   **`tools/strategy/decision_logic.py`**: Hardened routing engine that orchestrates sub-modules.
*   **`tools/strategy/keyword_processor.py`**: [NEW] Encapsulates signal detection and regex matching.
*   **`tools/strategy/neural_learner.py`**: [NEW] Handles Alpha-Go style reward/decay weights.
*   **`tools/strategy/token_governor.py`**: Real-time budget enforcement and cost tracking.
*   **`tools/strategy/strategy_manager.py`**: Manages tool intelligence weights (Bayesian sampling).
*   **`tools/audit/reflection_agent.py`**: Self-auditing loop that generates Hivemind entries (System 5).

### 📖 System 3: Memory & Knowledge
*   **`tools/memory/knowledge_manager.py`**: Core API for ChromaDB interactions (CRUD concepts).
*   **`tools/memory/pdf_ingestor.py`**: Ingests technical PDFs to teach the AI new frameworks.
*   **`tools/memory/code_indexer.py`**: Semantic indexing of the current repository's source code.
*   **`tools/memory/repo_mapper.py`**: Generates logical topologies of the codebase for RAG.
*   **`tools/memory/chroma_db_connect.py`**: Low-level connection handler for remote ChromaDB.
*   **`tools/memory/error_memory.py`**: [NEW] Tracks recurring errors specifically for orchestrator recovery.
*   **`tools/memory/ALGORITHMS.md`**: [NEW] Mathematical and logical documentation of the engine core.

### 🛡️ System 2 & 2c: Audit & Quality
*   **`tools/audit/supervisor_agent.py`**: (System 2) Executive audit agent with Tiered Ensemble logic.
*   **`tools/audit/ensemble_audit.py`**: [NEW] Multi-model consensus auditor (Weighted Parallel Voting).
*   **`tools/audit/guardrail_agent.py`**: (System 2c) Continuous guardrail for fast security audits.
*   **`tools/audit/gemini_reviewer.py`**: Cloud-based deep code review and audio transcription.
*   **`tools/audit/consult_architect.py`**: Internal consultation tool for complex structural decisions.
*   **`tools/audit/ui_designer.py`**: Specialized agent (UI Expert) for enforcing premium design standards. **MANDATE:** Must consult Stitch for all web tasks.

### 🛠️ System 1: Execution & Tools
*   **`tools/execution/sandbox_runner.py`**: Runs generated code in a safe, isolated environment.
*   **`tools/execution/shadow_tester.py`**: Automatically generates unit tests for new/modified code.

### 📡 System 6: Sensory Layer
*   **`tools/infrastructure/swarm_voice.py`**: Telegram voice-note listener with Gemini 3 transcription.
*   **`tools/infrastructure/native_ears.py`**: [ASYNC] macOS native always-listening sensory layer with ensemble gating.
*   **`tools/infrastructure/design_bridge.py`**: [NEW] ACP-to-MCP Bridge for orchestrating 13+ external design CLIs.
*   **`tools/utils/notifications.py`**: Native macOS notification bridge and audio feedback (say).

### 🔌 Infrastructure Layer (`tools/infrastructure/`)
*   **`tools/infrastructure/orchestrator.py`**: The main state-machine engine. Features non-blocking connectivity heartbeats, circuit breakers, and automatic local-PC failover.
*   **`tools/infrastructure/server.py`**: The MCP server that exposes these tools to your IDE.
*   **`tools/infrastructure/agents.py`**: Definitions for Agent Personas (Architect, Security, Swarm).
*   **`tools/infrastructure/tech_registry.py`**: Central registry of allowed technologies and documentation URIs.
*   **`tools/infrastructure/api_server.py`**: FastAPI wrapper with real-time SSE topology streaming (`/api/v1/topology/stream`).

### 🛠️ Shared Utilities (`tools/utils/`)
*   **`telemetry.py`**: Performance benchmarking and success-rate tracking.
*   **`notifications.py`**: Native macOS notification bridge.
*   **`secret_manager.py`**: AES-encrypted storage for API keys.
*   **`backtracker.py`**: Checkpoint/Restore system for rolling back failed code changes.
*   **`error_memory.py`**: Tracks recurring errors to prevent the AI from repeating mistakes.
*   **`path_utils.py`**: Universal path resolution for cross-platform (Mac/PC) compatibility.
*   **`workspace_manager.py`**: [NEW] Dynamic project discovery and registry management.
*   **`maze_protocol.py`**: [NEW] Utility for "Backward Verification" (The Maze Protocol).

### 🩺 Sovereign Testing & Benchmarks
*   **`tests/`**: Functional unit and integration tests.
    *   **`test_autopilot.py`**: [NEW] Automated tests for dynamic VRAM/RAM platform-sensing profiles.
    *   **`test_ralph_loop.py`**: [NEW] Automated tests for the autonomic Ralph-Loop self-healing recovery engine.
*   **`benchmarks/benchmark_protocol.py`**: Performance verification suite.
*   **`benchmarks/chaos_orchestrator.py`**: Stress-test script for budget and network failure.

### 🧠 Self-Evolution & Awareness [NEW]
*   **`dev/self_evolution/awareness_engine.py`**: Runs closed-loop State of the Union (SOTU) audits, evaluating memory density, tool performance, and security posture.

### 📊 Brain Health (Telemetry)
*   **`brain_health/usage_stats.json`**: Current session token expenditure log.
*   **`brain_health/BENCHMARKS.json`**: Historical performance metrics data.
*   **`brain_health/POST_MORTEM.md`**: Database of historical bugs and their architectural fixes.

### 🛠️ Core Files (Root Directory)
- **`SYSTEM_MAP.md`**: [NEW] The Spatial Root and "Memory Palace" of the system.
- **`STRUCTURE.md`**: (You are here) The technical map and source of truth for the repository.
- **`POST_MORTEM.md`**: Historical record of system failures and architectural corrections.
- **`LEGION_SPECULATIVE_RUN.md`**: [NEW] Server-side speculative decoding deployment and configuration blueprint.
- **`NEURAL_HIERARCHY.md`**: Deep-dive into the six-system agentic architecture (now includes Maze Protocol).
- **`.agent/rules/the-augmented-cto.md`**: The Orchestrator core rules (Source of Truth for Agent behavior).
- **`DEPLOYMENT_GUIDE.md`**: Instructions for setting up the local-first production swarm.
- **`requirements.txt`**: Python dependencies for the entire engine.
- **`docker-compose.yml`**: Infrastructure definitions for local ChromaDB and testing services.
- **`workspace_config.json`**: [NEW] Central registry for all projects watched by Kenbun.
- **`.env` / `.env.example`**: Environment configuration and API key placeholders.
- **`.kenbun_master.key`**: AES master key for the encrypted `secret_manager.py`.
### 🛠️ Service Layer (`core/services/`)
- **`services/swarm_daemon.py`**: Background service that monitors for autonomous task triggers and runs the Autonomic Heartbeat.
- **`tools/autonomic/autonomic_corrector.py`**: [NEW] Closed-loop self-healing engine with "Death Spiral" circuit breakers and log-rotation support.
- **`services/production_swarm.py`**: Entry point for high-reliability, long-running agent tasks.

### 🖥️ UI & Observability
*   **`dashboard/`**: Next.js 16 dashboard for real-time swarm visualization.
*   **`dashboard/src/components/DiscoveryForm.tsx`**: Strategic brief capture for UI tasks.
*   **`tools/scratch/`**: Temporary scripts and testing experiments.

### 🎨 Open Design Assets
*   **`design_systems/`**: 72 brand-specific Design Laws (Apple, Stripe, etc.).
*   **`tools/skills/`**: 31 modular Skill Protocols (pitch-deck, saas-landing).
*   **`tools/craft/`**: Universal design rules (typography, anti-ai-slop).

---

## 🛑 Maintenance Mandates
1. **Documentation Parity**: If a file is created, it MUST be added to this map.
2. **System Integrity**: No file should exist outside of a defined System Level (1-5) or Infra layer.
3. **Periodic Pruning**: Review this map weekly to remove "Ghost Files" (deprecated logic).
