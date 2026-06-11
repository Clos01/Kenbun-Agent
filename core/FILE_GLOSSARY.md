# 🐍 Kenbun: Exhaustive Python File Glossary

This document provides a 1:1 functional description of every Python file in the Kenbun engine.

---

## 🛡️ `core/agents/` (Assembly Agent Adapters)
*   **`adapter.py`**: AgentToolInterface (Adapter Pattern) for Kenbun Assembly Agents.
*   **`mock_sdk.py`**: Mock implementation of google.kenbun for development and testing environment compatibility.
*   **`trace.py`**: Traceability Manifest Logger for Kenbun Assembly Agents.
*   **`workflow.py`**: Workflow management and lifecycle hooks for Kenbun Assembly Agents.

## 📊 `core/benchmarks/` (Performance & Testing)
*   **`AUTONOMOUS_LEARNING.py`**: Automation script for testing self-learning behaviors.
*   **`CHAOS_TEST.py`**: Orchestrates failure injection testing across the assembly.
*   **`GENERATE_150_CASES.py`**: Data generator for creating 150 unique edge-case test scenarios.
*   **`HALLUCINATION_TEST.py`**: Validation suite to measure and prevent LLM hallucinations.
*   **`benchmark_protocol.py`**: Defines the standard protocols for executing performance benchmarks.
*   **`chaos_orchestrator.py`**: Coordinates multi-node chaos testing to ensure system resilience.
*   **`daily_report.py`**: Generates daily analytics and health reports for the assembly.
*   **`nightly_eval.py`**: Scheduled evaluator to run full system diagnostics overnight.

## 🧠 `core/dev/self_evolution/` (Self-Awareness)
*   **`awareness_engine.py`**: Analyzes token consumption, memory density, and local ensemble decisions to build State-of-the-Union (SOTU) audits.

## 🧠 `core/hivemind_memory/` (Long-Term Storage)
*   **`hive_memory.py`**: Core logic for long-term Hivemind semantic memory storage.

## 🛠️ `core/root/` (Diagnostics)
*   **`import_diagnostic.py`**: Verifies that all core modules can be imported cleanly without circular dependencies.

## 🧪 `core/scratch/` (Experimental Scripts)
*   **`assembly_test.py`**: Experimental script for testing multi-agent assembly behaviors.
*   **`test_models_direct.py`**: Script for testing LLM API connections directly bypassing the orchestrator.
*   **`test_supervisor_demo.py`**: Demonstration script of the System 2 Supervisor agent.
*   **`test_sve_breach.py`**: Experimental script testing Sovereign Environment breach responses.

## ⌨️ `core/scripts/` (Setup & Maintenance)
*   **`check_pc_brain.py`**: 🩺 PC Brain Health Check diagnostics.
*   **`sync_hivemind.py`**: Utility to force synchronization of the local ChromaDB Hivemind with remote nodes.

## 🔌 `core/services/` (Background Daemons)
*   **`assembly_daemon.py`**: Background service daemon that keeps the assembly actively monitoring the workspace.

