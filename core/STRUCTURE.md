# 🏗️ Kenbun/core: Master System Map

This is the definitive technical documentation for the Kenbun Professional Architecture

The system is segmented into two primary domains to ensure infinite scalability and professional separation of concerns.

## 📂 Project Hierarchy

* **kenbun/core/**: The "Brain" and "Engine" of the system.
  * **agents/**: Swarm agent adapters and traceability.
  * **benchmarks/**: Performance and reliability testing scripts.
  * **dev/self_evolution/**: Self-awareness and State-of-the-Union audits.
  * **hivemind_memory/**: Semantic long-term persistence.
  * **scripts/**: Diagnostics and brain-sync utilities.
  * **services/**: Background daemons running the swarm.
  * **tests/**: Sovereign verification and unit testing.
  * **tools/**: All MCP tools, strategy logic, and the API server.
  * **training_data/**: Export and LoRA fine-tuning pipelines.
* **kenbun/scripts/**: Core setup, onboarding bootstrap, and terminal agent entry points.
  * **bootstrap.py**: Guided hardware-sensing setup wizard, port remap, and Docker stack controls.
  * **terminal_chat.py**: Autonomous self-healing terminal developer chat shell (termchat).
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

### 🧠 System 4 & 5: Strategy & Reflection (`tools/strategy/`)
*   **`decision_logic.py`**: Hardened routing engine that orchestrates sub-modules.
*   **`keyword_processor.py`**: Encapsulates signal detection and regex matching.
*   **`neural_learner.py`**: Handles Alpha-Go style reward/decay weights.
*   **`token_governor.py`**: Real-time budget enforcement and cost tracking.
*   **`strategy_manager.py`**: Manages tool intelligence weights (Bayesian sampling).
*   **`hme_router.py`**: Hierarchical Mixture of Experts routing core.
*   **`tools/audit/reflection_agent.py`**: Self-auditing loop that generates Hivemind entries (System 5).

### 📖 System 3: Memory & Knowledge (`tools/memory/` & `hivemind_memory/`)
*   **`knowledge_manager.py`**: Core API for ChromaDB interactions (CRUD concepts).
*   **`pdf_ingestor.py`**: Ingests technical PDFs to teach the AI new frameworks.
*   **`code_indexer.py`**: Semantic indexing of the current repository's source code.
*   **`repo_mapper.py`**: Generates logical topologies of the codebase for RAG.
*   **`chroma_db_connect.py`**: Low-level connection handler for remote ChromaDB.

### 🛡️ System 2 & 2c: Audit & Quality (`tools/audit/`)
*   **`supervisor_agent.py`**: (System 2) Executive audit agent with Tiered Ensemble logic.
*   **`ensemble_audit.py`**: Multi-model consensus auditor (Weighted Parallel Voting).
*   **`guardrail_agent.py`**: (System 2c) Continuous guardrail for fast security audits.
*   **`gemini_reviewer.py`**: Cloud-based deep code review and audio transcription.
*   **`consult_architect.py`**: Internal consultation tool for complex structural decisions.
*   **`ui_designer.py`**: Specialized agent (UI Expert) for enforcing premium design standards.
*   **`adversarial_court.py`**: (System 2a) Adversarial LLM Auditing Court.
*   **`safe_linter.py`**: Deterministic static analysis wrapper.

### 🛠️ System 1: Execution & Tools (`tools/execution/`)
*   **`sandbox_runner.py`**: Runs generated code in a safe, isolated environment.
*   **`shadow_tester.py`**: Automatically generates unit tests for new/modified code.
*   **`claude_code_agent.py`**: Claude Code Sub-Agent Bridge for complex refactors.
*   **`shell_sentinel.py`**: Securely executes terminal commands, intercepting dangerous patterns.

### 📡 System 6: Sensory Layer (`tools/infrastructure/`)
*   **`swarm_voice.py`**: Telegram voice-note listener with Gemini 3 transcription.
*   **`native_ears.py`**: [ASYNC] macOS native always-listening sensory layer with ensemble gating.
*   **`design_bridge.py`**: ACP-to-MCP Bridge for orchestrating external design CLIs.

### 🔌 Infrastructure Layer (`tools/infrastructure/`)
*   **`orchestrator.py`**: The main state-machine engine orchestrating complex logic.
*   **`server.py`**: The MCP server that exposes tools to IDEs.
*   **`agents.py`**: Definitions for Agent Personas (Architect, Security, Swarm).
*   **`tech_registry.py`**: Central registry of allowed technologies and documentation URIs.
*   **`api_server.py`**: FastAPI wrapper with real-time SSE topology streaming.
*   **`pipelines/`**: Contains execution sequences (`bug_fix.py`, `code_review.py`, `research.py`).
*   **`routers/`**: FastAPI routers mapping API endpoints (`chat_router.py`, `topology_router.py`).

### 🤖 Agents & Interfaces (`agents/` & `tools/cli/`)
*   **`agents/adapter.py`**: Agent tool interfaces for the Swarm.
*   **`tools/cli/engine.py`**: Termchat and Reflex Shell REPL for local users.

### 🛠️ Shared Utilities (`tools/utils/`)
*   **`telemetry.py`**: Performance benchmarking and success-rate tracking.
*   **`notifications.py`**: Native macOS notification bridge.
*   **`secret_manager.py`**: AES-encrypted storage for API keys.
*   **`backtracker.py`**: Checkpoint/Restore system for rolling back failed code changes.
*   **`error_memory.py`**: Tracks recurring errors to prevent the AI from repeating mistakes.
*   **`path_utils.py`**: Universal path resolution for cross-platform compatibility.
*   **`workspace_manager.py`**: Dynamic project discovery and registry management.
*   **`maze_protocol.py`**: Utility for "Backward Verification" (The Maze Protocol).
*   **`deepseek_client.py`**: Integration with DeepSeek cloud providers.

### 🩺 Sovereign Testing & Benchmarks (`tests/` & `benchmarks/`)
*   **`tests/test_autopilot.py`**: Automated tests for hardware-sensing profiles.
*   **`tests/test_ralph_loop.py`**: Autonomic rollback and self-healing tests.
*   **`tests/master_swarm_test.py`**: End-to-end integration tests of the swarm.
*   **`benchmarks/benchmark_protocol.py`**: Performance verification suite.
*   **`benchmarks/chaos_orchestrator.py`**: Stress-test script for failure injection.

### 🧠 Self-Evolution & Training (`dev/self_evolution/` & `training_data/`)
*   **`dev/self_evolution/awareness_engine.py`**: Runs closed-loop SOTU audits.
*   **`training_data/export_brain.py`**: Exports the Hivemind for LoRA fine-tuning.

### 📊 Brain Health (Telemetry)
*   **`brain_health/usage_stats.json`**: Current session token expenditure log.
*   **`brain_health/BENCHMARKS.json`**: Historical performance metrics data.
*   **`brain_health/POST_MORTEM.md`**: Database of historical bugs and their architectural fixes.

### ⌨️ Core Setup & Onboarding Scripts (`scripts/`)
*   **`scripts/bootstrap.py`**: Guided setup wizard and Docker stack controls.
*   **`scripts/terminal_chat.py`**: Cognitive LLM developer agent shell.
*   **`scripts/full_audit_scan.py`**: Autonomic code scanning tool.

### 🛠️ Root Directory Files
- **`STRUCTURE.md`**: The root topological map and source of truth for the repository.
- **`README.md`**: Core system description and setup instructions.
- **`CONTRIBUTING.md`**: Contribution workflow, testing guidelines, and Git practices.
- **`KENBUN.md`**: Neural identity and Agent operational constraints.
- **`pyproject.toml`**: Metadata and dependencies configuration.
- **`docker-compose.yml`**: Docker services orchestrating the local environment.
- **`.env` / `.env.example`**: Environment configuration and API key placeholders.

### 🛠️ Core Workspace Metadata (`core/`)
- **`core/STRUCTURE.md`**: (You are here) The technical codebase map for the intelligence engine.
- **`core/SYSTEM_MAP.md`**: The Spatial Root and "Memory Palace" of the system.
- **`core/FILE_GLOSSARY.md`**: Exhaustive 1:1 functional descriptions of all Python modules.
- **`core/NEURAL_HIERARCHY.md`**: Deep-dive into the six-system agentic architecture.
- **`core/DEPLOYMENT_GUIDE.md`**: Setup manual for local-first swarm execution.
- **`core/POST_MORTEM.md`**: Historical log of software bugs and architectural resolutions.

### 🛠️ Service Layer (`core/services/` & `core/tools/autonomic/`)
- **`services/swarm_daemon.py`**: Background service executing the Autonomic Heartbeat.
- **`tools/autonomic/autonomic_corrector.py`**: Closed-loop self-healing engine with circuit breakers.

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
1. **Documentation Parity**: If a file is created, it MUST be added to this map and `FILE_GLOSSARY.md`.
2. **System Integrity**: No file should exist outside of a defined System Level (1-5) or Infra layer.
3. **Periodic Pruning**: Review this map weekly to remove "Ghost Files" (deprecated logic).
