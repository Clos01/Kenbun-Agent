import React from 'react';

interface SwarmLegendProps {
  isDragging: boolean;
  counts?: Record<string, number>;
  activeRoom?: string | null;
  onToggleRoom?: (room: string) => void;
}

const ROOMS = ["Central_Logic", "Vault", "Observatory", "Simulations", "Archives"];

const ROOM_DOT: Record<string, { dot: string; glow: string }> = {
  Central_Logic: { dot: "bg-[#B8422E]", glow: "bg-[#B8422E]/40" },
  Vault: { dot: "bg-teal-500", glow: "bg-teal-500/40" },
  Observatory: { dot: "bg-blue-500", glow: "bg-blue-500/40" },
  Simulations: { dot: "bg-indigo-500", glow: "bg-indigo-500/40" },
  Archives: { dot: "bg-amber-500", glow: "bg-amber-500/40" },
};

export default function SwarmLegend({ isDragging, counts, activeRoom, onToggleRoom }: SwarmLegendProps) {
  const anyActive = activeRoom != null;

  return (
    <div
      onMouseDown={(e) => e.stopPropagation()}
      onMouseUp={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
      onTouchStart={(e) => e.stopPropagation()}
      onTouchEnd={(e) => e.stopPropagation()}
      className={`absolute bottom-20 right-4 sm:bottom-8 sm:right-10 z-[100] flex flex-wrap gap-x-2 sm:gap-x-3 gap-y-1.5 max-w-[calc(100%-2rem)] sm:max-w-[320px] justify-end bg-[var(--background)]/85 px-3 py-2 sm:px-4 sm:py-3 border border-[var(--border)]/45 backdrop-blur-2xl shadow-xl transition-opacity duration-300 rounded-xl ${
        isDragging ? 'opacity-20' : 'opacity-100'
      }`}
    >
      {ROOMS.map((room) => {
        const { dot, glow } = ROOM_DOT[room] || ROOM_DOT.Archives;
        const count = counts?.[room] ?? 0;
        const isActive = activeRoom === room;
        const disabled = count === 0;
        const faded = anyActive && !isActive;

        return (
          <button
            key={room}
            type="button"
            disabled={disabled}
            onClick={() => !disabled && onToggleRoom?.(room)}
            title={disabled ? `${room} — no nodes` : isActive ? `Show all rooms` : `Isolate ${room} (${count})`}
            aria-pressed={isActive}
            className={`flex items-center gap-2 select-none rounded-lg px-2 py-1 transition-all ${
              disabled ? 'opacity-25 cursor-default' : 'cursor-pointer hover:bg-[var(--foreground)]/5'
            } ${isActive ? 'ring-1 ring-[var(--accent)]/50 bg-[var(--accent)]/10' : ''} ${faded ? 'opacity-40' : ''}`}
          >
            <div className="relative flex items-center justify-center w-3 h-3">
              {isActive && !disabled && (
                <span className={`absolute inline-flex h-3 w-3 rounded-full ${glow} opacity-75 animate-ping`} />
              )}
              <div className={`relative w-2 h-2 rounded-full ${dot}`} />
            </div>
            <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-[var(--foreground)] opacity-70">{room}</span>
            <span className="text-[9px] font-mono font-bold tabular-nums text-[var(--foreground)]/50">{count.toLocaleString()}</span>
          </button>
        );
      })}
    </div>
  );
}
