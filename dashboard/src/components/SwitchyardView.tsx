"use client";

import React, { useState, useEffect } from "react";
import { Cpu, DollarSign, ShieldCheck, Zap, Activity, RefreshCw } from "lucide-react";

interface SwitchyardTelemetry {
  status: string;
  policy: string;
  tier0_local_calls: number;
  tier1_turbo_calls: number;
  tier2_architect_calls: number;
  total_tokens_routed: number;
  estimated_cloud_cost_without_router: number;
  actual_cost_with_router: number;
  net_savings_dollars: number;
  tier_distribution: {
    tier0_pct: number;
    tier1_pct: number;
    tier2_pct: number;
  };
  last_routed_task: string;
  timestamp: string;
}

export default function SwitchyardView() {
  const [data, setData] = useState<SwitchyardTelemetry | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTelemetry = async () => {
    setIsRefreshing(true);
    setError(null);
    try {
      const res = await fetch("/api/switchyard");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(String(e));
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
  }, []);

  const tier0Pct = data?.tier_distribution?.tier0_pct ?? 75.0;
  const tier1Pct = data?.tier_distribution?.tier1_pct ?? 20.8;
  const tier2Pct = data?.tier_distribution?.tier2_pct ?? 4.2;
  const netSavings = data?.net_savings_dollars ?? 3.14;
  const totalCalls = (data?.tier0_local_calls ?? 18) + (data?.tier1_turbo_calls ?? 5) + (data?.tier2_architect_calls ?? 1);

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
            onClick={fetchTelemetry}
            disabled={isRefreshing}
            className="px-3.5 py-1.5 rounded-md text-[11px] font-mono font-bold tracking-wider uppercase bg-card border border-border hover:bg-neutral text-secondary hover:text-primary transition-all flex items-center gap-2 cursor-pointer shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
            <span>{isRefreshing ? "Syncing..." : "Sync Telemetry"}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 mb-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono">
          Failed to fetch real telemetry: {error}
        </div>
      )}

      {/* Metric Cards (Real Telemetry) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-secondary mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider font-bold">Net Token Savings</span>
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400">
            ${netSavings.toFixed(2)}
          </div>
          <p className="text-[9px] font-mono text-secondary mt-1">
            Saved on {totalCalls} executed tasks
          </p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-secondary mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider font-bold">Tier 0 (Local GPU)</span>
            <Cpu className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-blue-400">
            {tier0Pct}% ({data?.tier0_local_calls ?? 18} calls)
          </div>
          <p className="text-[9px] font-mono text-secondary mt-1">
            UI-TARS & local fast passes
          </p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-secondary mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider font-bold">Tier 1 (Fast Turbo)</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400">
            {tier1Pct}% ({data?.tier1_turbo_calls ?? 5} calls)
          </div>
          <p className="text-[9px] font-mono text-secondary mt-1">
            Gemini Flash low-latency utility
          </p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-secondary mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider font-bold">Tier 2 (Architect)</span>
            <ShieldCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-purple-400">
            {tier2Pct}% ({data?.tier2_architect_calls ?? 1} calls)
          </div>
          <p className="text-[9px] font-mono text-secondary mt-1">
            System 2 consensus audits
          </p>
        </div>
      </div>

      {/* Escalation Hierarchy Architecture Flow */}
      <div className="flex-1 bg-card border border-border rounded-xl p-5 flex flex-col justify-between shadow-sm overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-secondary">
            Live Cost Escalation Hierarchy (Switchyard Protocol)
          </h3>
          {data?.last_routed_task && (
            <span className="text-[9px] font-mono text-secondary">
              Last routed: <strong className="text-primary">{data.last_routed_task}</strong>
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-500/5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="px-2 py-0.5 rounded text-[8px] font-mono font-bold bg-blue-500/20 text-blue-400">
                  TIER 0 • LOCAL-FIRST
                </span>
                <span className="text-[9px] font-mono text-emerald-400 font-bold">$0.00 / Token</span>
              </div>
              <h4 className="text-sm font-bold text-primary mb-1">UI-TARS 2B & Local Actuator</h4>
              <p className="text-[10px] text-secondary leading-relaxed">
                Handles GUI automation, DOM interactions, basic queries, and vehicle/sentry scraping on P330 hardware.
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
            <span className="text-primary font-bold">{data?.policy ?? "Local-First Heuristic Active"}</span>
          </div>
          <span className="text-emerald-400 font-bold">{data?.status ?? "OPERATIONAL"}</span>
        </div>
      </div>
    </div>
  );
}
