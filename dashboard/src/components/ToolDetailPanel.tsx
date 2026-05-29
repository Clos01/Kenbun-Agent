import React, { memo, useState } from "react";
import MetricItem from "./MetricItem";
import { AccuracyGauge } from "./Visuals";
import { ToolStat, useToolMetrics, getToolDescription } from "@/lib/tools";
import { motion, AnimatePresence } from "framer-motion";

interface ToolDetailPanelProps {
  selectedTool: ToolStat;
}

interface MetricExplainer {
  title: string;
  definition: string;
  behavior: string;
  impact: string;
}

const METRIC_EXPLAINERS: Record<string, MetricExplainer> = {
  tool: {
    title: "Tool Identifier",
    definition: "The unique namespace of the active neural capability node in the Kenbun swarm.",
    behavior: "Each tool corresponds to an autonomous background daemon, safety linter, vector database synchronizer, or cognitive strategy router.",
    impact: "Allocates precise boundaries so that agents can route tasks efficiently without overloading the context window."
  },
  alpha: {
    title: "α (Success Parameter)",
    definition: "The Bayesian pseudo-count tracking successful outcomes and validated completions.",
    behavior: "This parameter increments by +1 every time the supervisor approves a commit, a code review completes with 0 warnings, or unit tests pass successfully.",
    impact: "Forms the mathematical numerator in Thompson Sampling, directly boosting the likelihood that the governor routes future tasks to this node."
  },
  beta: {
    title: "β (Failure Parameter)",
    definition: "The Bayesian pseudo-count tracking failed trials, timeouts, or linter regressions.",
    behavior: "Increments when System 2 supervisor audits detect a security flaw (such as SQL injection risks), a test suite fails, or compilation breaks during trial runs.",
    impact: "Increases the variance and down-weights the selection probability, ensuring the agent avoids routing high-risk operations to unstable components."
  },
  entropy: {
    title: "System Exploration Entropy",
    definition: "A mathematical measurement of uncertainty and exploratory randomness in the Thompson selection window.",
    behavior: "High entropy indicates that the governor is actively exploring alternative neural pathways to find more efficient models. Low entropy (negative values) means selection has stabilized.",
    impact: "Ensures the system balances exploitation (using proven high-accuracy routes) with exploration (testing newer models) to prevent falling into local minima."
  },
  momentum: {
    title: "Velocity Momentum",
    definition: "The short-term moving average delta of node accuracy and execution throughput speed.",
    behavior: "Measures the rate of change over the last 10 execution windows, calculating whether accuracy gains are accelerating or decelerating.",
    impact: "Provides early warnings. Flat or dropping momentum alerts developers to creeping technical debt or API performance degradation."
  },
  mom_delta: {
    title: "Model-over-Model (MoM) Delta",
    definition: "Long-term performance variance comparing the current swarm capability baseline with previous checkpoints.",
    behavior: "Compares current multi-agent trial benchmarks against the historical baseline recorded in the core telemetry database.",
    impact: "Indicates the macro-evolution of the system. Positive values verify that the newly indexed code topology is actively improving cognitive performance."
  }
};

