import React from 'react';
import { motion } from 'framer-motion';
import { Focus, X, FileText, ShieldAlert, Wrench, Loader2 } from 'lucide-react';
import { StarNode } from './types';
import { ROOM_COLORS_MAP_DARK, ROOM_COLORS_MAP_LIGHT } from './constants';
import { TOOL_EQUATIONS } from '@/lib/equations';
import { CONFIG } from '@/lib/config';

interface InspectorPanelProps {
  selectedNode: StarNode;
  setSelectedNode: (node: StarNode | null) => void;
  handleFocusNode: (node: StarNode) => void;
  isFullscreen: boolean;
  isDark: boolean;
}

export default function InspectorPanel({
  selectedNode,
  setSelectedNode,
  handleFocusNode,
  isFullscreen,
  isDark
}: InspectorPanelProps) {
  const roomColorsMap = isDark ? ROOM_COLORS_MAP_DARK : ROOM_COLORS_MAP_LIGHT;
  
  const toolName = selectedNode.file.split('/').pop()?.replace('.py', '') || '';
  const equationObj = TOOL_EQUATIONS[toolName];

  const [auditStatus, setAuditStatus] = React.useState<'idle' | 'running' | 'completed' | 'error'>('idle');
  const [auditReport, setAuditReport] = React.useState<string | null>(null);
  const [auditError, setAuditError] = React.useState<string | null>(null);
  const intervalRef = React.useRef<any>(null);

  React.useEffect(() => {
    // Reset audit states and clear interval when active node changes
    setAuditStatus('idle');
    setAuditReport(null);
    setAuditError(null);
    
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [selectedNode.id]);

  const handleRunAudit = async (workflow: 'code_review' | 'bug_fix') => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    setAuditStatus('running');
    setAuditReport(null);
    setAuditError(null);

    try {
      const res = await fetch(`${CONFIG.API_BASE}/orchestrate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow,
          task: workflow === 'code_review' 
            ? `Run a full SVE verifier audit and supervisor style check on ${selectedNode.file.split('/').pop()}.`
            : `Diagnose and fix any logical regressions or syntax errors in ${selectedNode.file.split('/').pop()}.`,
          file_path: selectedNode.file,
          project_path: '.'
        })
      });

      if (!res.ok) {
        throw new Error(`HTTP Error ${res.status} ${res.statusText}`);
      }

      const data = await res.json();
      if (data.status === 'error' || data.status === 'blocked') {
        setAuditStatus('error');
        setAuditError(data.message || 'Job blocked by security guardrails');
        return;
      }

      const jobId = data.job_id;
      let attempts = 0;
      const maxAttempts = 60; // 2 minutes max polling

      const interval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${CONFIG.API_BASE}/orchestrate/status/${jobId}`);
          if (!statusRes.ok) {
            throw new Error(`Failed to fetch status`);
          }
          const statusData = await statusRes.json();
          
          if (statusData.status === 'completed' || statusData.status === 'approved' || statusData.status === 'review_needed' || statusData.status === 'error') {
            clearInterval(interval);
            intervalRef.current = null;
            if (statusData.status === 'error') {
              setAuditStatus('error');
              setAuditError(statusData.error || 'Pipeline execution failed.');
            } else {
              setAuditStatus('completed');
              setAuditReport(statusData.result || 'No report returned.');
            }
          } else if (attempts >= maxAttempts) {
            clearInterval(interval);
            intervalRef.current = null;
            setAuditStatus('error');
            setAuditError('Orchestration job timed out.');
          }
          attempts++;
        } catch (err) {
          clearInterval(interval);
          intervalRef.current = null;
          setAuditStatus('error');
          setAuditError(err instanceof Error ? err.message : 'Error polling job status');
        }
      }, 2000);
      
      intervalRef.current = interval;

    } catch (err) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setAuditStatus('error');
      setAuditError(err instanceof Error ? err.message : 'Network error initiating job');
    }
  };

  return (
    <motion.div 
      onMouseDown={(e) => e.stopPropagation()}
      onMouseUp={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      initial={{ opacity: 0, x: -30, scale: 0.98 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: -30, scale: 0.98 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`absolute z-[150] w-88 md:w-96 bg-[var(--background)]/80 border border-[var(--border)] backdrop-blur-3xl p-6 md:p-8 shadow-[0_0_50px_rgba(0,0,0,0.25)] dark:shadow-[0_0_50px_rgba(0,0,0,0.65)] space-y-6 rounded-sm transition-all duration-300 relative overflow-hidden ${
        isFullscreen ? 'bottom-28 left-10' : 'top-24 left-10'
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
            onClick={() => setAuditStatus('idle')}
            className="px-4 py-2 border border-rose-500/30 hover:bg-rose-500/10 text-[9px] font-mono uppercase tracking-widest text-rose-500 rounded-sm"
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
              onClick={() => setAuditStatus('idle')}
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
        <span className={`text-[9px] font-mono font-bold uppercase tracking-[0.2em] px-2.5 py-1 border rounded-sm ${roomColorsMap[selectedNode.room]}`}>
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
        <p className="text-[9px] font-mono text-[var(--foreground)] opacity-40 break-all select-all leading-normal bg-[var(--border)]/10 p-2 border border-[var(--border)]/30 rounded-sm">
          {selectedNode.file}
        </p>
      </div>

      {/* Semantic Snippet Code Block */}
      <div className="space-y-2">
        <span className="text-[8px] font-mono font-bold uppercase tracking-widest opacity-30">Semantic Signal Code</span>
        <div className="text-[10px] font-mono leading-relaxed p-4 border border-[var(--border)]/30 bg-[var(--background)]/40 text-[var(--foreground)] max-h-44 overflow-y-auto custom-scrollbar whitespace-pre-wrap select-text rounded-sm">
          {selectedNode.snippet || "Empty signal payload."}
        </div>
      </div>

      {/* Mathematical Model */}
      {equationObj && (
        <div className="space-y-2">
          <span className="text-[8px] font-mono font-bold uppercase tracking-widest opacity-30 text-[var(--foreground)]">Mathematical Model</span>
          <div className="p-4 border bg-[var(--background)]/30 border-[var(--border)]/30 rounded-sm">
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
            onClick={() => handleRunAudit('code_review')}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--accent)]/10 text-[8px] font-mono uppercase tracking-wider transition-all rounded-sm hover:scale-[1.02] active:scale-[0.98]"
            title="Trigger full SVE code review"
          >
            <ShieldAlert className="w-3 h-3 text-[var(--accent)]" />
            SVE Code Audit
          </button>
          <button
            onClick={() => handleRunAudit('bug_fix')}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--accent)]/10 text-[8px] font-mono uppercase tracking-wider transition-all rounded-sm hover:scale-[1.02] active:scale-[0.98]"
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
          className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--accent)] hover:text-white text-[9px] font-mono uppercase tracking-widest transition-all duration-200 rounded-sm hover:scale-[1.03] active:scale-[0.98]"
        >
          <Focus className="w-3.5 h-3.5" />
          Recenter Focus
        </button>
      </div>
    </motion.div>
  );
}
