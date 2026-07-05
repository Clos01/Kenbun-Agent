import React from 'react';

interface SwarmLegendProps {
  isDragging: boolean;
}

export default function SwarmLegend({ isDragging }: SwarmLegendProps) {
  return (
    <div 
      onMouseDown={(e) => e.stopPropagation()}
      onMouseUp={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      className={`absolute bottom-8 right-10 z-[100] flex flex-wrap gap-x-6 gap-y-2 bg-[var(--background)]/90 p-4 border border-[var(--border)] backdrop-blur-2xl artisan-shadow transition-opacity duration-300 rounded-sm ${
        isDragging ? 'opacity-20' : 'opacity-100'
      }`}
    >
      {["Central_Logic", "Vault", "Observatory", "Simulations", "Archives"].map(room => {
        let dotColor = "";
        if (room === "Central_Logic") dotColor = "bg-[#B8422E]";
        else if (room === "Vault") dotColor = "bg-teal-500";
        else if (room === "Observatory") dotColor = "bg-blue-500";
        else if (room === "Simulations") dotColor = "bg-indigo-500";
        else dotColor = "bg-amber-500";

        return (
          <div key={room} className="flex items-center gap-2.5 select-none">
            <div className={`w-2 h-2 rounded-full ${dotColor} animate-pulse-slow`} />
            <span className="text-[9px] font-mono font-bold uppercase tracking-widest opacity-50 text-[var(--foreground)]">{room}</span>
          </div>
        );
      })}
    </div>
  );
}