## 🧪 `core/tests/` (Sovereign Verification Suite)
*   **`bayesian_hme_test.py`**: Unit tests for the Bayesian Hierarchical Mixture of Experts router.
*   **`cart_benchmark.py`**: Benchmark tests for the CART decision tree logic.
*   **`conftest.py`**: Shared pytest fixtures for the entire test suite.
*   **`hme_benchmark.py`**: General benchmarks for the HME routing engine.
*   **`hme_benchmark_100k.py`**: High-load (100k iterations) HME benchmark.
*   **`hme_benchmark_1k.py`**: Standard load (1k iterations) HME benchmark.
*   **`hme_benchmark_20k.py`**: Medium load (20k iterations) HME benchmark.
*   **`hme_benchmark_5k.py`**: Low load (5k iterations) HME benchmark.
*   **`hme_failure_audit.py`**: Audits the failure recovery mechanisms of the HME router.
*   **`integrity_test.py`**: Broad integrity tests for database and file states.
*   **`mars_test.py`**: Unit tests for the MARS auditor logic.
*   **`master_assembly_test.py`**: End-to-end integration test of the full Assembly capability.
*   **`security_penetration_test.py`**: Automated security vulnerability scanning tests.
*   **`test_autonomic.py`**: Validates the autonomic self-healing subroutines.
*   **`test_autopilot.py`**: Validates dynamic VRAM/RAM hardware sensing profiles on macOS and Linux.
*   **`test_brain_health.py`**: Validates the telemetry and usage statistics tracking.
*   **`test_chaos.py`**: Unit tests for the chaos orchestrator modules.
*   **`test_chat_sessions.py`**: Unit tests for the chat history and terminal state managers.
*   **`test_ensemble.py`**: Verification suite for the consensus logic of the Supervisor agent.
*   **`test_linter_autofix.py`**: Tests the automatic code linting and fixing logic.
*   **`test_llm_utils.py`**: Unit tests for LLM provider utility wrappers.
*   **`test_lmstudio_router.py`**: Tests the local LM Studio model routing logic.
*   **`test_mab.py`**: Tests the Multi-Armed Bandit strategy manager.
*   **`test_mcp_integration.py`**: Validates the MCP Server integrations.
*   **`test_parallel.py`**: Tests the parallel task distribution manager.
*   **`test_ralph_loop.py`**: Validates autonomic rollback, re-grounding, and self-healing.
*   **`test_smoke.py`**: Layer 1 — Smoke tests. Guarantees the core engine imports cleanly.
*   **`test_speculative_decoding.py`**: Tests for speculative decoding inference optimizations.
*   **`test_strategy.py`**: Comprehensive tests for all System 4 strategy logics.
*   **`test_system_2_rigor.py`**: System 2 & 2c Rigor Test suite for auditing standards.
*   **`test_token_governor.py`**: Tests the daily budget and token tracking mechanisms.

## 🛠️ `core/tools/` (Root Tool Utils)
*   **`harvester.py`**: Root utility for gathering logs for System 5 Reflection.
*   **`registry.py`**: Root registry mapping MCP tools to internal python functions.
*   **`assembly_trigger.py`**: Event hook that triggers the assembly based on external inputs.

## 🛡️ `core/tools/audit/` (System 2 & 2c)
*   **`adversarial_court.py`**: System 2a: Adversarial LLM Auditing Court for rigorous code reviews.
*   **`budget_dashboard.py`**: Extracts token budget analytics for the observatory dashboard.
*   **`consult_architect.py`**: Internal tool for checking structural changes against the Master Blueprint.
*   **`discovery_agent.py`**: System 5 Discovery Agent — The "Discovery Form" Generator.
*   **`ensemble_audit.py`**: Runs parallel audits across multiple local models and calculates consensus.
*   **`gemini_reviewer.py`**: Gemini Code Reviewer — Cloud-based AI review with cross-validation.
*   **`guardrail_agent.py`**: System 2c: Continuous Guardrail Agent for fast security checks.
*   **`linter_autofix.py`**: Automatically resolves syntax and styling errors identified by safe_linter.
*   **`mars_auditor.py`**: Multi-Agent Review System (MARS) logic auditor.
*   **`reflection_agent.py`**: System 5 Post-task analyst that saves "Lessons Learned".
*   **`safe_linter.py`**: Deterministic static analysis linter wrapper.
*   **`shaka_logic_sentinel.py`**: ⛩️ SHAKA LOGIC SENTINEL (Vegapunk Punk-01 Satellite) for advanced logic guardrails.
*   **`supervisor_agent.py`**: The "High Council" lead managing multi-tier fallbacks.
*   **`ui_designer.py`**: The "UI Expert" enforcing premium aesthetics and glassmorphism.
*   **`vision_auditor.py`**: Evaluates UI mockups and web changes using Vision models.
*   **`yolo_sandbox.py`**: High-speed sandbox for running risky code snippets with immediate rollback.

## 🔄 `core/tools/autonomic/` (Self-Healing)
*   **`autonomic_corrector.py`**: Closed-loop self-healing engine with "Death Spiral" circuit breakers.
*   **`sve_pulse.py`**: Sovereign Environment Pulse monitor for system vitals.

## ⚡ `core/tools/bootstrap/` (Initialization)
*   **`wizard.py`**: Guided hardware-sensing setup wizard and provider credentials config.

## 💻 `core/tools/cli/` (Terminal Interfaces)
*   **`edge_router.py`**: Routes CLI commands to the appropriate LLM edge nodes.
*   **`engine.py`**: 🌸 Kenbun Termchat & Reflex Shell (CLI Agent REPL).

