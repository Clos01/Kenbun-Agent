"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  X, 
  Search, 
  HelpCircle, 
  Compass, 
  Columns, 
  LayoutGrid, 
  Layers, 
  Activity, 
  ShieldCheck, 
  Database, 
  Terminal, 
  Settings,
  GitBranch,
  FileText,
  Zap,
  CheckCircle2,
  ExternalLink,
  ChevronRight
} from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

export type ModuleKey = 
  | "bridge" 
  | "board" 
  | "fleet" 
  | "apps" 
  | "telemetry" 
  | "supervisor" 
  | "hivemind" 
  | "chat" 
  | "settings";

interface SystemGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialModule?: ModuleKey;
}

interface GuideContent {
  title: string;
  badge: string;
  icon: any;
  overview: string;
  whatItDoes: string[];
  howToUse: { title: string; desc: string; code?: string }[];
  proTips: string[];
}

export const MODULE_GUIDES: Record<ModuleKey, GuideContent> = {
  bridge: {
    title: "Build Console",
    badge: "Telemetry & Command",
    icon: Compass,
    overview: "The Command & Control Telemetry Center for the Kenbun AI Swarm, giving you live visual telemetry into tools, accuracy metrics, and AI execution latency.",
    whatItDoes: [
      "Visualizes all active MCP tools, subagents, and memory nodes in an interactive 3D/2D Galaxy Map.",
      "Measures real-time Bayesian Posterior accuracy rates across automated tool calls.",
      "Tracks execution throughput, latency graphs, and token consumption.",
      "Provides a live Mission Runner to dispatch tasks to the swarm directly from the UI."
    ],
    howToUse: [
      {
        title: "1. View the System Architecture",
        desc: "Click and drag to pan the cosmos. Click any node to open the Inspector Panel, view file snippets, and see incoming/outgoing dependency links."
      },
      {
        title: "2. Run System Diagnostics",
        desc: "Inside the node Inspector Panel, click 'RUN CODE REVIEW' to trigger a System 2 security audit or 'DIAGNOSE & FIX' to resolve code regressions."
      },
      {
        title: "3. Dispatch Build Commands",
        desc: "Scroll down to the Mission Runner terminal, select a pre-canned button (e.g. 'Audit Security Rules') or type any prompt, then click 'Run Mission'."
      }
    ],
    proTips: [
      "Click any room filter (core, utils, api, db) at the top of the map to spotlight specific code modules.",
      "Use the Bayesian Accuracy Gauge to verify system fidelity before deploying code changes to production."
    ]
  },
  board: {
    title: "Mission Board & Workflow",
    badge: "Agile & SOW Studio",
    icon: Columns,
    overview: "Your agile mission command center featuring Kanban card columns, interactive Flowchart dependency diagrams, and automated Statement of Work (SOW) generation.",
    whatItDoes: [
      "Manages task lifecycle cards across lists (To Do, In Progress, Blocked, Done).",
      "Renders task prerequisite pipelines on an interactive Flowchart canvas.",
      "Generates dynamic, theme-styled SOW documents with automated word count and PDF export.",
      "Provides Calendar and Feed views for team activity tracking."
    ],
    howToUse: [
      {
        title: "1. Switch Between Views",
        desc: "Click the view selector in the top header (e.g., 'WORKFLOW ▾') to toggle between Board (Kanban), Workflow (Flowchart), SOW (Document Studio), Calendar, and Feed."
      },
      {
        title: "2. Understand Glowing Flowchart Lines",
        desc: "Directional dashed lines show prerequisite execution order. Task A points to Task B if Task A must be completed before Task B can begin."
      },
      {
        title: "3. Generate Statements of Work (SOW)",
        desc: "Switch to 'SOW' mode. Select a contract template, customize parameters, preview estimated reading time, and click 'EXPORT PDF' to generate contract files."
      }
    ],
    proTips: [
      "Click any card on the Flowchart to view incoming predecessors and jump directly across the canvas.",
      "Cards dynamically sync with the local Planka PostgreSQL database."
    ]
  },
  fleet: {
    title: "Agent Manager",
    badge: "Multi-Agent Orchestration",
    icon: LayoutGrid,
    overview: "Monitors and coordinates parallel AI agent workers, subagent tasks, thread pools, and distributed execution pipelines.",
    whatItDoes: [
      "Dispatches background autonomous agent tasks via FastMCP and Ollama/Gemini routers.",
      "Monitors real-time worker thread pool load and job completion status.",
      "Logs agent reasoning steps and subagent messages across UUID session contexts.",
      "Enforces automatic watchdog error handling and retry loops."
    ],
    howToUse: [
      {
        title: "1. Dispatch a Fleet Task",
        desc: "Enter a task description, select the target model (Flash, Pro, Lite), and click 'Dispatch Worker'."
      },
      {
        title: "2. Inspect Active Workers",
        desc: "View running worker cards to monitor CPU/memory overhead, current step index, and log output."
      },
      {
        title: "3. Kill or Pause Stuck Tasks",
        desc: "Use the 'Terminate' button on any worker card to stop execution safely without corrupting workspace state."
      }
    ],
    proTips: [
      "Use persistent UUID Session IDs to let subagents resume context over multiple execution rounds.",
      "The Orchestrator automatically delegates heavy reasoning tasks to System 2."
    ]
  },
  apps: {
    title: "Services Hub",
    badge: "Local Stack Services",
    icon: Layers,
    overview: "Direct access launcher and status monitor for all 6 self-hosted tools in the Sovereign Tech Stack.",
    whatItDoes: [
      "Provides single-click access to Planka (Kanban), n8n (Automation), Ollama (Local LLM), Gitea (Git Repo), Supabase (PostgreSQL), and FastMCP.",
      "Monitors HTTP health checks and container status for each service.",
      "Pushes cloud API costs to near zero by prioritizing local execution nodes."
    ],
    howToUse: [
      {
        title: "1. Launch Service UIs",
        desc: "Click any app card (e.g. 'n8n Workflows' or 'Planka Board') to open the native web dashboard for that tool."
      },
      {
        title: "2. Check Service Health",
        desc: "Green badges indicate the local Docker container is active and responding cleanly to health pings."
      }
    ],
    proTips: [
      "n8n automations run locally on port 5678 and connect directly to local Ollama inference endpoints.",
      "Planka task cards are stored locally in the postgres planka_db container."
    ]
  },
  telemetry: {
    title: "Metrics & Telemetry",
    badge: "Analytics & Signals",
    icon: Activity,
    overview: "Deep telemetry dashboard tracking API latency, signal memory graphs, token consumption, and historical system events.",
    whatItDoes: [
      "Renders sharp area charts of API latency and token usage over time.",
      "Displays memory signal graphs tracking agent decisions and system health.",
      "Provides searchable telemetry logs with error tracebacks and response status codes."
    ],
    howToUse: [
      {
        title: "1. Filter Telemetry by Timeframe",
        desc: "Use the timeframe toggle (1H, 24H, 7D) to inspect historical execution trends."
      },
      {
        title: "2. Inspect Memory Signals",
        desc: "Scroll through the Memory Signals list to verify how system memories are ingested and retrieved."
      }
    ],
    proTips: [
      "Look out for latency spikes above 2000ms to identify heavy cloud LLM queries that can be offloaded to local Ollama models."
    ]
  },
  supervisor: {
    title: "Security Audit",
    badge: "System 2 Safety Evaluator",
    icon: ShieldCheck,
    overview: "System 2 safety gatekeeper that audits code changes, verifies security boundaries, prevents SQL/shell injection, and enforces architectural guardrails.",
    whatItDoes: [
      "Executes 2-pass multi-model security reviews before any code is approved for execution.",
      "Audits proposed changes for SQL injection, shell injection, unsanitized inputs, and secret leakage.",
      "Enforces architectural guardrails and project conventions.",
      "Provides an Adversarial Court mode for supreme evaluation."
    ],
    howToUse: [
      {
        title: "1. Run Manual Code Audit",
        desc: "Paste code or select a file path, enter your audit proposal, and click 'Consult Supervisor'."
      },
      {
        title: "2. Review Audit Verdict",
        desc: "The Supervisor returns 'APPROVED', 'BLOCKED', or 'REJECTED' along with a line-by-line critique checklist."
      },
      {
        title: "3. Enable Iterative Auto-Fix Mode",
        desc: "Set 'iterative_mode=True' to allow System 2 to auto-correct lints and security warnings automatically."
      }
    ],
    proTips: [
      "The Supervisor is mandatory for signing off complex task groups before completion.",
      "No security rule can be bypassed without explicit user approval."
    ]
  },
  hivemind: {
    title: "Code Search",
    badge: "System 3 Vector Store",
    icon: Database,
    overview: "Long-term persistent memory store combining Honcho conversation history and ChromaDB vector embeddings for instant semantic search.",
    whatItDoes: [
      "Stores architectural concepts, fixed bugs, user preferences, and lessons learned across sessions.",
      "Ingests PDFs, markdown docs, and web URLs into vector embeddings.",
      "Provides semantic concept search and pruning tools."
    ],
    howToUse: [
      {
        title: "1. Ingest Knowledge Files",
        desc: "Drag & drop PDF files or enter doc URLs into the Ingestion Panel to vectorize them into Hivemind memory."
      },
      {
        title: "2. Search Concepts",
        desc: "Use the semantic search bar to find past decisions, bug post-mortems, or user preferences."
      },
      {
        title: "3. Prune Stale Memories",
        desc: "Select outdated concepts and click 'Prune' to keep memory vector stores clean and performant."
      }
    ],
    proTips: [
      "When a complex bug is fixed, post-mortems are automatically remembered in the Hivemind so the agent never repeats the same error.",
      "Queries use pgvector and Chroma DB for sub-10ms similarity searches."
    ]
  },
  chat: {
    title: "AI Swarm Chat",
    badge: "Conversational Agent",
    icon: Terminal,
    overview: "Multi-model AI chat interface supporting local Ollama, cloud Gemini Flash/Pro, parameter mechanics, and dynamic MCP tool execution.",
    whatItDoes: [
      "Executes real-time pair programming, research, and command tasks with Antigravity AI.",
      "Supports auto-replacement of '[Generated Script]' placeholders with live executable Python/JS code.",
      "Maintains persistent chat session history across turns."
    ],
    howToUse: [
      {
        title: "1. Send a Request",
        desc: "Type your query or task prompt in the chat input. Mention specific tools or subagents if desired."
      },
      {
        title: "2. Inspect Tool Outputs",
        desc: "Click on tool execution blocks in the message stream to view raw JSON outputs, file diffs, or execution logs."
      }
    ],
    proTips: [
      "Use slash commands like /goal or /schedule to automate long-running tasks or cron jobs."
    ]
  },
  settings: {
    title: "Controls & Settings",
    badge: "Theme & Tenant Context",
    icon: Settings,
    overview: "Global workspace configuration manager for visual theme presets, active tenant scoping, API key secrets, and model parameters.",
    whatItDoes: [
      "Switches between 8 curated visual theme presets (Limestone, Obsidian, Forest, Cobalt, Breeze, Midnight, Cyber, Sunset).",
      "Manages multi-tenant workspace contexts.",
      "Configures local and cloud API endpoints."
    ],
    howToUse: [
      {
        title: "1. Switch Theme Preset",
        desc: "Click any theme swatch (e.g. 'Limestone' or 'Obsidian') to update all UI colors, card tokens, and typography dynamically."
      },
      {
        title: "2. Set Active Tenant",
        desc: "Use the tenant dropdown to scope data, Planka boards, and telemetry to a specific project."
      }
    ],
    proTips: [
      "Theme tokens automatically propagate to generated Statements of Work (SOWs) and PDF exports!"
    ]
  }
};

