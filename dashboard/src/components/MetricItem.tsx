import React from "react";

interface MetricItemProps {
  label: string;
  value: string;
  valueClassName?: string;
  className?: string;
  onClick?: () => void;
  isActive?: boolean;
}

export function MetricItem({ label, value, valueClassName = "", className = "", onClick, isActive = false }: MetricItemProps) {
  const Component = onClick ? "button" : "div";
  return (
    <Component
      onClick={onClick}
      type={onClick ? "button" : undefined}
      className={`p-4 border text-left w-full rounded-md space-y-1 transition-colors ${
        onClick 
          ? "cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--gold)]/50" 
          : ""
      } ${
        isActive 
          ? "border-[var(--gold)] bg-[var(--sand)]/40 shadow-sm" 
          : "border-[var(--border-muted)] bg-[var(--background)]/20 hover:border-[var(--gold)]/40 hover:bg-[var(--background)]/30"
      } ${className}`}
      aria-pressed={onClick ? isActive : undefined}
      aria-label={`${label}: ${value}`}
    >
      <div className="text-[10px] sm:text-xs font-data font-bold uppercase tracking-widest opacity-65 truncate">
        {label}
      </div>
      <div className={`text-lg font-sans font-black truncate ${valueClassName}`} title={value}>
        {value || "—"}
      </div>
    </Component>
  );
}

export default MetricItem;