export const ToolDetailPanel = memo(function ToolDetailPanel({ selectedTool }: ToolDetailPanelProps) {
  const [selectedMetric, setSelectedMetric] = useState<string | null>("beta"); // Default to "beta" for immediate user focus
  const metrics = useToolMetrics(selectedTool);
  if (!metrics) return null;

  const toolDesc = getToolDescription(metrics.tool_id);
  const explainer = selectedMetric ? METRIC_EXPLAINERS[selectedMetric] : null;

  return (
    <div className="mt-6 p-6 border border-[var(--gold)] bg-[var(--background)]/60 rounded-md artisan-shadow">
      {/* Symmetrical, responsive CSS Grid layout replacing fragile flexbox layouts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-4">
        <MetricItem 
          label="Tool" 
          value={metrics.tool_id} 
          className="col-span-1 sm:col-span-2 lg:col-span-2"
          onClick={() => setSelectedMetric(selectedMetric === "tool" ? null : "tool")}
          isActive={selectedMetric === "tool"}
        />
        <MetricItem 
          label="α (Success)" 
          value={metrics.alphaStr} 
          valueClassName="text-[var(--gold)]" 
          onClick={() => setSelectedMetric(selectedMetric === "alpha" ? null : "alpha")}
          isActive={selectedMetric === "alpha"}
        />
        <MetricItem 
          label="β (Failure)" 
          value={metrics.betaStr} 
          onClick={() => setSelectedMetric(selectedMetric === "beta" ? null : "beta")}
          isActive={selectedMetric === "beta"}
        />
        <MetricItem 
          label="Entropy" 
          value={metrics.entropyStr} 
          valueClassName={metrics.entropyIsLow ? "text-emerald-400" : ""} 
          onClick={() => setSelectedMetric(selectedMetric === "entropy" ? null : "entropy")}
          isActive={selectedMetric === "entropy"}
        />
        <MetricItem 
          label="Momentum" 
          value={metrics.deltaStr} 
          onClick={() => setSelectedMetric(selectedMetric === "momentum" ? null : "momentum")}
          isActive={selectedMetric === "momentum"}
        />
        <MetricItem 
          label="MoM Δ" 
          value={metrics.momDeltaStr} 
          onClick={() => setSelectedMetric(selectedMetric === "mom_delta" ? null : "mom_delta")}
          isActive={selectedMetric === "mom_delta"}
        />
      </div>

      {/* Dynamic Metric Explainer Section */}
      <AnimatePresence mode="wait">
        {explainer && (
          <motion.div
            key={selectedMetric}
            initial={{ opacity: 0, y: 10, scale: 0.995 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.995 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            aria-live="polite"
            role="region"
            className="mt-6 p-5 border border-[var(--gold)]/30 bg-[var(--sand)]/15 rounded-md space-y-4 font-mono text-xs min-h-[140px]"
          >
            <div className="flex justify-between items-center border-b border-[var(--border-muted)] pb-2.5">
              <span className="text-[10px] font-black uppercase tracking-[0.3em] text-[var(--gold)]">Telemetry Metric Explainer</span>
              <span className="font-data font-bold text-sm uppercase text-[var(--foreground)]">{explainer?.title}</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="space-y-1">
                <span className="text-[9px] font-bold uppercase tracking-wider opacity-45">Definition</span>
                <p className="leading-relaxed text-[11px] opacity-80">{explainer.definition}</p>
              </div>
              <div className="space-y-1">
                <span className="text-[9px] font-bold uppercase tracking-wider opacity-45">Under the Hood</span>
                <p className="leading-relaxed text-[11px] opacity-80">{explainer.behavior}</p>
              </div>
              <div className="space-y-1">
                <span className="text-[9px] font-bold uppercase tracking-wider opacity-45">Operational Impact</span>
                <p className="leading-relaxed text-[11px] opacity-80 text-[var(--gold)] font-bold">{explainer.impact}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {toolDesc && (
        <div className="mt-6 border-t border-[var(--border-muted)] pt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-1 space-y-1">
            <div className="text-[10px] sm:text-xs font-bold uppercase tracking-widest opacity-65">System Tier</div>
            <div className="text-xs font-mono font-bold text-[var(--gold)] mt-1">
              {toolDesc.system}
            </div>
            <div className="text-[10px] sm:text-xs font-bold uppercase tracking-widest opacity-65 pt-3">Operational Role</div>
            <div className="text-sm font-sans font-bold mt-1">
              {toolDesc.role}
            </div>
          </div>
          <div className="md:col-span-2 space-y-1">
            <div className="text-[10px] sm:text-xs font-bold uppercase tracking-widest opacity-65">System Description</div>
            <p className="text-[11px] opacity-75 leading-relaxed font-mono mt-1">
              {toolDesc.desc}
            </p>
          </div>
        </div>
      )}

      <div className="mt-6 pt-4 border-t border-[var(--border-muted)]/40">
        <AccuracyGauge
          success={metrics.gaugeSuccess}
          total={metrics.gaugeTotal}
          label={`Bayesian Posterior (Trials: ${metrics.successCount} S / ${metrics.failureCount} F)`}
        />
      </div>
    </div>
  );
});

export default ToolDetailPanel;
