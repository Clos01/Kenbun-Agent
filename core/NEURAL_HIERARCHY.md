# 🏛️ Kenbun Neural Hierarchy v2.0: The Bayesian Governor

This document outlines the architecture for evolving the Kenbun AI stack from a retrieval-based system to a probabilistic learning system.

## 1. The 4-Tier Hierarchy

| Layer | System | Responsibility | Implementation |
| :--- | :--- | :--- | :--- |
| **Execution** | **System 1** | Fast draft generation, initial tool execution. | Gemini 2.0 Flash (Cloud) / Gemma (Local) |
| **Guardrail** | **System 2c** | Fast heuristic & local security constraint audit. | Python Heuristics + Llama 3 (Local) |
| **Audit** | **System 2** | Security review, logic validation, "Senior" critique. | Executive consult_supervisor (High-Fidelity) |
| **Memory** | **System 3** | Semantic search with Parent-Child Hierarchy. | ChromaDB (Vector DB) + Recursive AST |
| **Strategy** | **System 4** | **The Bayesian Governor.** Tool selection & confidence. | Python + SQLite (Local Bayesian Store) |
| **Sensory** | **System 6** | **Voice & Signal.** Remote command ingestion. | Telegram API + Gemini 3 (Audio) |

---

## 2. Core Components of System 4 (Bayesian Strategy)

### A. Bayesian Tool Selector
Instead of a static list of tools, System 4 tracks a **Beta Distribution** $(\alpha, \beta)$ for each tool's success rate per task category (e.g., "frontend", "api", "security").
- **Success Update**: $\alpha \leftarrow \alpha + 1$
- **Failure Update**: $\beta \leftarrow \beta + 1$
- **Inference**: Samples from the distribution (Thompson Sampling) to pick the tool most likely to succeed.
- **Storage**: Persisted in `kenbun_intelligence.db` (SQLite) for ultra-low latency (<1ms) lookups during orchestration.

### B. Hierarchical System 3 (Memory)
To solve the "Blob" problem, memory is now structured:
- **Parent Index**: Entire files or large logical blocks (Classes/Modules).
- **Child Index**: Small, high-precision chunks (Functions/Hooks) linked to parents.
- **Benefit**: Retains full context while providing precise search results.

---

## 3. Scalable Infrastructure Implementation

### 🛠️ Core Files (Root Directory)
- **`SYSTEM_MAP.md`**: [NEW] The Spatial Root and "Memory Palace" of the system.
- **`STRUCTURE.md`**: (You are here) The technical map and source of truth for the repository.
- **`POST_MORTEM.md`**: Historical record of system failures and architectural corrections.
- **`NEURAL_HIERARCHY.md`**: Deep-dive into the six-system agentic architecture (now includes Maze Protocol).

### 1. State Persistence
- **Problem**: In-memory weights fail in distributed environments.
- **Solution**: SQLite was chosen for initial local deployment to minimize network overhead. All high-scale knowledge remains on the **Remote PC (100.104.211.61)** via ChromaDB to maintain data sovereignty and performance.

### 2. Streamed Asynchronous Audit (Latency Fix)
- **Workflow**:
    1. **System 4** picks the strategy (low latency).
    2. **System 1** streams the initial response to the user immediately.
    3. **System 2** runs the Audit/Supervisor review in the background.
    4. If System 2 finds a risk, it sends a "Correction Payload" to the UI via WebSockets or a secondary message.

### 3. Signal Resilience (System 4 + 6)
- **Problem**: Mobile hotspots cause high-latency hangs during remote DB lookups.
- **Solution**: Implemented a **2-second socket reachability check** in `strategy_manager.py`. If the remote PC is unreachable, the system auto-triggers "Local Fallback Mode" in milliseconds, ensuring the swarm never stalls while the user is mobile.
- **Feedback Loop**: System 6 provides immediate "Swarm Initiated" audio/text feedback before long-running tasks, keeping the user informed in real-time.

### 4. Loop Safety (Circuit Breaker)
- Implement a `max_retries` and `min_confidence` threshold. If the Bayesian Governor's confidence drops below 20%, it must halt and ask the user for clarification rather than consuming tokens in a loop.

---

## 4. Verification & Testing

- **A/B Testing**: Run one group of requests through standard RAG and another through the Bayesian Governor.
- **Benchmarking**: Measure the "Correction Rate" from the Supervisor. A successful Bayesian Governor should reduce the number of times the Supervisor has to reject a solution.
---

## 5. The Maze Protocol & Spatial Rooting

To optimize performance on limited hardware and reduce cognitive switching costs, the architecture now uses **Spatial Rooting**.

### A. The "Maze" Protocol (Backward Verification)
Before any task is marked "Approved," the System 2 Supervisor must perform a **Backward Walk**:
1.  **Exit to Entrance**: Trace the logic from the final output/return back to the initial input/trigger.
2.  **Evidence Check**: Ensure every visual change has a corresponding code logic.
3.  **Dangling Logic**: Identify any "dead vines" (unused variables, dangling imports) created during the task.
4.  **Verification Tool**: Use `tools/utils/maze_protocol.py` to verify path integrity.

### B. Spatial Rooting (The Memory Palace)
The codebase is mapped spatially in `SYSTEM_MAP.md`.
- **Sensory Hall**: Ingestion.
- **The Atelier**: Execution.
- **The Archives**: Memory.
- **High Council**: Audit.
- **The Observatory**: Dashboard.

**Mandate**: All agents must anchor their search queries in the relevant "Room" to minimize context congestion and maximize inference precision.
