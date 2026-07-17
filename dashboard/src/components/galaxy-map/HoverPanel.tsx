import React from 'react';
import { motion } from 'framer-motion';
import { StarNode, ActiveJob } from './types';
import { ROOM_COLORS_MAP_DARK, ROOM_COLORS_MAP_LIGHT } from './constants';

interface HoverPanelProps {
  hovered: StarNode;
  isFullscreen: boolean;
  isDark: boolean;
  activeJob?: ActiveJob;
}

export default function HoverPanel({
  hovered,
  isFullscreen,
  isDark,
  activeJob
}: HoverPanelProps) {
  const roomColorsMap = isDark ? ROOM_COLORS_MAP_DARK : ROOM_COLORS_MAP_LIGHT;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 15 }}
      className={`absolute z-[120] pointer-events-none w-80 bg-[var(--background)]/75 border border-[var(--border)]/45 backdrop-blur-xl p-5 shadow-2xl space-y-3 rounded-xl ${
        isFullscreen ? 'bottom-28 left-10' : 'top-24 left-10'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className={`text-[8px] font-mono uppercase tracking-widest px-2.5 py-1 border border-[var(--border)]/40 rounded-md ${roomColorsMap[hovered.room]}`}>
          {hovered.room}
        </span>
        <span className="text-[7px] font-mono opacity-30">ID_{hovered.id.slice(0, 4)}</span>
      </div>
      <h4 className="text-xs font-heading font-bold text-[var(--foreground)] truncate">{hovered.file.split('/').pop()}</h4>
      <p className="text-[10px] font-mono opacity-35 truncate">{hovered.file}</p>
      
      {activeJob && (
        <div className="pt-2 border-t border-[var(--border)]/30 flex items-center justify-between text-[8px] font-mono">
          <span className="opacity-40 uppercase">Sovereign State:</span>
          <span className={`font-bold ${
            activeJob.status === 'running' ? 'text-amber-500 animate-pulse' :
            activeJob.status === 'completed' ? 'text-emerald-500' : 'text-rose-500'
          }`}>
            {activeJob.status === 'running' 
              ? (activeJob.workflow === 'bug_fix' ? 'AUTONOMIC FIXING...' : 'SVE AUDITING...') 
              : activeJob.status.toUpperCase()}
          </span>
        </div>
      )}
    </motion.div>
  );
}
