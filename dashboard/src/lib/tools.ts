import { useMemo } from "react";

/**
 * Kenbun Neural Hierarchy Core Tools Directory
 * Encapsulates System Tiers, Operational Roles, and Functional Descriptions for Systems 1-6.
 */

export interface ToolDescription {
  system: string;
  role: string;
  desc: string;
}

export interface ToolStat {
  tool_id: string;
  success_rate: number;
  alpha: number;
  beta: number;
  confidence: string;
  delta: number;
  mom_delta: number;
  entropy: number;
  success_count?: number;
  failure_count?: number;
  history_trend?: any[];
}

export const TOOL_DESCRIPTIONS: Record<string, ToolDescription> = {
  token_governor: {
    system: "System 4 (Strategy)",
    role: "Real-time Budget Enforcement",
    desc: "Enforces token budgets and tracks session costs. Prevents cost runaways from Cloud AI prompts by dynamically switching to cheaper local or lightweight cloud endpoints as spend nears daily ceilings."
  },
  telemetry_pulse: {
    system: "System 6 (Sensory / Telemetry)",
    role: "System-wide Micro-benchmarks",
    desc: "Measures and records active operational metrics, including success rates, tool execution latencies, load, and performance benchmarks, broadcasting at 1Hz frequency."
  },
  fleet_monitor: {
    system: "Sensory / Observatory",
    role: "Infrastructure Node Sentinel",
    desc: "Tracks the connectivity, latency, and health of active local, remote, and cloud node workers (LM Studio, Gemini Flash, P330 GPU worker, and ChromaDB) to ensure safe routing."
  },
  topology_mapper: {
    system: "System 3 (Memory / Observatory)",
    role: "Semantic Code Mapper",
    desc: "Indexes codebase functions, variables, and modules in ChromaDB, projecting high-dimensional vector embeddings into an organic 2D visual layout (Galaxy Map)."
  },
  audit_supervisor: {
    system: "System 2 (Reasoning & Ethics)",
    role: "Multi-tier Code Audit & Gatekeeper",
    desc: "Intercepts initial execution proposals and performs strict safety, architectural, and security audits via local LLM consensus (Ensemble Audit) before code commit."
  },
  background_sync: {
    system: "System 6 (Autonomic Daemons)",
    role: "Schedules & Maintenance Runner",
    desc: "Manages background jobs, file watch loops, nightly re-indexing pipelines, and automated synchronization of data models across distributed compute environments."
  },
  vector_sync_worker: {
    system: "System 3 (Short-Term Memory)",
    role: "Incremental Memory Sync",
    desc: "Monitors changes to source files and dynamically extracts, chunks, embeds, and updates the local and remote ChromaDB vector indices to keep semantic search current."
  },
  bayesian_governor: {
    system: "System 4 (Strategy)",
    role: "Thompson Sampling Router",
    desc: "Models tool performance as a Beta distribution and runs Thompson Sampling (UCB1) to route prompts to the absolute highest-probability execution path."
  },
  sovereignty_engine: {
    system: "System 6 (Self-Healing)",
    role: "AST Law Enforcer & Logic Sentinel",
    desc: "Runs the Sovereign Verification Engine (SVE) to identify regressions or logical codebase hallucinations, validating changes against the project's source of truth."
  },
  memory_classifier: {
    system: "System 3 (Memory)",
    role: "Context Allocation Autopilot",
    desc: "Analyzes incoming tasks and maps them to spatial 'rooms' in the memory repository, filtering context injection down to what is strictly necessary to save tokens."
  },
  neural_classifier: {
    system: "System 4/3 (Vector ML)",
    role: "Codebase Anomaly Detector",
    desc: "Runs Random Forest models over ChromaDB embeddings to spot logical anomalies, highlighting code blocks that are misclassified or structurally inconsistent."
  },
  intelligence_engine: {
    system: "System 5/4 (Reflection)",
    role: "Swarm Analyst & Optimizer",
    desc: "Synthesizes system execution logs, token burn, and success benchmarks to suggest autonomous weight adjustments and structural tuning for future swarm runs."
  },
  scan_repo: {
    system: "System 1 (Execution)",
    role: "Sovereign Repository Scanner",
    desc: "Crawls the workspace hierarchy to analyze project structure, file types, package dependencies, and codebase composition prior to semantic indexing."
  },
  run_code_safely: {
    system: "System 1 (Execution)",
    role: "Sandboxed Test Executor",
    desc: "Executes code modifications in isolated, sandboxed environments to verify semantic correctness, compile safety, lint conformances, and test suite outcomes."
  },
  list_checkpoints: {
    system: "System 6 (Autonomic)",
    role: "State Snapshot Sentinel",
    desc: "Queries the local state history, providing a list of previous git, database, and repository checkpoints available for immediate hot rollback."
  },
  index_codebase: {
    system: "System 3 (Memory)",
    role: "Cognitive Vector Compiler",
    desc: "Processes project files to construct high-density parent-child code chunk relationships, generating and updating semantic embeddings in ChromaDB."
  },
  delete_from_hivemind: {
    system: "System 5 (Reflection)",
    role: "Cognitive Knowledge Pruner",
    desc: "Removes old, obsolete, or hallucinated facts and logical assumptions from the persistent shared long-term knowledge repository."
  },
  get_brain_health: {
    system: "System 5 (Reflection)",
    role: "Swarm Health Auditor",
    desc: "Queries CPU benchmarks, socket statuses, and local ensemble model voting statistics to assess orchestrator sanity and general database health."
  },
  audit_package_safety: {
    system: "System 2c (Guardrail)",
    role: "Deterministic Package Sentinel",
    desc: "Scans third-party package requests to block unsafe, deprecated, or malicious dependency scripts from entering the project environment."
  },
  ask_architect: {
    system: "System 2 (Reasoning & Ethics)",
    role: "Structural Design Advisor",
    desc: "Consults local architecture patterns and best-practice rules to resolve complex structural disputes and enforce professional coding standards."
  },
  ask_ui_expert: {
    system: "System 5 (Design Discovery)",
    role: "Heritage Layout Auditor",
    desc: "Validates visual elements against DESIGN.md to guarantee harmonious color tokens, fluid spacing grids, sharp high-DPI scaling, and responsive layout styling."
  },
  consult_supervisor: {
    system: "System 2 (Reasoning & Ethics)",
    role: "Executive Swarm Council Gatekeeper",
    desc: "Coordinates local LLM voting pools (Gemma/Llama) and cloud-grounded models to review security metrics and code commits before final approval."
  },
  audit_guardrail: {
    system: "System 2c (Guardrail)",
    role: "Fast Static Security Guard",
    desc: "Performs instant deterministic audits to screen code changes for unsafe shell processes, hardcoded API keys, or directory traversal vulnerabilities."
  },
  autofix_linter: {
    system: "System 2c (Guardrail)",
    role: "AST Code Format & Linter",
    desc: "Executes automatic formatting runs to resolve minor syntax deviations, dangling imports, or standard style regressions in real time."
  },
  research_official_docs: {
    system: "System 1 (Execution)",
    role: "Official Documentation Crawler",
    desc: "Searches official frameworks libraries and caches (Next.js, FastAPI, Supabase) to resolve syntax ambiguities and fetch certified developer guidance."
  },
  review_code_with_gemini: {
    system: "System 1/2 (Cloud Execution)",
    role: "Consensus Code Auditor",
    desc: "Delegates comprehensive codebases reviews to high-capacity cloud models to run tiered audits and multi-model consensus verifications."
  },
  research_with_gemini: {
    system: "System 1 (Execution)",
    role: "Sovereign Cloud Intelligence Researcher",
    desc: "Executes broad developer search queries backed by high-capacity cloud intelligence to solve complex system integration roadblocks."
  },
  remember_fix: {
    system: "System 5 (Reflection)",
    role: "Post-Mortem Memory Synapser",
    desc: "Logs fixed issues and code regressions into the error memory bank in ChromaDB, creating permanent post-mortem lessons."
  },
  recall_fix: {
    system: "System 3 (Memory)",
    role: "Historical Anomaly Retriever",
    desc: "Extracts previous developer post-mortems and bug resolutions from error memory to quickly solve recurring development errors."
  },
  save_checkpoint: {
    system: "System 6 (Autonomic)",
    role: "Workspace Snapshot Engine",
    desc: "Saves the workspace's state and file modifications to a secure, transaction-safe local backup point."
  },
  restore_checkpoint: {
    system: "System 6 (Autonomic)",
    role: "Workspace State Restorer",
    desc: "Performs clean filesystem restores, rolling back workspace modifications to a specified stable historical checkpoint."
  },
  orchestrate: {
    system: "System 4 (Strategy)",
    role: "Swarm Pipeline Conductor",
    desc: "Directs background tasks, connectivity heartbeats, circuit breakers, and parallel speculative reasoning runs across active workers."
  },
  save_to_hivemind: {
    system: "System 5 (Reflection)",
    role: "Hivemind Publisher",
    desc: "Distills successfully executed developmental plans and solutions into structured conceptual files inside the memory palace."
  },
  search_hivemind_concepts: {
    system: "System 3 (Memory)",
    role: "Hivemind Memory Explorer",
    desc: "Runs high-speed vector similarity queries across persistent memory vaults to retrieve historical developer instructions."
  },
  search_codebase: {
    system: "System 3 (Memory)",
    role: "Semantic Code Retriever",
    desc: "Performs intent-based queries on local codebase embeddings to locate specific hooks, functions, or database schemas."
  },
  think_about_tools: {
    system: "System 4 (Strategy)",
    role: "Thompson Weight Solver",
    desc: "Evaluates Bayesian Thompson routing distributions inside the intelligence store to balance exploration and exploitation vectors."
  },
  patch_hivemind_concept: {
    system: "System 5 (Reflection)",
    role: "Hivemind Concept Synapser",
    desc: "Applies precision updates and adjustments to existing vector embeddings inside ChromaDB memory."
  },
  ingest_knowledge_from_pdf: {
    system: "System 3 (Memory)",
    role: "PDF Knowledge Ingestor",
    desc: "Parses, chunks, and indexes dense structural textbooks and technical PDFs directly into ChromaDB."
  },
  prune_hivemind: {
    system: "System 5 (Reflection)",
    role: "Memory Palace Sweeper",
    desc: "Scans long-term concepts to clean up duplicate files or orphaned memories, optimizing retrieval latency."
  },
  get_intelligence_stats: {
    system: "System 4 (Strategy)",
    role: "Thompson Telemetry Logger",
    desc: "Retrieves success-to-failure counts, exploration momentum, and exploration entropy statistics directly from the SQLite intelligence database."
  },
  reflect_on_task: {
    system: "System 5 (Reflection)",
    role: "Post-Task Review Sentinel",
    desc: "Conducts closed-loop analysis on completed task checklists to generate a sovereign post-mortem report and clean up dangling parameters."
  }
};

