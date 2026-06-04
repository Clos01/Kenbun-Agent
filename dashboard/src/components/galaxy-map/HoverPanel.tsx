import React from 'react';
import { motion } from 'framer-motion';
import { StarNode } from './types';
import { ROOM_COLORS_MAP_DARK, ROOM_COLORS_MAP_LIGHT } from './constants';

interface HoverPanelProps {
  hovered: StarNode;
  isFullscreen: boolean;
  isDark: boolean;
}

export default function HoverPanel({
  hovered,
  isFullscreen,
  isDark
}: HoverPanelProps) {
  const roomColorsMap = isDark ? ROOM_COLORS_MAP_DARK : ROOM_COLORS_MAP_LIGHT;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 15 }}
      className={`absolute z-[120] pointer-events-none w-80 bg-[var(--background)]/90 border border-[var(--border)] backdrop-blur-xl p-5 artisan-shadow space-y-3 rounded-sm ${
        isFullscreen ? 'bottom-28 left-10' : 'top-24 left-10'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className={`text-[8px] font-mono uppercase tracking-widest px-2 py-0.5 border rounded-sm ${roomColorsMap[hovered.room]}`}>
          {hovered.room}
        </span>
        <span className="text-[7px] font-mono opacity-30">ID_{hovered.id.slice(0, 4)}</span>
      </div>
      <h4 className="text-xs font-heading font-bold text-[var(--foreground)] truncate">{hovered.file.split('/').pop()}</h4>
      <p className="text-[10px] font-mono opacity-35 truncate">{hovered.file}</p>
    </motion.div>
  );
}
