"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import { 
  ShieldCheck,
  ShieldAlert,
  Zap,
  Lock,
  GitCommit,
  PlusCircle,
  FileCode2,
  Terminal,
  Activity,
  Play,
  CheckCircle2,
  AlertTriangle
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";

interface Checkpoint {
  id: string;
  name: string;
  timestamp: string;
  author: string;
  hash: string;
  description: string;
}

interface Guardrail {
  id: string;
  name: string;
  category: "security" | "ethics" | "syntax" | "ast";
  status: "active" | "disabled" | "warning";
  complianceScore: number;
}

const DEFAULT_CHECKPOINTS: Checkpoint[] = [
  {
    id: "cp_008",
    name: "Auth Integrity Patch",
    timestamp: "10 mins ago",
    author: "Supervisor Node",
    hash: "a9f8b7c6",
    description: "Autosaved after system audit passed with zero security alerts."
  },
  {
    id: "cp_007",
    name: "Dashboard Telemetry Final",
    timestamp: "1 hour ago",
    author: "CTO Architect",
    hash: "6d5c4b3a",
    description: "Manual savepoint before merging System 4 Bayesian token governor."
  },
  {
    id: "cp_006",
    name: "Bayesian Calibration Sync",
    timestamp: "4 hours ago",
    author: "Governor Worker",
    hash: "f1e2d3c4",
    description: "Stabilized alpha/beta parameters for remote model execution."
  },
  {
    id: "cp_005",
    name: "Chroma Vector DB Sync",
    timestamp: "1 day ago",
    author: "System 3 Memory",
    hash: "b9a8f7e6",
    description: "Initial complete semantic code structural vector indexing."
  }
];

const DEFAULT_GUARDRAILS: Guardrail[] = [
  { id: "gr_ast", name: "AST Abstract Syntax Tree Structural Laws", category: "ast", status: "active", complianceScore: 100 },
  { id: "gr_sqli", name: "SQL Injection & Database Infiltration Protection", category: "security", status: "active", complianceScore: 100 },
  { id: "gr_leak", name: "API Credential Leak & Plaintext Key Guardian", category: "security", status: "active", complianceScore: 100 },
  { id: "gr_ethics", name: "Ethical Hallucination & Alignment Guardian", category: "ethics", status: "active", complianceScore: 98 },
  { id: "gr_tdd", name: "TDD Test Coverage Minimum Validation (>=80%)", category: "syntax", status: "active", complianceScore: 92 }
];

