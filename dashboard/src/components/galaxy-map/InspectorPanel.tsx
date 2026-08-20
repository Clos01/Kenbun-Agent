import React from 'react';
import { motion } from 'framer-motion';
import { Focus, X, FileText, ShieldAlert, Wrench, Loader2 } from 'lucide-react';
import { StarNode, ActiveJob } from './types';
import { ROOM_COLORS_MAP_DARK, ROOM_COLORS_MAP_LIGHT } from './constants';
import { TOOL_EQUATIONS } from '@/lib/equations';

interface InspectorPanelProps {
  selectedNode: StarNode;
  setSelectedNode: (node: StarNode | null) => void;
  handleFocusNode: (node: StarNode) => void;
  isFullscreen: boolean;
  isDark: boolean;
  activeJob?: ActiveJob;
  triggerNodeAudit: (node: StarNode, workflow: 'code_review' | 'bug_fix') => void;
  clearNodeAudit: (nodeId: string) => void;
}

export default function InspectorPanel({
  selectedNode,
  setSelectedNode,
  handleFocusNode,
  isFullscreen,
  isDark,
  activeJob,
  triggerNodeAudit,
  clearNodeAudit
}: InspectorPanelProps) {
  const roomColorsMap = isDark ? ROOM_COLORS_MAP_DARK : ROOM_COLORS_MAP_LIGHT;
  
  const toolName = selectedNode.file.split('/').pop()?.replace('.py', '') || '';
  const equationObj = TOOL_EQUATIONS[toolName];

  const auditStatus = activeJob?.status || 'idle';
  const auditReport = activeJob?.report || null;
  const auditError = activeJob?.error || null;

  return (
    <motion.div 
      onMouseDown={(e) => e.stopPropagation()}
      onMouseUp={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      onTouchStart={(e) => e.stopPropagation()}
      onTouchEnd={(e) => e.stopPropagation()}
      initial={{ opacity: 0, y: 30, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 30, scale: 0.98 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`fixed sm:absolute z-[150] inset-x-3 bottom-20 sm:bottom-auto top-auto sm:top-24 sm:left-10 sm:right-auto w-auto sm:w-96 max-h-[75vh] sm:max-h-none overflow-y-auto bg-[var(--background)]/90 border border-[var(--border)]/60 backdrop-blur-3xl p-5 sm:p-8 shadow-[0_0_50px_rgba(0,0,0,0.35)] space-y-5 rounded-md transition-all duration-300 relative overflow-hidden ${
        isFullscreen ? 'sm:bottom-28 sm:top-auto sm:left-10' : 'sm:top-24 sm:left-10'
      }`}
    >
      {/* Dynamic SVE Audit Loading / Progress Overlay */}
      {auditStatus === 'running' && (
        <div className="absolute inset-0 bg-[var(--background)]/90 backdrop-blur-md z-[200] flex flex-col items-center justify-center p-6 space-y-4">
          <Loader2 className="w-8 h-8 text-[var(--accent)] animate-spin" />
          <p className="text-[10px] font-mono uppercase tracking-[0.25em] text-[var(--foreground)]">Orchestrator Executing...</p>
          <span className="text-[9px] font-mono text-[var(--foreground)] opacity-50 text-center animate-pulse px-4">
            Running SVE Verifier & System 2 Supervisor Audit on {selectedNode.file.split('/').pop()}
          </span>
        </div>
      )}

      {/* Dynamic SVE Audit Error Overlay */}
      {auditStatus === 'error' && (
        <div className="absolute inset-0 bg-[var(--background)]/90 backdrop-blur-md z-[200] flex flex-col items-center justify-center p-6 space-y-4">
          <ShieldAlert className="w-8 h-8 text-rose-500" />
          <p className="text-[10px] font-mono uppercase tracking-wider text-rose-500 font-bold">Pipeline Error</p>
          <p className="text-[9px] font-mono text-[var(--foreground)] opacity-60 text-center px-4 max-h-40 overflow-y-auto">
            {auditError}
          </p>
          <button 
            onClick={() => clearNodeAudit(selectedNode.id)}
            className="px-4 py-2 border border-rose-500/30 hover:bg-rose-500/10 text-[9px] font-mono uppercase tracking-widest text-rose-500 rounded-lg transition-all duration-300"
          >
            Close
          </button>
        </div>
      )}

      {/* Dynamic SVE Audit Completed Report Overlay */}
      {auditStatus === 'completed' && (
        <div className="absolute inset-0 bg-[var(--background)]/95 backdrop-blur-md z-[200] flex flex-col p-6 space-y-4 overflow-hidden">
          <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] font-bold text-[var(--accent)] flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5" />
              Sovereign Report
            </span>
            <button 
              onClick={() => clearNodeAudit(selectedNode.id)}
              className="p-1 text-[var(--foreground)] opacity-50 hover:opacity-100 transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto custom-scrollbar text-[9.5px] font-mono leading-relaxed whitespace-pre-wrap select-text pr-2 text-[var(--foreground)]/90">
            {auditReport}
          </div>
        </div>
      )}

      {/* Header / Badges */}
      <div className="flex items-center justify-between">
        <span className={`text-[9px] font-mono font-bold uppercase tracking-[0.2em] px-2.5 py-1 border border-[var(--border)]/40 rounded-md ${roomColorsMap[selectedNode.room]}`}>
          {selectedNode.room}
        </span>
        <div className="flex items-center gap-3">
          <button
            onClick={() => handleFocusNode(selectedNode)}
            title="Focus node"
            className="p-1 text-[var(--foreground)] opacity-40 hover:opacity-100 hover:text-[var(--accent)] transition-all"
          >
            <Focus className="w-3.5 h-3.5" />
          </button>
          <div className="w-[1px] h-3 bg-[var(--border)]" />
          <button 
            onClick={() => setSelectedNode(null)}
            title="Close Inspector"
            className="p-1 text-[var(--foreground)] opacity-40 hover:opacity-100 transition-all"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Title / Path */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 opacity-40 text-[var(--foreground)]" />
          <h3 className="text-base font-heading font-semibold text-[var(--foreground)] tracking-tight truncate">
            {selectedNode.file.split('/').pop()}
          </h3>
        </div>
        <p className="text-[9px] font-mono text-[var(--foreground)] opacity-40 break-all select-all leading-normal bg-[var(--border)]/10 p-2 border border-[var(--border)]/30 rounded-lg">
          {selectedNode.file}
        </p>
      </div>

      {/* Semantic Snippet Code Block */}
      <div className="space-y-2">
        <span className="text-[8px] font-mono font-bold uppercase tracking-widest opacity-30">Semantic Signal Code</span>
        <div className="text-[10px] font-mono leading-relaxed p-4 border border-[var(--border)]/30 bg-[var(--background)]/40 text-[var(--foreground)] max-h-44 overflow-y-auto custom-scrollbar whitespace-pre-wrap select-text rounded-lg">
          {selectedNode.snippet || "Empty signal payload."}
        </div>
      </div>

      {/* Mathematical Model */}
      {equationObj && (
        <div className="space-y-2">
          <span className="text-[8px] font-mono font-bold uppercase tracking-widest opacity-30 text-[var(--foreground)]">Mathematical Model</span>
          <div className="p-4 border bg-[var(--background)]/30 border-[var(--border)]/30 rounded-lg">
            <pre className="text-[10px] font-mono text-[var(--foreground)] font-semibold leading-relaxed whitespace-pre-wrap">{equationObj.math}</pre>
            <details className="group mt-3">
              <summary className="text-[9px] font-bold uppercase tracking-wider text-[var(--foreground)] opacity-60 cursor-pointer select-none list-none flex items-center gap-1.5 hover:opacity-100 transition-opacity">
                <span>Explain Formula</span>
                <span className="text-[7px] transition-transform duration-200 group-open:rotate-180">▼</span>
              </summary>
              <div className="mt-2 pt-2 border-t border-[var(--border)]/30">
                <p className="text-[9px] font-mono text-[var(--foreground)] opacity-70 mt-1">{equationObj.desc}</p>
              </div>
            </details>
          </div>
        </div>
      )}

      {/* Sovereign SVE & Orchestrator Tools */}
      <div className="border-t border-[var(--border)]/30 pt-4 flex flex-col gap-2">
        <span className="text-[8px] font-mono font-bold uppercase tracking-widest opacity-30 select-none">Sovereign Orchestration</span>
        <div className="flex gap-2">
          <button
            onClick={() => triggerNodeAudit(selectedNode, 'code_review')}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--accent)]/10 text-[8px] font-mono uppercase tracking-wider transition-all rounded-lg hover:scale-[1.02] active:scale-[0.98]"
            title="Trigger full SVE code review"
          >
            <ShieldAlert className="w-3 h-3 text-[var(--accent)]" />
            SVE Code Audit
          </button>
          <button
            onClick={() => triggerNodeAudit(selectedNode, 'bug_fix')}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--accent)]/10 text-[8px] font-mono uppercase tracking-wider transition-all rounded-lg hover:scale-[1.02] active:scale-[0.98]"
            title="Attempt autonomic bug fix"
          >
            <Wrench className="w-3 h-3 text-[var(--accent)]" />
            Autonomic Fix
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="pt-2 flex items-center justify-between border-t border-[var(--border)]/30">
        <span className="text-[8px] font-mono opacity-30 select-none">NODE_ID: {selectedNode.id.slice(0, 8)}</span>
        <button
          onClick={() => handleFocusNode(selectedNode)}
          className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--accent)] hover:text-white text-[9px] font-mono uppercase tracking-widest transition-all duration-200 rounded-lg hover:scale-[1.03] active:scale-[0.98]"
        >
          <Focus className="w-3.5 h-3.5" />
          Recenter Focus
        </button>
      </div>
    </motion.div>
  );
}
