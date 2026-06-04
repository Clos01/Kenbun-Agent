"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import Sidebar from "@/components/Sidebar";
import { 
  Activity, 
  Terminal, 
  ShieldAlert, 
  Cpu, 
  BarChart3, 
  Database,
  Zap,
  Search,
  ShieldCheck,
  Clock,
  Gauge
} from "lucide-react";
import { 
  SharpAreaChart, 
  LinearTrend, 
  AccuracyGauge, 
  ToolMatrix 
} from "@/components/Visuals";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";
import { ToolStat } from "@/lib/tools";
import { useLogStream, LogRecord } from "./useLogStream";

interface TelemetryTrendPoint {
  accuracy: number;
  load: number;
}

interface TelemetryData {
  load: string;
  latency: string;
  memory: { capacity: number };
  lm_studio?: { status: string; model?: string; latency?: string };
  history_trend?: TelemetryTrendPoint[];
  [key: string]: unknown;
}

interface BudgetData {
  daily_limit: number;
  daily_usage: number;
  remaining: number;
  status: string;
  model_breakdown?: Record<string, number>;
  history?: number[];
  [key: string]: unknown;
}



interface ModelNode {
  name: string;
  version: string;
  role: string;
  endpoint: string;
  latency: string;
  cost: string;
  capabilities: string[];
  isOnline: boolean;
  isLocal: boolean;
}