export default function SystemGuideModal({ 
  isOpen, 
  onClose, 
  initialModule = "bridge" 
}: SystemGuideModalProps) {
  const { preset } = useTheme();
  const [activeTab, setActiveTab] = useState<ModuleKey>(initialModule);
  const [searchQuery, setSearchQuery] = useState("");

  const currentGuide = MODULE_GUIDES[activeTab] || MODULE_GUIDES.bridge;
  const ActiveIcon = currentGuide.icon;
  const tourAvailable = typeof window !== "undefined" && !!((window as any).__kenbunTours && (window as any).__kenbunTours.size > 0);

  // Filter modules matching search query
  const filteredKeys = useMemo(() => {
    if (!searchQuery.trim()) return Object.keys(MODULE_GUIDES) as ModuleKey[];
    const q = searchQuery.toLowerCase();
    return (Object.keys(MODULE_GUIDES) as ModuleKey[]).filter(key => {
      const g = MODULE_GUIDES[key];
      return (
        g.title.toLowerCase().includes(q) ||
        g.badge.toLowerCase().includes(q) ||
        g.overview.toLowerCase().includes(q) ||
        g.whatItDoes.some(w => w.toLowerCase().includes(q)) ||
        g.howToUse.some(h => h.title.toLowerCase().includes(q) || h.desc.toLowerCase().includes(q))
      );
    });
  }, [searchQuery]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/65 backdrop-blur-md z-[150]"
          />

          {/* Modal Container */}
          <div className="fixed inset-0 z-[160] flex items-center justify-center p-3 sm:p-6 pointer-events-none">
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              transition={{ type: "spring", damping: 28, stiffness: 300 }}
              className="w-full max-w-5xl h-[85vh] max-h-[750px] bg-card border border-border rounded-2xl shadow-2xl pointer-events-auto flex flex-col overflow-hidden text-primary"
            >
              {/* HEADER BAR */}
              <div className="px-5 py-4 border-b border-border/80 flex items-center justify-between gap-4 bg-neutral/40 shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-tertiary/10 border border-tertiary/25 flex items-center justify-center text-tertiary font-bold shadow-xs">
                    <HelpCircle className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="font-bold text-base tracking-tight text-primary flex items-center gap-2">
                      Kenbun System Guide &amp; Documentation
                    </h2>
                    <p className="text-xs text-secondary">
                      Comprehensive user manual &amp; operational guide for all web app modules
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {/* Search Bar */}
                  <div className="relative hidden sm:block w-56">
                    <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none" />
                    <input
                      type="text"
                      placeholder="Search guides..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full bg-neutral border border-border/80 rounded-lg py-1.5 pl-8 pr-3 text-xs text-primary placeholder:text-secondary/60 focus:outline-none focus:border-tertiary"
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery("")}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-secondary hover:text-primary"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>

                  <button
                    onClick={onClose}
                    className="p-2 rounded-xl hover:bg-neutral text-secondary hover:text-primary transition-colors cursor-pointer border border-transparent hover:border-border"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* MAIN CONTENT SPLIT LAYOUT */}
              <div className="flex-1 flex flex-col sm:flex-row min-h-0 overflow-hidden">
                {/* LEFT NAVIGATION SIDEBAR */}
                <div className="w-full sm:w-64 border-b sm:border-b-0 sm:border-r border-border/80 bg-neutral/30 flex flex-row sm:flex-col overflow-x-auto sm:overflow-y-auto shrink-0 p-2 sm:p-3 gap-1 custom-scrollbar">
                  {filteredKeys.length === 0 ? (
                    <div className="p-4 text-center text-xs text-secondary">
                      No matching guides found
                    </div>
                  ) : (
                    filteredKeys.map((key) => {
                      const item = MODULE_GUIDES[key];
                      const Icon = item.icon;
                      const isActive = activeTab === key;
                      return (
                        <button
                          key={key}
                          onClick={() => setActiveTab(key)}
                          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all cursor-pointer text-xs shrink-0 ${
                            isActive
                              ? "bg-tertiary/10 border border-tertiary/25 text-tertiary font-bold shadow-xs"
                              : "border border-transparent text-secondary hover:text-primary hover:bg-neutral/60"
                          }`}
                        >
                          <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-tertiary" : "opacity-60"}`} />
                          <div className="min-w-0 flex-1 truncate">
                            <div className="truncate font-semibold">{item.title}</div>
                            <div className="text-[9px] text-secondary uppercase tracking-widest font-mono opacity-80 truncate">
                              {item.badge}
                            </div>
                          </div>
                          {isActive && <ChevronRight className="w-3.5 h-3.5 ml-auto text-tertiary hidden sm:block shrink-0" />}
                        </button>
                      );
                    })
                  )}
                </div>

                {/* RIGHT GUIDE DETAILS BODY */}
                <div className="flex-1 overflow-y-auto p-5 sm:p-8 space-y-6 custom-scrollbar bg-card">
                  {/* MODULE TITLE BANNER */}
                  <div className="flex items-start justify-between gap-4 border-b border-border/60 pb-5">
                    <div className="space-y-1.5">
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-tertiary/10 border border-tertiary/20 text-tertiary text-[10px] font-mono font-bold uppercase tracking-widest">
                        <ActiveIcon className="w-3 h-3" />
                        {currentGuide.badge}
                      </div>
                      <h1 className="text-2xl font-bold tracking-tight text-primary">
                        {currentGuide.title}
                      </h1>
                      <p className="text-xs text-secondary leading-relaxed max-w-2xl">
                        {currentGuide.overview}
                      </p>
                    </div>
                  </div>

                  {/* SECTION 1: WHAT IT DOES */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-tertiary flex items-center gap-2">
                      <Zap className="w-3.5 h-3.5 text-tertiary" />
                      What This Module Does
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {currentGuide.whatItDoes.map((item, idx) => (
                        <div
                          key={idx}
                          className="p-3.5 bg-neutral/40 border border-border/60 rounded-xl space-y-1 text-xs text-secondary leading-relaxed"
                        >
                          <div className="flex items-start gap-2">
                            <CheckCircle2 className="w-3.5 h-3.5 text-tertiary mt-0.5 shrink-0" />
                            <span>{item}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* SECTION 2: HOW TO USE IT */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-tertiary flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5 text-tertiary" />
                      How to Use It (Step-by-Step)
                    </h3>
                    <div className="space-y-3">
                      {currentGuide.howToUse.map((step, idx) => (
                        <div
                          key={idx}
                          className="p-4 bg-neutral/50 border border-border/70 rounded-xl space-y-1.5"
                        >
                          <h4 className="font-bold text-xs text-primary flex items-center gap-2">
                            <span className="w-5 h-5 rounded-full bg-tertiary/15 text-tertiary font-mono text-[10px] flex items-center justify-center font-bold">
                              {idx + 1}
                            </span>
                            {step.title}
                          </h4>
                          <p className="text-xs text-secondary leading-relaxed pl-7">
                            {step.desc}
                          </p>
                          {step.code && (
                            <pre className="mt-2 ml-7 p-2.5 bg-neutral border border-border rounded-lg text-[10px] font-mono text-tertiary overflow-x-auto">
                              <code>{step.code}</code>
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* SECTION 3: PRO TIPS */}
                  {currentGuide.proTips.length > 0 && (
                    <div className="p-4 bg-tertiary/5 border border-tertiary/20 rounded-xl space-y-2">
                      <h4 className="text-xs font-bold text-tertiary flex items-center gap-2 uppercase tracking-wider font-mono">
                        💡 Pro Tips &amp; Architecture Notes
                      </h4>
                      <ul className="space-y-1 text-xs text-secondary list-disc list-inside leading-relaxed">
                        {currentGuide.proTips.map((tip, idx) => (
                          <li key={idx}>{tip}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>

              {/* FOOTER */}
              <div className="px-6 py-3 border-t border-border/80 bg-neutral/40 flex items-center justify-between shrink-0 text-xs">
                <div className="text-[10px] font-mono text-secondary uppercase tracking-widest">
                  Kenbun Sovereign Hive &bull; Documentation System v3.2
                </div>
                <div className="flex items-center gap-2">
                  {tourAvailable && (
                  <button
                    onClick={() => { if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("kenbun:start-tour")); onClose(); }}
                    className="px-4 py-1.5 bg-primary/10 text-primary rounded-lg font-bold text-xs hover:bg-primary/20 active:scale-95 transition-all cursor-pointer inline-flex items-center gap-1.5"
                  >
                    &#9658; Take the Tour
                  </button>
                  )}
                  <button
                    onClick={onClose}
                    className="px-4 py-1.5 bg-tertiary text-white rounded-lg font-bold text-xs shadow-xs hover:opacity-90 active:scale-95 transition-all cursor-pointer"
                  >
                    Close Guide
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