## 🎨 `core/tools/cli/ui/` (CLI Renderers)
*   **`banner.py`**: 🌸 Kenbun Banner ASCII art rendering.
*   **`renderer.py`**: 🌸 Kenbun UI Renderer for terminal layout management.
*   **`skin_engine.py`**: 🌸 Kenbun Skin Engine for CLI theme processing.

## 🎨 `core/tools/design/` (Design Systems)
*   **`guardrail.py`**: Enforces strict adherence to the Heritage Design System tokens.
*   **`oracle.py`**: LLM agent responsible for mapping abstract UI requests to specific Design Tokens.

## 🛠️ `core/tools/execution/` (System 1)
*   **`claude_code_agent.py`**: Claude Code Sub-Agent Bridge for executing complex refactors.
*   **`p330_worker.py`**: P330 SFF Worker Node Client for remote distributed execution.
*   **`sandbox_runner.py`**: Sandbox Runner — Safe code execution in ephemeral Docker containers.
*   **`shadow_tester.py`**: Automatically generates and runs unit tests for proposed fixes.
*   **`shell_sentinel.py`**: Securely executes terminal commands while intercepting dangerous patterns.
*   **`wasm_interpreter.py`**: WebAssembly interpreter wrapper for running fast, isolated code blocks.

## 🔌 `core/tools/infrastructure/` (System 6 & Infra)
*   **`agent_dispatcher.py`**: Dispatches incoming requests to specific agent personas based on strategy.
*   **`agents.py`**: Class definitions and personas for all system agents.
*   **`ai_gateway.py`**: Hardware-agnostic LLM gateway routing between Ollama, LM Studio, and Cloud.
*   **`api_server.py`**: FastAPI wrapper with real-time SSE topology streaming.
*   **`auth.py`**: Authentication mechanisms for the API server and dashboard.
*   **`config.py`**: Central loader for `.env` and `workspace_config.json` parameters.
*   **`design_bridge.py`**: ACP-to-MCP Bridge for orchestrating 13+ external design CLIs.
*   **`distribute.py`**: 🏛️ Kenbun Sovereign Distribution Engine (System 2 Sanitizer - Refactored).
*   **`docker_manager.py`**: Controls Docker stacks and ephemeral sandbox containers.
*   **`middleware.py`**: FastAPI middleware for logging and security headers.
*   **`monitor.py`**: Real-time telemetry monitoring of system health.
*   **`native_ears.py`**: macOS background service for always-on voice command ingestion.
*   **`orchestrator.py`**: The Orchestrator — Meta-tool that chains tools into intelligent workflows.
*   **`parallel_manager.py`**: Manages parallel asynchronous task execution across the Assembly.
*   **`queue_manager.py`**: Manages the Redis/In-memory task queues.
*   **`server.py`**: The primary MCP Server entry point.
*   **`sovereign_decorators.py`**: Python decorators enforcing system-level security constraints.
*   **`sovereign_verifier.py`**: Verifies that executed code conforms to Sovereign isolation boundaries.
*   **`assembly_voice.py`**: Telegram bot integration for remote voice commands.
*   **`tech_registry.py`**: Central registry of allowed technologies and documentation URIs.
*   **`topology_manager.py`**: Maintains the active topological map of connected nodes.

## 🛤️ `core/tools/infrastructure/pipelines/` (Workflow Sequences)
*   **`bug_fix.py`**: Standardized pipeline sequence for autonomous bug remediation.
*   **`code_review.py`**: Standardized pipeline sequence for conducting a full codebase audit.
*   **`consult_supervisor_tool.py`**: Pipeline wrapper for invoking the System 2 Supervisor.
*   **`design_ui.py`**: Pipeline sequence for UI discovery, generation, and design evaluation.
*   **`research.py`**: Pipeline sequence for browsing documentation and web results.
*   **`shadow_test.py`**: Pipeline sequence for generating and executing unit tests against changes.

## 🔀 `core/tools/infrastructure/routers/` (Network Routers)
*   **`chat_router.py`**: FastAPI routes handling standard developer chat interactions.
*   **`config_router.py`**: FastAPI routes handling system configuration updates.
*   **`diagnostics_router.py`**: FastAPI routes handling health checks and SOTU reports.
*   **`intelligence_router.py`**: FastAPI routes interfacing directly with System 4 strategy logic.
*   **`llm_tools.py`**: FastAPI routes exposing MCP tools over HTTP.
*   **`router_logic.py`**: Shared logic and dependency injection for FastAPI routers.
*   **`topology_router.py`**: FastAPI routes for streaming node connections (`/api/v1/topology/stream`).