const ModelCognitiveEnsemble = ({ lmStudioOnline }: { lmStudioOnline: boolean }) => {
  const models: ModelNode[] = [
    {
      name: "Gemini 3.5 Pro",
      version: "gemini-3.5-pro",
      role: "Swarm Orchestrator & Planner",
      endpoint: "https://api.google.com/gemini/v3.5",
      latency: "1.4s",
      cost: "$1.25 / $5.00 per 1M tkn",
      capabilities: ["Context Window (2M)", "Autonomous Agent Loops", "High-Level Planning"],
      isOnline: true,
      isLocal: false
    },
    {
      name: "Llama-3-8B-Instruct",
      version: "llama-3-8b-instruct",
      role: "Local Security Sentinel",
      endpoint: "http://localhost:1234/v1",
      latency: "45ms (TFT)",
      cost: "$0.000 (Sovereign)",
      capabilities: ["Privacy Scrubbing", "AST Audit Gating", "100% Physical Security"],
      isOnline: lmStudioOnline,
      isLocal: true
    },
    {
      name: "Claude 3.5 Sonnet",
      version: "claude-3.5-sonnet",
      role: "Precision Code Architect",
      endpoint: "https://api.anthropic.com/v1",
      latency: "2.1s",
      cost: "$3.00 / $15.00 per 1M tkn",
      capabilities: ["Strict AST Compliance", "Zero Regression Edits", "Type-Safe Components"],
      isOnline: true,
      isLocal: false
    }
  ];

  return (
    <div className="flex flex-col gap-4">
      {models.map((model, i) => (
        <motion.div 
          key={model.name}
          initial={{ opacity: 0, x: -15 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: i * 0.1 }}
          whileHover={{ x: 4, borderColor: "var(--gold)" }}
          className={`p-4 border-2 rounded-sm bg-background/30 flex flex-col justify-between transition-all duration-300 relative overflow-hidden ${
            model.isLocal 
              ? model.isOnline 
                ? "border-amber-600/30 shadow-[0_0_12px_rgba(212,163,89,0.04)]" 
                : "border-red-500/20"
              : "border-border hover:shadow-[0_0_12px_rgba(212,163,89,0.04)]"
          }`}
        >
          {/* Left accent bar for active node */}
          {model.isOnline && !model.isLocal && (
            <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-gold" />
          )}
          {model.isOnline && model.isLocal && (
            <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-amber-500 animate-pulse" />
          )}

          {/* Background grid matrix lines */}
          <div className="absolute inset-0 pointer-events-none select-none high-tech-grid bg-[size:10px_10px]" />

          <div className="flex justify-between items-start gap-2 relative z-10">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`w-1.5 h-1.5 rounded-full ${
                  model.isOnline 
                    ? model.isLocal 
                      ? 'bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.5)] animate-pulse' 
                      : 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)] animate-pulse'
                    : 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]'
                }`} />
                <span className="text-[8px] font-mono tracking-widest uppercase opacity-40">
                  {model.isLocal ? "LOCAL NODE" : "CLOUD API"}
                </span>
              </div>
              <h4 className="font-serif font-black text-sm tracking-tight text-foreground truncate">
                {model.name}
              </h4>
              <span className="text-[8px] font-mono text-gold/80 block -mt-1 truncate">
                {model.version}
              </span>
            </div>

            <div className="text-right shrink-0">
              <span className="text-[7px] font-mono text-foreground/40 block">LATENCY</span>
              <span className="text-[10px] font-mono font-bold text-foreground">
                {model.isOnline ? model.latency : "OFFLINE"}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-border/20 text-[9px] relative z-10">
            <div>
              <span className="opacity-30 font-mono block text-[7px] tracking-wider">ROLE</span>
              <span className="font-mono font-bold text-foreground/70 truncate block">{model.role}</span>
            </div>
            <div className="text-right">
              <span className="opacity-30 font-mono block text-[7px] tracking-wider">COMPUTE COST</span>
              <span className={`font-mono font-bold ${model.isLocal ? 'text-emerald-500' : 'text-foreground/70'}`}>
                {model.cost}
              </span>
            </div>
          </div>

          <div className="mt-3 relative z-10">
            <span className="text-[7px] font-mono tracking-widest opacity-25 block mb-1">COGNITIVE_VECTORS</span>
            <div className="flex flex-wrap gap-1">
              {model.capabilities.slice(0, 2).map((cap, i) => (
                <span key={i} className="text-[7px] font-mono uppercase bg-foreground/[0.02] border border-border/40 px-1 py-0.5 rounded text-foreground/50 truncate max-w-[120px]">
                  {cap}
                </span>
              ))}
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
};

interface NodeConfig {
  id: string;
  title: string;
  icon: React.ReactNode;
  color: string;
  desc: string;
  glowColor: string;
}

const FLOWCHART_NODES: NodeConfig[] = [
  {
    id: "orchestrator",
    title: "Swarm Orchestration",
    icon: <Cpu className="w-4 h-4" />,
    color: "border-tertiary/30 bg-tertiary/10 text-tertiary",
    desc: "Swarm Command Lead (Gemini)",
    glowColor: "rgba(184, 66, 46, 0.12)"
  },
  {
    id: "sentinel",
    title: "Security Sentinel",
    icon: <ShieldAlert className="w-4 h-4" />,
    color: "border-red-500/30 bg-red-500/10 text-red-500",
    desc: "AST Static Gating check",
    glowColor: "rgba(239, 68, 68, 0.08)"
  },
  {
    id: "vector",
    title: "Sovereign Vector Node",
    icon: <Database className="w-4 h-4" />,
    color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-500",
    desc: "ChromaDB memory sync",
    glowColor: "rgba(16, 185, 129, 0.08)"
  },
  {
    id: "local",
    title: "Local Llama Sentinel",
    icon: <ShieldCheck className="w-4 h-4" />,
    color: "border-amber-500/30 bg-amber-500/10 text-amber-500",
    desc: "Workstation GPU gate",
    glowColor: "rgba(245, 158, 11, 0.08)"
  },
  {
    id: "healer",
    title: "Autonomic Healer",
    icon: <Zap className="w-4 h-4" />,
    color: "border-blue-500/30 bg-blue-500/10 text-blue-500",
    desc: "Self-healing repairs",
    glowColor: "rgba(59, 130, 246, 0.08)"
  }
];

const getLogCategory = (message: string): string | null => {
  const msg = message.toLowerCase();
  if (msg.includes("security") || msg.includes("audit") || msg.includes("ast") || msg.includes("backtracing") || msg.includes("breaches") || msg.includes("sentinel")) {
    return "sentinel";
  }
  if (msg.includes("lm studio") || msg.includes("llama") || msg.includes("heartbeat") || msg.includes("port 1234") || msg.includes("local port")) {
    return "local";
  }
  if (msg.includes("chromadb") || msg.includes("vector") || msg.includes("segments") || msg.includes("dirichlet") || msg.includes("prior") || msg.includes("toolstat") || msg.includes("concepts")) {
    return "vector";
  }
  if (msg.includes("healing") || msg.includes("repair") || msg.includes("retry") || msg.includes("timeout") || msg.includes("failover") || msg.includes("stable") || msg.includes("stabilized") || msg.includes("garbage")) {
    return "healer";
  }
  if (msg.includes("orchestrator") || msg.includes("budget") || msg.includes("tokens") || msg.includes("limit")) {
    return "orchestrator";
  }
  return null;
};

const CognitiveFlowchart = ({ logs, activeCategory }: { logs: LogRecord[], activeCategory: string | null }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const nodeRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [coords, setCoords] = useState<Record<string, { x: number; y: number }>>({});

  const updateCoords = useCallback(() => {
    if (!containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const newCoords: Record<string, { x: number; y: number }> = {};

    Object.entries(nodeRefs.current).forEach(([id, el]) => {
      if (el) {
        const rect = el.getBoundingClientRect();
        newCoords[id] = {
          x: rect.left - containerRect.left + rect.width / 2,
          y: rect.top - containerRect.top + rect.height / 2
        };
      }
    });

    setCoords(newCoords);
  }, []);

  useEffect(() => {
    updateCoords();

    // Additional timeout schedules to account for DOM settlement and layout recalculations
    const timer = setTimeout(updateCoords, 100);
    const backupTimer = setTimeout(updateCoords, 500);

    let resizeObserver: ResizeObserver | null = null;
    if (typeof window !== "undefined" && window.ResizeObserver && containerRef.current) {
      resizeObserver = new window.ResizeObserver(() => {
        updateCoords();
      });
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      clearTimeout(timer);
      clearTimeout(backupTimer);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
    };
  }, [updateCoords, activeCategory, logs.length]);

  // Single-pass O(N) grouping computed via React.useMemo to eliminate O(N*M) scanning bottleneck
  const latestLogs = React.useMemo(() => {
    const map: Record<string, LogRecord> = {};
    logs.forEach(log => {
      const category = getLogCategory(log.message);
      if (category) {
        map[category] = log;
      }
    });
    return map;
  }, [logs]);

  const renderCard = (id: string) => {
    const node = FLOWCHART_NODES.find(n => n.id === id);
    if (!node) return null; // Safe guard, no non-null assertions (!)
    
    const latestLog = latestLogs[node.id];
    const isActive = activeCategory === node.id;

    return (
      <motion.div
        key={node.id}
        ref={(el) => {
          if (el) {
            nodeRefs.current[node.id] = el;
          } else {
            delete nodeRefs.current[node.id];
          }
        }}
        animate={{ 
          borderColor: isActive ? "var(--tertiary)" : "var(--border)",
          boxShadow: isActive 
            ? "0 4px 20px -5px rgba(0, 136, 95, 0.15)" 
            : "0 4px 12px rgba(15, 37, 55, 0.02)",
          scale: isActive ? 1.03 : 1
        }}
        transition={{ type: "spring", stiffness: 350, damping: 22 }}
        className="w-full max-w-[250px] p-4 border border-[var(--border)] rounded-sm transition-all duration-300 bg-white/95 backdrop-blur-xl flex flex-col gap-2.5 artisan-shadow z-10 relative"
      >
        {/* Node Header */}
        <div className="flex justify-between items-center border-b border-border/40 pb-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className={`p-1.5 rounded-sm border shrink-0 bg-background/55 ${node.color}`}>
              {node.icon}
            </div>
            <div className="min-w-0">
              <h5 className="font-mono font-black text-[9.5px] uppercase tracking-wider text-foreground">
                {node.title}
              </h5>
              <span className="text-[6.5px] font-mono text-foreground/45 block uppercase truncate -mt-0.5 font-bold">
                {node.desc}
              </span>
            </div>
          </div>
          <span className={`w-2 h-2 rounded-full border-2 border-background shrink-0 shadow-md ${
            isActive ? "bg-tertiary motion-safe:animate-ping" : "bg-border/30"
          }`} />
        </div>

        {/* Node Log Content (Highly legible high-contrast text!) */}
        <div className="flex-1 min-h-[52px] flex flex-col justify-between pt-1">
          {latestLog ? (
            <>
              <p className="text-[10px] font-bold text-[var(--foreground)] font-mono leading-relaxed line-clamp-2 select-text shadow-sm bg-[var(--background)]/25 p-1.5 border border-[var(--border)] rounded-sm">
                {latestLog.message}
              </p>
              <div className="flex justify-between items-center text-[7px] font-mono opacity-50 border-t border-border/20 pt-1.5 mt-1.5">
                <span>{latestLog.timestamp}</span>
                <span className={`px-2 py-0.5 rounded font-black uppercase text-[5.5px] border tracking-wider shadow-sm ${
                  latestLog.type === "step" ? "border-amber-500/30 text-amber-500 bg-amber-500/10" :
                  latestLog.type === "success" ? "border-emerald-500/30 text-emerald-500 bg-emerald-500/10" :
                  latestLog.type === "error" ? "border-red-500/30 text-red-500 bg-red-500/10 motion-safe:animate-pulse" :
                  "border-border text-foreground/50"
                }`}>
                  {latestLog.type}
                </span>
              </div>
            </>
          ) : (
            <p className="text-[8px] font-mono opacity-20 italic uppercase pt-3 text-center">
              Awaiting neural sync...
            </p>
          )}
        </div>
      </motion.div>
    );
  };

  return (
    <div 
      ref={containerRef}
      className="relative w-full min-h-[480px] md:h-[500px] border border-[var(--border)] bg-white/60 rounded-sm overflow-hidden select-none flex-1 flex flex-col"
    >
      {/* 2026 HUD Canvas elements: Corner Blueprint Crosshairs */}
      <div className="absolute top-3 left-3 text-[8px] font-mono text-border/30 pointer-events-none select-none">+ HUD_SYS_2026</div>
      <div className="absolute top-3 right-3 text-[8px] font-mono text-border/30 pointer-events-none select-none">NODE_MATRIX_SYS_3 +</div>
      <div className="absolute bottom-3 left-3 text-[8px] font-mono text-border/30 pointer-events-none select-none">+ [ALIGN: TRUE]</div>
      <div className="absolute bottom-3 right-3 text-[8px] font-mono text-border/30 pointer-events-none select-none">[GRID: 25px_SCALE] +</div>

      {/* Blueprint Grid Lines */}
      <div className="absolute inset-0 pointer-events-none high-tech-grid bg-[size:25px_25px]" />

      {/* Dynamic Background Glowing Orbs (blur-3xl) based on active node state */}
      {FLOWCHART_NODES.map((node) => {
        const isActive = activeCategory === node.id;
        const coord = coords[node.id];
        if (!coord) return null;
        return (
          <motion.div
            key={`glow-${node.id}`}
            initial={{ opacity: 0 }}
            animate={{ 
              opacity: isActive ? 1 : 0,
              scale: isActive ? 1.3 : 0.8
            }}
            transition={{ duration: 0.8 }}
            style={{ 
              left: coord.x - 72,
              top: coord.y - 72,
              backgroundColor: node.glowColor
            }}
            className="absolute w-36 h-36 rounded-full blur-3xl pointer-events-none z-0"
          />
        );
      })}

      {/* SVG Connecting Wires */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-0 hidden md:block">
        {/* Curving Bezier curves connecting Swarm Orchestrator to flanking nodes */}
        {FLOWCHART_NODES.filter(n => n.id !== "orchestrator").map((node) => {
          const start = coords["orchestrator"];
          const end = coords[node.id];
          if (!start || !end) return null;
          
          const path = `M ${start.x} ${start.y} Q ${(start.x + end.x)/2} ${(start.y + end.y)/2 - 30} ${end.x} ${end.y}`;
          const isActive = activeCategory === node.id;
          
          // Determine premium connection colors based on systems
          const glowColor = node.id === "sentinel" ? "rgba(239, 68, 68, 0.45)" : 
                            node.id === "vector" ? "rgba(16, 185, 129, 0.45)" :
                            node.id === "local" ? "rgba(245, 158, 11, 0.45)" : 
                            "rgba(59, 130, 246, 0.45)";
                            
          const activeStroke = node.id === "sentinel" ? "#EF4444" : 
                               node.id === "vector" ? "#10B981" :
                               node.id === "local" ? "#F59E0B" : 
                               "#3B82F6";

          return (
            <g key={node.id}>
              {/* Glowing SVG Wire backing shadow */}
              {isActive && (
                <path 
                  d={path} 
                  fill="none" 
                  stroke={glowColor} 
                  strokeWidth="5" 
                  className="blur-md"
                />
              )}
              {/* Premium light backing line that works on clean backgrounds */}
              <path 
                d={path} 
                fill="none" 
                stroke="rgba(15, 37, 55, 0.1)" 
                strokeWidth="1.5" 
                className="opacity-45" 
              />
              {/* Animated active pulse traveling vector */}
              <motion.path 
                d={path} 
                fill="none" 
                stroke={isActive ? activeStroke : "rgba(15, 37, 55, 0.05)"} 
                strokeWidth="2.5" 
                strokeDasharray="6 6"
                animate={{ strokeDashoffset: isActive ? [-100, 0] : [0, 0] }}
                transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
                className={isActive ? "opacity-100" : "opacity-0"}
              />
            </g>
          );
        })}
      </svg>

      {/* Grid columns */}
      <div className="flex-grow grid grid-cols-1 md:grid-cols-3 gap-6 p-8 relative z-10 w-full h-full">
        {/* Column 1: Gateways (Sentinel & Local Llama) */}
        <div className="flex flex-col justify-between items-center md:items-start h-full gap-6">
          <div className="w-full flex justify-center md:justify-start">
            {renderCard("sentinel")}
          </div>
          <div className="w-full flex justify-center md:justify-start">
            {renderCard("local")}
          </div>
        </div>

        {/* Column 2: Command Lead (Orchestration) */}
        <div className="flex flex-col justify-center items-center h-full">
          {renderCard("orchestrator")}
        </div>

        {/* Column 3: Memory and Healer */}
        <div className="flex flex-col justify-between items-center md:items-end h-full gap-6">
          <div className="w-full flex justify-center md:justify-end">
            {renderCard("vector")}
          </div>
          <div className="w-full flex justify-center md:justify-end">
            {renderCard("healer")}
          </div>
        </div>
      </div>
    </div>
  );
};

export default function IntelStream() {
  const API_BASE = CONFIG.API_BASE; 
  const logs = useLogStream(API_BASE);
  const [viewMode, setViewMode] = useState<'flowchart' | 'ledger'>('flowchart');
  const [budget, setBudget] = useState<BudgetData | null>(null);
  const [intelligence, setIntelligence] = useState<ToolStat[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [error, setError] = useState<boolean>(false);
  const [isLogsExpanded, setIsLogsExpanded] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [logFilter, setLogFilter] = useState("");
  const [selectedTool, setSelectedTool] = useState<ToolStat | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // Keep standard refs to hold current abort controller and loading states
  const abortControllerRef = useRef<AbortController | null>(null);

  const getActiveCategory = () => {
    if (logs.length === 0) return null;
    const latestLog = logs[logs.length - 1];
    const msg = latestLog.message.toLowerCase();
    if (msg.includes("security") || msg.includes("audit") || msg.includes("ast") || msg.includes("backtracing") || msg.includes("breaches") || msg.includes("sentinel")) {
      return "sentinel";
    }
    if (msg.includes("lm studio") || msg.includes("llama") || msg.includes("heartbeat") || msg.includes("port 1234") || msg.includes("local port")) {
      return "local";
    }
    if (msg.includes("chromadb") || msg.includes("vector") || msg.includes("segments") || msg.includes("dirichlet") || msg.includes("prior") || msg.includes("toolstat") || msg.includes("concepts")) {
      return "vector";
    }
    if (msg.includes("healing") || msg.includes("repair") || msg.includes("retry") || msg.includes("timeout") || msg.includes("failover") || msg.includes("stable") || msg.includes("stabilized") || msg.includes("garbage")) {
      return "healer";
    }
    if (msg.includes("orchestrator") || msg.includes("budget") || msg.includes("tokens") || msg.includes("limit")) {
      return "orchestrator";
    }
    return "orchestrator";
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      setMounted(true);
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  // Global Scroll Lock for Fullscreen Focus
  useEffect(() => {
    if (isLogsExpanded) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => { document.body.style.overflow = 'unset'; };
  }, [isLogsExpanded]);

  const fetchTelemetry = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    const controller = new AbortController();
    abortControllerRef.current = controller;

    let hasFetchError = false;

    // Fetch Stats & Telemetry (Logs are now streamed separately via EventSource)
    try {
      const statsRes = await fetch(`${API_BASE}/stats`, { 
        cache: 'no-store',
        signal: controller.signal
      });
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setBudget(statsData.budget);
        setIntelligence(statsData.intelligence || []);
        setTelemetry(statsData.telemetry);
        
        setSelectedTool((prev: ToolStat | null) => {
          if (!statsData.intelligence || statsData.intelligence.length === 0) {
            return null;
          }
          if (!prev) {
            return statsData.intelligence[0];
          }
          const freshTool = statsData.intelligence.find((t: ToolStat) => t.tool_id === prev.tool_id);
          return freshTool || statsData.intelligence[0];
        });
      } else {
        hasFetchError = true;
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        console.warn("Stats fetch failed:", err);
        hasFetchError = true;
      }
    }

    setError(hasFetchError);
  }, [API_BASE]);

  // Self-correcting loop using setTimeout to avoid overlapping network calls
  useEffect(() => {
    let active = true;
    let timerId: NodeJS.Timeout;

    const loop = async () => {
      if (!active) return;
      await fetchTelemetry();
      if (active) {
        timerId = setTimeout(loop, 3000);
      }
    };

    loop();

    return () => {
      active = false;
      clearTimeout(timerId);
    };
  }, [fetchTelemetry]); // Static dependency array prevents infinite synchronization loop

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth"
      });
    }
  }, [logs]);


  // Filtered Logs matching user input
  const filteredLogs = logs.filter(log => 
    log.message.toLowerCase().includes(logFilter.toLowerCase())
  );

  const formatLog = (log: LogRecord) => {
    return (
      <div className="flex gap-4 items-stretch py-2.5 hover:bg-foreground/[0.02] transition-all px-3 rounded-md relative group/row">
        {/* Glow accent under hover */}
        <div className="absolute inset-y-1 left-0 w-[2px] bg-gold opacity-0 group-hover/row:opacity-100 transition-opacity" />

        {/* Timeline connector thread & pulsing node bullet */}
        <div className="flex flex-col items-center shrink-0 w-8 relative">
          <div className="absolute top-0 bottom-0 w-[1px] bg-border/20" />
          <span className={`w-2.5 h-2.5 rounded-full mt-2.5 z-10 border-2 border-background transition-all duration-300 ${
            log.type === "step" ? "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)] animate-pulse" :
            log.type === "success" ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" :
            log.type === "error" ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)] animate-ping" :
            "bg-foreground/30"
          }`} />
        </div>

        {/* Timestamp */}
        <span className="opacity-40 text-[9px] font-mono tracking-wider w-20 shrink-0 self-center font-bold">
          {log.timestamp}
        </span>

        {/* Premium Severity pill with glassmorphic borders */}
        <span className="shrink-0 self-center w-24">
          {log.type === "step" && (
            <span className="text-[7px] tracking-widest uppercase font-mono font-bold px-2 py-0.5 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.1)]">
              ENGINE_PULSE
            </span>
          )}
          {log.type === "error" && (
            <span className="text-[7px] tracking-widest uppercase font-mono font-bold px-2 py-0.5 rounded-full border border-red-500/30 bg-red-500/10 text-red-500 shadow-[0_0_6px_rgba(239,68,68,0.1)]">
              ERROR_ALERT
            </span>
          )}
          {log.type === "success" && (
            <span className="text-[7px] tracking-widest uppercase font-mono font-bold px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.1)]">
              VERIFIED
            </span>
          )}
          {log.type === "info" && (
            <span className="text-[7px] tracking-widest uppercase font-mono font-bold px-2 py-0.5 rounded-full border border-border bg-foreground/5 text-foreground/50">
              SYS_TRACE
            </span>
          )}
        </span>

        {/* Message block */}
        <span className="flex-1 font-mono text-[10px] text-foreground/80 leading-relaxed break-all select-all self-center pl-2">
          {log.message}
        </span>
      </div>
    );
  };

  const LogContent = (
    <div className={`transition-all duration-500 border border-[var(--border)] bg-white/60 backdrop-blur-md p-6 overflow-hidden artisan-shadow relative group rounded-md flex flex-col ${
      isLogsExpanded ? 'w-full h-full max-h-[90vh]' : 'h-[640px]'
    }`}>
      {/* Absolute high-tech grid background overlay */}
      <div className="absolute inset-0 pointer-events-none select-none high-tech-grid bg-[size:20px_20px]" />
      
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4 mb-6 border-b border-border/40 pb-4 relative z-10">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-gold animate-pulse shrink-0" />
          <Terminal className="w-4 h-4 text-gold shrink-0" />
          <span className="ind-header text-[10px] uppercase tracking-wider font-bold mr-2 shrink-0">Neural Signal Log Streamer</span>
          
          {/* Dual-View Mode Selector Button Group */}
          <div className="flex border border-border/60 rounded-sm overflow-hidden p-0.5 bg-background/55 shadow-[inset_0_1px_3px_rgba(0,0,0,0.2)]">
            <button 
              onClick={() => setViewMode('flowchart')}
              className={`px-3 py-1 text-[7px] font-mono font-bold uppercase transition-all rounded-sm ${
                viewMode === 'flowchart' 
                  ? 'bg-gold text-black shadow-[0_0_8px_rgba(212,163,89,0.2)] font-black' 
                  : 'text-foreground/45 hover:text-foreground/80'
              }`}
            >
              Cognitive Flow
            </button>
            <button 
              onClick={() => setViewMode('ledger')}
              className={`px-3 py-1 text-[7px] font-mono font-bold uppercase transition-all rounded-sm ${
                viewMode === 'ledger' 
                  ? 'bg-gold text-black shadow-[0_0_8px_rgba(212,163,89,0.2)] font-black' 
                  : 'text-foreground/45 hover:text-foreground/80'
              }`}
            >
              Signal Ledger
            </button>
          </div>
        </div>
        
        <div className="flex flex-1 sm:max-w-xs items-center gap-2 border border-border/60 px-3 py-1.5 bg-background/55 rounded-sm">
          <Search className="w-3.5 h-3.5 opacity-30 shrink-0" />
          <input 
            type="text"
            placeholder="FILTER TELEMETRY SIGNALS..."
            value={logFilter}
            onChange={(e) => setLogFilter(e.target.value)}
            className="w-full bg-transparent border-0 text-[9px] font-mono focus:outline-none placeholder-foreground/30 text-foreground"
          />
          {logFilter && (
            <button onClick={() => setLogFilter("")} className="text-[8px] hover:text-gold opacity-50 font-bold font-mono">CLEAR</button>
          )}
        </div>

        <button 
          onClick={() => setIsLogsExpanded(!isLogsExpanded)}
          className="p-1.5 text-gold hover:bg-gold hover:text-black transition-all border border-border/60 rounded self-end sm:self-auto pointer-events-auto shadow-[0_0_8px_rgba(212,163,89,0.05)]"
          title={isLogsExpanded ? "Collapse ledger" : "Fullscreen ledger"}
        >
          {isLogsExpanded ? (
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          ) : (
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
          )}
        </button>
      </div>

      {/* Holographic HUD Split Grid Layout */}
      <div className="flex-1 flex gap-6 overflow-hidden relative z-10">
        {viewMode === 'flowchart' ? (
          <CognitiveFlowchart logs={logs} activeCategory={getActiveCategory()} />
        ) : (
          /* Left Side: Animated Log ledger timeline stream */
          <div 
            ref={scrollRef} 
            onWheel={(e) => e.stopPropagation()}
            className="flex-1 overflow-y-auto space-y-0.5 custom-scrollbar pr-3 relative"
          >
            {filteredLogs.length > 0 ? (
              <AnimatePresence initial={false}>
                {filteredLogs.map((log) => (
                  <motion.div
                    key={log.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: "spring", stiffness: 350, damping: 25 }}
                  >
                    {formatLog(log)}
                  </motion.div>
                ))}
              </AnimatePresence>
            ) : (
              <div className="opacity-20 uppercase tracking-[0.4em] text-center pt-36 font-bold font-mono text-[9px]">
                {logFilter ? "No matching signals located." : "Awaiting neural pulse..."}
              </div>
            )}
          </div>
        )}

        {/* Right Side: Tactical telemetry control status panel (HUD) */}
        <div className="hidden md:flex flex-col w-56 border-l border-border/40 pl-6 gap-6 self-stretch justify-between shrink-0 font-mono select-none">
          <div className="space-y-5">
            <div className="space-y-1">
              <span className="text-[7px] text-foreground/45 uppercase tracking-widest block font-bold">Telemetry Link</span>
              <div className="flex items-center gap-2 border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1.5 rounded">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping shrink-0" />
                <span className="text-[8px] font-bold text-emerald-500 tracking-wider">SSE_FLOW // LIVE</span>
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-[7px] text-foreground/45 uppercase tracking-widest block font-bold">Batch Throttle</span>
              <div className="border border-border/60 bg-foreground/[0.02] px-2.5 py-1.5 rounded text-[8px] font-bold text-foreground/80 tracking-wide">
                100ms BUFFER DELAY
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-[7px] uppercase font-bold tracking-widest text-foreground/45">
                <span>Buffer Depth</span>
                <span className="text-gold font-bold">{logs.length} / 150</span>
              </div>
              <div className="h-1.5 border border-border/60 bg-foreground/5 rounded-sm p-[1px] overflow-hidden">
                <div 
                  className="h-full bg-gold transition-all duration-300"
                  style={{ width: `${(logs.length / 150) * 100}%` }}
                />
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-[7px] text-foreground/45 uppercase tracking-widest block font-bold">Safety Seal</span>
              <div className="flex items-center gap-1.5 text-[8px] text-gold/80 font-bold border border-gold/20 bg-gold/5 px-2.5 py-1.5 rounded">
                <span className="text-[7px]">🔒</span>
                <span>XSS_SHIELD // SECURE</span>
              </div>
            </div>
          </div>

          <div className="space-y-2 border-t border-border/30 pt-4">
            <div className="text-[7px] opacity-45 uppercase font-bold tracking-widest">Cognitive Matrix</div>
            <div className="text-[9px] font-bold text-foreground/80 truncate">
              system3_memory // node
            </div>
            <div className="text-[7px] opacity-35 leading-normal">
              * SSE signals are dynamically scrubbed and verified offline via the static AST Backtracing Sentinel.
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background flex selection:bg-gold selection:text-white max-w-[100vw] overflow-x-hidden relative">
      {/* Dynamic Heritage Grid Grain */}
      <div className="grain-overlay" />

      <Sidebar />
      
      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 h-screen overflow-y-auto custom-scrollbar min-w-0 overflow-x-hidden z-10">
        
        {/* HEADER BAR */}
        <header className="h-20 lg:h-24 border-b-2 border-border flex items-center justify-between px-6 lg:px-10 bg-background/80 sticky top-0 backdrop-blur-xl z-30">
          <div className="flex items-center gap-4 lg:gap-8">
            <span className="ind-header text-[10px] opacity-100 font-black">Intel Unit</span>
            <div className="h-6 w-[2px] bg-border" />
            <span className="font-serif italic text-lg lg:text-xl text-primary">Dynamic System Telemetry</span>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-4 px-4 py-2 border border-border bg-background/40 artisan-shadow rounded-sm">
              <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest">Swarm Pulse</span>
              <span className={`text-xs font-mono font-bold flex items-center gap-2 ${error ? 'text-red-500' : 'text-gold'}`}>
                <span className="w-1.5 h-1.5 rounded-full bg-current animate-ping" />
                {error ? 'DISCONNECTED' : 'STABLE'}
              </span>
            </div>
            <Activity className={`w-4 h-4 ${error ? 'text-red-500' : 'text-gold'} animate-pulse`} />
          </div>
        </header>

        {/* INNER SCROLL CONTAINER */}
        <motion.div 
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex-1 p-6 lg:p-10 xl:p-12 space-y-10 lg:space-y-14 pb-48"
        >
          {error && (
            <div className="p-6 border border-red-500 bg-red-500/5 flex items-center gap-6 rounded-md">
              <ShieldAlert className="w-6 h-6 text-red-500" />
              <div className="space-y-0">
                <span className="ind-header text-red-500 opacity-100">Connection Interrupted</span>
                <p className="text-[9px] font-bold text-red-500/60 uppercase tracking-widest">
                  Could not interface with the local Mission Control API node. Ensure the python backend server is initialized.
                </p>
              </div>
            </div>
          )}
          
          {/* SYSTEM HARDWARE & DATABASE TELEMETRY GRID */}
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="p-6 border border-border bg-background/40 artisan-shadow space-y-4 hover:border-gold/30 transition-all rounded">
              <div className="flex justify-between items-center opacity-60">
                <Cpu className="w-4 h-4 text-gold" />
                <span className="text-[8px] font-mono tracking-wider">HOST_RESOURCE</span>
              </div>
              <div>
                <div className="text-3xl font-serif font-black tracking-tight">{telemetry?.load ? `${parseFloat(telemetry.load).toFixed(2)}` : "1.00"}</div>
                <div className="text-[9px] opacity-40 uppercase tracking-wider font-bold mt-1">Host CPU Load Index</div>
              </div>
              <div className="h-1 bg-border/20 overflow-hidden">
                <div 
                  className="h-full bg-gold transition-all duration-1000" 
                  style={{ width: `${Math.min((parseFloat(telemetry?.load || "1.0") / 8) * 100, 100)}%` }} 
                />
              </div>
            </div>

            <div className="p-6 border border-border bg-background/40 artisan-shadow space-y-4 hover:border-gold/30 transition-all rounded">
              <div className="flex justify-between items-center opacity-60">
                <Clock className="w-4 h-4 text-gold" />
                <span className="text-[8px] font-mono tracking-wider">PING_LATENCY</span>
              </div>
              <div>
                <div className="text-3xl font-serif font-black tracking-tight">{telemetry?.latency || "8.5ms"}</div>
                <div className="text-[9px] opacity-40 uppercase tracking-wider font-bold mt-1">Telemetry Roundtrip API</div>
              </div>
              <div className="h-1 bg-border/20 overflow-hidden">
                <div 
                  className="h-full bg-gold transition-all duration-1000" 
                  style={{ width: `${Math.min((parseFloat(telemetry?.latency || "10") / 200) * 100, 100)}%` }} 
                />
              </div>
            </div>

            <div className="p-6 border border-border bg-background/40 artisan-shadow space-y-4 hover:border-gold/30 transition-all rounded">
              <div className="flex justify-between items-center opacity-60">
                <Database className="w-4 h-4 text-gold" />
                <span className="text-[8px] font-mono tracking-wider">VECTOR_NODE</span>
              </div>
              <div>
                <div className="text-3xl font-serif font-black tracking-tight">
                  {telemetry?.memory?.capacity ? telemetry.memory.capacity.toLocaleString() : "0"}
                </div>
                <div className="text-[9px] opacity-40 uppercase tracking-wider font-bold mt-1">Signals Indexed (ChromaDB)</div>
              </div>
              <div className="h-1 bg-border/20 overflow-hidden">
                <div 
                  className="h-full bg-gold transition-all duration-1000" 
                  style={{ width: `${Math.min((telemetry?.memory?.capacity || 0) / 5000 * 100, 100)}%` }} 
                />
              </div>
            </div>

            <div className={`p-6 border bg-background/40 artisan-shadow space-y-4 hover:border-gold/30 transition-all rounded ${telemetry?.lm_studio?.status === "Online" ? "border-border" : "border-red-500/10 hover:border-red-500/30"}`}>
              <div className="flex justify-between items-center opacity-60">
                <ShieldCheck className={`w-4 h-4 ${telemetry?.lm_studio?.status === "Online" ? "text-gold" : "text-red-500/60 animate-pulse"}`} />
                <span className="text-[8px] font-mono tracking-wider">LOCAL_COGNITION</span>
              </div>
              <div>
                <div className={`text-base font-bold font-mono tracking-tighter truncate ${telemetry?.lm_studio?.status === "Online" ? "text-primary" : "text-red-500/90"}`}>
                  {telemetry?.lm_studio?.status === "Online" ? (telemetry?.lm_studio?.model || "Llama-3-8B-Instruct") : "LM Studio Offline"}
                </div>
                <div className="text-[9px] opacity-40 uppercase tracking-wider font-bold mt-2">
                  Local Supervisor Status: <span className={`font-bold ${telemetry?.lm_studio?.status === "Online" ? 'text-gold' : 'text-red-500/80'}`}>{telemetry?.lm_studio?.status || "Offline"}</span>
                </div>
              </div>
              <div className="h-1 bg-border/20 overflow-hidden">
                <div 
                  className={`h-full transition-all duration-1000 ${telemetry?.lm_studio?.status === "Online" ? 'bg-gold' : 'bg-red-500/50'}`} 
                  style={{ width: telemetry?.lm_studio?.status === "Online" ? '100%' : '10%' }} 
                />
              </div>
            </div>
          </section>

          {/* MAIN GRAPHICS GRID (Financial, Allocation Breakdown, Temporal Entropy) */}
          <section className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Financial Ledger (Available Capital + Model Allocation) */}
            <div className="lg:col-span-5 flex flex-col gap-6">
              
              <div className="p-6 border-2 border-border bg-background/40 artisan-shadow space-y-6 flex-1 rounded-sm">
                <div className="flex items-center gap-3 border-b border-border pb-3">
                  <Gauge className="w-4 h-4 text-gold" />
                  <span className="ind-header text-[10px]">Financial Intelligence</span>
                </div>

                <div className="space-y-1">
                  <span className="text-[8px] opacity-40 uppercase font-bold tracking-widest">Available Reserve Capital</span>
                  <div className="text-5xl font-serif font-black tracking-tighter text-foreground leading-none">
                    ${budget?.remaining ? budget.remaining.toFixed(4) : "0.0000"}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
                  <div className="space-y-1">
                    <span className="text-[8px] opacity-40 uppercase font-bold tracking-wider">Daily Usage</span>
                    <div className="text-base font-bold text-gold">${budget?.daily_usage?.toFixed(4) || "0.0000"}</div>
                  </div>
                  <div className="space-y-1 text-right">
                    <span className="text-[8px] opacity-40 uppercase font-bold tracking-wider">Allocated Limit</span>
                    <div className="text-base font-bold text-foreground/80">${budget?.daily_limit?.toFixed(2) || "0.00"}</div>
                  </div>
                </div>

                {budget && (
                  <div className="space-y-2 pt-2">
                    <div className="flex justify-between text-[8px] uppercase tracking-wider font-bold opacity-40">
                      <span>Daily Burn Envelope</span>
                      <span>{((budget.daily_usage / budget.daily_limit) * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-2 border border-border bg-background/60 p-[2px] rounded-sm overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-1000 ${
                          budget.status === "Green" ? 'bg-gold' : 'bg-gold/80'
                        }`} 
                        style={{ width: `${Math.min((budget.daily_usage / budget.daily_limit) * 100, 100)}%` }} 
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Model Cognitive Ensemble Grid */}
              <div className="p-6 border-2 border-border bg-background/40 artisan-shadow space-y-4 rounded-sm flex flex-col justify-between">
                <ModelCognitiveEnsemble lmStudioOnline={telemetry?.lm_studio?.status === "Online"} />
              </div>
            </div>

            {/* Cost Progression Curve */}
            <div className="lg:col-span-7">
              <div className="p-6 border-2 border-border bg-background/40 artisan-shadow h-full flex flex-col justify-between rounded-sm">
                <div className="flex justify-between items-center mb-6">
                  <div className="flex items-center gap-3">
                    <BarChart3 className="w-4 h-4 text-gold" />
                    <span className="ind-header text-[10px]">Temporal Entropy Index</span>
                  </div>
                  <span className="text-[7px] font-mono tracking-widest opacity-30">LAST_24_CYCLES</span>
                </div>
                <div className="flex-1 min-h-[220px] flex items-center justify-center">
                  <SharpAreaChart data={budget?.history || Array(24).fill(0.0001)} />
                </div>
                <div className="flex justify-between text-[7px] font-mono opacity-30 mt-4 border-t border-border pt-4">
                  <span>T-24 Hours</span>
                  <span>T-12 Hours</span>
                  <span>Real Time (Present)</span>
                </div>
              </div>
            </div>
          </section>

          {/* DUAL LAYER: BAYESIAN PROBABILITY MATRIX & DIAGNOSTIC DRAWER */}
          <section className="space-y-6">
            <div className="flex items-center gap-3 border-b-2 border-border pb-3">
              <Zap className="w-4 h-4 text-gold" />
              <span className="ind-header opacity-100">Bayesian Tool Convergence Matrix</span>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
              {/* Tool Matrix Grid */}
              <div className="xl:col-span-8 space-y-4">
                <p className="text-[9px] opacity-40 uppercase tracking-widest font-black">
                  Select a tool node to synchronize diagnostic sensors and extract real learning curves
                </p>
                {intelligence.length > 0 ? (
                  <ToolMatrix 
                    tools={intelligence as unknown as { tool_id: string; success_rate: number; [key: string]: unknown }[]} 
                    selectedId={selectedTool?.tool_id} 
                    onSelect={(t) => setSelectedTool(t as unknown as ToolStat)} 
                  />
                ) : (
                  <div className="py-20 text-center border-2 border-dashed border-border rounded text-xs opacity-30 uppercase font-mono">
                    Compiling cognitive statistics...
                  </div>
                )}
              </div>

              {/* Selected Tool Diagnostics Drawer */}
              <div className="xl:col-span-4">
                <AnimatePresence mode="wait">
                  {selectedTool ? (
                    <motion.div 
                      key={selectedTool.tool_id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 20 }}
                      transition={{ duration: 0.3 }}
                      className="p-6 border-2 border-gold/40 bg-background/60 artisan-shadow space-y-6 h-full flex flex-col justify-between rounded"
                    >
                      <div className="space-y-4">
                        <div className="flex justify-between items-start border-b border-border pb-4">
                          <div>
                            <span className="text-[8px] font-mono text-gold border border-gold/30 px-1 py-0.5 font-bold uppercase rounded bg-gold/10">
                              Active Bayesian Node
                            </span>
                            <h3 className="text-sm font-black font-mono tracking-tight mt-2 text-foreground truncate max-w-[200px]">
                              {selectedTool.tool_id}
                            </h3>
                          </div>
                          <div className={`px-2 py-0.5 text-[8px] font-mono font-black uppercase rounded ${
                            selectedTool.confidence === "HIGH" 
                              ? "bg-green-500/10 text-green-500 border border-green-500/20" 
                              : "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                          }`}>
                            {selectedTool.confidence} CONF
                          </div>
                        </div>

                        {/* Success vs Failure Accuracy Bar */}
                        <div className="pt-2">
                          <AccuracyGauge 
                            success={selectedTool.success_count ?? 0} 
                            total={(selectedTool.success_count ?? 0) + (selectedTool.failure_count ?? 0)}
                            label="Success Distribution"
                          />
                        </div>

                        {/* Statistics Grid */}
                        <div className="grid grid-cols-2 gap-4 bg-foreground/[0.02] p-4 border border-border rounded">
                          <div>
                            <div className="text-[8px] opacity-40 uppercase font-bold tracking-widest">Bayesian Prior Alpha</div>
                            <div className="text-lg font-serif font-black text-foreground">{selectedTool.alpha.toFixed(2)}</div>
                          </div>
                          <div>
                            <div className="text-[8px] opacity-40 uppercase font-bold tracking-widest">Bayesian Prior Beta</div>
                            <div className="text-lg font-serif font-black text-foreground">{selectedTool.beta.toFixed(2)}</div>
                          </div>
                          <div className="pt-2 border-t border-border/40">
                            <div className="text-[8px] opacity-40 uppercase font-bold tracking-widest">Success Trails</div>
                            <div className="text-lg font-serif font-black text-gold">{selectedTool.success_count}</div>
                          </div>
                          <div className="pt-2 border-t border-border/40">
                            <div className="text-[8px] opacity-40 uppercase font-bold tracking-widest">Failure Trails</div>
                            <div className="text-lg font-serif font-black text-foreground/50">{selectedTool.failure_count}</div>
                          </div>
                        </div>

                        {/* Trend Chart Title */}
                        <div className="space-y-2">
                          <div className="flex justify-between items-center text-[8px] font-bold uppercase tracking-widest opacity-60">
                            <span>Historic Convergence Graph</span>
                            <span className="text-gold font-mono">{selectedTool.delta > 0 ? `+${selectedTool.delta}%` : `${selectedTool.delta}%`} DoD</span>
                          </div>
                          {selectedTool.history_trend && selectedTool.history_trend.length > 0 ? (
                            <div className="p-2 border border-border bg-background rounded-sm">
                              <LinearTrend data={selectedTool.history_trend.map((h: TelemetryTrendPoint) => h.accuracy)} />
                            </div>
                          ) : (
                            <div className="h-32 flex items-center justify-center border border-dashed border-border opacity-20 text-[9px] font-mono uppercase">
                              Graph timeline seeding...
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="text-[8px] font-mono text-foreground/40 leading-relaxed border-t border-border pt-4">
                        * Entropy deviation score of <span className="text-gold">{selectedTool.entropy?.toFixed(4) || "0.000"}</span> was modeled dynamically using the agent&apos;s Dirichlet convergence probability engine.
                      </div>
                    </motion.div>
                  ) : (
                    <div className="h-full flex items-center justify-center p-8 border-2 border-dashed border-border rounded text-center opacity-30 text-xs uppercase font-mono">
                      No tool selected.
                    </div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </section>

          {/* DYNAMIC LOG LEDGER */}
          <section className="space-y-6">
            <div className="flex items-center justify-between border-b-2 border-border pb-3">
              <span className="ind-header opacity-100 flex items-center gap-3">
                <Terminal className="w-4 h-4 text-gold" /> Swarm Logic Ledger Stream
              </span>
            </div>
            
            {mounted && isLogsExpanded ? createPortal(
              <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-sm flex items-center justify-center p-6 sm:p-10">
                <div className="w-full max-w-6xl h-full flex flex-col justify-center">
                  {LogContent}
                </div>
              </div>,
              document.body
            ) : LogContent}
          </section>

        </motion.div>

        {/* FOOTER STATS PANEL */}
        <footer className="h-16 border-t-2 border-border flex items-center justify-between px-10 bg-background/80 text-[8px] font-black uppercase tracking-[0.8em] opacity-40 sticky bottom-0 backdrop-blur-xl z-20">
          <span>SECURE_DATA_NODE // 17774</span>
          <span className="hidden sm:inline">STABLE_FLOW_OK // SYSTEM_3</span>
        </footer>

      </main>
    </div>
  );
}
