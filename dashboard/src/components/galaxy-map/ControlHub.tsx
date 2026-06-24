import React from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Link2, Type } from 'lucide-react';

interface ControlHubProps {
  showConnections: boolean;
  setShowConnections: (val: boolean) => void;
  showLabels: boolean;
  setShowLabels: (val: boolean) => void;
  handleZoom: (factor: number) => void;
  handleRecenter: () => void;
  handleToggleFullscreen: () => void;
  isFullscreen: boolean;
}

export default function ControlHub({
  showConnections,
  setShowConnections,
  showLabels,
  setShowLabels,
  handleZoom,
  handleRecenter,
  handleToggleFullscreen,
  isFullscreen
}: ControlHubProps) {
  return (
    <div 
      onMouseDown={(e) => e.stopPropagation()}
      onMouseUp={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      className="absolute top-8 right-10 z-[100] flex items-center gap-3 select-none p-1.5 bg-[var(--background)]/40 border border-[var(--border)] backdrop-blur-xl rounded-sm shadow-2xl"
    >
      {/* Toggle Constellation Connections */}
      <button
        onClick={() => setShowConnections(!showConnections)}
        title="Toggle Constellation Connections"
        className={`p-2.5 border rounded-sm transition-all duration-200 hover:scale-105 active:scale-95 ${
          showConnections 
            ? 'bg-[var(--accent)] border-[var(--accent)] text-white shadow-[0_0_12px_rgba(244,63,94,0.35)]' 
            : 'border-transparent bg-transparent text-[var(--foreground)] opacity-60 hover:opacity-100 hover:bg-white/[0.05] dark:hover:bg-white/[0.02]'
        }`}
      >
        <Link2 className="w-4 h-4" />
      </button>

      {/* Toggle Signal Labels */}
      <button
        onClick={() => setShowLabels(!showLabels)}
        title="Toggle Signal Labels"
        className={`p-2.5 border rounded-sm transition-all duration-200 hover:scale-105 active:scale-95 ${
          showLabels 
            ? 'bg-[var(--accent)] border-[var(--accent)] text-white shadow-[0_0_12px_rgba(244,63,94,0.35)]' 
            : 'border-transparent bg-transparent text-[var(--foreground)] opacity-60 hover:opacity-100 hover:bg-white/[0.05] dark:hover:bg-white/[0.02]'
        }`}
      >
        <Type className="w-4 h-4" />
      </button>

      <div className="w-[1px] h-4 bg-[var(--border)] mx-1" />

      {/* Zoom In */}
      <button 
        onClick={() => handleZoom(1.3)}
        title="Zoom In"
        className="p-2.5 border border-transparent text-[var(--foreground)] rounded-sm opacity-60 hover:opacity-100 hover:bg-white/[0.05] dark:hover:bg-white/[0.02] hover:text-[var(--accent)] transition-all duration-200 hover:scale-105 active:scale-95"
      >
        <ZoomIn className="w-4 h-4" />
      </button>

      {/* Zoom Out */}
      <button 
        onClick={() => handleZoom(1 / 1.3)}
        title="Zoom Out"
        className="p-2.5 border border-transparent text-[var(--foreground)] rounded-sm opacity-60 hover:opacity-100 hover:bg-white/[0.05] dark:hover:bg-white/[0.02] hover:text-[var(--accent)] transition-all duration-200 hover:scale-105 active:scale-95"
      >
        <ZoomOut className="w-4 h-4" />
      </button>

      {/* Recenter */}
      <button 
        onClick={handleRecenter}
        title="Recenter Map"
        className="p-2.5 border border-transparent text-[var(--foreground)] rounded-sm opacity-60 hover:opacity-100 hover:bg-white/[0.05] dark:hover:bg-white/[0.02] hover:text-[var(--accent)] transition-all duration-200 hover:scale-105 active:scale-95"
      >
        <RotateCcw className="w-4 h-4" />
      </button>

      {/* Fullscreen Toggle */}
      <button 
        onClick={handleToggleFullscreen}
        title="Toggle Fullscreen"
        className="p-2.5 border border-transparent text-[var(--foreground)] rounded-sm opacity-60 hover:opacity-100 hover:bg-white/[0.05] dark:hover:bg-white/[0.02] hover:text-[var(--accent)] transition-all duration-200 hover:scale-105 active:scale-95"
      >
        {isFullscreen ? (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
        ) : (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
        )}
      </button>
    </div>
  );
}
