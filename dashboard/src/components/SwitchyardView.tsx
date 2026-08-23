"use client";

import React, { useState } from "react";
import { Cpu, DollarSign, ShieldCheck, Zap, Activity, RefreshCw } from "lucide-react";

export default function SwitchyardView() {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshData = () => {
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 800);
  };

  return (
    <div className="w-full h-full flex flex-col bg-background text-primary overflow-hidden select-none p-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase bg-primary/10 text-tertiary border border-border">
              NVIDIA SwitchYard Engine
            </span>
            <span className="text-[11px] font-mono text-secondary">
              Multi-Stage Cost Escalation Router
            </span>
          </div>
          <h1 className="text-xl font-bold text-primary tracking-tight">
            Token Expenditure & Routing Observability
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={refreshData}
            className="px-3.5 py-1.5 rounded-md text-[11px] font-mono font-bold tracking-wider uppercase bg-card border border-border hover:bg-neutral text-secondary hover:text-primary transition-all flex items-center gap-2 cursor-pointer shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
            <span>Sync Telemetry</span>
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-secondary mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider font-bold">Cumulative Savings</span>
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400">$1,428.50</div>
          <p className="text-[9px] font-mono text-secondary mt-1">Saved via P330 Local-First Routing</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-secondary mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider font-bold">Tier 0 (Local GPU)</span>
            <Cpu className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-blue-400">74.2%</div>
          <p className="text-[9px] font-mono text-secondary mt-1">UI-TARS 2B & Ollama local passes</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-secondary mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider font-bold">Tier 1 (Fast Turbo)</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400">21.5%</div>
          <p className="text-[9px] font-mono text-secondary mt-1">Gemini Flash low-latency utility</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-secondary mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider font-bold">Tier 2 (Architect Cloud)</span>
            <ShieldCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-purple-400">4.3%</div>
          <p className="text-[9px] font-mono text-secondary mt-1">System 2 high-level consensus audits</p>
        </div>
      </div>

      {/* Escalation Hierarchy Architecture Flow */}
      <div className="flex-1 bg-card border border-border rounded-xl p-5 flex flex-col justify-between shadow-sm overflow-y-auto">
        <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-secondary mb-4">
          Active Cost Escalation Hierarchy (Switchyard Protocol)
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-500/5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="px-2 py-0.5 rounded text-[8px] font-mono font-bold bg-blue-500/20 text-blue-400">
                  TIER 0 • LOCAL-FIRST
                </span>
                <span className="text-[9px] font-mono text-emerald-400 font-bold">$0.00 / Token</span>
              </div>
              <h4 className="text-sm font-bold text-primary mb-1">UI-TARS 2B & FastMCP</h4>
              <p className="text-[10px] text-secondary leading-relaxed">
                Handles GUI automation, DOM interactions, basic queries, and high-frequency scraping on P330 Nvidia hardware.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-border/50 text-[9px] font-mono text-secondary flex justify-between">
              <span>Latency: ~80ms</span>
              <span className="text-emerald-400">Active Node</span>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="px-2 py-0.5 rounded text-[8px] font-mono font-bold bg-amber-500/20 text-amber-400">
                  TIER 1 • ESCALATION
                </span>
                <span className="text-[9px] font-mono text-amber-400 font-bold">$0.075 / 1M Tokens</span>
              </div>
              <h4 className="text-sm font-bold text-primary mb-1">Gemini 2.0 Flash</h4>
              <p className="text-[10px] text-secondary leading-relaxed">
                Invoked when Tier 0 confidence is below 80% or when complex multi-document synthesis is needed.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-border/50 text-[9px] font-mono text-secondary flex justify-between">
              <span>Latency: ~400ms</span>
              <span className="text-amber-400">On-Demand</span>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-purple-500/30 bg-purple-500/5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="px-2 py-0.5 rounded text-[8px] font-mono font-bold bg-purple-500/20 text-purple-400">
                  TIER 2 • ARCHITECT CONSENSUS
                </span>
                <span className="text-[9px] font-mono text-purple-400 font-bold">$3.00 / 1M Tokens</span>
              </div>
              <h4 className="text-sm font-bold text-primary mb-1">Claude 3.7 / Gemini Pro</h4>
              <p className="text-[10px] text-secondary leading-relaxed">
                Reserved strictly for System 2 architectural audits, multi-repo refactoring, and security boundary reviews.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-border/50 text-[9px] font-mono text-secondary flex justify-between">
              <span>Latency: ~1.8s</span>
              <span className="text-purple-400">Gated Approval</span>
            </div>
          </div>
        </div>

        <div className="mt-4 p-3 rounded-lg bg-background border border-border flex items-center justify-between text-[10px] font-mono">
          <div className="flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-secondary">Switchyard Routing Policy:</span>
            <span className="text-primary font-bold">Local-First Heuristic Active (Max Tier 0 Allocation)</span>
          </div>
          <span className="text-emerald-400 font-bold">100% Operational</span>
        </div>
      </div>
    </div>
  );
}