/**
 * Safely resolves a tool's description metadata, returning a fallback description on unknown tool IDs.
 */
export function getToolDescription(id: string | undefined): ToolDescription {
  if (!id || !TOOL_DESCRIPTIONS[id]) {
    return {
      system: "Unknown System",
      role: "Undefined Worker Node",
      desc: "This component is running without modular description payload. Check NEURAL_HIERARCHY.md for system allocation details."
    };
  }
  return TOOL_DESCRIPTIONS[id];
}

/**
 * Strict runtime schema validator and parser for ToolStat objects.
 * Insulates the frontend layout from malformed or incomplete API payloads.
 */
export function validateToolStat(data: any): ToolStat {
  const d = data || {};
  return {
    tool_id: String(d["tool_id"] || "unknown_tool"),
    success_rate: typeof d["success_rate"] === "number" && isFinite(d["success_rate"]) ? d["success_rate"] : 0,
    alpha: typeof d["alpha"] === "number" && isFinite(d["alpha"]) ? d["alpha"] : 0,
    beta: typeof d["beta"] === "number" && isFinite(d["beta"]) ? d["beta"] : 0,
    confidence: String(d["confidence"] || "LOW"),
    delta: typeof d["delta"] === "number" && isFinite(d["delta"]) ? d["delta"] : 0,
    mom_delta: typeof d["mom_delta"] === "number" && isFinite(d["mom_delta"]) ? d["mom_delta"] : 0,
    entropy: typeof d["entropy"] === "number" && isFinite(d["entropy"]) ? d["entropy"] : 0,
    success_count: typeof d["success_count"] === "number" && isFinite(d["success_count"]) ? d["success_count"] : 0,
    failure_count: typeof d["failure_count"] === "number" && isFinite(d["failure_count"]) ? d["failure_count"] : 0,
    history_trend: Array.isArray(d["history_trend"]) ? d["history_trend"] : undefined,
  };
}

