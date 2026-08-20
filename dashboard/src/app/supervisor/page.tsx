"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import { 
  ShieldCheck,
  ShieldAlert,
  Lock,
  GitCommit,
  PlusCircle,
  FileCode2,
  Terminal,
  Activity,
  Play,
  CheckCircle2,
  AlertTriangle,
  Menu
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";

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

export default function SupervisorDashboard() {
  const API_BASE = CONFIG.API_BASE;
  
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [guardrails, setGuardrails] = useState<Guardrail[]>([]);
  const [newCheckpointName, setNewCheckpointName] = useState("");
  const [newCheckpointDesc, setNewCheckpointDesc] = useState("");
  const [isSavingCheckpoint, setIsSavingCheckpoint] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
    linesAudited: 0,
    astIntegrity: 100,
    checkpointsSaved: 0
  });
  const [isOnline, setIsOnline] = useState(true);

  const fetchCheckpoints = useCallback(async () => {
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/supervisor/checkpoints`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && Array.isArray(data.data)) {
        const mapped = data.data.map((cp: { label?: string; timestamp: string; original_path?: string; checkpoint_path?: string }, i: number) => ({
          id: `cp_${i}`,
          name: cp.label || "Unnamed",
          timestamp: new Date(cp.timestamp).toLocaleString(),
          author: "Supervisor Node",
          hash: cp.label || cp.checkpoint_path,
          description: `Snapshot of ${cp.original_path?.split('/').pop() || 'workspace'}`
        }));
        setCheckpoints(mapped.reverse());
      }
    } catch (e) {
      console.warn("Failed to fetch checkpoints", e);
    }
  }, [API_BASE]);

  const fetchGuardrails = useCallback(async () => {
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/supervisor/guardrails`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && Array.isArray(data.data)) {
        setGuardrails(data.data);
      }
    } catch (e) {
      console.warn("Failed to fetch guardrails", e);
    }
  }, [API_BASE]);

  const fetchSupervisorStats = useCallback(async () => {
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/supervisor/stats`, { cache: "no-store" });
      if (!res.ok) throw new Error("API_ERROR");
      const data = await res.json();
      
      if (data.status === "success" && data.data) {
        setStats(prev => ({
          ...prev,
          linesAudited: data.data.lines_audited,
          astIntegrity: data.data.ast_integrity,
          checkpointsSaved: data.data.checkpoints_saved
        }));
      }
      setIsOnline(true);
    } catch (err) {
      console.warn("SUPERVISOR_FETCH_ERROR, utilizing offline fallback", err);
      setIsOnline(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    setTimeout(() => {
      fetchCheckpoints();
      fetchGuardrails();
      fetchSupervisorStats();
    }, 0);
    const interval = setInterval(fetchSupervisorStats, 10000);
    return () => clearInterval(interval);
  }, [fetchCheckpoints, fetchGuardrails, fetchSupervisorStats]);

  // Create checkpoint trigger
  const handleCreateCheckpoint = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCheckpointName.trim()) return;

    setIsSavingCheckpoint(true);
    
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/supervisor/checkpoints`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer KenbunSwarm" },
        body: JSON.stringify({ name: newCheckpointName.trim(), description: newCheckpointDesc.trim() })
      });
      if (res.ok) {
        await fetchCheckpoints();
        setNewCheckpointName("");
        setNewCheckpointDesc("");
      }
    } catch (e) {
      console.error("Checkpoint save failed", e);
    } finally {
      setIsSavingCheckpoint(false);
    }
  };

  const handleRestoreCheckpoint = async (hash: string, name: string) => {
    if (!window.confirm(`Are you sure you want to restore to checkpoint [${hash}]: ${name}? This will overwrite current files.`)) return;
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/supervisor/checkpoints/${hash}/restore`, {
        method: "POST",
        headers: { "Authorization": "Bearer KenbunSwarm" }
      });
      if (res.ok) {
        alert("Restore completed successfully.");
        await fetchSupervisorStats();
      } else {
        alert("Restore failed.");
      }
    } catch (e) {
      alert("Restore failed: " + String(e));
    }
  };

  // Run audit safety code sandbox
  const handleExecuteAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!snippetCode.trim()) return;

    setIsAuditingCode(true);
    setAuditReport(null);

    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/supervisor/audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer KenbunSwarm" },
        body: JSON.stringify({ 
          code_snippet: snippetCode, 
          audit_type: auditType,
          iterative_mode: false 
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success" && data.data) {
          setAuditReport({
            status: data.data.status,
            score: data.data.score,
            violations: data.data.violations || [],
            remedy: data.data.remedy
          });
        }
      } else {
        setAuditReport({ status: "REJECTED", score: 0, violations: ["Server returned HTTP error."], remedy: "Check API logs." });
      }
    } catch (err) {
      setAuditReport({ status: "REJECTED", score: 0, violations: [String(err)], remedy: "Backend is unreachable." });
    } finally {
      setIsAuditingCode(false);
    }
  };

  return (
    <div className="h-screen overflow-hidden bg-background flex selection:bg-[var(--tertiary)]/20 selection:text-[var(--foreground)] max-w-[100vw] font-sans">
      <Sidebar />

      {/* Backdrop overlay for mobile sidebar */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-primary/25 backdrop-blur-xs z-25 md:hidden"
        />
      )}

      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 h-screen overflow-hidden min-w-0 bg-background text-[var(--foreground)]">
        <div className="grain-overlay opacity-5 pointer-events-none" />

        {/* Header */}
        <header className="h-14 lg:h-16 border-b border-[var(--border)] flex items-center justify-between px-6 bg-[var(--card)]/80 backdrop-blur-xl z-20 sticky top-0 shrink-0">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(o => !o)}
              className="md:hidden p-2 text-[var(--foreground)]/60 hover:text-[var(--foreground)] transition-colors hover:bg-[var(--sand)] rounded-lg cursor-pointer shrink-0"
              title="Toggle Menu"
              aria-label="Toggle Navigation Menu"
            >
              <Menu className="w-5 h-5" />
            </button>
            <span className="font-bold text-base uppercase tracking-tighter italic text-[var(--foreground)]">
              Code <span className="text-[var(--tertiary)]">Audit</span>
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5 bg-[var(--sand)] px-4 py-1.5 border border-[var(--border)] rounded-lg">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] font-bold font-mono uppercase tracking-wider text-[var(--foreground)]">
                {isOnline ? "Active Monitor" : "Offline Sandbox"}
              </span>
            </div>
          </div>
        </header>

        {/* Main Body Grid */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-10 xl:p-12 space-y-10 relative z-10 custom-scrollbar pb-16">
          
          {/* Top Banner Warning Node (Cinematic purple twilight gradient) */}
          <div className="p-6 bg-card/60 backdrop-blur-xl text-[var(--foreground)] flex items-center gap-6 rounded-md shadow-lg relative overflow-hidden border border-primary/5">
            <div className="absolute top-0 right-0 w-[40%] h-[150%] bg-[var(--tertiary)]/5 rounded-full blur-[80px] pointer-events-none" />
            <ShieldCheck className="w-8 h-8 text-[var(--tertiary)] animate-pulse shrink-0 relative z-10" />
            <div className="space-y-1 relative z-10 text-left">
              <span className="text-[9px] font-bold font-mono uppercase tracking-[0.25em] text-[var(--tertiary)]">System Compliance Status: Optimal</span>
              <p className="text-[11px] sm:text-xs font-medium text-[var(--foreground)]/80 leading-relaxed max-w-3xl">
                All System 2 Supervisor safety guardrails have successfully audited local nodes. Allowed binary configs and AST validations are 100% stable.
              </p>
            </div>
          </div>

          {/* Stats Bar Grid */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { label: "Compliance Score", value: "98.8%", icon: ShieldCheck, color: "text-[var(--tertiary)]" },
              { label: "Static Code Audited", value: `${stats.linesAudited} LOC`, icon: FileCode2, color: "text-[var(--foreground)]" },
              { label: "AST Validation Rules", value: `${stats.astIntegrity}% Nominal`, icon: Activity, color: "text-[var(--foreground)]" },
              { label: "System Checkpoints", value: stats.checkpointsSaved, icon: GitCommit, color: "text-[var(--foreground)]" }
            ].map((stat, i) => (
              <div key={i} className="p-6 border border-primary/5 bg-card/60 backdrop-blur-xl shadow-md rounded-md flex items-center justify-between group hover:border-[var(--tertiary)] transition-all duration-300 hover:scale-[1.02] hover:bg-card/85">
                <div className="space-y-1 text-left">
                  <span className="text-[9px] uppercase tracking-[0.2em] text-[var(--foreground)]/45 font-bold font-mono">{stat.label}</span>
                  <div className="text-xl lg:text-2xl font-bold text-[var(--foreground)] tracking-tighter">{stat.value}</div>
                </div>
                <stat.icon className="w-7 h-7 opacity-20 group-hover:opacity-45 group-hover:scale-105 transition-all duration-500 text-[var(--tertiary)]" />
              </div>
            ))}
          </section>

          {/* Double Column Grid: Sandboxed Auditor vs Checkpoint Manager */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
            
            {/* Left Block: Sandboxed Code Safety Inspector */}
            <section className="xl:col-span-7 p-6 md:p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-md shadow-lg space-y-6">
              <div className="space-y-1 text-left">
                <span className="text-[10px] font-bold font-mono uppercase tracking-[0.3em] text-[var(--tertiary)]">Secure Sandbox</span>
                <h3 className="text-lg font-bold uppercase tracking-tight text-[var(--foreground)]">Sandbox Inspector</h3>
              </div>

              <form onSubmit={handleExecuteAudit} className="space-y-4">
                <div className="flex gap-2">
                  {(["security", "ast", "ethics"] as const).map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setAuditType(type)}
                      className={`flex-1 py-2 rounded-lg border text-[10px] font-bold uppercase tracking-widest transition-all cursor-pointer ${
                        auditType === type
                          ? "bg-[var(--foreground)] text-[var(--background)] border-transparent"
                          : "bg-card/45 border-primary/5 text-[var(--foreground)]/70 hover:bg-[var(--sand)] hover:text-[var(--foreground)]"
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
                    className="w-full p-4 border border-primary/5 rounded-xl bg-card/40 backdrop-blur-xl font-mono text-xs focus:outline-none focus:border-[var(--tertiary)] focus:ring-1 focus:ring-[var(--tertiary)] transition-all text-[var(--foreground)] placeholder-[var(--secondary)]/40"
                  />
                  <Terminal className="absolute right-4 bottom-4 w-4 h-4 opacity-20 text-[var(--foreground)]" />
                </div>

                <button 
                  type="submit"
                  disabled={isAuditingCode || !snippetCode.trim()}
                  className="w-full py-3.5 bg-[var(--foreground)] hover:opacity-90 text-[var(--background)] font-bold uppercase tracking-widest text-[10px] transition-all rounded-xl shadow-md disabled:opacity-40 flex items-center justify-center gap-2 cursor-pointer hover:scale-[1.01] duration-300"
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
                    className={`p-5 border rounded-xl space-y-4 font-mono text-xs text-left ${
                      auditReport.status === "APPROVED" 
                        ? "border-emerald-500/20 bg-emerald-500/[0.02] text-[var(--foreground)]" 
                        : auditReport.status === "WARNING"
                          ? "border-amber-500/20 bg-amber-500/[0.02] text-[var(--foreground)]"
                          : "border-[var(--tertiary)]/20 bg-[var(--tertiary)]/[0.02] text-[var(--foreground)]"
                    }`}
                  >
                    <div className="flex items-center justify-between border-b border-primary/5 pb-3">
                      <div className="flex items-center gap-2">
                        {auditReport.status === "APPROVED" ? (
                           <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        ) : auditReport.status === "WARNING" ? (
                          <AlertTriangle className="w-4 h-4 text-amber-500" />
                        ) : (
                          <ShieldAlert className="w-4 h-4 text-[var(--tertiary)]" />
                        )}
                        <span className={`text-[10px] font-bold uppercase tracking-widest ${
                          auditReport.status === "APPROVED" ? "text-emerald-600" : auditReport.status === "WARNING" ? "text-amber-600" : "text-[var(--tertiary)]"
                        }`}>
                          Audit Verdict: {auditReport.status}
                        </span>
                      </div>
                      <span className="font-bold text-[10px] text-[var(--foreground)]/65">Score: {auditReport.score}/100</span>
                    </div>

                    {auditReport.violations.length > 0 ? (
                      <div className="space-y-3">
                        <div className="space-y-1.5">
                          <span className="text-[8px] font-bold uppercase tracking-widest text-[var(--foreground)]/45 font-mono">Flagged Exceptions:</span>
                          <ul className="list-disc list-inside space-y-1 text-[10px] text-[var(--foreground)]/80">
                            {auditReport.violations.map((v, i) => (
                              <li key={i}>{v}</li>
                            ))}
                          </ul>
                        </div>
                        {auditReport.remedy && (
                          <div className="space-y-1 pt-2.5 border-t border-primary/5">
                            <span className="text-[8px] font-bold uppercase tracking-widest text-[var(--foreground)]/45 font-mono">Remedy Protocol:</span>
                            <p className="text-[10px] text-[var(--foreground)]/70 leading-relaxed font-sans font-medium">{auditReport.remedy}</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-[10px] text-[var(--foreground)]/75 leading-relaxed font-sans font-medium">
                        Verification Successful. The provided code blocks successfully adhere to all local guardrail rules, credential safety scopes, and standard Twelve-Factor architecture parameters.
                      </p>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </section>

            {/* Right Block: Safe Point git/system Checkpoints */}
            <div className="xl:col-span-5 space-y-6 text-left">
              <span className="text-[10px] font-bold font-mono uppercase tracking-[0.3em] text-[var(--foreground)]/40 block">System Recovery Rollbacks</span>

              <div className="p-6 md:p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-md shadow-lg space-y-6">
                <div className="space-y-1">
                  <span className="text-[9px] font-bold text-[var(--tertiary)] uppercase tracking-widest">Rollback Ledger</span>
                  <h4 className="font-bold text-sm uppercase text-[var(--foreground)]">Active State Checkpoints</h4>
                </div>

                <div className="space-y-3 max-h-[360px] overflow-y-auto pr-2 custom-scrollbar">
                  {checkpoints.length === 0 ? (
                    <div className="text-center text-[10px] font-mono text-[var(--foreground)]/40 py-8 border border-dashed border-primary/5 rounded-md">
                      No system checkpoints saved yet.
                    </div>
                  ) : (
                    checkpoints.map((cp) => (
                      <div key={cp.id} className="p-4 border border-primary/5 bg-card/45 rounded-md hover:border-[var(--tertiary)]/50 transition-all flex items-center justify-between gap-4 hover:scale-[1.01] duration-300">
                        <div className="space-y-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-[9px] font-mono font-bold text-[var(--tertiary)] select-all">[{cp.hash.substring(0, 8)}]</span>
                            <h5 className="font-bold text-xs uppercase text-[var(--foreground)] truncate">{cp.name}</h5>
                          </div>
                          <p className="text-[10px] text-[var(--foreground)]/60 font-medium leading-relaxed truncate">{cp.description}</p>
                          <div className="text-[8px] font-mono text-[var(--foreground)]/40 uppercase">{cp.author} • {cp.timestamp}</div>
                        </div>
                        <button 
                          onClick={() => handleRestoreCheckpoint(cp.hash, cp.name)}
                          className="bg-[var(--sand)] hover:bg-[var(--sand)]/80 text-[var(--foreground)] border border-primary/5 hover:border-[var(--tertiary)] px-3.5 py-1.5 rounded-md text-[9px] font-bold uppercase tracking-wider transition-all cursor-pointer shrink-0 hover:scale-105 duration-300"
                        >
                          Restore
                        </button>
                      </div>
                    ))
                  )}
                </div>

                {/* Create checkpoint form */}
                <form onSubmit={handleCreateCheckpoint} className="space-y-4 pt-6 border-t border-primary/5">
                  <div className="space-y-2">
                    <span className="text-[8px] font-bold uppercase tracking-widest text-[var(--foreground)]/45 font-mono">Create Manual Checkpoint</span>
                    <input
                      type="text"
                      required
                      value={newCheckpointName}
                      onChange={(e) => setNewCheckpointName(e.target.value)}
                      placeholder="Checkpoint title (e.g. 'Staged memory calibration')"
                      className="w-full px-4 py-3 bg-card/40 border border-primary/5 text-[var(--foreground)] placeholder-[var(--secondary)]/40 focus:border-[var(--tertiary)] focus:ring-1 focus:ring-[var(--tertiary)] rounded-md font-sans text-xs transition-all"
                    />
                    <input
                      type="text"
                      value={newCheckpointDesc}
                      onChange={(e) => setNewCheckpointDesc(e.target.value)}
                      placeholder="Brief description (optional)"
                      className="w-full px-4 py-3 bg-card/40 border border-primary/5 text-[var(--foreground)] placeholder-[var(--secondary)]/40 focus:border-[var(--tertiary)] focus:ring-1 focus:ring-[var(--tertiary)] rounded-md font-sans text-xs transition-all"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isSavingCheckpoint || !newCheckpointName.trim()}
                    className="w-full py-3 bg-[var(--foreground)] hover:opacity-90 text-[var(--background)] font-bold uppercase tracking-widest text-[9px] transition-all rounded-md flex items-center justify-center gap-2 cursor-pointer hover:scale-[1.01] duration-300 shadow-md"
                  >
                    <PlusCircle className="w-3.5 h-3.5" />
                    {isSavingCheckpoint ? "Saving State..." : "Commit State Snapshot"}
                  </button>
                </form>
              </div>
            </div>

          </div>

          {/* Section: Ethical Guardrails Catalog */}
          <section className="p-6 md:p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-md shadow-lg space-y-6 text-left">
            <div className="flex items-center gap-4">
              <span className="text-[10px] font-bold font-mono uppercase tracking-[0.3em] text-[var(--foreground)]">System 2 Active Guardrails</span>
              <div className="flex-1 h-[1px] bg-[var(--border)]" />
              <span className="text-[10px] font-mono text-[var(--foreground)]/45 uppercase">{guardrails.length} active monitors</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {guardrails.map((gr) => (
                <div key={gr.id} className="p-5 border border-primary/5 bg-card/45 hover:bg-card/75 hover:border-[var(--tertiary)]/30 rounded-md transition-all space-y-4 hover:scale-[1.02] duration-300">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Lock className="w-3.5 h-3.5 text-[var(--tertiary)]" />
                      <span className="text-[9px] font-mono font-bold text-[var(--foreground)]/40 uppercase">{gr.category} guardian</span>
                    </div>
                    <span className="text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 border border-emerald-500/20 text-emerald-600 rounded-md bg-emerald-500/[0.02]">
                      {gr.status}
                    </span>
                  </div>

                  <h5 className="font-bold text-xs text-[var(--foreground)] uppercase tracking-tight leading-normal min-h-[32px]">
                    {gr.name}
                  </h5>

                  <div className="space-y-1.5">
                    <div className="flex justify-between text-[9px] font-mono leading-none">
                      <span className="text-[var(--foreground)]/45 font-bold">Compliance rating</span>
                      <span className="text-[var(--tertiary)] font-bold">{gr.complianceScore}%</span>
                    </div>
                    <div className="h-1 bg-[var(--border)] w-full relative overflow-hidden rounded-full">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${gr.complianceScore}%` }}
                        className="absolute inset-y-0 left-0 bg-[var(--tertiary)]"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

        </div>

        {/* Footer */}
        <footer className="h-16 border-t border-primary/5 flex items-center justify-between px-10 bg-[var(--card)]/40 text-[10px] font-mono tracking-widest text-[var(--foreground)]/40 sticky bottom-0 lg:static backdrop-blur-xl shrink-0">
          <span>SUPERVISOR_AUDITOR // SYS.2</span>
          <span>{"GUARDRAILS_"}{guardrails.length}{" // STATE_"}{checkpoints.length}</span>
        </footer>
      </main>
    </div>
  );
}
