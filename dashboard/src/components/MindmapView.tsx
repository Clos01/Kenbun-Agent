"use client";

import React, { useMemo, useRef, useState, useEffect, useCallback } from "react";
import { GitBranch, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

// Self-contained mindmap. Deliberately shares NO layout or edge code with the
// flowchart renderer — it is a strict root -> column -> card TREE, so branches
// never cross and it stays easy to follow no matter how many cards exist.

interface Card {
  id: string;
  listId: string;
  name: string;
  description: string;
  position: number;
  isClosed: boolean;
}
interface List {
  id: string;
  boardId: string;
  name: string;
  position: number;
  type: string;
}
interface MindmapViewProps {
  cards: Card[];
  lists: List[];
  onSelectCard: (cardId: string) => void;
  scale: number;
  setScale: React.Dispatch<React.SetStateAction<number>>;
  offset: { x: number; y: number };
  setOffset: React.Dispatch<React.SetStateAction<{ x: number; y: number }>>;
}

type Status = "todo" | "in_progress" | "blocked" | "completed";
function statusOf(listName: string): Status {
  const n = (listName || "").toLowerCase();
  if (n.includes("in progress")) return "in_progress";
  if (n.includes("blocked")) return "blocked";
  if (n.includes("done") || n.includes("completed")) return "completed";
  return "todo";
}
const DOT: Record<Status, string> = {
  todo: "bg-neutral-400",
  in_progress: "bg-sky-500",
  blocked: "bg-amber-500",
  completed: "bg-emerald-500"
};

// Geometry
const ROOT_W = 152, ROOT_H = 46;
const LIST_W = 178, LIST_H = 34;
const CARD_W = 216, CARD_H = 52;
const ROW = 76, GAP1 = 180, GAP2 = 240;

interface MNode { kind: "root" | "list" | "card"; id: string; name: string; status: Status; cx: number; cy: number; w: number; h: number; }
interface MEdge { id: string; x1: number; y1: number; x2: number; y2: number; }

export default function MindmapView({ cards, lists, onSelectCard, scale, setScale, offset, setOffset }: MindmapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [panning, setPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });

  const model = useMemo(() => {
    const active = cards.filter(c => !c.isClosed);
    const lanes = lists
      .map(l => ({ list: l, cards: active.filter(c => c.listId === l.id) }))
      .filter(x => x.cards.length > 0);

    const nodes: MNode[] = [];
    const edges: MEdge[] = [];

    let slotRight = 0;
    let slotLeft = 0;
    const allCyRight: number[] = [];
    const allCyLeft: number[] = [];

    lanes.forEach(({ list, cards: lc }, laneIdx) => {
      const isRight = laneIdx % 2 === 0;
      
      let slot = isRight ? slotRight : slotLeft;
      if (slot > 0) {
        slot += 1.5; // Add extra vertical spacing between categories
      }
      
      const st = statusOf(list.name);
      const cys: number[] = [];
      const listX = isRight ? (ROOT_W/2 + GAP1) : (-ROOT_W/2 - GAP1 - LIST_W);
      const cardX = isRight ? (listX + LIST_W + GAP2) : (listX - GAP2 - CARD_W);
      
      lc.forEach(card => {
        const cy = slot * ROW;
        slot++;
        cys.push(cy);
        if (isRight) allCyRight.push(cy); else allCyLeft.push(cy);
        nodes.push({ kind: "card", id: card.id, name: card.name, status: st, cx: cardX + CARD_W / 2, cy, w: CARD_W, h: CARD_H });
      });
      
      const listCy = cys.length ? cys.reduce((a, b) => a + b, 0) / cys.length : (slot * ROW);
      const listId = `list_${list.id}`;
      nodes.push({ kind: "list", id: listId, name: list.name.toUpperCase(), status: st, cx: listX + LIST_W / 2, cy: listCy, w: LIST_W, h: LIST_H });
      
      lc.forEach((card, i) => {
        const e1 = isRight ? (listX + LIST_W) : listX;
        const e2 = isRight ? cardX : (cardX + CARD_W);
        edges.push({ id: `${listId}_${card.id}`, x1: e1, y1: listCy, x2: e2, y2: cys[i] });
      });
      
      if (isRight) slotRight = slot; else slotLeft = slot;
    });

    const rootCyRight = allCyRight.length ? allCyRight.reduce((a, b) => a + b, 0) / allCyRight.length : 0;
    const rootCyLeft = allCyLeft.length ? allCyLeft.reduce((a, b) => a + b, 0) / allCyLeft.length : 0;
    const allCyCount = allCyRight.length + allCyLeft.length;
    const rootCy = allCyCount ? ((rootCyRight * allCyRight.length) + (rootCyLeft * allCyLeft.length)) / allCyCount : 0;

    nodes.push({ kind: "root", id: "root", name: "Project Board", status: "todo", cx: 0, cy: rootCy, w: ROOT_W, h: ROOT_H });
    
    lanes.forEach(({ list }, laneIdx) => {
      const isRight = laneIdx % 2 === 0;
      const ln = nodes.find(n => n.id === `list_${list.id}`);
      if (ln) {
        const x1 = isRight ? ROOT_W/2 : -ROOT_W/2;
        const x2 = isRight ? (ROOT_W/2 + GAP1) : (-ROOT_W/2 - GAP1);
        edges.push({ id: `root_list_${list.id}`, x1, y1: rootCy, x2, y2: ln.cy });
      }
    });

    // Normalise so the tree centres on the origin (== container centre).
    nodes.forEach(n => { n.cy -= rootCy; });
    edges.forEach(e => { e.y1 -= rootCy; e.y2 -= rootCy; });

    const totalW = (ROOT_W/2 + GAP1 + LIST_W + GAP2 + CARD_W) * 2;
    const maxCy = Math.max(...allCyRight, ...allCyLeft, 0);
    const minCy = Math.min(...allCyRight, ...allCyLeft, 0);
    const height = (maxCy - minCy) + CARD_H * 2;
    return { nodes, edges, width: totalW, height, empty: lanes.length === 0 };
  }, [cards, lists]);

  const fit = useCallback(() => {
    const el = containerRef.current;
    if (!el) { setScale(0.9); setOffset({ x: 0, y: 0 }); return; }
    const sx = (el.clientWidth - 80) / Math.max(1, model.width);
    const sy = (el.clientHeight - 80) / Math.max(1, model.height);
    setScale(Math.max(0.35, Math.min(1.1, Math.min(sx, sy))));
    setOffset({ x: 0, y: 0 });
  }, [model.width, model.height]);

  useEffect(() => { fit(); }, [fit]);

  // Non-passive wheel zoom so the page never scrolls under the diagram.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const dir = e.deltaY < 0 ? 1 : -1;
      setScale(prev => Math.min(2.4, Math.max(0.3, prev + dir * 0.08)));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const onMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest("[data-node]")) return;
    setPanning(true);
    panStart.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!panning) return;
    setOffset({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y });
  };
  const stop = () => setPanning(false);

  const nodeStyle = (n: MNode): React.CSSProperties => ({
    left: n.cx - n.w / 2,
    top: n.cy - n.h / 2,
    width: n.w,
    height: n.h,
    position: "absolute"
  });

  return (
    <div className="flex-1 flex flex-col overflow-hidden relative">
      {/* Canvas */}
      <div
        ref={containerRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={stop}
        onMouseLeave={stop}
        className={`flex-1 relative overflow-hidden select-none ${panning ? "cursor-grabbing" : "cursor-grab"}`}
        style={{
          backgroundColor: "var(--neutral)",
          backgroundImage: "radial-gradient(var(--border) 1px, transparent 0)",
          backgroundSize: "22px 22px"
        }}
      >
        {model.empty ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center px-8">
            <GitBranch className="w-10 h-10 text-secondary/25" />
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] font-bold text-secondary">No cards to map yet</p>
          </div>
        ) : (
          <div
            className="absolute left-1/2 top-1/2"
            style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`, transformOrigin: "center center" }}
          >
            {/* Branch lines (strict tree — no crossings) */}
            <svg className="absolute overflow-visible pointer-events-none" style={{ left: 0, top: 0, width: 1, height: 1 }}>
              {model.edges.map(e => {
                const mx = (e.x1 + e.x2) / 2;
                const d = `M ${e.x1} ${e.y1} C ${mx} ${e.y1}, ${mx} ${e.y2}, ${e.x2} ${e.y2}`;
                return (
                  <path
                    key={e.id}
                    d={d}
                    fill="none"
                    stroke="var(--tertiary)"
                    strokeOpacity={0.45}
                    strokeWidth={1.75}
                    strokeLinecap="round"
                  />
                );
              })}
            </svg>

            {/* Nodes */}
            {model.nodes.map(n => {
              if (n.kind === "root") {
                return (
                  <div key={n.id} data-node style={nodeStyle(n)}
                    className="flex items-center justify-center rounded-full text-center font-bold text-[10px] tracking-wider uppercase select-none shadow-sm"
                  >
                    <div className="w-full h-full flex items-center justify-center rounded-full px-3"
                      style={{ backgroundColor: "var(--tertiary)", color: "var(--neutral)" }}>
                      {n.name}
                    </div>
                  </div>
                );
              }
              if (n.kind === "list") {
                return (
                  <div key={n.id} data-node style={nodeStyle(n)}
                    className="flex items-center gap-2 rounded-lg border px-3 select-none shadow-sm"
                  >
                    <div className="w-full h-full flex items-center gap-2 rounded-lg border px-3"
                      style={{ backgroundColor: "color-mix(in srgb, var(--tertiary) 12%, var(--card))", borderColor: "color-mix(in srgb, var(--tertiary) 35%, transparent)" }}>
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${DOT[n.status]}`} />
                      <span className="font-mono text-[9px] font-bold uppercase tracking-widest text-primary truncate">{n.name}</span>
                    </div>
                  </div>
                );
              }
              return (
                <div key={n.id} data-node onClick={() => onSelectCard(n.id)} style={nodeStyle(n)}
                  className="rounded-lg border cursor-pointer transition-all hover:scale-[1.02] shadow-sm pointer-events-auto"
                >
                  <div className="w-full h-full flex items-center gap-2 rounded-lg border px-3"
                    style={{ backgroundColor: "var(--card)", borderColor: "var(--border)" }}>
                    <span className={`w-2 h-2 rounded-full shrink-0 ${DOT[n.status]}`} />
                    <span className="text-[10px] font-semibold text-primary leading-snug line-clamp-2">{n.name}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
