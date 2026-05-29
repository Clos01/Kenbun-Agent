import React from 'react';
import { motion } from 'framer-motion';
import { Focus, X, FileText } from 'lucide-react';
import { StarNode } from './types';
import { ROOM_COLORS_MAP_DARK, ROOM_COLORS_MAP_LIGHT } from './constants';

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

  return (
    <motion.div 
      onMouseDown={(e) => e.stopPropagation()}
      onMouseUp={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      initial={{ opacity: 0, x: -30, scale: 0.98 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: -30, scale: 0.98 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`absolute z-[150] w-88 md:w-96 bg-[var(--background)]/95 border border-[var(--border)] backdrop-blur-2xl p-6 md:p-8 artisan-shadow space-y-6 rounded-sm ${
        isFullscreen ? 'bottom-28 left-10' : 'top-24 left-10'
      }`}
    >
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
        <p className="text-[9px] font-mono text-[var(--foreground)] opacity-40 break-all select-all leading-normal bg-primary/[0.02] p-2 border border-primary/5 rounded-sm">
          {selectedNode.file}
        </p>
      </div>

      {/* Semantic Snippet Code Block */}
      <div className="space-y-2">
        <span className="text-[8px] font-mono font-bold uppercase tracking-widest opacity-30">Semantic Signal Code</span>
        <div className="text-[10px] font-mono leading-relaxed p-4 border bg-primary/[0.02] border-primary/5 text-[var(--foreground)] max-h-44 overflow-y-auto custom-scrollbar whitespace-pre-wrap select-text">
          {selectedNode.snippet || "Empty signal payload."}
        </div>
      </div>

      {/* Actions */}
      <div className="pt-2 flex items-center justify-between">
        <span className="text-[8px] font-mono opacity-30 select-none">NODE_ID: {selectedNode.id.slice(0, 8)}</span>
        <button
          onClick={() => handleFocusNode(selectedNode)}
          className="flex items-center gap-2 px-4 py-2 border border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--accent)] hover:text-white text-[9px] font-mono uppercase tracking-widest transition-all duration-300 rounded-sm"
        >
          <Focus className="w-3.5 h-3.5" />
          Recenter Focus
        </button>
      </div>
    </motion.div>
  );
}
