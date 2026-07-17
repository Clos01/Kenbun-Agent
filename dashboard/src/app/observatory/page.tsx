"use client";

import React, { useEffect, useState, useMemo, useCallback, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import { 
  ShieldCheck,
  Activity,
  BrainCircuit,
  ShieldAlert,
  Database,
  TrendingUp,
  Target,
  ArrowUpRight,
  ArrowDownRight
} from "lucide-react";
import { SharpAreaChart, SquareDonut, AccuracyGauge, ContextWindowBar } from "@/components/Visuals";
import GalaxyMap from "@/components/GalaxyMap";
// import RoamingMascot from "@/components/RoamingMascot";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";
import { TOOL_EQUATIONS } from "@/lib/equations";
import { useTenant } from "@/context/TenantContext";

const getToolDescription = (toolId: string): string => {
  const dict: Record<string, string> = {
    consult_supervisor: "Verifies code patches against security constraints and architectural guidelines using multi-model voting.",
    audit_guardrail: "Evaluates inputs and outputs in real-time to block unauthorized commands or API payloads.",
    autofix_linter: "Autonomously detects and repairs structural code patterns and lint violations.",
    research_official_docs: "Retrieves verified framework specifications and API references from official documentation repositories.",
    ask_architect: "Queries the team's historical system blueprint and design documents to resolve structural patterns.",
    ask_ui_expert: "Applies high-fidelity visual guidelines to correct alignment, colors, and layout aesthetics.",
    get_design_tokens: "Provides pre-defined color constants, border radii, and font sizes to maintain unified layouts.",
    review_code_with_gemini: "Runs a 4-stage pipeline (AI Review → Docs → Supervisor → Consensus) for code verification.",
    research_with_gemini: "Performs deep web research and official docs grounding for new technology stacks.",
    write_website_content: "Generates premium website text and marketing content optimized for user engagement.",
    run_code_safely: "Executes untrusted scripts and test suites inside an isolated sandboxed sandbox.",
    scan_repo: "Analyzes codebase structure, dependencies, and configuration directories for active tech stacks.",
    remember_fix: "Saves a verified bug fix to the global Knowledge Hive so it can be automatically applied to future bugs.",
    recall_fix: "Searches the Knowledge Hive for previously approved solutions to speed up autonomic repairs.",
    save_checkpoint: "Takes a snapshot of the current state of files before making major edits.",
    restore_checkpoint: "Rolls back files to a previous verified state to recover from logical regressions.",
    list_checkpoints: "Retrieves all saved repository state snapshots.",
    orchestrate: "Manages multi-agent background tasks and handles automatic retries and progress tracking.",
    orchestrate_status: "Polls the status of active background workflows and processes.",
    save_to_hivemind: "Injects semantic data patterns and concepts into the local System 3 memory store.",
    search_hivemind_concepts: "Queries System 3 vector embeddings to locate matching logical guidelines.",
    delete_from_hivemind: "Prunes outdated data patterns or guidelines from the System 3 memory store.",
    workspace_post: "Writes workspace notifications or alerts to the developer dashboard.",
    workspace_read: "Reads active workspace alerts and workspace messages.",
    workspace_inject: "Injects customized files or templates into the active workspace directory.",
    workspace_resolve_alert: "Flags active workspace warnings or alerts as resolved.",
    index_codebase: "Scans and indexes workspace code symbols for semantic codebase searching.",
    search_codebase: "Runs vector search queries across the indexed code repository.",
    think_about_tools: "Outputs step-by-step implementation blueprints using FastMCP tools.",
    patch_hivemind_concept: "Edits specific data fields within a saved System 3 memory concept.",
    ingest_knowledge_from_pdf: "Parses and vectorizes PDF manuals into the global Knowledge Hive.",
    ingest_url_to_hivemind: "Scrapes and indexes a documentation webpage into the System 3 store.",
    ingest_file_to_hivemind: "Vectorizes a text or codebase file directly into local memory.",
    prune_hivemind: "Prunes unused vector embeddings to optimize System 3 query latency.",
    get_intelligence_stats: "Displays metrics on indexing volume, brain health, and memory health.",
    reflect_on_task: "Runs an agent review on a completed task to evaluate scalability and security.",
    get_brain_health: "Evaluates memory density and supervisor alignment status.",
    audit_package_safety: "Runs dependency scans to detect outdated or vulnerable packages.",
    sync_jira_issue: "Synchronizes planka cards with external issue trackers.",
    create_bitbucket_pr: "Autonomously drafts and opens pull requests with supervisor consensus.",
    session_search: "Searches through session logs."
  };
  return dict[toolId] || "Performs autonomous back-office pipelines and agentic actions.";
};

type TabId = "overview" | "intelligence" | "memory" | "feed";

interface TelemetryTrendPoint {
  accuracy: number;
  load: number;
}

interface IntelligenceTool {
  tool_id: string;
  success_rate: number;
  success_count?: number;
  failure_count?: number;
  alpha?: number;
  beta?: number;
  confidence?: string;
  delta?: string;
  mom_delta?: string;
  category?: string;
  history_trend?: TelemetryTrendPoint[];
}

interface TaskItem {
  id: string;
  objective: string;
  project: string;
  status: "todo" | "doing" | "done";
  est_cost?: number;
}

interface BudgetInfo {
  remaining: number;
  daily_usage: number;
}

interface BuildInfo {
  status: string;
}

interface MemorySignal {
  file: string;
  line: number;
  content: string;
}

interface IntelligencePulse {
  id: string;
  tool: string;
  timestamp: string;
  confidence: number;
  logic: string;
  result: "success" | "failure";
  output?: string;
}

interface PulseInfo {
  active_system: string;
  supervisor: string;
  status: string;
}

interface TelemetryInfo {
  latency: string;
  uptime: string;
  load: string;
  memory?: { capacity: number };
  performance?: { context_tokens: number };
  history_trend?: TelemetryTrendPoint[];
}

interface SystemLog {
  content?: string;
  message?: string;
  [key: string]: unknown;
}

const CHART_SVG_HEIGHT = 240;
const CHART_SVG_WIDTH = 1000;

const ACCURACY_PADDING_TOP = 20;
const LOAD_PADDING_TOP = 40;

const ACCURACY_SCALE_FACTOR = (CHART_SVG_HEIGHT - ACCURACY_PADDING_TOP) / 100;
const LOAD_SCALE_FACTOR = (CHART_SVG_HEIGHT - LOAD_PADDING_TOP) / 100;

interface Point2D {
  x: number;
  y: number;
}

function safeNumber(val: unknown, fallback: number = 0): number {
  if (typeof val !== "number" || Number.isNaN(val) || !Number.isFinite(val)) {
    return fallback;
  }
  return val;
}

export function decimateTelemetry<T>(
  trend: T[] | null | undefined,
  maxPoints: number = 100,
  extractors: Array<(item: T) => number | undefined> = []
): T[] {
  if (!trend || trend.length === 0) return [];
  const len = trend.length;
  if (len <= maxPoints) return trend;
  
  if (extractors.length === 0) {
    const step = Math.ceil(len / maxPoints);
    const sampled: T[] = [];
    for (let i = 0; i < len; i += step) {
      sampled.push(trend[i]);
    }
    return sampled;
  }

  // We divide the array into targetBuckets. Each bucket contributes outlier points.
  // We subtract 2 to reserve space for absolute start and end boundary anchors.
  const targetBuckets = Math.max(2, Math.floor((maxPoints - 2) / (extractors.length * 2)));
  const bucketSize = (len - 2) / targetBuckets;
  
  const sampled: T[] = [];
  sampled.push(trend[0]); // Always anchor start boundary
  
  let lastAddedIdx = 0;
  
  // Allocate static index array once outside of the loop to achieve a highly-efficient, reduced-allocation design
  const indices: number[] = new Array(extractors.length * 2);

  for (let i = 0; i < targetBuckets; i++) {
    const start = Math.floor(1 + i * bucketSize);
    const end = Math.min(Math.floor(1 + (i + 1) * bucketSize), len - 1);
    if (start >= end) continue;
    
    let indicesCount = 0;
    
    // Evaluate all selectors for this bucket independently
    for (let e = 0; e < extractors.length; e++) {
      const getVal = extractors[e];
      const firstItem = trend[start];
      if (!firstItem) continue;
      
      let minVal = safeNumber(getVal(firstItem), 100);
      let maxVal = safeNumber(getVal(firstItem), 0);
      
      let minIdx = start;
      let maxIdx = start;
      
      for (let j = start + 1; j < end; j++) {
        const item = trend[j];
        if (!item) continue;
        const val = safeNumber(getVal(item), 0);
        if (val < minVal) {
          minVal = val;
          minIdx = j;
        }
        if (val > maxVal) {
          maxVal = val;
          maxIdx = j;
        }
      }
      
      indices[indicesCount++] = minIdx;
      indices[indicesCount++] = maxIdx;
    }
    
    // Sort unique indices chronologically to preserve visual shape
    // Since indicesCount is very small (usually 2-4 items), a fast insertion sort is highly optimal in V8
    for (let k = 1; k < indicesCount; k++) {
      const key = indices[k];
      let l = k - 1;
      while (l >= 0 && indices[l] > key) {
        indices[l + 1] = indices[l];
        l--;
      }
      indices[l + 1] = key;
    }
    
    // Deduplicate and push chronologically
    for (let k = 0; k < indicesCount; k++) {
      const idx = indices[k];
      if (k > 0 && idx === indices[k - 1]) continue;
      
      const item = trend[idx];
      if (item && idx > lastAddedIdx && idx < len - 1) {
        sampled.push(item);
        lastAddedIdx = idx;
      }
    }
  }
  
  // Anchor final end boundary point
  const lastItem = trend[len - 1];
  if (lastItem && len - 1 > lastAddedIdx) {
    sampled.push(lastItem);
  }
  
  return sampled;
}

export function mapTrendToCoordinates(
  trend: TelemetryTrendPoint[],
  width: number,
  height: number,
  paddingTop: number,
  extractor: (pt: TelemetryTrendPoint) => number | undefined
): Point2D[] {
  const len = trend.length;
  if (len === 0) return [];

  const safeWidth = Math.max(1, safeNumber(width, 1000));
  const safeHeight = Math.max(1, safeNumber(height, 240));
  const safePaddingTop = Math.max(0, safeNumber(paddingTop, 20));

  const count = len > 1 ? len - 1 : 1;
  const step = safeWidth / count;
  const scaleFactor = Math.max(0, (safeHeight - safePaddingTop) / 100);

  const points: Point2D[] = [];
  for (let i = 0; i < len; i++) {
    const d = trend[i];
    const x = len === 1 ? safeWidth / 2 : i * step;
    
    let rawVal = 0;
    try {
      rawVal = safeNumber(d ? extractor(d) : undefined, 0);
    } catch (err) {
      console.warn("Coordinate extraction error at index", i, err);
    }

    const clampedVal = Math.max(0, Math.min(100, rawVal));
    const y = safeHeight - clampedVal * scaleFactor;

    // Apply strict coordinate checks to block NaN or Infinity values from rendering
    const safeX = Number.isFinite(x) ? Math.round(x) : 0;
    const safeY = Number.isFinite(y) ? Math.round(y) : safeHeight;

    points.push({
      x: safeX,
      y: safeY
    });
  }
  return points;
}

export function serializeSvgPaths(
  points: Point2D[],
  width: number,
  height: number
): { lineD: string; areaD: string } {
  const len = points.length;
  if (len === 0) return { lineD: "", areaD: "" };

  const safeWidth = Math.max(1, safeNumber(width, 1000));
  const safeHeight = Math.max(1, safeNumber(height, 240));

  const pathParts: string[] = [];
  for (let i = 0; i < len; i++) {
    const pt = points[i];
    if (Number.isFinite(pt.x) && Number.isFinite(pt.y)) {
      pathParts.push(`${pt.x},${pt.y}`);
    }
  }

  if (pathParts.length === 0) {
    return { lineD: "", areaD: "" };
  }

  if (pathParts.length === 1) {
    const y = points[0].y;
    const lineD = `M 0,${y} L ${safeWidth},${y}`;
    const areaD = `${lineD} L ${safeWidth},${safeHeight} L 0,${safeHeight} Z`;
    return { lineD, areaD };
  }

  const lineD = `M ${pathParts.join(' L ')}`;
  const firstX = points[0].x;
  const lastX = points[len - 1].x;
  const areaD = `${lineD} L ${lastX},${safeHeight} L ${firstX},${safeHeight} Z`;

  return { lineD, areaD };
}

export default function HeritageObservatory() {
  const { tenantId } = useTenant();
  const API_BASE = CONFIG.API_BASE;
  const [stats, setStats] = useState<IntelligenceTool[]>([]);
  const [logs, setLogs] = useState<(string | SystemLog)[]>([]);
  const [kanban, setKanban] = useState<TaskItem[]>([]);
  const [budget, setBudget] = useState<BudgetInfo | null>(null);
  const [buildStatus, setBuildStatus] = useState<BuildInfo>({ status: "Healthy" });
  const [selectedTool, setSelectedTool] = useState<IntelligenceTool | null>(null);
  const [activeToolModal, setActiveToolModal] = useState<IntelligenceTool | null>(null);
  const [error, setError] = useState(false);
  const [telemetry, setTelemetry] = useState<TelemetryInfo>({ latency: "0ms", uptime: "0h", load: "0.0", memory: { capacity: 0 } });
  const [pulse, setPulse] = useState<PulseInfo>({ active_system: "GEMINI-3-FLASH", supervisor: "LM Studio", status: "idle" });
  const [memorySignals, setMemorySignals] = useState<MemorySignal[]>([]);
  const [intelligenceHistory, setIntelligenceHistory] = useState<IntelligencePulse[]>([]);
  const [selectedDecision, setSelectedDecision] = useState<IntelligencePulse | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showFidelity, setShowFidelity] = useState(true);
  const [showLoad, setShowLoad] = useState(true);

  // VPN Reachability and Offline Gate states
  const [consecutiveFailures, setConsecutiveFailures] = useState<number>(0);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [isIntentionalOffline, setIsIntentionalOffline] = useState<boolean>(false);

  // Use refs to stabilize the callback function reference and prevent interval thrashing
  const selectedToolRef = useRef<IntelligenceTool | null>(null);
  const isPausedRef = useRef<boolean>(false);

  useEffect(() => {
    selectedToolRef.current = selectedTool;
  }, [selectedTool]);

  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);

  const activeTrend = useMemo<TelemetryTrendPoint[]>(() => {
    const rawHistory = (selectedTool?.history_trend || telemetry.history_trend || []) as TelemetryTrendPoint[];
    return decimateTelemetry(
      rawHistory, 
      100, 
      [(pt) => pt?.accuracy, (pt) => pt?.load]
    );
  }, [selectedTool, telemetry.history_trend]);

  const trendStats = useMemo(() => {
    const hasTrend = activeTrend && activeTrend.length > 0;
    
    let avgFidelity = 0;
    let peakLoad = 0;
    let minFidelity = 100;
    let stabilityRating = "NOMINAL";
    
    if (hasTrend) {
      let sumFidelity = 0;
      let maxLoad = 0;
      let minFidelityVal = 100;
      const len = activeTrend.length;
      
      for (let i = 0; i < len; i++) {
        const pt = activeTrend[i];
        const fidelity = pt.accuracy ?? 0;
        const load = pt.load ?? 0;
        
        sumFidelity += fidelity;
        if (load > maxLoad) maxLoad = load;
        if (fidelity < minFidelityVal) minFidelityVal = fidelity;
      }
      
      avgFidelity = sumFidelity / len;
      peakLoad = maxLoad;
      minFidelity = minFidelityVal;
      
      let sumSqDiff = 0;
      for (let i = 0; i < len; i++) {
        const fidelity = activeTrend[i].accuracy ?? 0;
        sumSqDiff += Math.pow(fidelity - avgFidelity, 2);
      }
      const variance = sumSqDiff / len;
      const stdDev = Math.sqrt(variance);
      stabilityRating = stdDev < 1.5 ? "OPTIMIZED" : stdDev < 4 ? "STABLE" : "STRESSED";
    }
    
    return {
      avgFidelity,
      peakLoad,
      minFidelity,
      stabilityRating
    };
  }, [activeTrend]);

  const pathStrings = useMemo(() => {
    if (!activeTrend || activeTrend.length === 0) {
      return { loadD: "", accuracyD: "", loadAreaD: "", accuracyAreaD: "" };
    }
    
    const loadPoints = mapTrendToCoordinates(activeTrend, CHART_SVG_WIDTH, CHART_SVG_HEIGHT, LOAD_PADDING_TOP, (pt) => pt.load);
    const accuracyPoints = mapTrendToCoordinates(activeTrend, CHART_SVG_WIDTH, CHART_SVG_HEIGHT, ACCURACY_PADDING_TOP, (pt) => pt.accuracy);
    
    const loadPaths = serializeSvgPaths(loadPoints, CHART_SVG_WIDTH, CHART_SVG_HEIGHT);
    const accuracyPaths = serializeSvgPaths(accuracyPoints, CHART_SVG_WIDTH, CHART_SVG_HEIGHT);

    return { 
      loadD: loadPaths.lineD, 
      accuracyD: accuracyPaths.lineD, 
      loadAreaD: loadPaths.areaD, 
      accuracyAreaD: accuracyPaths.areaD 
    };
  }, [activeTrend]);

  const horizontalGridlines = useMemo(() => {
    return [0.166, 0.375, 0.583, 0.792].map(p => p * CHART_SVG_HEIGHT);
  }, []);

  const fetchData = useCallback(async () => {
    if (isPausedRef.current) return;

    const requestOptions = {
      cache: 'no-store' as const,
      headers: {
        'x-tenant-id': tenantId
      }
    };

    // 1. Fetch Stats (Telemetry, Tools, Budget, Pulse)
    fetch(`${API_BASE}/stats`, requestOptions)
      .then(res => {
        if (!res.ok) throw new Error("Stats fetch failed");
        return res.json();
      })
      .then(statsData => {
        const tools = statsData.intelligence || [];
        setStats(tools);
        setPulse(statsData.pulse || { active_system: "GEMINI-3-FLASH", supervisor: "LM Studio", status: "idle" });
        setBudget(statsData.budget || { remaining: 0.00, daily_usage: 0.0 });
        setTelemetry({
          ...(statsData.telemetry || {}),
          history_trend: statsData.history_trend || []
        });
        
        const currentSelected = selectedToolRef.current;
        if (!currentSelected && tools.length > 0) {
          setSelectedTool(tools[0]);
        } else if (currentSelected) {
          const updated = tools.find((t: IntelligenceTool) => t.tool_id === currentSelected.tool_id);
          if (updated) setSelectedTool(updated);
        }
        setError(false);
        setConsecutiveFailures(0);
      })
      .catch(err => {
        console.warn("BRIDGE_STATS_FETCH_ERROR:", err);
        setError(true);
        setConsecutiveFailures((prev) => {
          const next = prev + 1;
          if (next >= 5) setIsPaused(true);
          return next;
        });
      });

    // 2. Fetch Logs
    fetch(`${API_BASE}/logs`, requestOptions)
      .then(res => {
        if (!res.ok) throw new Error("Logs fetch failed");
        return res.json();
      })
      .then(logsData => setLogs(logsData.logs || []))
      .catch(err => console.warn("BRIDGE_LOGS_FETCH_ERROR:", err));

    // 3. Fetch Kanban
    fetch(`${API_BASE}/kanban`, requestOptions)
      .then(res => {
        if (!res.ok) throw new Error("Kanban fetch failed");
        return res.json();
      })
      .then(kanbanData => setKanban(kanbanData.tasks || []))
      .catch(err => console.warn("BRIDGE_KANBAN_FETCH_ERROR:", err));

    // 4. Fetch Build Status
    fetch(`${API_BASE}/api/v1/build/status`, requestOptions)
      .then(res => {
        if (!res.ok) throw new Error("Build status fetch failed");
        return res.json();
      })
      .then(buildData => setBuildStatus(buildData))
      .catch(err => console.warn("BRIDGE_BUILD_FETCH_ERROR:", err));

    // 5. Fetch Memory Signals
    fetch(`${API_BASE}/api/v1/memory/signals`, requestOptions)
      .then(res => {
        if (!res.ok) throw new Error("Memory signals fetch failed");
        return res.json();
      })
      .then(memoryData => setMemorySignals(memoryData.signals || []))
      .catch(err => console.warn("BRIDGE_MEMORY_FETCH_ERROR:", err));

    // 6. Fetch Intelligence History
    fetch(`${API_BASE}/api/v1/intelligence/history`, requestOptions)
      .then(res => {
        if (!res.ok) throw new Error("History fetch failed");
        return res.json();
      })
      .then(historyData => setIntelligenceHistory(historyData.history || []))
      .catch(err => console.warn("BRIDGE_HISTORY_FETCH_ERROR:", err));

  }, [API_BASE, tenantId]);

  const handleReconnect = useCallback(() => {
    setError(false);
    setConsecutiveFailures(0);
    setIsPaused(false);
    setIsIntentionalOffline(false);
    setTimeout(() => {
      fetchData();
    }, 0);
  }, [fetchData]);

  const handleDeclareIntentionalOffline = useCallback(() => {
    setIsIntentionalOffline(true);
  }, []);

  useEffect(() => {
    if (isPaused) return;

    const timer = setTimeout(() => {
      fetchData();
    }, 0);
    const interval = setInterval(fetchData, 3000);
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [fetchData, isPaused]);

  const rawSuccess = stats.reduce((acc, s) => acc + (s.success_count || 0), 0);
  const rawFailure = stats.reduce((acc, s) => acc + (s.failure_count || 0), 0);
  const totalSuccess = rawSuccess > 0 || rawFailure > 0 ? rawSuccess : stats.reduce((acc, s) => acc + Math.round((s.alpha || 0) * 10), 0);
  const totalSignals = rawSuccess > 0 || rawFailure > 0 ? (rawSuccess + rawFailure) : stats.reduce((acc, s) => acc + Math.round(((s.alpha || 0) + (s.beta || 0)) * 10), 0);
  
  const activeTask = kanban.find(t => t.status === "doing") || kanban[0];
  const usageHistory = [2, 5, 8, 4, 12, 7, 15, 10, 20, 14, 25, 18, 30, 22, 10, 5, 12, 18, 22, 15, 20];

  const handleInteraction = (clientX: number, currentTarget: HTMLDivElement) => {
    if (activeTrend.length === 0) return;
    const rect = currentTarget.getBoundingClientRect();
    const x = clientX - rect.left;
    const percentX = x / rect.width;
    const index = Math.min(
      Math.max(Math.round(percentX * (activeTrend.length - 1)), 0),
      activeTrend.length - 1
    );
    if (index !== hoverIndex) {
      setHoverIndex(index);
    }
  };

  const handleTouch = (e: React.TouchEvent<HTMLDivElement>) => {
    if (e.touches && e.touches[0]) {
      handleInteraction(e.touches[0].clientX, e.currentTarget);
    }
  };

  const handleMouse = (e: React.MouseEvent<HTMLDivElement>) => {
    handleInteraction(e.clientX, e.currentTarget);
  };


  const TABS = [
    { id: "overview", label: "Overview", icon: ShieldCheck },
    { id: "intelligence", label: "Intelligence", icon: BrainCircuit },
    { id: "memory", label: "Memory", icon: Database },
    { id: "feed", label: "Deep Feed", icon: Activity },
  ] as const;

  const handleTabKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const nextIndex = e.key === "ArrowRight" 
        ? (index + 1) % TABS.length 
        : (index - 1 + TABS.length) % TABS.length;
      
      const nextTabId = TABS[nextIndex].id;
      setActiveTab(nextTabId);
      
      // Shift focus to the new tab button
      const nextButton = document.getElementById(`tab-${nextTabId}`);
      if (nextButton) {
        nextButton.focus();
      }
    }
  };

  return (
    <div className="min-h-screen bg-neutral flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden font-sans">
      <Sidebar />
      
      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 pb-20 lg:pb-0 min-w-0 overflow-x-hidden">
        <div className="grain-overlay opacity-20" />
        
        {/* Heritage Command Header */}
        <header className="h-20 lg:h-24 border-b border-primary/5 flex items-center justify-between px-6 lg:px-10 bg-card/40 z-20 sticky top-0 backdrop-blur-xl shrink-0">
          <div className="flex items-center gap-2 sm:gap-4 lg:gap-8">
            <span className="text-[10px] font-black uppercase tracking-widest opacity-30 hidden sm:inline-block">Node.251649</span>
            <div className="h-6 w-[1px] bg-primary/10 hidden sm:block" />
            <span className="font-bold text-base sm:text-lg lg:text-xl uppercase tracking-tighter italic">Heritage <span className="text-tertiary">Observatory</span></span>
          </div>
          
          <div className="flex items-center gap-4 lg:gap-10">
            <div className="flex items-center gap-4 sm:gap-8">
              <div className="flex flex-col items-end hidden sm:flex">
                <span className="text-[8px] uppercase tracking-widest opacity-40 font-bold">Latency</span>
                <span className="text-xs font-bold text-primary">{telemetry.latency}</span>
              </div>
              <div className="flex flex-col items-end sm:border-l sm:border-primary/5 sm:pl-8">
                <span className="text-[8px] uppercase tracking-widest opacity-40 font-bold">Reserve</span>
                <span className="text-base sm:text-xl lg:text-2xl font-black text-tertiary italic tracking-tighter">${budget?.remaining?.toFixed(2) || "0.00"}</span>
              </div>
            </div>
          </div>
        </header>
          
        {/* Sub-Navigation Nodes */}
        <nav 
          role="tablist"
          aria-label="Observatory Subsystems"
          className="flex flex-wrap items-center gap-2 md:gap-4 px-4 md:px-10 py-4 md:py-6 border-b border-primary/5 bg-card/20 backdrop-blur-sm z-20 shrink-0"
        >
          <span className="text-[10px] font-black uppercase tracking-[0.3em] opacity-30 mr-2 sm:mr-4 shrink-0 hidden sm:inline-block">Subsystem</span>
          {TABS.map((tab, index) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`panel-${tab.id}`}
              id={`tab-${tab.id}`}
              tabIndex={activeTab === tab.id ? 0 : -1}
              onKeyDown={(e) => handleTabKeyDown(e, index)}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 sm:gap-3 px-3 sm:px-md py-2 sm:py-sm rounded-lg transition-all duration-500 border group shrink-0 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-tertiary motion-reduce:transition-none ${
                activeTab === tab.id 
                  ? "bg-primary text-neutral border-primary shadow-lg shadow-primary/10" 
                  : "bg-card/40 border-primary/5 text-secondary hover:text-primary hover:bg-card/80"
              }`}
            >
              <tab.icon className={`w-3.5 h-3.5 ${activeTab === tab.id ? "text-tertiary" : "text-secondary group-hover:text-primary transition-colors"}`} />
              <span className="text-[10px] font-black uppercase tracking-widest">{tab.label}</span>
              {activeTab === tab.id && (
                <motion.div 
                  layoutId="activeGlow"
                  className="w-1 h-1 rounded-full bg-tertiary animate-pulse motion-reduce:animate-none" 
                />
              )}
            </button>
          ))}
        </nav>

        <motion.div 
          key={activeTab}
          role="tabpanel"
          id={`panel-${activeTab}`}
          aria-labelledby={`tab-${activeTab}`}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex-1 overflow-y-auto p-6 lg:p-10 xl:p-12 space-y-12 relative z-10 custom-scrollbar pb-32"
        >
          {/* Active Error State Banner */}
          {error && !isIntentionalOffline && (
            <div className="p-6 border border-tertiary/20 bg-tertiary/5 flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8 rounded-none transition-all duration-300">
              <div className="flex items-center gap-6">
                <ShieldAlert className="w-6 h-6 text-tertiary animate-pulse" />
                <div className="space-y-1">
                  <span className="text-[10px] font-black uppercase tracking-widest text-tertiary">
                    {isPaused ? "Connection Lost / VPN Required" : "Sync Error"}
                  </span>
                  <p className="text-[9px] font-bold text-tertiary/60 uppercase tracking-widest leading-relaxed">
                    {isPaused 
                      ? `Heritage Control at ${API_BASE} is unreachable. Is this intentional?` 
                      : `Connection lost with Heritage Control (Reconnecting attempt ${consecutiveFailures} of 5)`}

                  </p>
                </div>
              </div>
              
              {isPaused && (
                <div className="flex items-center gap-4 shrink-0">
                  <button 
                    onClick={handleDeclareIntentionalOffline}
                    className="px-6 py-2.5 bg-tertiary hover:bg-tertiary/80 text-[#FAF9F6] border border-tertiary rounded-none uppercase font-black tracking-widest text-[9px] transition-all focus:outline-none focus:ring-1 focus:ring-[#FAF9F6]"
                  >
                    Yes, Work Offline
                  </button>
                  <button 
                    onClick={handleReconnect}
                    className="px-6 py-2.5 bg-transparent hover:bg-primary hover:text-neutral text-primary border border-primary/20 rounded-none uppercase font-black tracking-widest text-[9px] transition-all focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    No, Reconnect
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Elegant Bone/Gold Offline Mode Bar */}
          {isIntentionalOffline && (
            <div className="p-4 border border-[#AF966F]/20 bg-[#FAF9F6] flex items-center justify-between gap-6 mb-8 rounded-none transition-all duration-300">
              <div className="flex items-center gap-4">
                <div className="w-2 h-2 rounded-none bg-[#AF966F] animate-pulse" />
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-black uppercase tracking-widest text-[#1A1C1E]">
                    [OFFLINE MODE] Running on Cached Snapshot
                  </span>
                  <span className="text-[8px] font-bold text-secondary uppercase tracking-widest">
                    (Background polling suspended)
                  </span>
                </div>
              </div>
              
              <button 
                onClick={handleReconnect}
                className="px-6 py-2 bg-[#AF966F] hover:bg-[#AF966F]/80 text-[#FAF9F6] border border-[#AF966F] rounded-none uppercase font-black tracking-widest text-[9px] transition-all focus:outline-none focus:ring-1 focus:ring-[#AF966F]"
              >
                Go Online
              </button>
            </div>
          )}
          
          {activeTab === "overview" && (
            <div className="space-y-16">
              <section className="space-y-10">
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <motion.span className="text-[10px] font-black uppercase tracking-[0.4em] text-tertiary">Active Mission</motion.span>
                    <div className="flex-1 h-[1px] bg-tertiary/20" />
                  </div>
                  <h1 className="text-[clamp(2rem,4vw,5rem)] font-black text-primary leading-[0.9] break-words italic tracking-tighter uppercase">
                    {activeTask?.objective || "AWAITING_COMMAND"}
                  </h1>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 border border-primary/5 bg-card/60 backdrop-blur-xl artisan-shadow divide-x divide-primary/5 rounded-xl">
                  {[
                    { label: "Domain", value: activeTask?.project || "Heritage" },
                    { label: "Betterment", value: totalSignals > 0 ? `+${((totalSuccess / totalSignals) * 100).toFixed(1)}%` : "+0.0%" },
                    { label: "Neural Capacity", value: telemetry.memory?.capacity ? `${telemetry.memory.capacity.toLocaleString()} Signals` : "0 Signals", color: "text-tertiary" },
                    { label: "Value", value: activeTask?.est_cost ? `$${(activeTask.est_cost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "$0.00" }
                  ].map((stat, i) => (
                    <div key={i} className="p-8 space-y-2">
                      <span className="text-[10px] uppercase tracking-[0.2em] opacity-30 font-black">{stat.label}</span>
                      <div className={`text-xl lg:text-3xl font-black tracking-tighter italic ${stat.color || "text-primary"}`}>{stat.value}</div>
                    </div>
                  ))}
                </div>

                <div className="w-full min-h-[400px] p-10 border border-primary/5 bg-card/60 backdrop-blur-xl shadow-xl shadow-primary/5 flex flex-col space-y-8 rounded-2xl">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">Neural Topology</span>
                      <p className="text-[11px] font-bold opacity-30 uppercase tracking-widest italic">Vector Visualization // Node.251649</p>
                    </div>
                    <div className="flex items-center gap-3 bg-primary/5 px-4 py-2 border border-primary/5 rounded-full">
                      <div className="w-2 h-2 rounded-full bg-tertiary animate-pulse" />
                      <span className="text-[10px] font-black text-tertiary uppercase tracking-widest">{telemetry.memory?.capacity || 0} Registered Signals</span>
                    </div>
                  </div>
                  <div className="flex-1 relative min-h-[600px] border border-primary/5 bg-card/40 rounded-xl overflow-hidden">
                    <GalaxyMap />
                  </div>
                </div>
              </section>

              <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12">
                <div className="lg:col-span-8 space-y-6">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40">Temporal Load Index</span>
                    <TrendingUp className="w-4 h-4 text-tertiary" />
                  </div>
                  <div className="p-8 border border-primary/5 bg-card/60 backdrop-blur-md shadow-sm rounded-xl">
                    <SharpAreaChart data={usageHistory} />
                  </div>
                </div>
                <div className="lg:col-span-4 space-y-6">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40">Signal Entropy</span>
                    <Database className="w-4 h-4 opacity-20" />
                  </div>
                  <div className="p-8 border border-primary/5 bg-card/60 backdrop-blur-md shadow-sm rounded-xl">
                    <SquareDonut data={[
                      { label: "Neural", value: 45, color: "#1A1C1E" },
                      { label: "Exec", value: 30, color: "#6C7278" },
                      { label: "Rec", value: 25, color: "#B8422E" },
                    ]} />
                  </div>
                </div>
              </section>
            </div>
          )}

          {activeTab === "intelligence" && (
            <div className="space-y-12 pb-20">
              <section className="grid grid-cols-1 xl:grid-cols-12 gap-8 lg:gap-12">
                <div className="xl:col-span-4">
                  <motion.div layout className="p-10 border border-primary/5 bg-card/60 backdrop-blur-xl shadow-sm space-y-10 h-full rounded-2xl">
                    <div className="flex items-center justify-between">
                      <div className="flex flex-col">
                        <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">Neural Fidelity</span>
                        <span className="text-[10px] font-bold opacity-30 uppercase tracking-widest">{selectedTool?.tool_id || "Global_State"}</span>
                      </div>
                      <Target className="w-5 h-5 text-tertiary" />
                    </div>
                    <AccuracyGauge 
                      success={selectedTool ? (selectedTool.success_count || selectedTool.failure_count ? (selectedTool.success_count || 0) : Math.round((selectedTool.alpha || 0) * 10)) : totalSuccess} 
                      total={selectedTool ? (selectedTool.success_count || selectedTool.failure_count ? ((selectedTool.success_count || 0) + (selectedTool.failure_count || 0)) : Math.round(((selectedTool.alpha || 0) + (selectedTool.beta || 0)) * 10)) : totalSignals} 
                      label={selectedTool ? `Bayesian Posterior (Trials: ${selectedTool.success_count || 0} S / ${selectedTool.failure_count || 0} F)` : `Global System Fidelity (Trials: ${rawSuccess} S / ${rawFailure} F)`}
                    />
                    <div className="space-y-6 pt-6 border-t border-primary/5">
                       <div className="flex items-center justify-between">
                        <span className="text-[10px] font-black uppercase tracking-widest opacity-40">Confidence</span>
                        <span className="text-[10px] font-bold text-tertiary">{selectedTool?.confidence || "OPTIMIZED"}</span>
                      </div>
                      <div className="h-1 bg-primary/5 w-full relative overflow-hidden rounded-full">
                        <motion.div 
                          initial={{ width: 0 }}
                          animate={{ width: "88%" }}
                          className="absolute inset-y-0 left-0 bg-tertiary"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-6 pt-6 border-t border-primary/5">
                      <ContextWindowBar usedTokens={telemetry.performance?.context_tokens || 6144} maxTokens={8192} label="Gemma 4 Context Window" />
                    </div>

                    <div className="grid grid-cols-2 gap-8 pt-8 border-t border-primary/5">
                      <div className="space-y-2">
                        <span className="text-[8px] font-black uppercase tracking-widest opacity-30">Day Δ</span>
                        <div className={`text-xl font-black italic ${parseFloat(selectedTool?.delta || "0") >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {parseFloat(selectedTool?.delta || "0") >= 0 ? '+' : ''}{selectedTool?.delta || "0.0"}%
                        </div>
                      </div>
                      <div className="space-y-2 text-right">
                        <span className="text-[8px] font-black uppercase tracking-widest opacity-30">Mo Δ</span>
                        <div className={`text-xl font-black italic ${parseFloat(selectedTool?.mom_delta || "0") >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {parseFloat(selectedTool?.mom_delta || "0") >= 0 ? '+' : ''}{selectedTool?.mom_delta || "0.0"}%
                        </div>
                      </div>
                    </div>
                  </motion.div>
                </div>
                <div className="xl:col-span-8">
                  <div className="p-10 border border-primary/5 bg-card/60 backdrop-blur-xl shadow-sm space-y-8 h-full rounded-2xl flex flex-col justify-between">
                    <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-primary/5 pb-6 gap-4">
                      <div className="flex flex-col">
                        <div className="flex items-center gap-2.5">
                          <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">
                            {selectedTool ? `${selectedTool.tool_id.toUpperCase()} Performance` : 'Global Performance'}
                          </span>
                          <details className="group relative">
                            <summary className="cursor-pointer list-none text-[8.5px] font-black text-tertiary hover:opacity-100 opacity-60 transition-opacity flex items-center justify-center border border-tertiary/20 rounded-full w-4 h-4 select-none">
                              i
                            </summary>
                            <div className="absolute left-0 mt-2 z-[250] w-72 bg-neutral/95 backdrop-blur-md border border-primary/10 p-4 rounded-xl shadow-2xl space-y-2 pointer-events-auto text-[9.5px] font-mono leading-relaxed normal-case tracking-normal text-secondary text-left">
                              <p className="font-bold text-primary uppercase text-[10px] tracking-wider">Performance Analytics Guide</p>
                              <p className="opacity-90">This chart plots tool performance metrics over the last 30 epochs (execution cycles):</p>
                              <div className="space-y-1.5 pt-1.5 border-t border-primary/5">
                                <p><strong className="text-tertiary">Fidelity (Orange Line):</strong> The accuracy, security, and logical correctness score of tool outputs (0-100%).</p>
                                <p><strong className="text-primary">Load Index (Grey Line):</strong> The computational work, token utilization, and memory consumption (0-100).</p>
                                <p><strong className="text-stone-300">F/L Ratio:</strong> Efficiency rating. High fidelity and low load yield the highest efficiency.</p>
                              </div>
                            </div>
                          </details>
                        </div>
                        <p className="text-[10px] font-bold opacity-30 uppercase tracking-widest italic">Accuracy vs Load Topology</p>
                      </div>
                      
                      {/* Interactive Legend with Toggles */}
                      <div className="flex items-center gap-6">
                        <button 
                          onClick={() => setShowFidelity(!showFidelity)}
                          className={`flex items-center gap-2 px-3 py-1 rounded-full border transition-all ${
                            showFidelity 
                              ? 'bg-tertiary/10 border-tertiary/30 text-tertiary' 
                              : 'bg-primary/5 border-transparent text-primary/30 hover:text-primary/50'
                          }`}
                        >
                          <div className={`w-2 h-2 rounded-full ${showFidelity ? 'bg-tertiary animate-pulse' : 'bg-primary/30'}`} />
                          <span className="text-[9px] font-black uppercase tracking-widest">Fidelity</span>
                        </button>
                        <button 
                          onClick={() => setShowLoad(!showLoad)}
                          className={`flex items-center gap-2 px-3 py-1 rounded-full border transition-all ${
                            showLoad 
                              ? 'bg-primary/10 border-primary/20 text-primary' 
                              : 'bg-primary/5 border-transparent text-primary/30 hover:text-primary/50'
                          }`}
                        >
                          <div className={`w-2 h-2 rounded-full ${showLoad ? 'bg-primary' : 'bg-primary/30'}`} />
                          <span className="text-[9px] font-black uppercase tracking-widest">Load</span>
                        </button>
                      </div>
                    </div>

                    {/* Live Metrics Sub-Bar */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-primary/[0.02] border border-primary/5 rounded-xl text-[10px] uppercase font-bold tracking-widest divide-y md:divide-y-0 md:divide-x divide-primary/5">
                      <div className="space-y-1">
                        <span className="opacity-30 text-[8px]">Avg Fidelity</span>
                        <div className="text-sm font-black text-tertiary italic">{trendStats.avgFidelity.toFixed(1)}%</div>
                        <p className="text-[7.5px] opacity-40 font-mono normal-case tracking-normal leading-normal mt-1">Average correctness score across recent task executions.</p>
                      </div>
                      <div className="space-y-1 pt-2 md:pt-0 md:pl-4">
                        <span className="opacity-30 text-[8px]">Peak Load</span>
                        <div className="text-sm font-black text-primary italic">{trendStats.peakLoad.toFixed(1)}%</div>
                        <p className="text-[7.5px] opacity-40 font-mono normal-case tracking-normal leading-normal mt-1">Highest recorded context or compute usage overhead.</p>
                      </div>
                      <div className="space-y-1 pt-2 md:pt-0 md:pl-4">
                        <span className="opacity-30 text-[8px]">Fidelity Floor</span>
                        <div className="text-sm font-black text-secondary/70 italic">{trendStats.minFidelity.toFixed(1)}%</div>
                        <p className="text-[7.5px] opacity-40 font-mono normal-case tracking-normal leading-normal mt-1">Lowest recorded correctness score (worst-case output).</p>
                      </div>
                      <div className="space-y-1 pt-2 md:pt-0 md:pl-4">
                        <span className="opacity-30 text-[8px]">Stability Rating</span>
                        <div className={`text-sm font-black italic ${
                          trendStats.stabilityRating === "OPTIMIZED" ? "text-green-600 animate-pulse" : 
                          trendStats.stabilityRating === "STABLE" ? "text-primary" : "text-tertiary"
                        }`}>
                          {trendStats.stabilityRating}
                        </div>
                        <p className="text-[7.5px] opacity-40 font-mono normal-case tracking-normal leading-normal mt-1">Consistency classification based on performance variance.</p>
                      </div>
                    </div>

                    {/* Chart Frame */}
                    <div className="h-[240px] w-full relative border border-primary/5 bg-neutral/20 p-2 rounded-md select-none">
                      
                      {/* Left Y-Axis Labels (Fidelity) */}
                      <div className="absolute left-2 top-2 bottom-6 flex flex-col justify-between text-[7px] font-black tracking-widest text-tertiary/40 pointer-events-none z-10">
                        <span>100%</span>
                        <span>75%</span>
                        <span>50%</span>
                        <span>25%</span>
                        <span>0%</span>
                      </div>

                      {/* Right Y-Axis Labels (Load) */}
                      <div className="absolute right-2 top-2 bottom-6 flex flex-col justify-between text-[7px] font-black tracking-widest text-primary/30 pointer-events-none z-10 text-right">
                        <span>100</span>
                        <span>75</span>
                        <span>50</span>
                        <span>25</span>
                        <span>0</span>
                      </div>

                      {/* Bottom X-Axis Labels */}
                      <div className="absolute bottom-1 left-12 right-12 flex justify-between text-[7px] font-black tracking-widest text-primary/20 pointer-events-none z-10">
                        <span>30 epochs ago</span>
                        <span>15 epochs ago</span>
                        <span>Now</span>
                      </div>

                      {/* Graph Main SVG Area */}
                      <div className="absolute inset-0 left-10 right-10 top-2 bottom-6">
                        {activeTrend.length > 0 ? (
                          <div className="w-full h-full relative">
                            <svg 
                              className="w-full h-full" 
                              viewBox={`0 0 1000 ${CHART_SVG_HEIGHT}`} 
                              preserveAspectRatio="none"
                              aria-label="Accuracy versus load performance analytics chart"
                              role="img"
                            >
                              <defs>
                                <linearGradient id="fidelityGrad" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor="var(--tertiary)" stopOpacity="0.18" />
                                  <stop offset="100%" stopColor="var(--tertiary)" stopOpacity="0.00" />
                                </linearGradient>
                                <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor="var(--secondary)" stopOpacity="0.12" />
                                  <stop offset="100%" stopColor="var(--secondary)" stopOpacity="0.00" />
                                </linearGradient>
                              </defs>

                              {/* Background Gridlines */}
                              <g>
                                {/* Horizontal gridlines */}
                                {horizontalGridlines.map((y, idx) => (
                                  <line 
                                    key={`grid-h-${idx}`} 
                                    x1="0" 
                                    y1={y} 
                                    x2="1000" 
                                    y2={y} 
                                    stroke="var(--primary)" 
                                    strokeOpacity="0.04" 
                                    strokeDasharray="3 3" 
                                  />
                                ))}
                                
                                {/* Vertical gridlines */}
                                <line x1="200" y1="0" x2="200" y2={CHART_SVG_HEIGHT} stroke="var(--primary)" strokeOpacity="0.03" strokeDasharray="3 3" />
                                <line x1="400" y1="0" x2="400" y2={CHART_SVG_HEIGHT} stroke="var(--primary)" strokeOpacity="0.03" strokeDasharray="3 3" />
                                <line x1="600" y1="0" x2="600" y2={CHART_SVG_HEIGHT} stroke="var(--primary)" strokeOpacity="0.03" strokeDasharray="3 3" />
                                <line x1="800" y1="0" x2="800" y2={CHART_SVG_HEIGHT} stroke="var(--primary)" strokeOpacity="0.03" strokeDasharray="3 3" />
                              </g>

                              <>
                                {/* Load Area Gradient */}
                                {showLoad && (
                                  <motion.path 
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ duration: 0.5 }}
                                    d={pathStrings.loadAreaD}
                                    fill="url(#loadGrad)"
                                  />
                                )}

                                {/* Accuracy Area Gradient */}
                                {showFidelity && (
                                  <motion.path 
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ duration: 0.5 }}
                                    d={pathStrings.accuracyAreaD}
                                    fill="url(#fidelityGrad)"
                                  />
                                )}

                                {/* Load Curve Line */}
                                {showLoad && (
                                  <motion.path 
                                    initial={{ pathLength: 0 }}
                                    animate={{ pathLength: 1 }}
                                    transition={{ duration: 1.2, ease: "easeInOut" }}
                                    key={selectedTool?.tool_id + "-load"}
                                    d={pathStrings.loadD}
                                    fill="none"
                                    stroke="var(--secondary)"
                                    strokeOpacity="0.3"
                                    strokeWidth="1.5"
                                  />
                                )}

                                {/* Accuracy Curve Line */}
                                {showFidelity && (
                                  <motion.path 
                                    initial={{ pathLength: 0 }}
                                    animate={{ pathLength: 1 }}
                                    transition={{ duration: 1.2, ease: "easeInOut" }}
                                    key={selectedTool?.tool_id + "-accuracy"}
                                    d={pathStrings.accuracyD}
                                    fill="none"
                                    stroke="var(--tertiary)"
                                    strokeWidth="2.5"
                                  />
                                )}
                              </>
                            </svg>

                            {/* Mouse/Touch Detection Overlay */}
                            <div 
                              className="absolute inset-0 cursor-crosshair z-20 touch-none rounded-xl overflow-hidden"
                              onMouseMove={handleMouse}
                              onTouchMove={handleTouch}
                              onTouchStart={handleTouch}
                              onMouseLeave={() => setHoverIndex(null)}
                              onTouchEnd={() => setHoverIndex(null)}
                            />

                            {/* Interactive Visual Markers (Lines/Dots/Tooltip) */}
                            {hoverIndex !== null && (() => {
                              const currentPoint = activeTrend[hoverIndex];
                              if (!currentPoint) return null;
                              const stepPercent = activeTrend.length > 1 ? (hoverIndex / (activeTrend.length - 1)) * 100 : 0;
                              
                              const rawAccuracy = safeNumber(currentPoint.accuracy, 0);
                              const clampedAccuracy = Math.max(0, Math.min(100, rawAccuracy));
                              const accuracyY = Math.max(0, Math.min(CHART_SVG_HEIGHT, CHART_SVG_HEIGHT - clampedAccuracy * ACCURACY_SCALE_FACTOR));

                              const rawLoad = safeNumber(currentPoint.load, 0);
                              const clampedLoad = Math.max(0, Math.min(100, rawLoad));
                              const loadY = Math.max(0, Math.min(CHART_SVG_HEIGHT, CHART_SVG_HEIGHT - clampedLoad * LOAD_SCALE_FACTOR));

                              const tooltipLeft = hoverIndex > activeTrend.length / 2 ? `calc(${stepPercent}% - 180px)` : `calc(${stepPercent}% + 16px)`;
                              const tooltipTop = `${Math.min(Math.max((accuracyY / CHART_SVG_HEIGHT) * 100 - 15, 5), 55)}%`;

                              return (
                                <>
                                  {/* Vertical Cursor Tracking Line */}
                                  <div 
                                    className="absolute top-0 bottom-0 border-l border-dashed border-primary/20 pointer-events-none" 
                                    style={{ left: `${stepPercent}%` }}
                                  >
                                    <div className="absolute top-0 -translate-x-1/2 bg-primary text-neutral text-[6px] px-1 py-[2px] font-black uppercase rounded-md tracking-widest whitespace-nowrap shadow-md shadow-primary/10">
                                      T-{activeTrend.length - 1 - hoverIndex}
                                    </div>
                                  </div>

                                  {/* Fidelity Pulsing Highlight Dot */}
                                  {showFidelity && (
                                    <div 
                                      className="absolute w-3 h-3 rounded-full bg-tertiary border border-neutral shadow-[0_0_10px_var(--tertiary)] -translate-x-1/2 -translate-y-1/2 pointer-events-none z-10 transition-all duration-75"
                                      style={{ 
                                        left: `${stepPercent}%`, 
                                        top: `${(accuracyY / CHART_SVG_HEIGHT) * 100}%` 
                                      }}
                                    />
                                  )}

                                  {/* Load Pulsing Highlight Dot */}
                                  {showLoad && (
                                    <div 
                                      className="absolute w-3 h-3 rounded-full bg-secondary border border-neutral shadow-[0_0_10px_var(--secondary)] -translate-x-1/2 -translate-y-1/2 pointer-events-none z-10 transition-all duration-75"
                                      style={{ 
                                        left: `${stepPercent}%`, 
                                        top: `${(loadY / CHART_SVG_HEIGHT) * 100}%` 
                                      }}
                                    />
                                  )}

                                  {/* Floating Glassmorphic Tooltip */}
                                  <div 
                                    className="absolute bg-neutral/95 backdrop-blur-md border border-primary/10 shadow-2xl p-4 rounded-xl space-y-2 text-[10px] z-30 pointer-events-none transition-all duration-75 min-w-[160px] uppercase font-bold tracking-widest"
                                    style={{ left: tooltipLeft, top: tooltipTop }}
                                  >
                                    <div className="text-[8px] opacity-40 flex justify-between border-b border-primary/5 pb-1 mb-1 font-mono">
                                      <span>Epoch Sequence</span>
                                      <span>T-{activeTrend.length - 1 - hoverIndex}</span>
                                    </div>
                                    {showFidelity && (
                                      <div className="flex justify-between items-center text-tertiary">
                                        <span>Fidelity</span>
                                        <span className="font-black italic">{rawAccuracy.toFixed(1)}%</span>
                                      </div>
                                    )}
                                    {showLoad && (
                                      <div className="flex justify-between items-center text-primary">
                                        <span>Load Index</span>
                                        <span className="font-black italic">{rawLoad.toFixed(1)}%</span>
                                      </div>
                                    )}
                                    <div className="pt-1.5 border-t border-primary/5 text-[7px] opacity-40 flex justify-between font-mono">
                                      <span>F/L Ratio</span>
                                      <span>{(rawAccuracy / Math.max(1, rawLoad)).toFixed(2)}</span>
                                    </div>
                                  </div>
                                </>
                              );
                            })()}
                          </div>
                        ) : (
                          <div className="w-full h-full flex items-center justify-center border border-dashed border-primary/10 opacity-20 italic text-xs font-bold uppercase tracking-widest">
                            Awaiting temporal propagation...
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              {/* --- MIDDLE ROW: Reasoning Horizon (Horizontal) --- */}
              <section className="space-y-8">
                <div className="flex items-center justify-between border-b border-primary/5 pb-4">
                  <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">Reasoning Horizon</span>
                  <div className="flex items-center gap-4">
                    <span className="text-[10px] font-bold opacity-30 uppercase tracking-widest">{intelligenceHistory.length} Historical Pulses</span>
                    <div className="w-2 h-2 rounded-full bg-tertiary animate-pulse" />
                  </div>
                </div>

                {intelligenceHistory.length > 0 && (
                  <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-10 border border-tertiary/20 bg-card/60 artisan-shadow space-y-8 relative overflow-hidden group rounded-2xl"
                  >
                    <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                      <BrainCircuit className="w-40 h-40" />
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="px-3 py-1 bg-tertiary text-white text-[9px] font-black uppercase tracking-widest">Priority Intelligence</div>
                      <div className="h-[1px] flex-1 bg-tertiary/20" />
                      <span className="text-[10px] font-black text-tertiary">{(Math.max(...intelligenceHistory.map(h => h.confidence || 0)) * 100).toFixed(0)}% Confidence</span>
                    </div>
                    
                    {(() => {
                      const best = [...intelligenceHistory].sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0];
                      return (
                        <div className="space-y-6 relative z-10">
                          <h2 className="text-3xl md:text-4xl font-black text-primary leading-tight max-w-4xl italic tracking-tighter uppercase">
                            {"\""}{best.logic}{"\""}
                          </h2>
                          <div className="flex items-center gap-8">
                            <div className="space-y-1">
                              <span className="text-[8px] font-black uppercase tracking-widest opacity-40">Agent</span>
                              <div className="text-xs font-bold text-tertiary uppercase">{best.tool}</div>
                            </div>
                            <div className="space-y-1">
                              <span className="text-[8px] font-black uppercase tracking-widest opacity-40">Status</span>
                              <div className={`text-xs font-bold ${best.result === 'success' ? 'text-green-600' : 'text-red-600'} uppercase`}>{best.result.toUpperCase()}</div>
                            </div>
                            <button 
                              onClick={() => setSelectedDecision(best)}
                              className="ml-auto px-6 py-2.5 bg-primary text-neutral text-[9px] font-black uppercase tracking-widest hover:bg-primary/90 transition-all rounded-lg shadow-lg shadow-primary/10"
                            >
                              Audit Logic
                            </button>
                          </div>
                        </div>
                      );
                    })()}
                  </motion.div>
                )}
                
                <div className="relative group">
                  <div className="flex items-center gap-6 overflow-x-auto custom-scrollbar pb-8 snap-x snap-mandatory">
                    {intelligenceHistory.length > 0 ? intelligenceHistory.map((item: IntelligencePulse, idx: number) => (
                      <motion.div 
                        key={item.id}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: idx * 0.05 }}
                        onClick={() => setSelectedDecision(item)}
                        className="min-w-[280px] sm:min-w-[400px] snap-center p-8 border border-primary/5 bg-card/60 hover:border-tertiary/40 hover:bg-card transition-all group cursor-pointer space-y-4 rounded-xl shadow-sm"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-black text-tertiary uppercase tracking-[0.2em]">{item.tool}</span>
                          <span className="text-[9px] font-bold opacity-20">{item.timestamp?.split('T')[1].split(':')[0]}</span>
                        </div>
                        <p className="text-sm font-bold text-primary/90 line-clamp-2 min-h-[40px] uppercase tracking-tighter">{"\""}{item.logic}{"\""}</p>
                        <div className="pt-4 border-t border-primary/5 flex items-center justify-between">
                           <span className={`text-[9px] font-black ${item.result === 'success' ? 'text-green-600' : 'text-red-600'} uppercase`}>{item.result.toUpperCase()}</span>
                           <div className="h-1.5 w-1.5 bg-tertiary rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                      </motion.div>
                    )) : (
                      <div className="w-full py-20 text-center border border-dashed border-primary/10 opacity-20 italic text-xs font-bold uppercase tracking-widest">
                        Awaiting historical propagation...
                      </div>
                    )}
                  </div>
                  {/* Visual Fade indicators */}
                  <div className="absolute inset-y-0 left-0 w-20 bg-gradient-to-r from-background to-transparent pointer-events-none z-10" />
                  <div className="absolute inset-y-0 right-0 w-20 bg-gradient-to-l from-background to-transparent pointer-events-none z-10" />
                  <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-background to-transparent pointer-events-none z-10" />
                </div>
              </section>

              <section>
                  <div className="p-10 border border-primary/5 bg-card/60 backdrop-blur-xl artisan-shadow space-y-10 rounded-2xl">
                    <div className="flex items-center justify-between border-b border-primary/5 pb-6">
                      <div className="flex flex-col">
                        <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">Tool Matrix</span>
                        <p className="text-[10px] font-bold opacity-30 uppercase tracking-widest italic">Neural Capability Topology</p>
                      </div>
                      <span className="px-3 py-1 border border-primary/10 text-[9px] font-black opacity-40 uppercase tracking-widest rounded-full">{stats.length} Nodes Active</span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
                       {stats.map((tool: IntelligenceTool, idx: number) => (
                         <div 
                           key={idx}
                           onClick={() => {
                             setSelectedTool(tool);
                             setActiveToolModal(tool);
                           }}
                           className={`p-6 border transition-all cursor-pointer group rounded-xl ${selectedTool?.tool_id === tool.tool_id ? 'border-tertiary bg-card shadow-xl shadow-tertiary/5' : 'border-primary/5 bg-card/40 hover:border-tertiary/20'}`}
                         >
                           <div className="flex items-center justify-between mb-4">
                             <span className="text-[10px] font-black text-primary/40 truncate pr-2 uppercase tracking-tighter">{tool.tool_id.replace(/_/g, ' ')}</span>
                             {parseFloat(tool.delta || "0") > 0 ? (
                               <ArrowUpRight className="w-3 h-3 text-green-600" />
                             ) : (
                               <ArrowDownRight className="w-3 h-3 text-red-600" />
                             )}
                           </div>
                           <div className="text-2xl font-black italic tracking-tighter text-primary">{Math.round(tool.success_rate * 100)}%</div>
                         </div>
                       ))}
                    </div>
                  </div>
              </section>              <AnimatePresence>
                {selectedDecision && (
                  <div className="fixed inset-0 z-[150] flex items-center justify-center p-6 md:p-20">
                     <motion.div 
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      onClick={() => setSelectedDecision(null)}
                      className="absolute inset-0 bg-primary/40 backdrop-blur-md"
                    />
                    <motion.div 
                      initial={{ scale: 0.9, opacity: 0, y: 20 }}
                      animate={{ scale: 1, opacity: 1, y: 0 }}
                      exit={{ scale: 0.9, opacity: 0, y: 20 }}
                      className="relative w-full max-w-5xl max-h-[90vh] md:max-h-none bg-background shadow-[0_0_100px_rgba(0,0,0,0.2)] overflow-y-auto md:overflow-hidden flex flex-col md:flex-row rounded-2xl border border-primary/10"
                    >
                       <div className="md:w-2/5 p-6 sm:p-10 md:p-12 bg-card flex flex-col justify-between border-r border-primary/5 shrink-0">
                          <div className="space-y-6 sm:space-y-10">
                            <div className="flex flex-col gap-2">
                              <span className="text-[10px] font-black uppercase tracking-[0.4em] text-tertiary">Audit Pulse</span>
                              <h3 className="text-3xl sm:text-4xl font-black text-primary uppercase tracking-tighter italic">Reasoning Process</h3>
                              <p className="text-[10.5px] text-secondary opacity-80 leading-relaxed font-mono mt-1">
                                This panel records System 2 Supervisor audit verifications. It checks all proposed agent logic against linter, security, and architectural guardrails before final verification.
                              </p>
                            </div>
                            
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-1 gap-4 sm:gap-8">
                               <div className="space-y-1 sm:space-y-2">
                                 <div className="flex items-center gap-1.5">
                                   <span className="text-[9px] font-black uppercase tracking-widest opacity-40">Neural Origin</span>
                                 </div>
                                 <p className="text-xs sm:text-sm font-bold text-primary uppercase">{selectedDecision.tool}</p>
                                 <p className="text-[8.5px] text-secondary opacity-50 font-mono">The agent tool/subsystem that requested this execution.</p>
                               </div>
                               <div className="space-y-1 sm:space-y-2">
                                 <div className="flex items-center gap-1.5">
                                   <span className="text-[9px] font-black uppercase tracking-widest opacity-40">Confidence Rating</span>
                                 </div>
                                 <p className="text-xl sm:text-2xl font-black italic text-tertiary">{(selectedDecision.confidence * 100).toFixed(1)}%</p>
                                 <p className="text-[8.5px] text-secondary opacity-50 font-mono">Likelihood score calculated based on system-wide trial history.</p>
                               </div>
                               <div className="space-y-1 sm:space-y-2 sm:col-span-2 md:col-span-1">
                                 <span className="text-[9px] font-black uppercase tracking-widest opacity-40">Temporal Stamp</span>
                                 <p className="text-xs sm:text-sm font-bold text-primary" suppressHydrationWarning>{new Date(selectedDecision.timestamp).toLocaleString()}</p>
                               </div>
                            </div>
                          </div>

                          <button 
                            onClick={() => setSelectedDecision(null)}
                            className="mt-6 sm:mt-12 w-full py-4 bg-primary text-neutral text-[10px] font-black uppercase tracking-[0.3em] hover:bg-primary/90 transition-all rounded-lg"
                          >
                            Close Audit
                          </button>
                       </div>

                       <div className="flex-1 p-6 sm:p-12 md:p-16 space-y-6 sm:space-y-10 max-h-none md:max-h-[80vh] md:overflow-y-auto custom-scrollbar">
                          <div className="space-y-4">
                            <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40 italic">Proposed Logic</span>
                            <blockquote className="text-2xl md:text-3xl font-black text-primary leading-tight uppercase tracking-tighter italic">
                              {"\""}{selectedDecision.logic}{"\""}
                            </blockquote>
                          </div>

                          <div className="space-y-6">
                             <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40 italic">Result set</span>
                             <div className="p-8 bg-card border border-primary/5 space-y-4 rounded-xl">
                                <div className="flex items-center justify-between border-b border-primary/5 pb-4">
                                  <div className="flex flex-col gap-0.5">
                                    <span className="text-[9px] font-black uppercase tracking-widest">Execution Result</span>
                                    <span className="text-[8.5px] text-secondary opacity-50 font-mono normal-case tracking-normal">Verifies whether the tool passed linter audits and code safety tests.</span>
                                  </div>
                                  <span className={`px-3 py-1 text-[9px] font-black uppercase tracking-widest ${selectedDecision.result === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'} rounded-md`}>
                                    {selectedDecision.result}
                                  </span>
                                </div>
                                <div className="space-y-4 pt-4">
                                  <div className="flex flex-col gap-2">
                                    <span className="text-[9px] font-black uppercase tracking-widest opacity-30">Raw Output</span>
                                    <pre className="text-xs font-bold text-primary/70 whitespace-pre-wrap leading-relaxed font-mono p-4 bg-primary/[0.02] border border-primary/5 rounded-lg">
                                      {selectedDecision.output || "No supplementary trace data available."}
                                    </pre>
                                  </div>
                                </div>
                             </div>
                          </div>
                       </div>
                    </motion.div>
                  </div>
                )}
              </AnimatePresence>

              <AnimatePresence>
                {activeToolModal && (
                  <div className="fixed inset-0 z-[150] flex items-center justify-center p-6 md:p-20">
                     <motion.div 
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      onClick={() => setActiveToolModal(null)}
                      className="absolute inset-0 bg-primary/40 backdrop-blur-md"
                    />
                    <motion.div 
                      initial={{ scale: 0.9, opacity: 0, y: 20 }}
                      animate={{ scale: 1, opacity: 1, y: 0 }}
                      exit={{ scale: 0.9, opacity: 0, y: 20 }}
                      className="relative w-full max-w-4xl max-h-[90vh] md:max-h-none bg-background shadow-[0_0_100px_rgba(0,0,0,0.2)] overflow-y-auto md:overflow-hidden flex flex-col md:flex-row rounded-2xl border border-primary/10"
                    >
                       {/* Left Panel: Primary Info and Gauge */}
                       <div className="md:w-5/12 p-6 sm:p-10 bg-card flex flex-col justify-between border-r border-primary/5 shrink-0">
                          <div className="space-y-6 sm:space-y-8">
                            <div className="flex flex-col gap-2">
                              <span className="text-[10px] font-black uppercase tracking-[0.4em] text-tertiary">Tool Profile</span>
                              <h3 className="text-xl sm:text-2xl font-black text-primary uppercase tracking-tighter italic break-all">
                                {activeToolModal.tool_id.split('_').join(' ')}
                              </h3>
                              <p className="text-[10.5px] text-secondary opacity-80 leading-relaxed font-mono mt-1">
                                {getToolDescription(activeToolModal.tool_id)}
                              </p>
                            </div>
                            
                            <div className="flex flex-col py-4 sm:py-6 border-y border-primary/5 gap-4 sm:gap-6">
                              <div className="text-center space-y-1">
                                <span className="text-[9px] font-black uppercase tracking-widest opacity-40">Success Rate</span>
                                <div className="text-4xl sm:text-5xl font-black italic tracking-tighter text-primary">
                                  {Math.round(activeToolModal.success_rate * 100)}%
                                </div>
                              </div>
                              
                              <AccuracyGauge 
                                success={activeToolModal.success_count || activeToolModal.failure_count ? (activeToolModal.success_count || 0) : Math.round((activeToolModal.alpha || 0) * 10)} 
                                total={activeToolModal.success_count || activeToolModal.failure_count ? ((activeToolModal.success_count || 0) + (activeToolModal.failure_count || 0)) : Math.round(((activeToolModal.alpha || 0) + (activeToolModal.beta || 0)) * 10)} 
                                label="Bayesian Posterior"
                              />
                              <p className="text-[8.5px] text-secondary opacity-50 font-mono">
                                A statistical model estimating true capability based on trial history.
                              </p>
                            </div>
 
                            <div className="grid grid-cols-2 gap-4 sm:gap-6">
                               <div className="space-y-1">
                                 <span className="text-[9px] font-black uppercase tracking-widest opacity-40">Confidence</span>
                                 <p className="text-base sm:text-lg font-black italic text-tertiary">{activeToolModal.confidence || "OPTIMIZED"}</p>
                                 <p className="text-[8px] text-secondary opacity-50 font-mono mt-1">Reliability based on test volume.</p>
                               </div>
                               <div className="space-y-1 text-right">
                                 <span className="text-[9px] font-black uppercase tracking-widest opacity-40">Category</span>
                                 <p className="text-xs font-bold text-primary uppercase">{activeToolModal.category || "GENERAL"}</p>
                               </div>
                            </div>
                          </div>
 
                          <button 
                            onClick={() => setActiveToolModal(null)}
                            className="mt-6 sm:mt-8 w-full py-4 bg-primary text-neutral text-[10px] font-black uppercase tracking-[0.3em] hover:bg-primary/90 transition-all rounded-lg"
                          >
                            Close Profile
                          </button>
                       </div>
 
                       {/* Right Panel: Performance, Prior and Deltas */}
                       <div className="flex-1 p-6 sm:p-10 md:p-12 space-y-6 sm:space-y-8 max-h-none md:max-h-[85vh] md:overflow-y-auto custom-scrollbar">
                          <div className="space-y-3">
                             <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40 italic">Historical Signals</span>
                             <p className="text-[8.5px] text-secondary opacity-65 font-mono">Tally of successful vs failed tool execution runs.</p>
                             <div className="grid grid-cols-3 gap-2 sm:gap-4">
                               <div className="p-2 sm:p-4 border border-primary/5 bg-card/40 rounded-xl space-y-1">
                                 <span className="text-[8px] font-black uppercase tracking-widest opacity-35">Total</span>
                                 <div className="text-base sm:text-xl font-black italic text-primary">{(activeToolModal.success_count || 0) + (activeToolModal.failure_count || 0)}</div>
                               </div>
                               <div className="p-2 sm:p-4 border border-primary/5 bg-card/40 rounded-xl space-y-1">
                                 <span className="text-[8px] font-black uppercase tracking-widest opacity-35 text-green-600">Success</span>
                                 <div className="text-base sm:text-xl font-black italic text-green-600">{activeToolModal.success_count || 0}</div>
                               </div>
                               <div className="p-2 sm:p-4 border border-primary/5 bg-card/40 rounded-xl space-y-1">
                                 <span className="text-[8px] font-black uppercase tracking-widest opacity-35 text-red-600">Fail</span>
                                 <div className="text-base sm:text-xl font-black italic text-red-600">{activeToolModal.failure_count || 0}</div>
                               </div>
                             </div>
                          </div>
 
                          <div className="space-y-3">
                             <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40 italic">Bayesian Distribution Parameters</span>
                             <p className="text-[8.5px] text-secondary opacity-65 font-mono">Mathematical prior parameters. Success shape alpha (α) vs Failure shape beta (β).</p>
                             <div className="grid grid-cols-2 gap-2 sm:gap-4">
                               <div className="p-3 sm:p-5 border border-primary/5 bg-card/40 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                                 <div className="space-y-1">
                                   <span className="text-[8px] font-black uppercase tracking-widest opacity-35">Alpha prior (α)</span>
                                   <div className="text-xl sm:text-2xl font-black italic text-primary">{(activeToolModal.alpha || 2.0).toFixed(1)}</div>
                                 </div>
                                 <span className="text-xs sm:text-sm font-bold opacity-15 text-green-600 font-mono">SUCCESS</span>
                               </div>
                               <div className="p-3 sm:p-5 border border-primary/5 bg-card/40 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                                 <div className="space-y-1">
                                   <span className="text-[8px] font-black uppercase tracking-widest opacity-35">Beta prior (β)</span>
                                   <div className="text-xl sm:text-2xl font-black italic text-primary">{(activeToolModal.beta || 2.0).toFixed(1)}</div>
                                 </div>
                                 <span className="text-xs sm:text-sm font-bold opacity-15 text-red-600 font-mono">FAILURE</span>
                               </div>
                             </div>
                          </div>
 
                          <div className="space-y-3">
                             <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40 italic">Temporal Delta Shifts</span>
                             <p className="text-[8.5px] text-secondary opacity-65 font-mono">Performance rate percentage changes relative to historical baselines.</p>
                             <div className="grid grid-cols-2 gap-2 sm:gap-4">
                               <div className="p-3 sm:p-5 border border-primary/5 bg-card/40 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                                 <span className="text-[8px] font-black uppercase tracking-widest opacity-35">24H Performance Shift</span>
                                 <div className={`text-lg sm:text-xl font-black italic ${parseFloat(activeToolModal.delta || "0") >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                   {parseFloat(activeToolModal.delta || "0") >= 0 ? '+' : ''}{activeToolModal.delta || "0.0"}%
                                 </div>
                               </div>
                               <div className="p-3 sm:p-5 border border-primary/5 bg-card/40 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                                 <span className="text-[8px] font-black uppercase tracking-widest opacity-35">30D Performance Shift</span>
                                 <div className={`text-lg sm:text-xl font-black italic ${parseFloat(activeToolModal.mom_delta || "0") >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                   {parseFloat(activeToolModal.mom_delta || "0") >= 0 ? '+' : ''}{activeToolModal.mom_delta || "0.0"}%
                                 </div>
                               </div>
                             </div>
                          </div>

                          {TOOL_EQUATIONS[activeToolModal.tool_id] && (
                            <div className="space-y-3 pt-4">
                              <span className="text-[10px] font-black uppercase tracking-[0.4em] text-[var(--gold)] italic">Mathematical Model</span>
                              <div className="p-5 border border-[var(--gold)]/30 bg-[var(--sand)]/15 rounded-md space-y-4">
                                <div className="p-4 bg-[var(--background)] rounded border border-[var(--border-muted)] overflow-x-auto custom-scrollbar">
                                  <pre className="text-[var(--foreground)] font-mono text-sm font-semibold leading-relaxed whitespace-pre-wrap">{TOOL_EQUATIONS[activeToolModal.tool_id].math}</pre>
                                </div>
                                <details className="group">
                                  <summary className="text-[10px] font-bold uppercase tracking-wider text-[var(--foreground)] opacity-60 cursor-pointer select-none list-none flex items-center gap-1.5 hover:opacity-100 transition-opacity">
                                    <span>Explain Formula</span>
                                    <span className="text-[8px] transition-transform duration-200 group-open:rotate-180">▼</span>
                                  </summary>
                                  <div className="mt-3 pt-3 border-t border-[var(--border-muted)]/50">
                                    <p className="text-[11px] opacity-80 leading-relaxed font-mono text-[var(--foreground)]">
                                      {TOOL_EQUATIONS[activeToolModal.tool_id].desc}
                                    </p>
                                  </div>
                                </details>
                              </div>
                            </div>
                          )}
                       </div>
                    </motion.div>
                  </div>
                )}
              </AnimatePresence>
            </div>
          )}

          {activeTab === "memory" && (() => {
            const hasRealSignals = memorySignals.length > 0;
            const displaySignals = hasRealSignals ? memorySignals : [
              {
                id: "sig_e8a719",
                file: "core/tools/infrastructure/routers/intelligence.py",
                line: "194",
                content: "@router.get(\"/api/v1/memory/signals\")\nasync def get_memory_signals():\n    \"\"\"Retrieves the latest 20 neural signals from ChromaDB.\"\"\"\n    # System 3 Memory router fetching vectors"
              },
              {
                id: "sig_f839c0",
                file: "dashboard/src/app/observatory/page.tsx",
                line: "542",
                content: "fetch(`${API_BASE}/api/v1/memory/signals`, requestOptions)\n  .then(res => res.json())\n  .then(memoryData => setMemorySignals(memoryData.signals || []))\n  # Frontend Observatory view subscribing to memory updates"
              },
              {
                id: "sig_a39b28",
                file: "core/tools/memory/honcho_connect.py",
                line: "117",
                content: "def query_embeddings(query_text: str, n_results: int = 5):\n    # Adapter to query local ChromaDB or Honcho vector store\n    # Vector searches find code snippets relevant to active agent tasks"
              }
            ];

            return (
              <div className="space-y-10 animate-fade-in">
                {/* Neural Memory Guide Banner */}
                <div className="p-6 border border-primary/5 bg-primary/[0.01] rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-6 text-left">
                  <div className="space-y-2 max-w-2xl">
                    <span className="text-[10px] font-black uppercase tracking-[0.3em] text-tertiary">System 3 Memory Guide</span>
                    <p className="text-[11px] leading-relaxed text-secondary opacity-80">
                      <strong>Neural Memory Capture Nodes</strong> represent code chunks, system configurations, and past bug fixes stored as mathematical vector embeddings in ChromaDB. As you run agent workflows, Kenbun dynamically indexes new snippets and queries these vectors to retrieve architectural context and auto-repair problems.
                    </p>
                  </div>
                  {!hasRealSignals && (
                    <div className="shrink-0 flex items-center gap-2.5 px-4 py-2 bg-[var(--gold)]/10 border border-[var(--gold)]/20 text-[9px] font-black uppercase tracking-widest text-[var(--gold)] rounded-full animate-pulse">
                      <div className="w-1.5 h-1.5 rounded-full bg-[var(--gold)]" />
                      <span>Demo Mode Active</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between border-b border-primary/5 pb-6">
                  <div className="space-y-1">
                    <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">Neural Memory</span>
                    <p className="text-[10px] font-bold opacity-30 uppercase tracking-widest italic">System 3 Signal Propagation // Recent Captures</p>
                  </div>
                  <div className="flex items-center gap-4">
                     <div className="text-[10px] font-black opacity-30 uppercase tracking-widest">
                       {hasRealSignals ? `${memorySignals.length} Active` : "Demo Mode"} Logic Pulses
                     </div>
                     <Database className="w-5 h-5 text-tertiary" />
                  </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                  {displaySignals.map((signal: any, idx: number) => (
                    <motion.div 
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      key={idx} 
                      className="p-8 border border-primary/5 bg-card/60 backdrop-blur-xl shadow-sm space-y-6 hover:border-tertiary/30 transition-all group cursor-pointer rounded-2xl relative text-left"
                    >
                      {!hasRealSignals && (
                        <div className="absolute top-2 right-4 text-[7px] font-black uppercase tracking-widest text-[var(--gold)] opacity-40">
                          Demo Node
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-black text-tertiary uppercase tracking-[0.2em]">Signal Node</span>
                        <span className="text-[9px] font-bold opacity-20">POS_L{signal.line}</span>
                      </div>
                      
                      <div className="space-y-2">
                        <div className="text-base font-black italic text-primary group-hover:text-tertiary transition-colors truncate uppercase tracking-tighter">{signal.file.split(':').pop()?.split('/').pop()}</div>
                        <div className="text-[10px] font-bold opacity-40 uppercase tracking-widest truncate italic">{signal.file}</div>
                      </div>

                      <div className="text-xs font-bold text-primary/80 bg-primary/[0.02] p-5 leading-relaxed border border-primary/5 rounded-xl overflow-hidden whitespace-pre-wrap min-h-[140px] max-h-[200px] overflow-y-auto custom-scrollbar font-mono">
                        {signal.content}
                      </div>
                      
                      <div className="pt-4 border-t border-primary/5 flex items-center justify-between">
                        <span className="text-[10px] font-black opacity-30 uppercase tracking-widest">Type: Vector_Embedding</span>
                        <div className="h-2 w-2 rounded-full bg-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            );
          })()}

          {activeTab === "feed" && (
            <div className="space-y-8">
              <div className="p-10 border border-primary/5 bg-card/60 backdrop-blur-xl artisan-shadow space-y-8 h-[800px] flex flex-col rounded-2xl">
                <div className="flex items-center justify-between border-b border-primary/5 pb-6">
                  <div className="flex items-center gap-4">
                    <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">Signal Archive</span>
                    <span className="text-[10px] font-bold opacity-30 uppercase tracking-widest italic">Live Terminal // Raw Feed</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-tertiary animate-pulse" />
                    <span className="text-[10px] font-black text-tertiary uppercase tracking-widest">Recording</span>
                  </div>
                </div>
                
                <div className="flex-1 overflow-y-auto space-y-4 font-mono pr-4 scrollbar-thin scrollbar-thumb-primary/10">
                  {logs.length > 0 ? logs.slice(-50).map((log: string | SystemLog, idx: number) => {
                    let messageStr = "";
                    let timestampVal: number | string | undefined;
                    
                    if (typeof log === 'string') {
                      messageStr = log;
                      // Detect JSON string format from backend
                      if (log.trim().startsWith("{") && log.trim().endsWith("}")) {
                        try {
                          const parsed = JSON.parse(log);
                          messageStr = parsed.message || messageStr;
                          timestampVal = parsed.timestamp;
                        } catch {}
                      }
                    } else if (log && typeof log === 'object') {
                      const logObj = log as Record<string, string | number | undefined>;
                      messageStr = String(logObj.message || logObj.content || JSON.stringify(log));
                      timestampVal = logObj.timestamp;
                    }

                    // Format timestamp
                    let timeDisplay = "--:--:--";
                    if (timestampVal) {
                      try {
                        const parsedTs = typeof timestampVal === 'number' ? timestampVal : parseFloat(timestampVal as string);
                        timeDisplay = !isNaN(parsedTs)
                          ? new Date(parsedTs * 1000).toLocaleTimeString()
                          : new Date(timestampVal as string).toLocaleTimeString();
                      } catch {
                        timeDisplay = String(timestampVal);
                      }
                    } else {
                      // Fallback to client-side current time if no timestamp is present
                      timeDisplay = new Date().toLocaleTimeString();
                    }

                    return (
                      <div key={idx} className="group flex items-start gap-6 opacity-60 hover:opacity-100 transition-opacity border-b border-primary/[0.02] pb-3">
                        <span className="text-[10px] font-black text-tertiary shrink-0">[{timeDisplay}]</span>
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-3">
                            <span className="text-[9px] font-black uppercase tracking-widest opacity-30 italic">System_Log //</span>
                          </div>
                          <p className="text-[11px] font-bold text-primary/90 leading-relaxed uppercase tracking-tighter">
                            {messageStr}
                          </p>
                        </div>
                      </div>
                    );
                  }) : (
                    <div className="h-full flex items-center justify-center border border-dashed border-primary/10 opacity-20 italic text-xs font-bold uppercase tracking-widest">
                      Awaiting terminal stream...
                    </div>
                  )}
                  <div className="text-[10px] font-bold text-tertiary animate-pulse pt-4 uppercase tracking-widest italic">_ Awaiting next signal pulse...</div>
                </div>
              </div>
            </div>
          )}
        </motion.div>

        {/* <RoamingMascot /> */}

        <footer className="h-16 border-t border-primary/10 flex items-center justify-between px-10 bg-card/60 text-[8px] font-black uppercase tracking-[0.8em] text-primary opacity-40 sticky bottom-0 lg:static backdrop-blur-xl">
          <span>NODE.251649 // Heritage.HIVE // STATUS: {buildStatus?.status || "HEALTHY"}</span>
          <div className="flex items-center gap-6">
            <span>LOC_127.0.0.1</span>
            <span className="text-tertiary opacity-80">/ ARCH: {pulse?.supervisor || "SYSTEM 2"}</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
