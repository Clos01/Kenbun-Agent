"use client";

import React from "react";
import { motion } from "framer-motion";


/**
 * A Sharp Accuracy Ledger (Success vs Failure)
 */
export const AccuracyGauge = ({ success, total, label = "Signals" }: { success: number, total: number, label?: string }) => {
  const failure = total - success;
  const successPct = total > 0 ? (success / total) * 100 : 0;
  const failurePct = total > 0 ? (failure / total) * 100 : 0;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center text-[8px] font-bold uppercase tracking-widest mb-1">
        <span className="opacity-60">{label}</span>
        <div className="flex gap-4">
          <span className="text-[var(--gold)]">Success ({successPct.toFixed(0)}%)</span>
          <span className="opacity-30">Failure ({failurePct.toFixed(0)}%)</span>
        </div>
      </div>
      <div className="h-4 flex border border-[var(--border)] bg-[var(--foreground)]/5 overflow-hidden p-[2px]">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${successPct}%` }}
          className="h-full bg-[var(--gold)]"
        />
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${failurePct}%` }}
          className="h-full bg-[var(--border)] opacity-20 ml-[2px]"
        />
      </div>
    </div>
  );
};

/**
 * A True Linear Line Chart (No Fill)
 */
export const LinearTrend = ({ data, color = "var(--gold)" }: { data: number[], color?: string }) => {
  const max = Math.max(...data, 1);
  const points = data.map((val, i) => `${(i / (data.length - 1)) * 100},${100 - (val / max) * 100}`).join(" ");

  return (
    <div className="h-32 w-full relative border-b border-l border-[var(--border)] bg-[var(--foreground)]/[0.01] overflow-hidden">
      <svg className="w-full h-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
        <motion.polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="1"
          strokeDasharray="400"
          strokeDashoffset="400"
          animate={{ strokeDashoffset: 0 }}
          transition={{ duration: 2, ease: "easeInOut" }}
        />
      </svg>
      <div className="absolute inset-0 grid grid-cols-4 pointer-events-none opacity-[0.05]">
        {[1, 2, 3].map(i => <div key={i} className="border-r border-black" />)}
      </div>
    </div>
  );
};

/**
 * A Sharp Square Donut Chart
 */
export const SquareDonut = ({ data }: { data: { label: string, value: number, color: string }[] }) => {
  const total = data.reduce((acc, d) => acc + d.value, 0);

  return (
    <div className="space-y-6">
      <div className="w-full h-12 flex border border-[var(--border)] overflow-hidden">
        {data.map((item, i) => {
          const width = (item.value / total) * 100;
          return (
            <motion.div 
              key={i}
              initial={{ width: 0 }}
              animate={{ width: `${width}%` }}
              style={{ backgroundColor: item.color }}
              className="h-full border-r border-black/10 last:border-0"
            />
          );
        })}
      </div>
      <div className="grid grid-cols-2 gap-4">
        {data.map((item, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-2 h-2" style={{ backgroundColor: item.color }} />
            <span className="text-[9px] font-bold uppercase tracking-widest opacity-40">{item.label}</span>
            <span className="text-[9px] font-bold ml-auto">{(item.value / total * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
};


interface MatrixTool {
  tool_id: string;
  success_rate: number;
  [key: string]: unknown;
}

/**
 * A High-Density Tool Probability Matrix (INTERACTIVE)
 */
export const ToolMatrix = ({ tools, onSelect, selectedId }: { tools: MatrixTool[], onSelect?: (tool: MatrixTool) => void, selectedId?: string }) => {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
      {tools.map((tool, i) => (
        <button 
          key={i} 
          onClick={() => onSelect?.(tool)}
          className={`group p-4 border-2 text-left transition-all relative artisan-shadow ${
            selectedId === tool.tool_id 
              ? 'border-[var(--gold)] bg-[var(--sand)]' 
              : 'border-[var(--border)] bg-[var(--background)] hover:bg-[var(--sand)]'
          }`}
        >
          <div className="flex justify-between items-start mb-4">
            <span className="text-[7px] font-mono font-bold opacity-30 group-hover:opacity-100 uppercase tracking-tighter">
              {tool.tool_id.replace(/_/g, ' ')}
            </span>
            <div className={`w-1.5 h-1.5 ${tool.success_rate > 0.8 ? 'bg-[var(--gold)]' : 'bg-[var(--border)] opacity-20'}`} />
          </div>
          <div className="space-y-2">
            <div className="h-1 bg-[var(--foreground)]/5 overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${tool.success_rate * 100}%` }}
                className="h-full bg-[var(--gold)]"
              />
            </div>
            <div className="flex justify-between items-center text-[9px] font-black font-serif">
              <span className="truncate opacity-60 group-hover:opacity-100 transition-opacity">SYSTEM NODE</span>
              <span className="text-[var(--gold)]">{(tool.success_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
          {selectedId === tool.tool_id && (
            <div className="absolute -top-1 -right-1 w-2 h-2 bg-[var(--gold)]" />
          )}
        </button>
      ))}
    </div>
  );
};

/**
 * A Sharp Step Area Chart
 */
export const SharpAreaChart = ({ data }: { data: number[] }) => {
  const max = Math.max(...data, 1);
  return (
    <div className="h-48 w-full relative border border-[var(--border)] bg-[var(--foreground)]/[0.02] overflow-hidden">
      <div className="absolute inset-0 flex items-end">
        {data.map((val, i) => (
          <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
            <motion.div 
              initial={{ height: 0 }}
              animate={{ height: `${(val / max) * 100}%` }}
              className="w-full bg-[var(--gold)]/20 border-t-2 border-[var(--gold)]"
            />
          </div>
        ))}
      </div>
      <div className="absolute inset-0 grid grid-cols-4 pointer-events-none opacity-[0.05]">
        {[1, 2, 3].map(i => <div key={i} className="border-r border-[var(--border)]" />)}
      </div>
    </div>
  );
};




/**
 * Context Window Utilization Bar (Gemma 4 / LLMs)
 */
export const ContextWindowBar = ({ usedTokens, maxTokens = 8192, label = "Context Window" }: { usedTokens: number, maxTokens?: number, label?: string }) => {
  const percentage = Math.min((usedTokens / maxTokens) * 100, 100);
  const isCritical = percentage > 90;
  
  return (
    <div className="space-y-4">
      <div className="flex justify-between text-[8px] font-bold uppercase tracking-widest mb-1">
        <span className="opacity-60">{label}</span>
        <span className={isCritical ? "text-red-500" : "text-[var(--gold)]"}>
          {usedTokens.toLocaleString()} / {maxTokens.toLocaleString()} Tokens
        </span>
      </div>
      <div className="h-4 w-full flex border border-[var(--border)] bg-[var(--foreground)]/5 overflow-hidden p-[2px]">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          className={`h-full ${isCritical ? 'bg-red-500' : 'bg-[var(--gold)]'}`}
        />
        <div className="flex-1 bg-[var(--border)] opacity-10 ml-[2px]" />
      </div>
      <div className="flex justify-between text-[7px] font-mono opacity-30 mt-1">
        <span>0</span>
        <span>4096</span>
        <span>{maxTokens}</span>
      </div>
    </div>
  );
};
