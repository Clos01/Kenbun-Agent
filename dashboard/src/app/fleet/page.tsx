"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import Sidebar from "@/components/Sidebar";
import { 
  ShieldAlert,
  Cpu,
  Cloud,
  Server,
  CircleDot,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Power,
  RefreshCw,
  Zap,
  Search,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Thermometer,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Activity,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Wifi,
  Flame,
  Clock,
  Database,
  BrainCircuit,
  ShieldCheck,
  Layers,
  BookOpen,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Filter,
  CheckCircle2,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ChevronRight,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Sparkles,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Info
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import WeightFormula from "@/components/WeightFormula";
import { CONFIG } from "@/lib/config";
import { ToolStat, validateToolStat } from "@/lib/tools";
import ToolDetailPanel from "@/components/ToolDetailPanel";
import { tenantFetch } from "@/lib/tenantFetch";

export interface SentryTelemetryData {
  status: string;
  host?: string;
  uptime_seconds?: number;
  cpu_load?: number[];
  cpu_percent?: number;
  cpu_temp_c?: number;
  ram_used_mb?: number;
  ram_total_mb?: number;
  ram_percent?: number;
  queries_total?: number;
  queries_blocked?: number;
  blocked_percent?: number;
  clients_active?: number;
}

interface BudgetData {
  daily_limit: number;
  current_usage: number;
  daily_usage: number;
  remaining: number;
  status: string;
  lifetime_spend: number;
  daily_input_tokens?: number;
  daily_output_tokens?: number;
  monthly_input_tokens?: number;
  monthly_output_tokens?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
  source?: string;
  note?: string;
}

interface WorkerStatus {
  name: string;
  type: "local" | "remote" | "cloud";
  status: "online" | "offline" | "degraded" | "offline (unconfigured)";
  role: string;
}

interface WorkerDetails {
  hardware: string;
  activeModel: string;
  responsibilities: string[];
  connection: string;
  performance: string;
}

const WORKER_DETAILS: Record<string, WorkerDetails> = {
  "LM Studio": {
    hardware: "Local CPU/GPU Swarm (Apple Silicon M-series/RTX Core)",
    activeModel: "Qwen2.5-Coder-7B-Instruct / Hermes-3-Llama3.1-8B (Q4_K_M)",
    responsibilities: [
      "System 2 Supervisor audits and semantic validation",
      "AST (Abstract Syntax Tree) static safety reviews",
      "Local reasoning, code logic checking, and offline execution capability",
      "Local supervisor fallback for critical security decision-making"
    ],
    connection: "http://localhost:1234/v1 (Local Daemon)",
    performance: "~25ms / ~45 tokens/sec execution speed"
  },
  "Gemini Flash": {
    hardware: "Google Tensor TPU v5e/v6 Cloud Clusters",
    activeModel: "gemini-2.0-flash / gemini-3-flash",
    responsibilities: [
      "Deep cloud-grounded developer research and API telemetry",
      "Dense code audits and large-context structural analysis",
      "Multi-agent debate synthesis & global consensus reasoning",
      "Official package documentation crawling and standard verifications"
    ],
    connection: "Secure Cloud API Gateway Router (HTTPS TLS 1.3)",
    performance: "~120ms / ~110 tokens/sec high-throughput generation"
  },
  "P330 Worker": {
    hardware: "Nvidia RTX 4090 / 24GB VRAM Remote Compute Cluster",
    activeModel: "bge-large-en-v1.5 / deepseek-coder-6.7b",
    responsibilities: [
      "Incremental embedding generation and codebase topology indexing",
      "Speculative AST verification and parallel reasoning checks",
      "High-dimensional vector search mappings and similarity computations",
      "Heavy off-loaded model execution routines"
    ],
    connection: "Remote Intranet Node (http://192.168.1.180:8000)",
    performance: "~18ms / ~65 tokens/sec compute capability"
  },
  "ChromaDB": {
    hardware: "Local NVMe High-IOPS Memory Partition",
    activeModel: "nomic-embed-text / Sentence-Transformers (Local Index)",
    responsibilities: [
      "Short-Term Memory storage & search infrastructure (System 3)",
      "High-dimensional vector space mapping of workspace files",
      "Cross-session semantic recall and continuous codebase embeddings",
      "Sub-millisecond cosine distance querying for code retrieval"
    ],
    connection: "http://portable_chroma:8000 (Docker Private Net)",
    performance: "< 5ms query response time"
  },
  "Legion Sentry": {
    hardware: "Raspberry Pi 4 Model B (4GB RAM) / Quad-core Cortex-A72 @ 1.8GHz",
    activeModel: "FTLDNS v5.24 + Unbound Recursive DNS Root Resolver",
    responsibilities: [
      "Network-wide ad-blocking and telemetry sinkhole (Pi-hole)",
      "DNS-over-HTTPS (DoH) recursive query resolver without ISP interception",
      "LAN perimeter device discovery, ARP inspection, and security sentry",
      "Hardware telemetry monitoring (thermal, load, RAM) for the sovereign cluster"
    ],
    connection: "http://192.168.1.183:80 / SSH (Tailscale: legion-sentry)",
    performance: "< 1.5ms cached DNS latency / 15-20% ad sinkhole rate"
  }
};

const COLOR_TOKENS = [
  { id: "primary", name: "Deep Navy (Primary)", variable: "--color-primary", lightHex: "#1A1C1E", darkHex: "#1A1C1E", description: "Primary text, deep boundaries, and structural frames" },
  { id: "secondary", name: "Slate Gray (Secondary)", variable: "--color-secondary", lightHex: "#6C7278", darkHex: "#6C7278", description: "Secondary text, subtle labels, and metadata" },
  { id: "tertiary", name: "Boston Clay (Accent)", variable: "--color-tertiary", lightHex: "#B8422E", darkHex: "#B8422E", description: "Primary interactive accent and focus indicators" },
  { id: "neutral", name: "Matte Paper (Neutral)", variable: "--color-neutral", lightHex: "#F7F5F2", darkHex: "#0D0E10", description: "Canvas background, cards, and modal sheets" },
  { id: "border", name: "Structural Border", variable: "--color-border", lightHex: "rgba(26, 28, 30, 0.08)", darkHex: "rgba(255, 255, 255, 0.08)", description: "Ultra-thin minimalist borders" }
];

function ColorSwatch({ token }: { token: typeof COLOR_TOKENS[0] }) {
  const [copied, setCopied] = useState(false);
  const copyVar = () => {
    navigator.clipboard.writeText(`var(${token.variable})`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={copyVar}
      className="p-3 border border-border/40 bg-card/40 rounded-md flex items-center justify-between text-left hover:border-tertiary transition-all cursor-pointer w-full group"
    >
      <div className="flex items-center gap-3">
        <div 
          className="w-6 h-6 rounded-md border border-border shadow-xs shrink-0" 
          style={{ backgroundColor: `var(${token.variable})` }} 
        />
        <div>
          <div className="text-xs font-semibold text-foreground group-hover:text-tertiary transition-colors">{token.name}</div>
          <div className="text-[10px] text-secondary font-mono">{token.variable}</div>
        </div>
      </div>
      <div className="text-right font-mono text-[10px] text-secondary space-y-0.5">
        <div>Light: {token.lightHex}</div>
        {copied && <div className="text-tertiary text-[9px] font-bold">COPIED</div>}
      </div>
    </button>
  );
}

/** Compact token formatter: 2142029 -> "2.14M", 108220 -> "108.2K". */
function formatTokens(n: number): string {
  if (!n || n < 0) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

export default function FleetCommand() {
  const API_BASE = CONFIG.API_BASE;
  const [mounted, setMounted] = useState(false);
  const [tools, setTools] = useState<ToolStat[]>([]);
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [toolsLoaded, setToolsLoaded] = useState(false);
  const [budget, setBudget] = useState<BudgetData | null>(null);
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [sentryStats, setSentryStats] = useState<{ queries: number; blocked: number; pct: number } | null>(null);
  const [sentryTelemetry, setSentryTelemetry] = useState<SentryTelemetryData | null>(null);
  const [sentryLoadingAction, setSentryLoadingAction] = useState<string | null>(null);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [sentryActionResult, setSentryActionResult] = useState<{ message?: string; error?: string; data?: any } | null>(null);
  const [confirmAction, setConfirmAction] = useState<"poweroff" | "reboot" | null>(null);
  const [selectedTool, setSelectedTool] = useState<ToolStat | null>(null);
  const [selectedWorker, setSelectedWorker] = useState<WorkerStatus | null>(null);
  const [error, setError] = useState(false);
  const [toolSearchQuery, setToolSearchQuery] = useState<string>("");
  const [selectedToolCategory, setSelectedToolCategory] = useState<string>("all");
  const [isBlueprintExpanded, setIsBlueprintExpanded] = useState<boolean>(true);

  useEffect(() => {
      // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelectedTool(null);
        setSelectedWorker(null);
        setConfirmAction(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (selectedTool || selectedWorker || confirmAction) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [selectedTool, selectedWorker, confirmAction]);

  const triggerSentryAction = async (action: string) => {
    setSentryLoadingAction(action);
    setSentryActionResult(null);
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/sentry/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.detail || "Action failed");
      }
      setSentryActionResult({ 
        message: json.message || "Action completed successfully.",
        data: json.data || json.devices 
      });
      setTimeout(fetchData, 1500);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      setSentryActionResult({ error: err.message || "Failed to execute Sentry action." });
    } finally {
      setSentryLoadingAction(null);
      setConfirmAction(null);
    }
  };

  const fetchData = useCallback(async () => {
    try {
      const statsRes = await tenantFetch(`${API_BASE}/stats`, { cache: 'no-store' });
      if (!statsRes.ok) throw new Error("API_ERROR");
      const statsData = await statsRes.json();
      
      const liveTools: unknown[] = Array.isArray(statsData.intelligence)
        ? statsData.intelligence
        : [];

      const validatedTools = liveTools.map((t: unknown) => validateToolStat(t));
      setTools(validatedTools.sort((a: ToolStat, b: ToolStat) => b.success_rate - a.success_rate));
      setToolsLoaded(true);

      // Extract budget & tokens
      if (statsData.budget) {
        setBudget(statsData.budget);
      }

      // Build worker status dynamically
      const lmStudioOnline = statsData.telemetry?.lm_studio?.status === "Online";
      const p330Online = statsData.telemetry?.p330?.status === "online";
      const configuredNodes = statsData.configured_nodes || {};

      let sentryOnline = false;
      try {
        const sentryRes = await tenantFetch(`${API_BASE}/api/v1/sentry/telemetry`, {
          signal: AbortSignal.timeout(2500)
        });
        if (sentryRes.ok) {
          const sentryData: SentryTelemetryData = await sentryRes.json();
          setSentryTelemetry(sentryData);
          if (sentryData && sentryData.status === "online") {
            sentryOnline = true;
            setSentryStats({
              queries: sentryData.queries_total ?? 0,
              blocked: sentryData.queries_blocked ?? 0,
              pct: sentryData.blocked_percent ?? 0
            });
          }
        }
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      } catch (e) {
        sentryOnline = false;
      }

      setWorkers([
        {
          name: "LM Studio",
          type: "local",
          status: lmStudioOnline ? "online" : "offline",
          role: "System 2 Supervisor — Local reasoning & code review"
        },
        {
          name: "Gemini Flash",
          type: "cloud",
          status: configuredNodes.gemini ? "online" : "offline (unconfigured)",
          role: "System 1 Cloud AI — Research, code review, consensus"
        },
        {
          name: "OpenAI",
          type: "cloud",
          status: configuredNodes.openai ? "online" : "offline (unconfigured)",
          role: "System 1 Cloud AI Fallback"
        },
        {
          name: "DeepSeek",
          type: "cloud",
          status: configuredNodes.deepseek ? "online" : "offline (unconfigured)",
          role: "Advanced Logic / Code Generation"
        },
        {
          name: "P330 Worker",
          type: "remote",
          status: p330Online ? "online" : "offline",
          role: "Remote GPU Node — Embeddings & heavy inference"
        },
        {
          name: "ChromaDB",
          type: "local",
          status: "online",
          role: "Vector Memory — Semantic search & code topology"
        },
        {
          name: "Legion Sentry",
          type: "remote",
          status: sentryOnline ? "online" : "offline",
          role: sentryOnline && sentryStats
            ? `DNS Sentry — Active (${sentryStats.blocked} ads / ${sentryStats.pct.toFixed(1)}% blocked today)`
            : "DNS Sentry — Recursive local resolver & Pi-hole filter"
        },
      ]);

      setError(false);
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (err) {
      setError(true);
      setToolsLoaded(true);
    }
  }, [API_BASE]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const getConfidenceColor = (conf: string) => {
    switch (conf) {
      case "HIGH": return "text-emerald-500 border-emerald-500/30 bg-emerald-500/10";
      case "MEDIUM": return "text-amber-500 border-amber-500/30 bg-amber-500/10";
      default: return "text-secondary border-border bg-neutral/40";
    }
  };

  const getDeltaIcon = (delta: number) => {
    if (delta > 10) return <ArrowUpRight className="w-3 h-3 text-emerald-500" />;
    if (delta < -5) return <ArrowDownRight className="w-3 h-3 text-red-500" />;
    return <Minus className="w-3 h-3 opacity-30" />;
  };

  const getWorkerIcon = (type: string) => {
    switch (type) {
      case "local": return <Server className="w-4 h-4" />;
      case "remote": return <Cpu className="w-4 h-4" />;
      case "cloud": return <Cloud className="w-4 h-4" />;
      default: return <CircleDot className="w-4 h-4" />;
    }
  };

  const onlineWorkers = workers.filter(w => w.status === "online").length;
  const avgSuccessRate = tools.length > 0
    ? (tools.reduce((sum, t) => sum + t.success_rate, 0) / tools.length * 100).toFixed(1)
    : "0";

  // Token totals calculation
  const totalInputTokens = budget?.total_input_tokens ?? 0;
  const totalOutputTokens = budget?.total_output_tokens ?? 0;
  const totalTokensAll = totalInputTokens + totalOutputTokens;
  const monthlyTokensAll = (budget?.monthly_input_tokens ?? 0) + (budget?.monthly_output_tokens ?? 0);
  const dailyTokensAll = (budget?.daily_input_tokens ?? 0) + (budget?.daily_output_tokens ?? 0);
  const inputPct = totalTokensAll > 0 ? Math.round((totalInputTokens / totalTokensAll) * 100) : 0;
  const outputPct = totalTokensAll > 0 ? 100 - inputPct : 0;

  // Filtered tools computation
  const filteredTools = useMemo(() => {
    return tools.filter((tool: ToolStat) => {
      const matchSearch = tool.tool_id.toLowerCase().includes(toolSearchQuery.toLowerCase());
      if (!matchSearch) return false;
      if (selectedToolCategory === "all") return true;
      if (selectedToolCategory === "audit") {
        return tool.tool_id.includes("audit") || tool.tool_id.includes("supervisor") || tool.tool_id.includes("review") || tool.tool_id.includes("linter");
      }
      if (selectedToolCategory === "memory") {
        return tool.tool_id.includes("memory") || tool.tool_id.includes("hivemind") || tool.tool_id.includes("fix") || tool.tool_id.includes("index") || tool.tool_id.includes("codebase");
      }
      if (selectedToolCategory === "execution") {
        return tool.tool_id.includes("code") || tool.tool_id.includes("checkpoint") || tool.tool_id.includes("git") || tool.tool_id.includes("execute");
      }
      if (selectedToolCategory === "strategy") {
        return tool.tool_id.includes("orchestrate") || tool.tool_id.includes("blueprint") || tool.tool_id.includes("kanban") || tool.tool_id.includes("delegate") || tool.tool_id.includes("cronjob");
      }
      if (selectedToolCategory === "infrastructure") {
        return tool.tool_id.includes("workspace") || tool.tool_id.includes("stats") || tool.tool_id.includes("health") || tool.tool_id.includes("tokens");
      }
      if (selectedToolCategory === "sensory") {
        return tool.tool_id.includes("browser") || tool.tool_id.includes("web") || tool.tool_id.includes("vision") || tool.tool_id.includes("speech") || tool.tool_id.includes("audio");
      }
      return true;
    });
  }, [tools, toolSearchQuery, selectedToolCategory]);

  return (
    <>
      <div className="h-screen overflow-hidden bg-background flex selection:bg-tertiary selection:text-white max-w-[100vw]">
        <Sidebar />
        
        <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 h-screen overflow-hidden min-w-0">
          {/* HEADER */}
          <header className="h-16 sm:h-20 border-b border-border flex items-center justify-between px-4 sm:px-6 lg:px-10 bg-background/80 z-20 sticky top-0 backdrop-blur-xl shrink-0">
            <div className="flex items-center gap-3">
              <span className="font-serif italic text-lg sm:text-xl text-primary font-bold">Agents & Fleet Command</span>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 border border-border bg-card/60 rounded-md text-[10px] font-mono">
                <span className="text-secondary font-bold uppercase">Workers</span>
                <span className="text-primary font-bold">{onlineWorkers}/{workers.length}</span>
              </div>
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 border border-border bg-card/60 rounded-md text-[10px] font-mono">
                <span className="text-secondary font-bold uppercase">Avg Accuracy</span>
                <span className="text-primary font-bold">{avgSuccessRate}%</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 border border-tertiary/30 bg-tertiary/10 rounded-md text-[10px] font-mono text-tertiary">
                <span className="font-bold uppercase">Total Tokens</span>
                <span className="font-bold select-all">{formatTokens(totalTokensAll)}</span>
              </div>
            </div>
          </header>

          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-10 space-y-8 relative z-10 custom-scrollbar pb-20"
          >
            {error && (
              <div className="p-4 border border-red-500/30 bg-red-500/10 rounded-md flex items-center gap-4 text-red-500 text-xs font-mono">
                <ShieldAlert className="w-5 h-5 shrink-0" />
                <div>
                  <span className="font-bold block">Fleet Gateway Offline</span>
                  <span className="opacity-80">Mission Control API unreachable at {API_BASE}</span>
                </div>
              </div>
            )}

            {/* DEVELOPER ARCHITECTURE & COGNITIVE ENGINE BLUEPRINT */}
            <section className="border border-tertiary/20 bg-card/70 backdrop-blur-md rounded-md p-6 lg:p-8 space-y-6 shadow-sm text-left">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-primary/5 pb-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <BrainCircuit className="w-5 h-5 text-tertiary" />
                    <h2 className="text-base sm:text-lg font-serif font-bold text-primary italic">
                      Developer Architecture Blueprint // 4-System Cognitive Engine
                    </h2>
                  </div>
                  <p className="text-xs text-secondary opacity-80 font-sans">
                    How Kenbun coordinates autonomous multi-agent reasoning, guardrail audits, vector memory, and hardware cluster nodes.
                  </p>
                </div>
                <button
                  onClick={() => setIsBlueprintExpanded(!isBlueprintExpanded)}
                  className="self-start sm:self-auto px-3 py-1.5 border border-primary/10 hover:border-tertiary/40 text-[9px] font-mono font-bold uppercase tracking-widest text-secondary hover:text-primary rounded-md transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <BookOpen className="w-3.5 h-3.5 text-tertiary" />
                  <span>{isBlueprintExpanded ? "Collapse Guide" : "Read Architecture Spec"}</span>
                </button>
              </div>

              {isBlueprintExpanded && (
                <div className="space-y-6">
                  {/* 4 Cognitive Systems Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="p-4 border border-primary/5 bg-primary/[0.02] rounded-md space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-tertiary">System 1</span>
                        <Zap className="w-3.5 h-3.5 text-tertiary" />
                      </div>
                      <div className="text-xs font-bold text-primary uppercase font-mono">Execution & Tools</div>
                      <p className="text-[11px] text-secondary leading-relaxed font-sans opacity-85">
                        Dynamic Harvester discovers <strong>88 sovereign FastMCP tools</strong>. Routes tasks, auto-fixes linter issues, executes code in sandboxes, and tracks Bayesian tool reliability.
                      </p>
                    </div>

                    <div className="p-4 border border-emerald-500/20 bg-emerald-500/[0.02] rounded-md space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-emerald-500">System 2</span>
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                      </div>
                      <div className="text-xs font-bold text-primary uppercase font-mono">Supervisor & Audit</div>
                      <p className="text-[11px] text-secondary leading-relaxed font-sans opacity-85">
                        Local Qwen2.5-Coder (LM Studio/Ollama) & Gemini Cloud perform <strong>multi-model consensus audits</strong>, AST static analysis, and block hazardous commands before execution.
                      </p>
                    </div>

                    <div className="p-4 border border-primary/5 bg-primary/[0.02] rounded-md space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-tertiary">System 3</span>
                        <Database className="w-3.5 h-3.5 text-tertiary" />
                      </div>
                      <div className="text-xs font-bold text-primary uppercase font-mono">Memory & Vectors</div>
                      <p className="text-[11px] text-secondary leading-relaxed font-sans opacity-85">
                        ChromaDB (6,977 codebase vectors) + Honcho dialectic fix memory. Sub-5ms cosine search for contextual codebase recall and auto-recovery.
                      </p>
                    </div>

                    <div className="p-4 border border-primary/5 bg-primary/[0.02] rounded-md space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-tertiary">System 4</span>
                        <Layers className="w-3.5 h-3.5 text-tertiary" />
                      </div>
                      <div className="text-xs font-bold text-primary uppercase font-mono">Workspace & Steering</div>
                      <p className="text-[11px] text-secondary leading-relaxed font-sans opacity-85">
                        Shared cognitive blackboard. Concepts decay with temporal salience (0.0 - 1.0). Allows developer to inject real-time steering directives mid-flight.
                      </p>
                    </div>
                  </div>

                  {/* Hardware Topology Explainer */}
                  <div className="p-4 border border-primary/5 bg-card/50 rounded-md flex flex-col md:flex-row md:items-center justify-between gap-4 text-[11px] font-mono text-secondary">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-tertiary shrink-0" />
                      <span><strong>Cluster Topology:</strong> Host (M-Series / Uvicorn + Next.js) ➔ Remote P330 (RTX 4090 GPU Embeddings) ➔ Legion Sentry (Pi-hole DNS Sinkhole :183)</span>
                    </div>
                    <div className="shrink-0 flex items-center gap-1 text-emerald-500 font-bold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Zero Cloud Lock-In</span>
                    </div>
                  </div>
                </div>
              )}
            </section>

            {/* SECTION 1: COMPUTE TOKEN LEDGER (REDESIGNED HERO) */}
            {budget && (
              <section className="border border-border/60 bg-card/60 backdrop-blur-md rounded-md overflow-hidden shadow-xs">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-border/40 bg-neutral/30">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary">
                      LLM Compute Token Telemetry
                    </h2>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] font-mono text-secondary">
                    <span className="px-2 py-0.5 rounded-sm bg-card border border-border uppercase font-semibold">
                      {budget.source === "kenbun_router" ? "Kenbun Router Ledger" : "System 4 Governor"}
                    </span>
                  </div>
                </div>

                {/* 4-KPI Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-border/40">
                  {/* 1. All-Time Hero */}
                  <div className="p-6 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-secondary font-bold">All-Time Tokens</span>
                      <Flame className="w-3.5 h-3.5 text-tertiary" />
                    </div>
                    <div>
                      <div className="text-3xl lg:text-4xl font-serif font-bold text-primary tracking-tight select-all">
                        {formatTokens(totalTokensAll)}
                      </div>
                      <div className="text-[11px] font-mono text-secondary pt-0.5 select-all">
                        {totalTokensAll.toLocaleString()} total processed
                      </div>
                    </div>
                    {/* Ratio bar */}
                    <div className="space-y-1.5 pt-1">
                      <div className="flex h-2 w-full rounded-full overflow-hidden bg-neutral border border-border/40">
                        <div className="h-full bg-tertiary" style={{ width: `${inputPct}%` }} />
                        <div className="h-full bg-secondary/40" style={{ width: `${outputPct}%` }} />
                      </div>
                      <div className="flex justify-between text-[9px] font-mono text-secondary">
                        <span>Input: {inputPct}%</span>
                        <span>Output: {outputPct}%</span>
                      </div>
                    </div>
                  </div>

                  {/* 2. Input / Output Breakdown */}
                  <div className="p-6 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-secondary font-bold">Input vs Output</span>
                      <Database className="w-3.5 h-3.5 text-secondary" />
                    </div>
                    <div className="space-y-2">
                      <div className="p-2.5 rounded-md bg-neutral/40 border border-border/40 flex items-center justify-between">
                        <span className="text-xs font-mono text-secondary flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-sm bg-tertiary" /> Input:
                        </span>
                        <span className="text-xs font-mono font-bold text-primary select-all">
                          {formatTokens(totalInputTokens)} <span className="text-[10px] text-secondary font-normal">({inputPct}%)</span>
                        </span>
                      </div>
                      <div className="p-2.5 rounded-md bg-neutral/40 border border-border/40 flex items-center justify-between">
                        <span className="text-xs font-mono text-secondary flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-sm bg-secondary/40" /> Output:
                        </span>
                        <span className="text-xs font-mono font-bold text-primary select-all">
                          {formatTokens(totalOutputTokens)} <span className="text-[10px] text-secondary font-normal">({outputPct}%)</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 3. Today */}
                  <div className="p-6 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-secondary font-bold">Today</span>
                      <span className="text-[9px] font-mono font-bold uppercase text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-sm border border-emerald-500/20">● Live</span>
                    </div>
                    <div>
                      <div className="text-2xl lg:text-3xl font-serif font-bold text-primary select-all">
                        {formatTokens(dailyTokensAll)}
                      </div>
                      <div className="text-[11px] font-mono text-secondary pt-1">
                        in {formatTokens(budget.daily_input_tokens || 0)} · out {formatTokens(budget.daily_output_tokens || 0)}
                      </div>
                    </div>
                    <div className="text-[10px] font-mono text-secondary/70 pt-1">
                      Daily limit: ${budget.daily_limit?.toFixed(2) || "20.00"}
                    </div>
                  </div>

                  {/* 4. This Month */}
                  <div className="p-6 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-secondary font-bold">This Month</span>
                      <Clock className="w-3.5 h-3.5 text-secondary" />
                    </div>
                    <div>
                      <div className="text-2xl lg:text-3xl font-serif font-bold text-tertiary select-all">
                        {formatTokens(monthlyTokensAll)}
                      </div>
                      <div className="text-[11px] font-mono text-secondary pt-1">
                        in {formatTokens(budget.monthly_input_tokens || 0)} · out {formatTokens(budget.monthly_output_tokens || 0)}
                      </div>
                    </div>
                    <div className="text-[10px] font-mono text-secondary/70 pt-1">
                      Total recorded compute cycles
                    </div>
                  </div>
                </div>

                {/* Footnote */}
                <div className="px-6 py-2.5 bg-neutral/20 border-t border-border/40 text-[10px] font-mono text-secondary flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-tertiary" />
                  <span>Counts actual LLM tokens routed through the Kenbun router across Gemini, OpenAI, and local LLM agents.</span>
                </div>
              </section>
            )}

            {/* SECTION 2: WORKER NODES */}
            <section className="space-y-4">
              <div className="flex items-center gap-3">
                <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary">
                  Infrastructure Nodes ({onlineWorkers}/{workers.length} Online)
                </h2>
                <div className="flex-1 h-[1px] bg-border/60" />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {workers.map((worker, i) => (
                  <motion.button 
                    key={worker.name}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    onClick={() => setSelectedWorker(worker)}
                    type="button"
                    className="p-5 border border-border/60 bg-card/60 backdrop-blur-md text-left w-full rounded-md space-y-4 hover:border-tertiary/60 hover:bg-card transition-all cursor-pointer shadow-xs group"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className={`w-8 h-8 rounded-md border flex items-center justify-center ${
                          worker.status === "online" 
                            ? "border-emerald-500/30 text-emerald-500 bg-emerald-500/10" 
                            : worker.status === "degraded"
                              ? "border-amber-500/30 text-amber-500 bg-amber-500/10"
                              : "border-red-500/30 text-red-500 bg-red-500/10"
                        }`}>
                          {getWorkerIcon(worker.type)}
                        </div>
                        <div>
                          <div className="text-xs font-serif font-bold text-primary group-hover:text-tertiary transition-colors">{worker.name}</div>
                          <div className="text-[9px] font-mono uppercase text-secondary">{worker.type}</div>
                        </div>
                      </div>
                      <div className={`w-2 h-2 rounded-full ${
                        worker.status === "online" ? "bg-emerald-500" : worker.status === "degraded" ? "bg-amber-500" : "bg-red-500"
                      }`} />
                    </div>

                    <p className="text-[11px] text-secondary font-mono leading-relaxed line-clamp-2">{worker.role}</p>

                    <div className="flex items-center justify-between gap-2 pt-1 border-t border-border/40">
                      <span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded-sm font-bold ${
                        worker.status === "online" 
                          ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20" 
                          : worker.status === "degraded"
                            ? "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                            : "bg-red-500/10 text-red-600 border border-red-500/20"
                      }`}>
                        {worker.status}
                      </span>
                      {worker.name === "Legion Sentry" && sentryTelemetry && sentryTelemetry.status === "online" && (
                        <span className="text-[9px] font-mono text-tertiary font-bold">
                          {sentryTelemetry.ram_percent}% RAM · {sentryTelemetry.cpu_temp_c}°C
                        </span>
                      )}
                    </div>
                  </motion.button>
                ))}
              </div>
            </section>

            {/* SECTION 3: TOOL INTELLIGENCE GRID */}
            <section className="space-y-4 text-left">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary">
                    Tool Matrix ({filteredTools.length} / {tools.length} Tools)
                  </h2>
                  <div className="w-12 h-[1px] bg-border/60" />
                </div>
                <span className="text-[10px] font-mono text-secondary">Recency-Weighted Posterior Scores</span>
              </div>

              {/* Tool Search & Category Filter Toolbar */}
              <div className="flex flex-col md:flex-row gap-3 p-4 border border-border/60 bg-card/40 rounded-md">
                <div className="relative flex-grow">
                  <Search className="w-3.5 h-3.5 text-secondary absolute left-3.5 top-3" />
                  <input
                    type="text"
                    value={toolSearchQuery}
                    onChange={(e) => setToolSearchQuery(e.target.value)}
                    placeholder="Search tools (e.g. 'supervisor', 'checkpoint', 'browser')..."
                    className="w-full pl-9 pr-4 py-2 border border-border/60 rounded-md bg-card/60 font-mono text-xs focus:outline-none focus:border-tertiary text-primary placeholder-secondary/40"
                  />
                </div>
                <div className="flex items-center gap-1.5 flex-wrap overflow-x-auto">
                  {(["all", "audit", "execution", "memory", "strategy", "infrastructure", "sensory"] as const).map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setSelectedToolCategory(cat)}
                      className={`px-2.5 py-1 text-[9px] font-mono font-bold uppercase tracking-wider rounded transition-all cursor-pointer ${
                        selectedToolCategory === cat
                          ? "bg-tertiary text-primary shadow-xs"
                          : "bg-neutral/40 hover:bg-neutral text-secondary hover:text-primary"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-4">
                <WeightFormula tools={tools} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                {filteredTools.map((tool: ToolStat, i: number) => (
                  <motion.button
                    key={`${tool.tool_id}-${i}`}
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.02 }}
                    onClick={() => setSelectedTool(selectedTool?.tool_id === tool.tool_id ? null : tool)}
                    className={`p-4 border text-left rounded-md transition-all cursor-pointer shadow-xs ${
                      selectedTool?.tool_id === tool.tool_id
                        ? 'border-tertiary bg-tertiary/10 ring-1 ring-tertiary'
                        : 'border-border/60 bg-card/60 hover:bg-card hover:border-tertiary/40'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-mono font-bold text-secondary uppercase tracking-wider truncate max-w-[120px]">
                        {tool.tool_id}
                      </span>
                      <div className={`w-1.5 h-1.5 rounded-full ${tool.success_rate > 0.7 ? 'bg-emerald-500' : tool.success_rate > 0.5 ? 'bg-amber-500' : 'bg-red-500'}`} />
                    </div>

                    <div className="text-xl font-serif font-bold text-primary mb-2">
                      {(tool.success_rate * 100).toFixed(1)}%
                    </div>

                    <div className="h-1 bg-neutral rounded-full overflow-hidden mb-2.5 border border-border/40">
                      <div
                        className="h-full bg-tertiary rounded-full"
                        style={{ width: `${tool.success_rate * 100}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <span className={`text-[8px] font-mono uppercase px-1.5 py-0.5 rounded-sm font-bold border ${getConfidenceColor(tool.confidence)}`}>
                        {tool.confidence}
                      </span>
                      <div className="flex items-center gap-1">
                        {getDeltaIcon(tool.delta)}
                        <span className="text-[9px] font-mono text-secondary/60">{tool.entropy.toFixed(2)}</span>
                      </div>
                    </div>
                  </motion.button>
                ))}
              </div>
            </section>

            {/* SECTION 4: DESIGN SYSTEM TOKEN REGISTRY */}
            <section className="p-6 border border-border/60 bg-card/40 rounded-md space-y-4">
              <div className="flex items-center gap-3">
                <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary">
                  Heritage Design System Tokens
                </h2>
                <div className="flex-1 h-[1px] bg-border/60" />
                <span className="text-[10px] font-mono text-secondary">ACTIVE SPEC</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {COLOR_TOKENS.map((token) => (
                  <ColorSwatch key={token.id} token={token} />
                ))}
              </div>
            </section>
          </motion.div>
        </main>
      </div>

      {/* ========================================================================= */}
      {/* PORTALED MODALS - Rendered to document.body for true full viewport        */}
      {/* ========================================================================= */}
      {mounted && createPortal(
        <>
          {/* 1. TOOL DETAIL MODAL */}
          <AnimatePresence>
            {selectedTool && (
              <div className="fixed inset-0 z-[9990] flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => setSelectedTool(null)}
                  className="fixed inset-0 w-full h-full bg-black/60 backdrop-blur-md cursor-pointer"
                />
                <motion.div
                  initial={{ scale: 0.95, opacity: 0, y: 15 }}
                  animate={{ scale: 1, opacity: 1, y: 0 }}
                  exit={{ scale: 0.95, opacity: 0, y: 15 }}
                  role="dialog"
                  aria-modal="true"
                  onClick={(e) => e.stopPropagation()}
                  className="relative w-full max-w-3xl bg-card border border-border p-6 sm:p-8 rounded-md shadow-2xl z-10 space-y-6 my-auto max-h-[90vh] overflow-y-auto custom-scrollbar"
                >
                  <div className="flex items-center justify-between border-b border-border pb-4">
                    <div className="space-y-1">
                      <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-tertiary">Tool Telemetry Spec</span>
                      <h3 className="text-xl font-serif font-bold text-primary uppercase">{selectedTool.tool_id}</h3>
                    </div>
                    <button
                      onClick={() => setSelectedTool(null)}
                      className="px-3 py-1.5 border border-border text-[10px] font-mono font-bold hover:border-tertiary hover:text-tertiary transition-colors rounded-md uppercase cursor-pointer"
                    >
                      CLOSE [ESC]
                    </button>
                  </div>
                  <ToolDetailPanel selectedTool={selectedTool} />
                </motion.div>
              </div>
            )}
          </AnimatePresence>

          {/* 2. WORKER NODE PROFILE MODAL */}
          <AnimatePresence>
            {selectedWorker && (() => {
              const details = WORKER_DETAILS[selectedWorker.name];
              return (
                <div className="fixed inset-0 z-[9990] flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={() => setSelectedWorker(null)}
                    className="fixed inset-0 w-full h-full bg-black/60 backdrop-blur-md cursor-pointer"
                  />
                  <motion.div
                    initial={{ scale: 0.95, opacity: 0, y: 15 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.95, opacity: 0, y: 15 }}
                    role="dialog"
                    aria-modal="true"
                    onClick={(e) => e.stopPropagation()}
                    className="relative w-full max-w-2xl bg-card border border-border p-6 sm:p-8 rounded-md shadow-2xl z-10 space-y-6 my-auto max-h-[90vh] overflow-y-auto custom-scrollbar"
                  >
                    <div className="flex items-center justify-between border-b border-border pb-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-md border flex items-center justify-center ${
                          selectedWorker.status === "online" 
                            ? "border-emerald-500/30 text-emerald-500 bg-emerald-500/10" 
                            : "border-amber-500/30 text-amber-500 bg-amber-500/10"
                        }`}>
                          {getWorkerIcon(selectedWorker.type)}
                        </div>
                        <div>
                          <span className="text-[10px] font-mono uppercase tracking-widest text-tertiary font-bold">Node Profile</span>
                          <h3 className="text-xl font-serif font-bold text-primary uppercase">{selectedWorker.name}</h3>
                        </div>
                      </div>
                      <button
                        onClick={() => setSelectedWorker(null)}
                        className="px-3 py-1.5 border border-border text-[10px] font-mono font-bold hover:border-tertiary hover:text-tertiary transition-colors rounded-md uppercase cursor-pointer"
                      >
                        CLOSE [ESC]
                      </button>
                    </div>

                    {details ? (
                      <div className="space-y-4 text-xs font-mono">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div className="p-3 border border-border/60 bg-neutral/30 rounded-md">
                            <span className="text-[9px] uppercase tracking-wider text-secondary font-bold">Hardware</span>
                            <p className="mt-1 font-serif font-bold text-primary">{details.hardware}</p>
                          </div>
                          <div className="p-3 border border-border/60 bg-neutral/30 rounded-md">
                            <span className="text-[9px] uppercase tracking-wider text-secondary font-bold">Active Model</span>
                            <p className="mt-1 font-bold text-tertiary truncate">{details.activeModel}</p>
                          </div>
                        </div>

                        <div className="p-3.5 border border-border/60 bg-neutral/30 rounded-md space-y-2">
                          <span className="text-[9px] uppercase tracking-wider text-secondary font-bold">Responsibilities</span>
                          <ul className="list-disc pl-4 space-y-1 text-secondary font-sans text-xs">
                            {details.responsibilities.map((resp, idx) => (
                              <li key={idx}>{resp}</li>
                            ))}
                          </ul>
                        </div>

                        {/* SENTRY ACTIONS */}
                        {selectedWorker.name === "Legion Sentry" && (
                          <div className="space-y-3 pt-2">
                            <span className="text-[10px] font-mono uppercase text-tertiary font-bold">Sentry Actions</span>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                              <button
                                type="button"
                                onClick={() => triggerSentryAction("speedtest")}
                                disabled={!!sentryLoadingAction}
                                className="px-3 py-2 border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 rounded-md font-bold text-[10px] flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                              >
                                <Zap className="w-3.5 h-3.5" /> Speedtest
                              </button>
                              <button
                                type="button"
                                onClick={() => triggerSentryAction("netwatch")}
                                disabled={!!sentryLoadingAction}
                                className="px-3 py-2 border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-600 rounded-md font-bold text-[10px] flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                              >
                                <Search className="w-3.5 h-3.5" /> Scan LAN
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedWorker(null);
                                  setConfirmAction("reboot");
                                }}
                                disabled={!!sentryLoadingAction}
                                className="px-3 py-2 border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 rounded-md font-bold text-[10px] flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                              >
                                <RefreshCw className="w-3.5 h-3.5" /> Reboot
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedWorker(null);
                                  setConfirmAction("poweroff");
                                }}
                                disabled={!!sentryLoadingAction}
                                className="px-3 py-2 border border-red-500/30 bg-red-500/10 hover:bg-red-500/20 text-red-600 rounded-md font-bold text-[10px] flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                              >
                                <Power className="w-3.5 h-3.5" /> Safe Shutdown
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-center opacity-40 py-8 font-mono">Telemetry profiling offline for this worker node.</p>
                    )}
                  </motion.div>
                </div>
              );
            })()}
          </AnimatePresence>

          {/* 3. SENTRY SAFE SHUTDOWN & REBOOT CONFIRMATION MODAL */}
          <AnimatePresence>
            {confirmAction && (
              <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => setConfirmAction(null)}
                  className="fixed inset-0 w-full h-full bg-black/75 backdrop-blur-md cursor-pointer"
                />
                <motion.div
                  initial={{ scale: 0.95, opacity: 0, y: 15 }}
                  animate={{ scale: 1, opacity: 1, y: 0 }}
                  exit={{ scale: 0.95, opacity: 0, y: 15 }}
                  role="alertdialog"
                  aria-modal="true"
                  onClick={(e) => e.stopPropagation()}
                  className={`relative w-full max-w-lg min-w-[320px] sm:min-w-[480px] bg-card p-6 sm:p-8 rounded-md border-2 z-10 space-y-6 shadow-2xl my-auto ${
                    confirmAction === "poweroff" ? "border-red-500/60" : "border-amber-500/60"
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-md flex items-center justify-center shrink-0 ${
                      confirmAction === "poweroff" ? "bg-red-500/20 text-red-500" : "bg-amber-500/20 text-amber-500"
                    }`}>
                      {confirmAction === "poweroff" ? <Power className="w-6 h-6" /> : <RefreshCw className="w-6 h-6" />}
                    </div>
                    <div>
                      <h4 className="text-lg sm:text-xl font-bold text-primary uppercase font-serif tracking-tight">
                        {confirmAction === "poweroff" ? "Confirm Safe Shutdown" : "Confirm System Reboot"}
                      </h4>
                      <span className="text-xs text-secondary font-mono">Legion Sentry (192.168.1.183) · Pi-hole DNS</span>
                    </div>
                  </div>

                  <div className="p-4 bg-neutral/60 border border-border/60 rounded-md text-xs sm:text-sm font-mono text-secondary leading-relaxed space-y-2">
                    <p>
                      {confirmAction === "poweroff"
                        ? "Are you sure you want to safely shut down Legion Sentry (Raspberry Pi)?"
                        : "Are you sure you want to reboot Legion Sentry?"}
                    </p>
                    {confirmAction === "poweroff" ? (
                      <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-md text-red-500 text-xs font-sans font-medium leading-normal">
                        ⚠️ <strong>Physical Reconnect Required:</strong> Once shut down, the Pi will fully power off. You must physically reconnect or power cycle the USB power cable to turn it back on.
                      </div>
                    ) : (
                      <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-md text-amber-600 text-xs font-sans font-medium leading-normal">
                        ⚠️ <strong>Brief DNS Interruption:</strong> Network ad-blocking and recursive DNS lookups will pause for ~45 seconds while the node restarts.
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setConfirmAction(null)}
                      className="px-5 py-2.5 border border-border hover:border-foreground/40 text-xs font-mono font-semibold rounded-md transition-colors cursor-pointer text-secondary hover:text-primary"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => triggerSentryAction(confirmAction)}
                      className={`px-5 py-2.5 text-xs font-mono font-bold rounded-md transition-colors flex items-center gap-2 cursor-pointer shadow-md active:scale-95 ${
                        confirmAction === "poweroff"
                          ? "bg-red-500 hover:bg-red-600 text-white shadow-red-500/20"
                          : "bg-amber-500 hover:bg-amber-600 text-black shadow-amber-500/20"
                      }`}
                    >
                      {confirmAction === "poweroff" ? <Power className="w-4 h-4" /> : <RefreshCw className="w-4 h-4" />}
                      {confirmAction === "poweroff" ? "Power Off Sentry" : "Reboot Now"}
                    </button>
                  </div>
                </motion.div>
              </div>
            )}
          </AnimatePresence>
        </>,
        document.body
      )}
    </>
  );
}
