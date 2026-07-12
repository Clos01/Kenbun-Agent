"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";


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
  const dataMax = Math.max(...data, 0);
  const max = dataMax > 0 ? dataMax : 1;
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
  const [hoveredIdx, setHoveredIdx] = React.useState<number | null>(null);
  const dataMax = Math.max(...data, 0);
  const max = dataMax > 0 ? dataMax : 1;

  // Build the SVG step path
  const points: { x: number; y: number }[] = data.map((val, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 100 - (val / max) * 90; // Leave 10% padding at top
    return { x, y };
  });

  let linePath = "";
  if (points.length > 0) {
    linePath = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      // Step: horizontal to current X, then vertical to current Y
      linePath += ` H ${curr.x} V ${curr.y}`;
    }
  }

  const areaPath = linePath 
    ? `${linePath} L 100 100 L 0 100 Z` 
    : "";

  return (
    <div 
      className="h-full min-h-[140px] w-full relative border border-[var(--border)] bg-gradient-to-b from-[var(--background)]/10 to-[var(--background)]/40 overflow-hidden rounded-sm select-none group/chart"
      onMouseLeave={() => {
        setHoveredIdx(null);
      }}
    >
      {/* Background Blueprint Grid (Vertical & Horizontal Matrix) */}
      <div className="absolute inset-0 grid grid-cols-6 pointer-events-none opacity-[0.03]">
        {[1, 2, 3, 4, 5].map(i => <div key={i} className="border-r border-foreground" />)}
      </div>
      <div className="absolute inset-0 grid grid-rows-6 pointer-events-none opacity-[0.03]">
        {[1, 2, 3, 4, 5].map(i => <div key={i} className="border-b border-foreground" />)}
      </div>

      {/* SVG Step Chart */}
      <svg 
        className="absolute inset-0 w-full h-full p-2 pt-8 pb-1 overflow-visible"
        viewBox="0 0 100 100" 
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="area-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--gold)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--gold)" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Filled Area */}
        {areaPath && (
          <motion.path
            d={areaPath}
            fill="url(#area-gradient)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
          />
        )}

        {/* Step Line */}
        {linePath && (
          <motion.path
            d={linePath}
            fill="none"
            stroke="var(--gold)"
            strokeWidth="1.2"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          />
        )}

        {/* Hover vertical tracking line */}
        {hoveredIdx !== null && (
          <line
            x1={points[hoveredIdx].x}
            y1={0}
            x2={points[hoveredIdx].x}
            y2={100}
            stroke="var(--gold)"
            strokeWidth="0.5"
            strokeDasharray="2 2"
            opacity="0.5"
          />
        )}

        {/* Hover dot */}
        {hoveredIdx !== null && (
          <circle
            cx={points[hoveredIdx].x}
            cy={points[hoveredIdx].y}
            r="1.5"
            fill="var(--background)"
            stroke="var(--gold)"
            strokeWidth="0.8"
          />
        )}
      </svg>

      {/* Floating HUD Tooltip */}
      <AnimatePresence>
        {hoveredIdx !== null && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute top-3 left-3 z-20 px-3 py-2 bg-zinc-950/95 backdrop-blur-md border-l-2 border-l-[var(--gold)] border-t border-r border-b border-white/5 rounded-sm font-mono text-[9px] flex flex-col gap-1 shadow-2xl pointer-events-none ring-1 ring-black/50"
          >
            <div className="flex justify-between items-center gap-6">
              <span className="text-stone-400 text-[7px] uppercase font-bold tracking-wider">CYCLE OFFSET</span>
              <span className="text-[var(--gold)] font-bold text-[9px]">T-{24 - hoveredIdx}H</span>
            </div>
            <div className="flex justify-between items-center gap-6">
              <span className="text-stone-400 text-[7px] uppercase font-bold tracking-wider">COMPUTE COST</span>
              <span className="font-bold text-stone-100 text-[9px]">${data[hoveredIdx].toFixed(6)}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Hover Trigger Areas (Columns) */}
      <div className="absolute inset-0 flex">
        {data.map((_, i) => (
          <div
            key={i}
            className="flex-1 h-full cursor-pointer z-10"
            onMouseEnter={() => setHoveredIdx(i)}
          />
        ))}
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
