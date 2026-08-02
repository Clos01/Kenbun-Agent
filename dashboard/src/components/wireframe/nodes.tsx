"use client";

/**
 * React Flow node renderers.
 *
 * Each node owns its own size. Nothing here is told how big to be, and nothing
 * declares a nominal height that the layout then has to trust — the layout reads
 * the size the browser measured. That single change removes the whole class of
 * bug where a card's declared height and its drawn height disagreed.
 */

import React from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { ComponentTree, screenWidth } from "./ScreenMock";
import { METHOD_COLOR, type WComponent } from "./layout";

const IN = { type: "target" as const, position: Position.Top };
const OUT = { type: "source" as const, position: Position.Bottom };

const dot = "!h-1.5 !w-1.5 !border-0 !bg-secondary/50";

export function ScreenNode({ data }: NodeProps) {
  const d = data as unknown as { label: string; body?: WComponent };
  return (
    <div
      className="overflow-hidden rounded-lg border border-primary/25 bg-card shadow-sm"
      style={{ width: screenWidth(d.body) }}
    >
      <div className="flex items-center gap-2 border-b border-border bg-neutral/60 px-3 py-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-secondary/40" />
        <div className="truncate text-[11px] font-bold uppercase tracking-[0.12em] text-primary">
          {d.label}
        </div>
      </div>
      <div className="p-3">{d.body ? <ComponentTree c={d.body} /> : null}</div>
    </div>
  );
}

export function EndpointNode({ data }: NodeProps) {
  const d = data as unknown as { method: string; path: string; desc?: string; payload?: string };
  const color = METHOD_COLOR[d.method] ?? "#868e96";
  return (
    <div className="w-[320px] overflow-hidden rounded-lg border-2 bg-card shadow-sm" style={{ borderColor: color }}>
      <Handle {...IN} className={dot} />
      <div className="flex items-stretch">
        <div
          className="flex w-16 shrink-0 items-center justify-center text-[10px] font-bold text-white"
          style={{ backgroundColor: color }}
        >
          {d.method}
        </div>
        <div className="min-w-0 flex-1 px-2.5 py-2">
          <div className="truncate font-mono text-[11px] text-primary">{d.path}</div>
          {d.desc && <div className="truncate text-[10px] text-secondary">{d.desc}</div>}
        </div>
      </div>
      {d.payload && (
        <pre className="max-h-40 overflow-hidden border-t border-border bg-neutral/70 px-2.5 py-2 font-mono text-[9px] leading-tight text-secondary">
          {d.payload}
        </pre>
      )}
      <Handle {...OUT} className={dot} />
    </div>
  );
}

export function EntityNode({ data }: NodeProps) {
  const d = data as unknown as { label: string; fields?: string[] };
  return (
    <div className="w-[260px] overflow-hidden rounded-lg border-2 border-[#7048e8] bg-card shadow-sm">
      <Handle {...IN} className={dot} />
      <Handle type="source" position={Position.Right} id="rel-out" className={dot} />
      <Handle type="target" position={Position.Left} id="rel-in" className={dot} />
      <div className="border-b border-[#7048e8]/40 bg-[#7048e8]/12 px-3 py-1.5">
        <div className="truncate text-[11px] font-bold text-primary">{d.label}</div>
      </div>
      <div className="flex flex-col gap-0.5 px-3 py-2">
        {(d.fields ?? []).map((f, i) => (
          <div key={i} className="truncate font-mono text-[10px] text-secondary">
            {f}
          </div>
        ))}
      </div>
      <Handle {...OUT} className={dot} />
    </div>
  );
}

export function IntegrationNode({ data }: NodeProps) {
  const d = data as unknown as { label: string; service?: string };
  return (
    <div className="w-[240px] overflow-hidden rounded-lg border-2 border-[#0ca678] bg-card shadow-sm">
      <Handle {...IN} className={dot} />
      <div className="border-b border-[#0ca678]/40 bg-[#0ca678]/12 px-3 py-1.5">
        <div className="truncate text-[11px] font-bold text-primary">{d.label}</div>
      </div>
      <div className="px-3 py-2">
        <div className="truncate text-[10px] uppercase tracking-wider text-secondary">
          {d.service || "external service"}
        </div>
      </div>
    </div>
  );
}

/** The band behind a layer. Non-interactive and always behind the real nodes, so
 *  it labels the row without ever intercepting a click meant for a card. */
export function BandNode({ data }: NodeProps) {
  const d = data as unknown as { label: string; width: number; height: number };
  return (
    <div
      className="pointer-events-none rounded-xl border border-dashed border-border/70 bg-neutral/30"
      style={{ width: d.width, height: d.height }}
    >
      <div className="px-4 py-2 text-[9px] font-bold uppercase tracking-[0.2em] text-secondary/50">
        {d.label}
      </div>
    </div>
  );
}

export const NODE_TYPES = {
  screen: ScreenNode,
  endpoint: EndpointNode,
  entity: EntityNode,
  integration: IntegrationNode,
  band: BandNode,
};