## 📖 `core/tools/memory/` (System 3)
*   **`chroma_db_connect.py`**: Low-level connection handler for remote ChromaDB.
*   **`code_indexer.py`**: Chunks and indexes the codebase for semantic search.
*   **`digester.py`**: Processes raw text and markdown into chunked embeddings.
*   **`knowledge_manager.py`**: Core API for ChromaDB interactions (CRUD concepts).
*   **`pdf_ingestor.py`**: Ingests technical PDFs to teach the AI new frameworks.
*   **`project_memory.py`**: Maintains the short-term working memory of the active conversation.
*   **`repo_mapper.py`**: Generates logical topologies of the codebase for RAG.

## 📝 `core/tools/skills/pptx-html-fidelity-audit/scripts/`
*   **`extract_pptx.py`**: Extract every shape on every slide of a .pptx into a JSON dump.
*   **`verify_layout.py`**: Verify a re-exported .pptx against footer-rail + canvas-bound invariants.

## 🧠 `core/tools/strategy/` (System 4)
*   **`bandit_learning.py`**: Multi-Armed Bandit logic for tool selection optimization.
*   **`bayesian_math.py`**: Core mathematical functions for Bayesian probability updates.
*   **`decision_logic.py`**: The "Governor" logic routing tasks to the correct system.
*   **`hme_router.py`**: Hierarchical Mixture of Experts (HME) core routing algorithms.
*   **`intelligence_engine.py`**: The primary intelligence engine processing context and rules.
*   **`keyword_processor.py`**: Encapsulates signal detection and regex matching for routing.
*   **`neural_classifier.py`**: Neural-net classifier for intention mapping.
*   **`neural_learner.py`**: Handles Alpha-Go style reward/decay weights.
*   **`strategy_manager.py`**: Manages tool intelligence weights (Bayesian sampling).
*   **`token_governor.py`**: Real-time budget enforcement and cost tracking.

## 🛠️ `core/tools/utils/` (Shared Toolkit)
*   **`backtracker.py`**: Agentic Backtracker — File checkpoint/restore for preventing doom loops.
*   **`bayesian.py`**: Shared utilities for probabilistic calculations.
*   **`chat_history_manager.py`**: Manages truncation and summarization of long message threads.
*   **`console_ui.py`**: Helper functions for printing formatted output to stdout.
*   **`deepseek_client.py`**: DeepSeek Cloud Client - Secure integration with DeepSeek-V3 / DeepSeek-R1.
*   **`env_builder.py`**: Parses and constructs `.env` configurations during bootstrap.
*   **`error_memory.py`**: Tracks recurring errors and past developer resolutions (System 2 feedback).
*   **`harvester.py`**: Legacy data harvester for log aggregation.
*   **`io_lock.py`**: Concurrency locking utility for safe file writes.
*   **`janitor.py`**: Automatic cleanup of temporary files and sandboxes.
*   **`llm_router.py`**: Utility layer for sending abstract prompts to specific LLM targets.
*   **`llm_utils.py`**: Token counting and text sanitation helpers.
*   **`maze_protocol.py`**: The "Backward Verification" utility (The Maze).
*   **`nightly_bake.py`**: Scheduled job for re-indexing and system maintenance.
*   **`notifications.py`**: Native macOS "Say" and Alert bridge.
*   **`orchestrator_helpers.py`**: Helper functions utilized by the Orchestrator meta-tool.
*   **`path_utils.py`**: Absolute path resolution for cross-platform stability.
*   **`secret_manager.py`**: AES-encrypted storage for API keys and tokens.
*   **`seed_observatory.py`**: Seed data injector for the Next.js observatory UI.
*   **`sync_intelligence.py`**: Synchronizes Bayesian weights across distributed nodes.
*   **`sync_to_pc.py`**: Syncs local changes to the Remote PC.
*   **`telemetry.py`**: Benchmarking and performance tracking utility.
*   **`workspace_manager.py`**: Dynamic project discovery and registry management.

## 📚 `core/training_data/` (Fine-Tuning)
*   **`export_brain.py`**: Exports the Hivemind into a JSONL format suitable for LoRA fine-tuning.
*   **`train_brain.py`**: Automated pipeline for fine-tuning local models on exported Brain data.
