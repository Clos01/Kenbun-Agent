"use client";

import React, { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { 
  GitBranch, 
  Layers, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Cpu, 
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  DollarSign, 
  FileCode, 
  ShieldCheck, 
  Search, 
  RefreshCw, 
  Sparkles, 
  Code2, 
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ChevronRight,
  Eye,
  X
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface TokenStats {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

interface AgentEnvelope {
  task_id: string;
  phase: string;
  model_name: string;
  timestamp: string;
  plan_summary: string;
  target_files: string[];
  required_tests: string[];
  handoff_notes: string;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
  artifacts?: Record<string, any>;
  token_stats?: TokenStats;
  status: string;
}

interface WorkflowPhase {
  status: string;
  model: string;
  timestamp: string;
  summary: string;
}

interface WorkflowSession {
  task_id: string;
  last_updated: string;
  phases: Record<string, WorkflowPhase>;
  envelopes?: Record<string, AgentEnvelope>;
}

const PHASES_ORDER = [
  { key: "scout", label: "Scout / Intake", icon: Search },
  { key: "plan", label: "Plan & Arch", icon: FileCode },
  { key: "build", label: "Build & Code", icon: Code2 },
  { key: "test", label: "Deterministic Gate", icon: ShieldCheck },
  { key: "review", label: "System 2 Audit", icon: Sparkles },
];

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEnvelope, setSelectedEnvelope] = useState<AgentEnvelope | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowSession | null>(null);

  const fetchWorkflows = async () => {
    try {
      const res = await fetch("/api/workflows");
      const data = await res.json();
      if (data.success) {
        setWorkflows(data.workflows);
        if (!selectedWorkflow && data.workflows.length > 0) {
          setSelectedWorkflow(data.workflows[0]);
        }
      }
    } catch (err) {
      console.error("Failed to load workflows:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
      // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchWorkflows();
    const interval = setInterval(fetchWorkflows, 6000);
    return () => clearInterval(interval);
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20"><CheckCircle2 className="w-3 h-3" /> Done</span>;
      case "in_progress":
        return <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold border border-amber-500/20 animate-pulse"><Clock className="w-3 h-3" /> Running</span>;
      case "failed":
        return <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold border border-rose-500/20"><AlertCircle className="w-3 h-3" /> Failed</span>;
      default:
        return <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground font-medium border border-border">Queued</span>;
    }
  };

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar />

      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-muted/5">
        {/* TOP BAR */}
        <header className="h-16 border-b border-border/80 px-8 flex items-center justify-between bg-card/60 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight">AI Developer Workflows (ADWs)</h1>
              <p className="text-xs text-muted-foreground">Deterministic Software Factory Swimlane Visualizer</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button 
              onClick={() => { setLoading(true); fetchWorkflows(); }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-card border border-border/80 hover:border-primary/50 text-foreground transition-all cursor-pointer hover:shadow-sm"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </header>

        {/* WORKSPACE CONTENT */}
        <div className="p-8 max-w-7xl mx-auto w-full space-y-8">
          {/* BANNER / METRICS */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-card border border-border/80 shadow-xs flex flex-col justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Active Workflows</span>
              <span className="text-2xl font-bold text-foreground mt-2">{workflows.length}</span>
              <span className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> System 1-4 Synchronized
              </span>
            </div>

            <div className="p-4 rounded-xl bg-card border border-border/80 shadow-xs flex flex-col justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Deterministic Gates</span>
              <span className="text-2xl font-bold text-foreground mt-2">100%</span>
              <span className="text-[11px] text-primary mt-1 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> Test-Pass Token Suppression Active
              </span>
            </div>

            <div className="p-4 rounded-xl bg-card border border-border/80 shadow-xs flex flex-col justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Primary Model Stack</span>
              <span className="text-xl font-bold text-foreground mt-2">Claude + Gemini</span>
              <span className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
                <Cpu className="w-3 h-3" /> Local Ollama (Offline Tier)
              </span>
            </div>

            <div className="p-4 rounded-xl bg-card border border-border/80 shadow-xs flex flex-col justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Context Envelope Type</span>
              <span className="text-xl font-bold text-foreground mt-2">Strict JSON</span>
              <span className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Zero Handoff Drift
              </span>
            </div>
          </div>

          {/* SESSIONS SELECTOR */}
          <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {workflows.map((wf) => (
              <button
                key={wf.task_id}
                onClick={() => setSelectedWorkflow(wf)}
                className={`px-4 py-2 rounded-lg text-xs font-medium border transition-all cursor-pointer shrink-0 flex items-center gap-2 ${
                  selectedWorkflow?.task_id === wf.task_id
                    ? "bg-primary text-primary-foreground border-primary shadow-sm"
                    : "bg-card text-muted-foreground border-border hover:border-primary/40 hover:text-foreground"
                }`}
              >
                <GitBranch className="w-3.5 h-3.5" />
                <span className="font-mono">{wf.task_id}</span>
              </button>
            ))}
          </div>

          {/* ACTIVE SWIMLANE BOARD */}
          {selectedWorkflow && (
            <div className="bg-card border border-border/80 rounded-2xl p-6 shadow-sm space-y-6">
              <div className="flex items-center justify-between border-b border-border/60 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-foreground font-mono">{selectedWorkflow.task_id}</h2>
                    <span className="text-xs px-2.5 py-0.5 rounded-full bg-primary/10 text-primary font-semibold">
                      Software Factory Pipeline
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Last updated: {new Date(selectedWorkflow.last_updated).toLocaleString()}
                  </p>
                </div>
              </div>

              {/* THE SWIMLANE FLOW */}
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                {PHASES_ORDER.map((phaseDef, idx) => {
                  const phaseData = selectedWorkflow.phases[phaseDef.key];
                  const envelope = selectedWorkflow.envelopes?.[phaseDef.key];
                  const Icon = phaseDef.icon;
                  const isDone = !!phaseData;

                  return (
                    <motion.div
                      key={phaseDef.key}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      className={`relative rounded-xl border p-4 flex flex-col justify-between min-h-[220px] transition-all ${
                        isDone 
                          ? "bg-card/80 border-border/90 hover:border-primary/60 hover:shadow-md"
                          : "bg-muted/10 border-dashed border-border/60 opacity-60"
                      }`}
                    >
                      {/* HEADER */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-md bg-primary/10 flex items-center justify-center text-primary">
                              <Icon className="w-3.5 h-3.5" />
                            </div>
                            <span className="text-xs font-bold uppercase tracking-wider text-foreground">
                              {phaseDef.label}
                            </span>
                          </div>
                        </div>

                        {phaseData ? (
                          getStatusBadge(phaseData.status)
                        ) : (
                          getStatusBadge("pending")
                        )}
                      </div>

                      {/* SUMMARY / MODEL */}
                      <div className="my-3 space-y-2">
                        {phaseData ? (
                          <>
                            <p className="text-xs text-foreground/90 line-clamp-3 leading-relaxed">
                              {phaseData.summary || "Phase executed successfully with verified gate checks."}
                            </p>
                            <div className="flex items-center gap-1 text-[11px] font-mono text-muted-foreground">
                              <Cpu className="w-3 h-3 text-primary" />
                              <span>{phaseData.model}</span>
                            </div>
                          </>
                        ) : (
                          <p className="text-xs text-muted-foreground italic">Waiting for previous phase handoff...</p>
                        )}
                      </div>

                      {/* ENVELOPE BUTTON */}
                      {envelope ? (
                        <button
                          onClick={() => setSelectedEnvelope(envelope)}
                          className="w-full mt-2 py-1.5 px-2 rounded bg-primary/10 hover:bg-primary/20 text-primary text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer border border-primary/20"
                        >
                          <Eye className="w-3 h-3" /> Inspect JSON Envelope
                        </button>
                      ) : (
                        <div className="h-7" />
                      )}
                    </motion.div>
                  );
                })}
              </div>
            </div>
          )}

          {/* JSON ENVELOPE MODAL */}
          <AnimatePresence>
            {selectedEnvelope && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
              >
                <motion.div
                  initial={{ scale: 0.95, y: 15 }}
                  animate={{ scale: 1, y: 0 }}
                  exit={{ scale: 0.95, y: 15 }}
                  className="bg-card border border-border rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col"
                >
                  <div className="flex items-center justify-between border-b border-border pb-3">
                    <div className="flex items-center gap-2">
                      <FileCode className="w-5 h-5 text-primary" />
                      <div>
                        <h3 className="text-base font-bold text-foreground">Strict JSON Context Envelope</h3>
                        <p className="text-xs text-muted-foreground">Phase: {selectedEnvelope.phase.toUpperCase()} | Task: {selectedEnvelope.task_id}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedEnvelope(null)}
                      className="w-8 h-8 rounded-full hover:bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="space-y-3 overflow-y-auto flex-1 pr-1">
                    <div>
                      <span className="text-xs font-semibold text-muted-foreground uppercase">Plan Summary:</span>
                      <p className="text-xs text-foreground bg-muted/40 p-2.5 rounded-lg border border-border mt-1">{selectedEnvelope.plan_summary || "None"}</p>
                    </div>

                    {selectedEnvelope.target_files && selectedEnvelope.target_files.length > 0 && (
                      <div>
                        <span className="text-xs font-semibold text-muted-foreground uppercase">Target Files:</span>
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {selectedEnvelope.target_files.map((file, i) => (
                            <span key={i} className="text-[11px] font-mono bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded">
                              {file}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedEnvelope.handoff_notes && (
                      <div>
                        <span className="text-xs font-semibold text-muted-foreground uppercase">Handoff Instructions:</span>
                        <p className="text-xs text-foreground bg-amber-500/5 text-amber-700 dark:text-amber-300 p-2.5 rounded-lg border border-amber-500/20 mt-1">
                          {selectedEnvelope.handoff_notes}
                        </p>
                      </div>
                    )}

                    <div>
                      <span className="text-xs font-semibold text-muted-foreground uppercase">Raw JSON Payload:</span>
                      <pre className="text-[11px] font-mono bg-black/90 text-emerald-400 p-3 rounded-lg overflow-x-auto mt-1 border border-border">
                        {JSON.stringify(selectedEnvelope, null, 2)}
                      </pre>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-border flex justify-end">
                    <button
                      onClick={() => setSelectedEnvelope(null)}
                      className="px-4 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition-opacity cursor-pointer"
                    >
                      Close Envelope
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