/**
 * Sanitizes and formats input values safely to prevent NaN rendering in the view layer.
 */
export function safeFormatNumber(value: unknown, decimals: number = 2, fallback: string = "0.00"): string {
  const num = typeof value === "number" ? value : parseFloat(String(value));
  return isFinite(num) && !isNaN(num) ? num.toFixed(decimals) : fallback;
}

/**
 * Custom React Hook to compute and sanitize active tool stats metrics defensively.
 */
export function useToolMetrics(tool: ToolStat | null) {
  return useMemo(() => {
    if (!tool) return null;

    // Validate inputs under hook context defensively
    const validated = validateToolStat(tool);
    const alpha = validated.alpha;
    const beta = validated.beta;
    const successCount = validated.success_count ?? 0;
    const failureCount = validated.failure_count ?? 0;

    return {
      tool_id: validated.tool_id,
      alphaStr: safeFormatNumber(alpha, 2),
      betaStr: safeFormatNumber(beta, 2),
      entropyStr: safeFormatNumber(validated.entropy, 5, "0.00000"),
      deltaStr: safeFormatNumber(validated.delta, 1, "0.0"),
      momDeltaStr: safeFormatNumber(validated.mom_delta, 1, "0.0"),
      successRateStr: safeFormatNumber((validated.success_rate ?? 0) * 100, 1) + "%",
      entropyIsLow: (validated.entropy ?? 0) < -0.02,
      successCount,
      failureCount,
      gaugeSuccess: successCount > 0 || failureCount > 0 ? successCount : Math.round(alpha * 10),
      gaugeTotal: successCount > 0 || failureCount > 0 ? (successCount + failureCount) : Math.round((alpha + beta) * 10),
    };
  }, [tool]);
}
