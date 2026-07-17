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
      className={`absolute bottom-8 right-10 z-[100] flex flex-wrap gap-x-6 gap-y-2 bg-[var(--background)]/75 px-5 py-3 border border-[var(--border)]/45 backdrop-blur-2xl shadow-xl transition-opacity duration-300 rounded-xl ${
        isDragging ? 'opacity-20' : 'opacity-100'
      }`}
    >
      {["Central_Logic", "Vault", "Observatory", "Simulations", "Archives"].map(room => {
        let dotColor = "";
        let glowColor = "";
        if (room === "Central_Logic") {
          dotColor = "bg-[#B8422E]";
          glowColor = "bg-[#B8422E]/40";
        } else if (room === "Vault") {
          dotColor = "bg-teal-500";
          glowColor = "bg-teal-500/40";
        } else if (room === "Observatory") {
          dotColor = "bg-blue-500";
          glowColor = "bg-blue-500/40";
        } else if (room === "Simulations") {
          dotColor = "bg-indigo-500";
          glowColor = "bg-indigo-500/40";
        } else {
          dotColor = "bg-amber-500";
          glowColor = "bg-amber-500/40";
        }
 
        return (
          <div key={room} className="flex items-center gap-3 select-none">
            <div className="relative flex items-center justify-center w-3 h-3">
              <span className={`absolute inline-flex h-3 w-3 rounded-full ${glowColor} opacity-75 animate-ping`} />
              <div className={`relative w-2 h-2 rounded-full ${dotColor}`} />
            </div>
            <span className="text-[9px] font-mono font-bold uppercase tracking-widest opacity-60 text-[var(--foreground)]">{room}</span>
          </div>
        );
      })}
    </div>
  );
}
