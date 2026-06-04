# 🐍 Kenbun: Exhaustive Python File Glossary

This document provides a 1:1 functional description of every Python file in the Kenbun engine.

---

## 🛡️ `tools/audit/` (System 2 & 2c)
*   **`supervisor_agent.py`**: The "High Council" lead. Manages multi-tier fallbacks and executive audits.
*   **`ensemble_audit.py`**: Runs parallel audits across multiple local models (Phi, Llama, etc.) and calculates consensus.
*   **`guardrail_agent.py`**: Fast, deterministic security checks (no network call needed).
*   **`gemini_reviewer.py`**: Deep-dive cloud-based code review using Gemini 1.5 Pro.
*   **`reflection_agent.py`**: (System 5) Post-task analyst that saves "Lessons Learned" to the Hivemind.
*   **`ui_designer.py`**: The "UI Expert." Enforces premium aesthetics and glassmorphism.
*   **`consult_architect.py`**: Internal tool for checking structural changes against the Master Blueprint.
*   **`test_ensemble.py`**: Verification suite for the consensus logic.

## 🔌 `tools/infrastructure/` (System 6 & Infrastructure)
*   **`server.py`**: The MCP Server entry point. Connects these tools to your IDE.
*   **`orchestrator.py`**: The state machine that executes complex multi-step "Swarms."
*   **`agents.py`**: Class definitions and personas for all system agents.
*   **`api_server.py`**: FastAPI wrapper for remote tool execution.
*   **`native_ears.py`**: macOS background service for always-on voice command ingestion.
*   **`swarm_voice.py`**: Telegram bot integration for remote voice commands.
*   **`tech_registry.py`**: Central source of truth for allowed tech stacks and docs.
*   **`monitor.py`**: Real-time telemetry monitoring of system health.

## 🛠️ `tools/execution/` (System 1)
*   **`sandbox_runner.py`**: Isolated Docker/local execution for testing generated code.
*   **`shadow_tester.py`**: Automatically generates and runs unit tests for proposed fixes.

## 📖 `tools/memory/` (System 3)
*   **`knowledge_manager.py`**: The primary API for interacting with the ChromaDB Hivemind.
*   **`chroma_db_connect.py`**: Handles low-level network persistence to the Remote PC.
*   **`code_indexer.py`**: Chunks and indexes the codebase for semantic search.
*   **`repo_mapper.py`**: Generates a skeleton map of the repository (classes/functions).
*   **`pdf_ingestor.py`**: Ingests technical documentation PDFs to teach the AI.
*   **`error_memory.py`**: Specific memory bank for recurring failures (System 2 feedback).

## 🧠 `tools/strategy/` (System 4)
*   **`decision_logic.py`**: The "Governor" logic. Routes tasks to the correct system.
*   **`strategy_manager.py`**: Tracks Bayesian tool weights ($\alpha, \beta$).
*   **`token_governor.py`**: Enforces token budgets and tracks session costs.

## 🧠 `dev/self_evolution/` (Self-Awareness) [NEW]
*   **`awareness_engine.py`**: Analyzes token consumption, memory density, and local ensemble decisions to build State-of-the-Union (SOTU) audits.

## 🛠️ `tools/utils/` (Shared Toolkit)
*   **`maze_protocol.py`**: The "Backward Verification" utility (The Maze).
*   **`backtracker.py`**: Checkpoint/Restore system for rolling back file changes.
*   **`path_utils.py`**: Absolute path resolution for cross-platform stability.
*   **`secret_manager.py`**: AES-encrypted storage for API keys and tokens.
*   **`notifications.py`**: Native macOS "Say" and Alert bridge.
*   **`telemetry.py`**: Benchmarking and performance tracking.
*   **`harvester.py`**: Utility for gathering logs for System 5 Reflection.
*   **`janitor.py`**: Automatic cleanup of temporary files and sandboxes.
*   **`sync_to_pc.py`**: Syncs local changes to the Remote PC.
*   **`sync_intelligence.py`**: Synchronizes Bayesian weights across nodes.
*   **`nightly_bake.py`**: Scheduled job for re-indexing and system maintenance.

## 🧪 `tests/` (Sovereign Verification Suite)
*   **`test_autopilot.py`**: Automated unit tests validating dynamic VRAM/RAM hardware sensing profiles on macOS and Linux.
*   **`test_ralph_loop.py`**: Automated integration tests validating autonomic rollback, re-grounding, and self-healing trial results inside the supervisor.