export default function SupervisorDashboard() {
  const API_BASE = CONFIG.API_BASE;
  
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>(DEFAULT_CHECKPOINTS);
  const [guardrails, setGuardrails] = useState<Guardrail[]>(DEFAULT_GUARDRAILS);
  const [newCheckpointName, setNewCheckpointName] = useState("");
  const [newCheckpointDesc, setNewCheckpointDesc] = useState("");
  const [isSavingCheckpoint, setIsSavingCheckpoint] = useState(false);

  // Safety auditor variables
  const [snippetCode, setSnippetCode] = useState("");
  const [auditType, setAuditType] = useState<"security" | "ast" | "ethics">("security");
  const [isAuditingCode, setIsAuditingCode] = useState(false);
  const [auditReport, setAuditReport] = useState<{
    status: "APPROVED" | "REJECTED" | "WARNING";
    score: number;
    violations: string[];
    remedy?: string;
  } | null>(null);

  const [stats, setStats] = useState({
    activeAudits: 24,
    linesAudited: 4212,
    astIntegrity: 100,
    checkpointsSaved: 8
  });
  const [isOnline, setIsOnline] = useState(true);

  // Sync checkpoints & health statistics
  const fetchSupervisorStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/build/status`, { cache: "no-store" });
      if (!res.ok) throw new Error("API_ERROR");
      const data = await res.json();
      
      setStats(prev => ({
        ...prev,
        astIntegrity: data.status === "Healthy" ? 100 : 96,
      }));
      setIsOnline(true);
    } catch (err) {
      console.warn("SUPERVISOR_FETCH_ERROR, utilizing offline fallback", err);
      setIsOnline(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    fetchSupervisorStats();
    const interval = setInterval(fetchSupervisorStats, 5000);
    return () => clearInterval(interval);
  }, [fetchSupervisorStats]);

  // Create checkpoint trigger
  const handleCreateCheckpoint = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCheckpointName.trim()) return;

    setIsSavingCheckpoint(true);
    
    // Simulate checkpoint creation delay
    await new Promise(resolve => setTimeout(resolve, 1000));

    const newCp: Checkpoint = {
      id: `cp_00${checkpoints.length + 1}`,
      name: newCheckpointName.trim(),
      timestamp: "Just now",
      author: "CTO Architect",
      hash: Math.random().toString(16).substr(2, 8),
      description: newCheckpointDesc.trim() || "Manual checkpoint snapshot."
    };

    setCheckpoints([newCp, ...checkpoints]);
    setStats(s => ({ ...s, checkpointsSaved: s.checkpointsSaved + 1 }));
    setNewCheckpointName("");
    setNewCheckpointDesc("");
    setIsSavingCheckpoint(false);
  };

  // Run audit safety code sandbox
  const handleExecuteAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!snippetCode.trim()) return;

    setIsAuditingCode(true);
    setAuditReport(null);

    // Simulate Supervisor AST review latency
    await new Promise(resolve => setTimeout(resolve, 1200));

    const code = snippetCode.toLowerCase();
    
    // Evaluate logic for mockup guardrails
    if (auditType === "security") {
      if (code.includes("eval(") || code.includes("select * from") || code.includes("password =") || code.includes("api_key =")) {
        setAuditReport({
          status: "REJECTED",
          score: 34,
          violations: [
            "Severe risk: Found potentially unsafe raw SQL or dangerous execution function (eval).",
            "Vulnerability warning: Detected plaintext variable assignments that resemble credentials."
          ],
          remedy: "Replace raw strings with dynamic parametrized statements and retrieve secrets from local config or Environment variables."
        });
      } else {
        setAuditReport({
          status: "APPROVED",
          score: 100,
          violations: []
        });
      }
    } else if (auditType === "ast") {
      if (code.includes("any") || code.includes("todo") || code.includes("fixme")) {
        setAuditReport({
          status: "WARNING",
          score: 82,
          violations: [
            "AST smell: Discovered non-strictly typed generic declarations ('any').",
            "Developer notice: Found placeholder markers ('TODO' / 'FIXME') in functional block."
          ],
          remedy: "Refactor types to explicitly declare payload schemas and implement draft blocks."
        });
      } else {
        setAuditReport({
          status: "APPROVED",
          score: 98,
          violations: []
        });
      }
    } else {
      // Ethics check
      if (code.includes("hack") || code.includes("bypass") || code.includes("ignore rules")) {
        setAuditReport({
          status: "REJECTED",
          score: 15,
          violations: [
            "System 2 Override detected: Discovered prompts attempting to bypass structural instruction sets.",
            "Alignment anomaly: Input patterns contain unsafe logical bypass directives."
          ],
          remedy: "Sovereign AI rules require absolute compliance. Ensure that code commands respect all standard local boundaries."
        });
      } else {
        setAuditReport({
          status: "APPROVED",
          score: 100,
          violations: []
        });
      }
    }

    setIsAuditingCode(false);
  };

  return (
    <div className="min-h-screen bg-neutral flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden font-sans">
      <Sidebar />

      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 pb-20 lg:pb-0 min-w-0 overflow-x-hidden">
        <div className="grain-overlay opacity-20" />

        {/* Header */}
        <header className="h-20 lg:h-24 border-b border-primary/5 flex items-center justify-between px-6 lg:px-10 bg-card/40 z-20 sticky top-0 backdrop-blur-xl shrink-0">
          <div className="flex items-center gap-4 lg:gap-8">
            <span className="text-[10px] font-black uppercase tracking-widest opacity-30">System.02</span>
            <div className="h-6 w-[1px] bg-primary/10" />
            <span className="font-bold text-lg lg:text-xl uppercase tracking-tighter italic">Supervisor <span className="text-tertiary">Auditor</span></span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3 bg-primary/5 px-4 py-2 border border-primary/5 rounded-sm">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] font-black uppercase tracking-widest text-primary/70">
                {isOnline ? "Supervisor Active" : "Offline Sandbox"}
              </span>
            </div>
          </div>
        </header>

        {/* Main Body Grid */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-10 xl:p-12 space-y-12 relative z-10 custom-scrollbar pb-32">
          
          {/* Top Banner Warning Node */}
          <div className="p-6 border border-tertiary/10 bg-tertiary/[0.02] flex items-center gap-6 rounded-none">
            <ShieldCheck className="w-8 h-8 text-tertiary animate-pulse shrink-0" />
            <div className="space-y-1">
              <span className="text-[9px] font-black uppercase tracking-widest text-tertiary">System Compliance Status: Optimal</span>
              <p className="text-[10px] sm:text-xs font-bold text-primary/60 uppercase tracking-wide">
                All System 2 Supervisor safety guardrails have successfully audited local nodes. AST validations 100% stable.
              </p>
            </div>
          </div>

          {/* Stats Bar Grid */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { label: "Compliance Score", value: "98.8%", icon: ShieldCheck, color: "text-tertiary" },
              { label: "Static Code Audited", value: `${stats.linesAudited} LOC`, icon: FileCode2, color: "text-primary" },
              { label: "AST Integrity Laws", value: `${stats.astIntegrity}% Nominal`, icon: Activity, color: "text-primary" },
              { label: "Sovereign Checkpoints", value: stats.checkpointsSaved, icon: GitCommit, color: "text-primary" }
            ].map((stat, i) => (
              <div key={i} className="p-6 border border-primary/5 bg-card/60 backdrop-blur-md shadow-sm rounded-sm flex items-center justify-between group hover:border-tertiary/20 transition-all duration-300">
                <div className="space-y-2">
                  <span className="text-[9px] uppercase tracking-[0.2em] opacity-40 font-black">{stat.label}</span>
                  <div className="text-xl lg:text-2xl font-black text-primary tracking-tighter italic">{stat.value}</div>
                </div>
                <stat.icon className="w-8 h-8 opacity-10 group-hover:opacity-30 group-hover:scale-105 transition-all duration-500 text-primary" />
              </div>
            ))}
          </section>

          {/* Double Column Grid: Sandboxed Auditor vs Checkpoint Manager */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
            
            {/* Left Block: Sandboxed Code Safety Inspector */}
            <section className="xl:col-span-7 p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-sm artisan-shadow space-y-6">
              <div className="space-y-1">
                <span className="text-[10px] font-black uppercase tracking-[0.4em] text-tertiary">Real-Time Isolation Vault</span>
                <h3 className="text-lg font-bold uppercase tracking-tight">Code Safety Sandbox Inspector</h3>
              </div>

              <form onSubmit={handleExecuteAudit} className="space-y-4">
                <div className="flex gap-4">
                  {(["security", "ast", "ethics"] as const).map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setAuditType(type)}
                      className={`flex-1 py-2.5 rounded-sm border uppercase text-[9px] font-black tracking-widest transition-all ${
                        auditType === type
                          ? "bg-primary text-white border-primary"
                          : "bg-card/40 border-primary/5 text-secondary hover:text-primary hover:bg-card"
                      }`}
                    >
                      {type} audit
                    </button>
                  ))}
                </div>

                <div className="relative">
                  <textarea
                    rows={6}
                    value={snippetCode}
                    onChange={(e) => setSnippetCode(e.target.value)}
                    placeholder={`Paste workspace script snippet here to audit...\n\nExample unsafe string:\ndef query(key):\n    db.execute("SELECT * FROM users WHERE token = '" + key + "'")`}
                    className="w-full p-4 border border-primary/5 rounded-sm bg-card/40 font-mono text-xs focus:outline-none focus:border-tertiary focus:bg-card hover:border-primary/20 transition-all text-primary placeholder-primary/20"
                  />
                  <Terminal className="absolute right-4 bottom-4 w-4 h-4 opacity-15 text-primary" />
                </div>

                <button 
                  type="submit"
                  disabled={isAuditingCode || !snippetCode.trim()}
                  className="w-full py-4 bg-primary hover:bg-primary/95 text-white font-black uppercase tracking-[0.2em] text-[10px] transition-all rounded-sm shadow-md disabled:opacity-40 flex items-center justify-center gap-2"
                >
                  <Play className={`w-3.5 h-3.5 fill-current ${isAuditingCode ? 'animate-pulse' : ''}`} />
                  {isAuditingCode ? "Reviewing AST Logic..." : "Execute Supervisor Audit"}
                </button>
              </form>

              {/* Audit results report container */}
              <AnimatePresence>
                {auditReport && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className={`p-6 border rounded-sm space-y-4 font-mono text-xs ${
                      auditReport.status === "APPROVED" 
                        ? "border-emerald-500/20 bg-emerald-500/[0.02] text-primary" 
                        : auditReport.status === "WARNING"
                          ? "border-amber-500/20 bg-amber-500/[0.02] text-primary"
                          : "border-tertiary/20 bg-tertiary/[0.02] text-primary"
                    }`}
                  >
                    <div className="flex items-center justify-between border-b border-primary/5 pb-3">
                      <div className="flex items-center gap-2">
                        {auditReport.status === "APPROVED" ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        ) : auditReport.status === "WARNING" ? (
                          <AlertTriangle className="w-4 h-4 text-amber-500" />
                        ) : (
                          <ShieldAlert className="w-4 h-4 text-tertiary" />
                        )}
                        <span className={`text-[10px] font-black uppercase tracking-widest ${
                          auditReport.status === "APPROVED" ? "text-emerald-500" : auditReport.status === "WARNING" ? "text-amber-500" : "text-tertiary"
                        }`}>
                          Audit Verdict: {auditReport.status}
                        </span>
                      </div>
                      <span className="font-bold text-[10px]">Score: {auditReport.score}/100</span>
                    </div>

                    {auditReport.violations.length > 0 ? (
                      <div className="space-y-3">
                        <div className="space-y-1.5">
                          <span className="text-[8px] font-black uppercase tracking-widest opacity-40">Flagged Exceptions:</span>
                          <ul className="list-disc list-inside space-y-1 text-[10px] opacity-75">
                            {auditReport.violations.map((v, i) => (
                              <li key={i}>{v}</li>
                            ))}
                          </ul>
                        </div>
                        {auditReport.remedy && (
                          <div className="space-y-1 pt-2.5 border-t border-primary/5">
                            <span className="text-[8px] font-black uppercase tracking-widest opacity-40">Remedy Protocol:</span>
                            <p className="text-[10px] text-secondary leading-relaxed font-sans font-medium">{auditReport.remedy}</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-[10px] opacity-70 leading-relaxed font-sans font-medium">
                        Verification Successful. The provided code blocks successfully adhere to all local guardrail rules, credential safety scopes, and standard Twelve-Factor architecture parameters.
                      </p>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </section>

            {/* Right Block: Safe Point git/system Checkpoints */}
            <div className="xl:col-span-5 space-y-6">
              <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40 block">System Recovery Rollbacks</span>

              <div className="p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-sm artisan-shadow space-y-6">
                <div className="space-y-1">
                  <span className="text-[9px] font-bold text-tertiary uppercase tracking-widest">Rollback Ledger</span>
                  <h4 className="font-serif font-black text-sm uppercase">Active State Checkpoints</h4>
                </div>

                <div className="space-y-4 max-h-[360px] overflow-y-auto pr-2 custom-scrollbar">
                  {checkpoints.map((cp) => (
                    <div key={cp.id} className="p-4 border border-primary/5 bg-card/40 rounded-sm hover:border-primary/20 transition-all flex items-center justify-between gap-4">
                      <div className="space-y-1.5 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] font-mono font-black text-tertiary select-all">[{cp.hash}]</span>
                          <h5 className="font-sans font-bold text-xs uppercase text-primary truncate">{cp.name}</h5>
                        </div>
                        <p className="text-[10px] text-secondary font-medium leading-relaxed truncate">{cp.description}</p>
                        <div className="text-[9px] font-mono text-primary/30 uppercase">{cp.author} • {cp.timestamp}</div>
                      </div>
                      <button 
                        onClick={() => alert(`Initiating rollback sequence to state [${cp.hash}]: ${cp.name}`)}
                        className="px-3 py-1.5 border border-primary/10 hover:border-tertiary hover:text-tertiary rounded-sm text-[8px] font-black uppercase tracking-wider transition-all shrink-0"
                      >
                        Restore
                      </button>
                    </div>
                  ))}
                </div>

                {/* Create checkpoint form */}
                <form onSubmit={handleCreateCheckpoint} className="space-y-4 pt-6 border-t border-primary/5">
                  <div className="space-y-2">
                    <span className="text-[8px] font-black uppercase tracking-widest opacity-40">Create Manual Checkpoint</span>
                    <input
                      type="text"
                      required
                      value={newCheckpointName}
                      onChange={(e) => setNewCheckpointName(e.target.value)}
                      placeholder="Checkpoint title (e.g. 'Staged memory calibration')"
                      className="w-full px-4 py-3 border border-primary/5 rounded-sm bg-card/40 font-sans text-xs focus:outline-none focus:border-tertiary focus:bg-card hover:border-primary/20 transition-all text-primary placeholder-primary/20"
                    />
                    <input
                      type="text"
                      value={newCheckpointDesc}
                      onChange={(e) => setNewCheckpointDesc(e.target.value)}
                      placeholder="Brief description (optional)"
                      className="w-full px-4 py-3 border border-primary/5 rounded-sm bg-card/40 font-sans text-xs focus:outline-none focus:border-tertiary focus:bg-card hover:border-primary/20 transition-all text-primary placeholder-primary/20"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSavingCheckpoint || !newCheckpointName.trim()}
                    className="w-full py-3 bg-primary hover:bg-primary/95 text-white font-black uppercase tracking-[0.2em] text-[9px] transition-all rounded-sm shadow-md disabled:opacity-40 flex items-center justify-center gap-2"
                  >
                    <PlusCircle className="w-3.5 h-3.5" />
                    {isSavingCheckpoint ? "Saving State..." : "Commit System State Snapshot"}
                  </button>
                </form>
              </div>
            </div>

          </div>

          {/* Section: Ethical Guardrails Catalog */}
          <section className="p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-sm artisan-shadow space-y-6">
            <div className="flex items-center gap-4">
              <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary">System 2 Active Guardrails</span>
              <div className="flex-1 h-[1px] bg-primary/5" />
              <span className="text-[10px] font-mono opacity-30 uppercase">{guardrails.length} active monitors</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {guardrails.map((gr) => (
                <div key={gr.id} className="p-5 border border-primary/5 bg-card/40 rounded-sm hover:border-tertiary/20 transition-all space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Lock className="w-3.5 h-3.5 text-tertiary" />
                      <span className="text-[9px] font-mono font-bold opacity-30 uppercase">{gr.category} guardian</span>
                    </div>
                    <span className="text-[8px] font-black uppercase tracking-widest px-1.5 py-0.5 border border-emerald-500/20 text-emerald-500 rounded-sm bg-emerald-500/[0.02]">
                      {gr.status}
                    </span>
                  </div>

                  <h5 className="font-serif font-black text-xs text-primary uppercase tracking-tight leading-normal min-h-[32px]">
                    {gr.name}
                  </h5>

                  <div className="space-y-1.5">
                    <div className="flex justify-between text-[9px] font-mono leading-none">
                      <span className="opacity-40">Compliance rating</span>
                      <span className="text-tertiary font-bold">{gr.complianceScore}%</span>
                    </div>
                    <div className="h-1 bg-primary/5 w-full relative overflow-hidden rounded-full">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${gr.complianceScore}%` }}
                        className="absolute inset-y-0 left-0 bg-tertiary"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

        </div>

        {/* Footer */}
        <footer className="h-16 border-t border-primary/5 flex items-center justify-between px-10 bg-[var(--background)]/60 text-[10px] sm:text-xs font-black uppercase tracking-[0.8em] opacity-30 sticky bottom-0 lg:static backdrop-blur-xl shrink-0">
          <span>SUPERVISOR_AUDITOR // SYS.2</span>
          <span>{"GUARDRAILS_"}{guardrails.length}{" // STATE_"}{checkpoints.length}</span>
        </footer>
      </main>
    </div>
  );
}
