# 🔬 Kenbun: The Core Algorithms

This document formalizes the mathematical and logical algorithms that power the Kenbun engine, ensuring high performance on limited hardware through "Logical Density."

---

## 1. The Bayesian Tool Selector (Strategy Algorithm)
**Goal**: Optimize tool selection without hardcoded rules.
**Type**: Thompson Sampling (Reinforcement Learning).

### The Math:
For every tool $T$ in category $C$, we maintain a **Beta Distribution** $Beta(\alpha_T, \beta_T)$:
- $\alpha_T$: Number of successful executions.
- $\beta_T$: Number of failed executions.

### The Algorithm:
1.  **Sample**: For each available tool, draw a random value $x$ from $Beta(\alpha_T, \beta_T)$.
2.  **Select**: Choose the tool with the highest $x$.
3.  **Explore/Exploit**: This naturally balances trying new tools (Exploration) and using proven ones (Exploitation).
4.  **Update**: After the task, System 5 (Reflection) increments $\alpha$ or $\beta$ based on the Supervisor's verdict.

---

## 2. The Maze Protocol (Backward Verification)
**Goal**: Ensure zero-regression logic.
**Type**: Recursive Dependency Tracing.

### The Algorithm:
1.  **Identify Exit**: The modified file/function.
2.  **Reverse AST Walk**: 
    - Identify all `import` statements and internal function calls.
    - Check if the destination exists in the current `sys.path`.
3.  **Root Anchorage**: Verify that the project root is prepended to `sys.path` at the entry point.
4.  **Dangling Link Check**: If a function was removed but its import remains, the protocol fails the "Backward Walk."

---

## 3. Spatial Context Pruning (Memory Palace RAG)
**Goal**: Reduce RAG noise and token cost.
**Type**: Hierarchical Semantic Search.

### The Algorithm:
1.  **Spatial Tagging**: Every chunk in ChromaDB is tagged with a "Room" (e.g., `room:Archives`).
2.  **Query Expansion**: When a user asks "Fix the DB," System 4 automatically appends `room:Archives` to the search metadata.
3.  **Pruning**: ChromaDB filters out all results NOT in the target room.
4.  **Result**: 90% reduction in irrelevant context results, fitting more high-value code into the local Gemma context window.

---

## 4. The Rolling Context Window (Hardware Optimization)
**Goal**: Prevent OOM (Out of Memory) on local GPUs.
**Type**: KV Cache Management.

### The Algorithm:
1.  **Threshold Detection**: Monitor if the current prompt + generated tokens exceed the hardware-defined limit (e.g., 10,896).
2.  **Rolling Eviction**: Instead of failing, the oldest 20% of the conversation context is "rolled" out.
3.  **Anchor Retention**: Crucial architectural rules (from `SYSTEM_MAP.md`) are designated as "Fixed Anchors" and are never evicted.
4.  **Decoding Speed**: By limiting the context size, we ensure the GPU prefill time remains sub-second, even on a 4B/9B model.

---

## 5. Multi-Tier Fallback (The High Council)
**Goal**: Guaranteed Reliability.
**Type**: Weighted Consensus.

### The Algorithm:
1.  **Tier 1 (Local Ensemble)**: 3 small models (Phi, Llama, Gemma) vote in parallel.
2.  **Tier 2 (Local Senior)**: If Tier 1 is "Hung Jury" (conflicting votes) or fails (404), escalate to Gemma 26B.
3.  **Tier 3 (Cloud Audit)**: If Local Senior fails or latency > 90s, escalate to Gemini 1.5 Pro.
4.  **Tier 4 (Bayesian Penalty)**: If a Tier fails, its $\beta$ weight is increased in the Governor.
