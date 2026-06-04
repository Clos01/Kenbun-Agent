import React from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Link2 } from 'lucide-react';

interface ControlHubProps {
  showConnections: boolean;
  setShowConnections: (val: boolean) => void;
  handleZoom: (factor: number) => void;
  handleRecenter: () => void;
  handleToggleFullscreen: () => void;
  isFullscreen: boolean;
}

export default function ControlHub({
  showConnections,
  setShowConnections,
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
      className="absolute top-8 right-10 z-[100] flex items-center gap-3 select-none"
    >
      {/* Toggle Constellation Connections */}
      <button
        onClick={() => setShowConnections(!showConnections)}
        title="Toggle Constellation Connections"
        className={`p-2.5 border rounded-sm transition-all duration-300 backdrop-blur-xl ${
          showConnections 
            ? 'bg-[var(--accent)] border-[var(--accent)] text-white' 
            : 'border-[var(--border)] bg-[var(--background)]/90 text-[var(--foreground)] opacity-60 hover:opacity-100'
        }`}
      >
        <Link2 className="w-4 h-4" />
      </button>

      {/* Zoom In */}
      <button 
        onClick={() => handleZoom(1.3)}
        title="Zoom In"
        className="p-2.5 border border-[var(--border)] bg-[var(--background)]/90 text-[var(--foreground)] rounded-sm hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all duration-300 backdrop-blur-xl"
      >
        <ZoomIn className="w-4 h-4" />
      </button>

      {/* Zoom Out */}
      <button 
        onClick={() => handleZoom(1 / 1.3)}
        title="Zoom Out"
        className="p-2.5 border border-[var(--border)] bg-[var(--background)]/90 text-[var(--foreground)] rounded-sm hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all duration-300 backdrop-blur-xl"
      >
        <ZoomOut className="w-4 h-4" />
      </button>

      {/* Recenter */}
      <button 
        onClick={handleRecenter}
        title="Recenter Map"
        className="p-2.5 border border-[var(--border)] bg-[var(--background)]/90 text-[var(--foreground)] rounded-sm hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all duration-300 backdrop-blur-xl"
      >
        <RotateCcw className="w-4 h-4" />
      </button>

      {/* Fullscreen Toggle */}
      <button 
        onClick={handleToggleFullscreen}
        title="Toggle Fullscreen"
        className="p-2.5 border border-[var(--border)] bg-[var(--background)]/90 text-[var(--foreground)] rounded-sm hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all duration-300 backdrop-blur-xl"
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
