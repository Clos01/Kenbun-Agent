"use client";

import React, { useState, useMemo, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { 
  X, 
  Plus,
  GitBranch,
  Copy,
  ChevronRight,
  ChevronDown,
  Layout,
  RefreshCw,
  Trash2,
  FileText,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Settings,
  Square,
  Diamond
} from "lucide-react";
import { parseCardMetadata, injectCardMetadata, KenbunMetadata } from "../app/board/page";
import { computeWorkOrder } from "../lib/prioritize";
import { useTheme } from "../context/ThemeContext";
import MindmapView from "./MindmapView";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const decodeHtmlEntities = (text: string) => {
  return text
    .replace(/&#039;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
};

const markdownComponents: any = {
  p: ({ children }: any) => <p className="mb-2 text-[10px] text-secondary leading-relaxed">{children}</p>,
  h1: ({ children }: any) => <h1 className="mb-2 text-xs font-bold text-primary mt-4">{children}</h1>,
  h2: ({ children }: any) => <h2 className="mb-2 text-[11px] font-bold text-primary mt-3">{children}</h2>,
  h3: ({ children }: any) => <h3 className="mb-1 text-[10px] font-bold text-primary mt-2">{children}</h3>,
  ul: ({ children }: any) => <ul className="list-disc pl-4 mb-2 space-y-1 text-[10px] text-secondary">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal pl-4 mb-2 space-y-1 text-[10px] text-secondary">{children}</ol>,
  li: ({ children }: any) => <li>{children}</li>,
  strong: ({ children }: any) => <strong className="font-bold text-primary">{children}</strong>,
  em: ({ children }: any) => <em className="italic text-secondary/80">{children}</em>,
  code: ({ children }: any) => <code className="bg-card text-tertiary px-1 py-0.5 rounded text-[9px] font-mono">{children}</code>,
  a: ({ href, children }: any) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-tertiary hover:underline">{children}</a>,
};

interface Card {
  id: string;
  listId: string;
  name: string;
  description: string;
  position: number;
  isClosed: boolean;
  dueDate?: string;
  listChangedAt?: string;
}

interface List {
  id: string;
  boardId: string;
  name: string;
  position: number;
  type: string;
}

interface WorkflowViewProps {
  cards: Card[];
  lists: List[];
  onOpenCard: (card: Card) => void;
  onUpdateCardDesc: (cardId: string, newDescription: string) => Promise<void>;
  onCreateCard: (name: string, listId: string, x: number, y: number) => Promise<void>;
  onDeleteCard: (cardId: string) => Promise<void>;
}

type ShapeType = "process" | "decision" | "terminal";
type LayoutDir = "TD" | "LR";

// ── Mindmap spacing guard ─────────────────────────────────────────────
// Mermaid's mindmap uses the cose-bilkent force layout, whose only config
// lever (padding) grows the bubbles instead of reliably widening the GAPS
// between them — so crowded mindmaps are a recurring problem. This is the
// single source of truth that fixes it: every rendered mindmap is passed
// through spaceOutMindmapNodes(), which shrinks each node in place so the
// bubbles sit further apart with more breathing room. Raise the factor for
// more air; lower it toward 1 for tighter. Because it runs on EVERY mindmap
// render (see the render effect), future mindmaps can never come out cramped.
const MINDMAP_SPACING_FACTOR = 1.28; // > 1 = more space between bubbles

function spaceOutMindmapNodes(svgEl: Element, factor: number): void {
  if (!(factor > 1)) return;
  const shrink = (1 / factor).toFixed(4);
  svgEl.querySelectorAll(".mindmap-node").forEach((node) => {
    const t = node.getAttribute("transform") || "";
    // Idempotent: never stack a second scale() on an already-processed node.
    if (t.includes("scale(")) return;
    node.setAttribute("transform", `${t} scale(${shrink})`.trim());
  });
}

function CustomSelect<T extends string>({
  value,
  onChange,
  options,
  label
}: {
  value: T;
  onChange: (val: T) => void;
  options: { value: T; label: string }[];
  label?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; right: number } | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // The toolbar lives inside an overflow-hidden container, so an absolutely
  // positioned menu gets clipped. Render it in a body portal with fixed
  // coordinates measured from the trigger so it's never cut off.
  const reposition = () => {
    const r = triggerRef.current?.getBoundingClientRect();
    if (r) setCoords({ top: r.bottom + 6, right: Math.max(8, window.innerWidth - r.right) });
  };

  const toggle = () => {
    if (!isOpen) reposition();
    setIsOpen(v => !v);
  };

  useEffect(() => {
    if (!isOpen) return;
    function onPointerDown(event: MouseEvent) {
      const t = event.target as Node;
      if (triggerRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setIsOpen(false);
    }
    // Reposition on layout shifts; close on scroll to avoid a detached menu.
    function onResize() { reposition(); }
    function onScroll() { setIsOpen(false); }
    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [isOpen]);

  const activeOption = options.find(o => o.value === value);

  return (
    <div className="relative inline-block text-left" ref={triggerRef}>
      <div className="flex items-center gap-1.5 bg-primary/[0.04] border border-border rounded-md px-2.5 py-1.5 hover:border-tertiary/30 transition-colors">
        {label && (
          <span className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
            {label}:
          </span>
        )}
        <button
          type="button"
          onClick={toggle}
          className="bg-transparent text-[9px] font-mono text-primary font-bold uppercase focus:outline-none cursor-pointer flex items-center gap-1 hover:text-primary transition-colors"
        >
          <span>{activeOption?.label || value}</span>
          <ChevronDown className="w-3 h-3 ml-0.5 opacity-60" />
        </button>
      </div>

      {typeof document !== "undefined" && createPortal(
        <AnimatePresence>
          {isOpen && coords && (
            <motion.div
              ref={menuRef}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.1 }}
              className="fixed origin-top-right rounded-lg border shadow-xl focus:outline-none overflow-hidden"
              style={{
                top: coords.top,
                right: coords.right,
                minWidth: "9rem",
                zIndex: 60,
                backgroundColor: "var(--card)",
                borderColor: "var(--border)"
              }}
            >
              <div className="py-1">
                {options.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      onChange(opt.value);
                      setIsOpen(false);
                    }}
                    className={`block w-full text-left px-3 py-2 text-[9px] font-mono font-bold uppercase tracking-wider whitespace-nowrap hover:bg-primary/5 cursor-pointer ${
                      opt.value === value ? "text-tertiary bg-tertiary/[0.06]" : "text-secondary hover:text-primary"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}

interface LayoutNode {
  id: string;
  type: "root" | "list" | "card";
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  status?: string;
  rank?: number;
  shape?: ShapeType;
  cardData?: any;
}

interface LayoutEdge {
  id: string;
  fromId: string;
  toId: string;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  orientation?: "horizontal" | "vertical";
  label?: string;
  style?: "dotted" | "solid";
}

function getStatusColorClass(status: string) {
  if (status === "completed") return "bg-emerald-500";
  if (status === "in_progress") return "bg-sky-500";
  if (status === "blocked") return "bg-amber-500";
  return "bg-neutral-500";
}

function getStatusText(status: string) {
  if (status === "completed") return "Completed";
  if (status === "in_progress") return "In Progress";
  if (status === "blocked") return "Blocked";
  return "To Do";
}

function getCardIcons(card: any) {
  const icons = [];
  if (card.description && card.description.trim().length > 0) {
    icons.push(<span key="desc" title="Has Description">📝</span>);
  }
  if (card.metadata.recurring && card.metadata.recurring !== "none") {
    icons.push(<span key="rec" title="Recurring task">🔁</span>);
  }
  if (card.metadata.location) {
    icons.push(<span key="loc" title="Has Location">📍</span>);
  }
  if (card.metadata.collections && card.metadata.collections.length > 0) {
    icons.push(<span key="tags" title="Has Collections">🏷️</span>);
  }
  return icons;
}

export default function WorkflowView({
  cards,
  lists,
  onOpenCard,
  onUpdateCardDesc,
  onCreateCard,
  onDeleteCard
}: WorkflowViewProps) {
  const { preset } = useTheme();
  const [layoutDir, setLayoutDir] = useState<LayoutDir>("LR");
  const [svgCode, setSvgCode] = useState<string>("");
  const [isRendering, setIsRendering] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [groupByLanes, setGroupByLanes] = useState<boolean>(true);
  const [lineStyle, setLineStyle] = useState<"basis" | "step" | "linear">("basis");
  const [diagramMode, setDiagramMode] = useState<"flowchart" | "mindmap" | "ascii">("flowchart");
  const [showSuggestedPath, setShowSuggestedPath] = useState<boolean>(true);
  const [showViewSettings, setShowViewSettings] = useState<boolean>(false);

  const canvasRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState<number>(1);
  const [offset, setOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const mermaidThemeStyles = useMemo(() => {
    return {
      completed: "fill:none,stroke:none,stroke-width:0px",
      in_progress: "fill:none,stroke:none,stroke-width:0px",
      blocked: "fill:none,stroke:none,stroke-width:0px",
      todo: "fill:none,stroke:none,stroke-width:0px"
    };
  }, []);

  // Selector / Modal states
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const [isAddingStep, setIsAddingStep] = useState<boolean>(false);
  const [newCardName, setNewCardName] = useState<string>("");
  const [newCardListId, setNewCardListId] = useState<string>(lists[0]?.id || "");
  const [newCardShape, setNewCardShape] = useState<ShapeType>("process");
  
  // Sidebar toggles
  const [activeSidebarTab, setActiveSidebarTab] = useState<"details" | "code">("details");

  const listMap = useMemo(() => {
    return new Map(lists.map(l => [l.id, l]));
  }, [lists]);

  // Compute Priority ranks & scores using prioritization model
  const workOrder = useMemo(() => {
    return computeWorkOrder(cards, lists);
  }, [cards, lists]);

  // Parse metadata layout, shape & dependencies for each card
  const parsedCards = useMemo(() => {
    return cards
      .filter(c => !c.isClosed)
      .map(card => {
        const { cleanDescription, metadata } = parseCardMetadata(card.description);
        const list = listMap.get(card.listId);
        const listName = list ? list.name.toLowerCase() : "";
        
        let status: "todo" | "in_progress" | "blocked" | "completed" = "todo";
        if (listName.includes("in progress")) status = "in_progress";
        else if (listName.includes("blocked")) status = "blocked";
        else if (listName.includes("done") || listName.includes("completed")) status = "completed";

        // Logic check: shape type (check metadata, fallback to keywords)
        let shape: ShapeType = "process";
        if (metadata.shape) {
          shape = metadata.shape as ShapeType;
        } else {
          const isGate = 
            card.name.toLowerCase().startsWith("gate:") || 
            card.name.toLowerCase().startsWith("decision:") || 
            card.name.toLowerCase().includes("gate") || 
            card.name.toLowerCase().includes("audit") || 
            card.name.toLowerCase().includes("check") ||
            card.name.toLowerCase().includes("decision");

          const isTerminal = 
            card.name.toLowerCase().startsWith("start:") || 
            card.name.toLowerCase().startsWith("end:") || 
            card.name.toLowerCase().includes("milestone") ||
            status === "completed" && card.name.toLowerCase().includes("done");

          if (isGate) shape = "decision";
          else if (isTerminal) shape = "terminal";
        }

        return {
          ...card,
          cleanDescription,
          metadata,
          dependencies: metadata.dependencies || [],
          linkLabels: metadata.linkLabels || {},
          shape,
          status,
          score: workOrder?.score?.get(card.id) || 0,
          rank: workOrder?.rank?.get(card.id) || 999,
          blocked: workOrder?.blocked?.has?.(card.id) || false
        };
      });
  }, [cards, listMap, workOrder]);

  const parsedCardMap = useMemo(() => {
    return new Map(parsedCards.map(c => [c.id, c]));
  }, [parsedCards]);

  const nextStepCardId = useMemo(() => {
    // "Next" must be dependency-ready (not blocked) so we never point the user
    // at something they can't actually start.
    const inProgressCards = parsedCards
      .filter(c => c.status === "in_progress" && !c.blocked)
      .sort((a, b) => a.rank - b.rank);
    if (inProgressCards.length > 0) return inProgressCards[0].id;

    const todoCards = parsedCards
      .filter(c => c.status === "todo" && !c.blocked)
      .sort((a, b) => a.rank - b.rank);
    if (todoCards.length > 0) return todoCards[0].id;

    return null;
  }, [parsedCards]);

  const layout = useMemo(() => {
    const nodes: LayoutNode[] = [];
    const edges: LayoutEdge[] = [];
    const lanes: { id: string; name: string; minX: number; maxX: number; minY: number; maxY: number }[] = [];

    // Mindmap is rendered by its own dedicated <MindmapView> component and does
    // NOT share this layout engine — the shared code made it hectic to follow.
    if (diagramMode === "flowchart") {
      const isHorizontal = layoutDir === "LR";
      // Spacing constants – tighter for compact readability
      const COL_GAP = 320;   // horizontal column spacing (LR mode)
      const CARD_V_GAP = 220; // vertical gap between cards in same column
      const ROW_GAP = 280;   // vertical row spacing (TD mode)
      const CARD_H_GAP = 280; // horizontal gap between cards in same row
      const CARD_W = 190;
      const CARD_H = 85;

      const MAX_PER_LINE = 5;

      let groups: { id: string; name: string; cards: typeof parsedCards }[] = [];

      if (groupByLanes) {
        groups = lists.map(list => ({
          id: list.id,
          name: list.name,
          cards: parsedCards.filter(c => c.listId === list.id).sort((a, b) => a.rank - b.rank)
        }));
      } else {
        const cardLevels = new Map<string, number>();
        parsedCards.forEach(c => cardLevels.set(c.id, 0));

        for (let pass = 0; pass < 10; pass++) {
          let changed = false;
          parsedCards.forEach(card => {
            let maxDepLevel = -1;
            card.dependencies.forEach(depId => {
              if (cardLevels.has(depId)) {
                maxDepLevel = Math.max(maxDepLevel, cardLevels.get(depId)!);
              }
            });
            if (maxDepLevel >= 0) {
              const newLevel = maxDepLevel + 1;
              if (cardLevels.get(card.id) !== newLevel) {
                cardLevels.set(card.id, newLevel);
                changed = true;
              }
            }
          });
          if (!changed) break;
        }

        const levelCardsMap = new Map<number, typeof parsedCards>();
        parsedCards.forEach(card => {
          const lvl = cardLevels.get(card.id) || 0;
          if (!levelCardsMap.has(lvl)) levelCardsMap.set(lvl, []);
          levelCardsMap.get(lvl)!.push(card);
        });

        const activeLevels = Array.from(levelCardsMap.keys()).sort((a, b) => a - b);
        groups = activeLevels.map(lvl => ({
          id: `level_${lvl}`,
          name: `Level ${lvl}`,
          cards: levelCardsMap.get(lvl)!.sort((a, b) => a.rank - b.rank)
        }));
      }

      const groupLayouts = groups.map(g => {
        const C = g.cards.length;
        const numLines = Math.ceil(C / MAX_PER_LINE);
        const maxInLine = Math.min(C, MAX_PER_LINE);
        
        let w = 0;
        let h = 0;
        if (isHorizontal) {
           w = numLines * CARD_W + Math.max(0, numLines - 1) * 60; // 60px gap between wrapped columns
           h = maxInLine * CARD_H + Math.max(0, maxInLine - 1) * CARD_V_GAP;
        } else {
           w = maxInLine * CARD_W + Math.max(0, maxInLine - 1) * CARD_H_GAP;
           h = numLines * CARD_H + Math.max(0, numLines - 1) * 60; // 60px gap between wrapped rows
        }
        return { ...g, w, h, numLines, maxInLine };
      });

      const GAP_BETWEEN_GROUPS = isHorizontal ? COL_GAP : ROW_GAP;
      let totalSpan = 0;
      groupLayouts.forEach(g => {
        totalSpan += (isHorizontal ? g.w : g.h);
      });
      totalSpan += Math.max(0, groupLayouts.length - 1) * GAP_BETWEEN_GROUPS;

      let currentOffset = -totalSpan / 2;

      groupLayouts.forEach(g => {
         if (isHorizontal) {
            const groupLeft = currentOffset;
            const groupTop = -g.h / 2;
            
            if (g.cards.length > 0 && groupByLanes) {
              lanes.push({
                id: g.id, name: g.name,
                minX: groupLeft - 30, maxX: groupLeft + g.w + 30,
                minY: groupTop - 60, maxY: groupTop + g.h + 30
              });
            }

            g.cards.forEach((card, i) => {
               const localCol = Math.floor(i / MAX_PER_LINE);
               const localRow = i % MAX_PER_LINE;
               const cx = groupLeft + localCol * (CARD_W + 60) + CARD_W / 2;
               const cy = groupTop + localRow * (CARD_H + CARD_V_GAP) + CARD_H / 2;
               nodes.push({
                 id: `card_${card.id}`, type: "card", label: card.name,
                 x: cx - CARD_W / 2, y: cy - CARD_H / 2,
                 width: CARD_W, height: CARD_H,
                 status: card.status, rank: card.rank, shape: card.shape, cardData: card
               });
            });
            currentOffset += g.w + GAP_BETWEEN_GROUPS;
         } else {
            const groupTop = currentOffset;
            const groupLeft = -g.w / 2;

            if (g.cards.length > 0 && groupByLanes) {
              lanes.push({
                id: g.id, name: g.name,
                minX: groupLeft - 30, maxX: groupLeft + g.w + 30,
                minY: groupTop - 60, maxY: groupTop + g.h + 30
              });
            }

            g.cards.forEach((card, i) => {
               const localRow = Math.floor(i / MAX_PER_LINE);
               const localCol = i % MAX_PER_LINE;
               const cx = groupLeft + localCol * (CARD_W + CARD_H_GAP) + CARD_W / 2;
               const cy = groupTop + localRow * (CARD_H + 60) + CARD_H / 2;
               nodes.push({
                 id: `card_${card.id}`, type: "card", label: card.name,
                 x: cx - CARD_W / 2, y: cy - CARD_H / 2,
                 width: CARD_W, height: CARD_H,
                 status: card.status, rank: card.rank, shape: card.shape, cardData: card
               });
            });
            currentOffset += g.h + GAP_BETWEEN_GROUPS;
         }
      });

      const nodeMap = new Map(nodes.map(n => [n.id, n]));

      // Smart anchor point selection based on layout constraints
      const getAnchors = (from: LayoutNode, to: LayoutNode): { fx: number, fy: number, tx: number, ty: number, orientation: "horizontal" | "vertical" } => {
        const isHorizontalLayout = layoutDir === "LR";
        
        const fcx = from.x + from.width / 2;
        const fcy = from.y + from.height / 2;
        const tcx = to.x + to.width / 2;
        const tcy = to.y + to.height / 2;
        
        let connectHorizontal = false;
        if (isHorizontalLayout) {
          // Cross-lane connections have different X coordinates
          connectHorizontal = Math.abs(from.x - to.x) > 10;
        } else {
          // Cross-lane connections have different Y coordinates
          connectHorizontal = Math.abs(from.y - to.y) <= 10;
        }

        if (connectHorizontal) {
          if (tcx > fcx) {
            return { fx: from.x + from.width, fy: fcy, tx: to.x, ty: tcy, orientation: "horizontal" };
          } else {
            return { fx: from.x, fy: fcy, tx: to.x + to.width, ty: tcy, orientation: "horizontal" };
          }
        } else {
          if (tcy > fcy) {
            return { fx: fcx, fy: from.y + from.height, tx: tcx, ty: to.y, orientation: "vertical" };
          } else {
            return { fx: fcx, fy: from.y, tx: tcx, ty: to.y + to.height, orientation: "vertical" };
          }
        }
      };
      // 1) Draw manual dependency edges ALWAYS
      parsedCards.forEach(card => {
        const toNode = nodeMap.get(`card_${card.id}`);
        if (!toNode) return;

        card.dependencies.forEach(depId => {
          const fromNode = nodeMap.get(`card_${depId}`);
          if (!fromNode) return;

          const label = card.linkLabels?.[depId];
          const a = getAnchors(fromNode, toNode);

          edges.push({
            id: `edge_${depId}_to_${card.id}`,
            fromId: fromNode.id,
            toId: toNode.id,
            fromX: a.fx, fromY: a.fy,
            toX: a.tx, toY: a.ty,
            orientation: a.orientation,
            label,
            style: "solid"
          });
        });
      });

      // 2) Draw suggested flow (dotted lines) if toggled on
      if (showSuggestedPath) {
        if (groupByLanes) {
          // Intra-lane connections (connecting items sequentially inside each lane)
          groups.forEach(group => {
            const laneCards = group.cards.filter(c => c.status !== "completed");
            for (let i = 0; i < laneCards.length - 1; i++) {
              const fromNode = nodeMap.get(`card_${laneCards[i].id}`);
              const toNode = nodeMap.get(`card_${laneCards[i + 1].id}`);
              if (fromNode && toNode) {
                const a = getAnchors(fromNode, toNode);
                edges.push({
                  id: `edge_lane_${laneCards[i].id}_to_${laneCards[i + 1].id}`,
                  fromId: fromNode.id,
                  toId: toNode.id,
                  fromX: a.fx, fromY: a.fy,
                  toX: a.tx, toY: a.ty,
                  orientation: a.orientation,
                  label: "suggested",
                  style: "dotted"
                });
              }
            }
          });

          // Cross-lane connections
          const laneLastCards: { groupId: string; card: typeof parsedCards[0] }[] = [];
          groups.forEach(group => {
            const laneCards = group.cards.filter(c => c.status !== "completed");
            if (laneCards.length > 0) {
              laneLastCards.push({ groupId: group.id, card: laneCards[laneCards.length - 1] });
            }
          });

          for (let i = 0; i < laneLastCards.length - 1; i++) {
            const fromNode = nodeMap.get(`card_${laneLastCards[i].card.id}`);
            const nextLaneFirstCards = groups.find(g => g.id === laneLastCards[i + 1].groupId)?.cards.filter(c => c.status !== "completed") || [];
            if (nextLaneFirstCards.length === 0) continue;
            
            const toNode = nodeMap.get(`card_${nextLaneFirstCards[0].id}`);
            if (fromNode && toNode) {
              const a = getAnchors(fromNode, toNode);
              edges.push({
                id: `edge_crosslane_${laneLastCards[i].card.id}_to_${nextLaneFirstCards[0].id}`,
                fromId: fromNode.id,
                toId: toNode.id,
                fromX: a.fx, fromY: a.fy,
                toX: a.tx, toY: a.ty,
                orientation: a.orientation,
                label: "suggested",
                style: "dotted"
              });
            }
          }
        } else {
          // No lanes: connect all active cards sequentially by rank across the board
          const activeSequence = parsedCards
            .filter(c => c.status !== "completed")
            .sort((a, b) => a.rank - b.rank);

          for (let i = 0; i < activeSequence.length - 1; i++) {
            const fromNode = nodeMap.get(`card_${activeSequence[i].id}`);
            const toNode = nodeMap.get(`card_${activeSequence[i + 1].id}`);
            if (fromNode && toNode) {
              const a = getAnchors(fromNode, toNode);
              edges.push({
                id: `edge_suggested_${activeSequence[i].id}_to_${activeSequence[i + 1].id}`,
                fromId: fromNode.id,
                toId: toNode.id,
                fromX: a.fx, fromY: a.fy,
                toX: a.tx, toY: a.ty,
                orientation: a.orientation,
                label: "suggested",
                style: "dotted"
              });
            }
          }
        }
      }
    }

    return { nodes, edges, lanes };
  }, [parsedCards, lists, diagramMode, groupByLanes, showSuggestedPath, layoutDir]);

  // Mindmap code builder
  const mindmapCode = useMemo(() => {
    // Strip characters that break Mermaid mindmap parsing, collapse whitespace.
    const clean = (s: string) => s.replace(/[^A-Za-z0-9 .\-]/g, " ").replace(/\s+/g, " ").trim();
    const trunc = (s: string) => (s.length > 30 ? `${s.slice(0, 29).trim()}...` : s);

    const lines: string[] = [];
    lines.push("mindmap");
    lines.push("  root((Project Board))");

    lists.forEach(list => {
      const listCards = parsedCards
        .filter(c => c.listId === list.id)
        .sort((a, b) => a.rank - b.rank);
      if (listCards.length > 0) {
        // Branch = column (square chip); leaves = cards (rounded chips). Giving
        // leaves an explicit shape lets us style them as clean themed chips.
        const branch = clean(list.name).toUpperCase() || "LANE";
        lines.push(`    [${branch}]`);
        listCards.forEach(card => {
          const leaf = trunc(clean(card.name)) || "Untitled";
          lines.push(`      (${leaf})`);
        });
      }
    });

    return lines.join("\n");
  }, [parsedCards, lists]);

  // ASCII Grid diagram builder
  const asciiGridCode = useMemo(() => {
    const cols: string[][] = [];
    const maxCards = Math.max(...lists.map(list => parsedCards.filter(c => c.listId === list.id).length), 0);
    
    lists.forEach(list => {
      const listCards = parsedCards.filter(c => c.listId === list.id);
      const colLines: string[] = [];
      
      const borderTop = "╭──────────────────────╮";
      const headerText = `│  ${list.name.toUpperCase().padEnd(18).substring(0, 18)}  │`;
      const borderBot = "╰──────────────────────╯";
      colLines.push(borderTop);
      colLines.push(headerText);
      colLines.push(borderBot);
      colLines.push("                        ");
      
      listCards.forEach(card => {
        const cleanName = card.name.replace(/[\r\n\t]/g, " ");
        const titleLine = `│ [#${card.rank}] ${cleanName.padEnd(14).substring(0, 14)} │`;
        const scoreLine = `│ Priority: ${String(card.score).padEnd(10).substring(0, 10)} │`;
        colLines.push("╭──────────────────────╮");
        colLines.push(titleLine);
        colLines.push(scoreLine);
        colLines.push("╰──────────────────────╯");
        colLines.push("                        ");
      });
      
      const targetLinesCount = 4 + maxCards * 5;
      while (colLines.length < targetLinesCount) {
        colLines.push("                        ");
      }
      
      cols.push(colLines);
    });
    
    const combinedLines: string[] = [];
    if (cols.length > 0) {
      const lineCount = cols[0].length;
      for (let i = 0; i < lineCount; i++) {
        combinedLines.push(cols.map(c => c[i]).join("    "));
      }
    }
    
    combinedLines.push("");
    combinedLines.push("CONNECTIONS / DEPENDENCIES:");
    combinedLines.push("===========================");
    let hasConnections = false;
    parsedCards.forEach(card => {
      card.dependencies.forEach(depId => {
        const depCard = parsedCardMap.get(depId);
        if (depCard) {
          const label = card.linkLabels?.[depId];
          const labelStr = label ? ` [${label}]` : "";
          combinedLines.push(`  ${depCard.name} -------->${labelStr} --------> ${card.name}`);
          hasConnections = true;
        }
      });
    });
    if (!hasConnections) {
      combinedLines.push("  (No relationships defined. Select nodes to link steps)");
    }
    
    return combinedLines.join("\n");
  }, [parsedCards, lists, parsedCardMap]);

  const selectedCard = useMemo(() => {
    if (!selectedCardId) return null;
    return parsedCardMap.get(selectedCardId) || null;
  }, [selectedCardId, parsedCardMap]);

  const hasInitialFit = useRef<boolean>(false);

  // Auto-fit: compute bounding box of all nodes and scale/offset to fit canvas
  useEffect(() => {
    if (layout.nodes.length === 0 || !canvasRef.current) return;
    if (hasInitialFit.current) return; // Only fit on the first meaningful load
    
    const el = canvasRef.current;
    const cw = el.clientWidth;
    const ch = el.clientHeight;
    if (cw === 0 || ch === 0) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    layout.nodes.forEach(n => {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + n.width);
      maxY = Math.max(maxY, n.y + n.height);
    });

    const diagramW = maxX - minX;
    const diagramH = maxY - minY;
    if (diagramW === 0 || diagramH === 0) return;

    const PADDING = 80; // px padding around diagram
    const fitScaleX = (cw - PADDING * 2) / diagramW;
    const fitScaleY = (ch - PADDING * 2) / diagramH;
    const fitScale = Math.min(fitScaleX, fitScaleY, 1.2); // cap at 120% zoom
    const clampedScale = Math.max(0.25, Math.min(fitScale, 1.2));

    // Center the diagram in the viewport
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    setScale(clampedScale);
    setOffset({
      x: -centerX * clampedScale,
      y: -centerY * clampedScale
    });
    hasInitialFit.current = true;
  }, [layout]);

  // Bind click callback globally for Mermaid nodes
  useEffect(() => {
    (window as unknown as Record<string, unknown>).onMermaidNodeClick = (nodeId: string) => {
      const cleanId = nodeId.replace("c_", "");
      setSelectedCardId(cleanId);
    };
    return () => {
      const w = window as unknown as Record<string, unknown>;
      delete w.onMermaidNodeClick;
    };
  }, []);

  // Generate Mermaid Chart Source Code
  const mermaidCode = useMemo(() => {
    const lines: string[] = [];
    lines.push(`graph ${layoutDir}`);
    lines.push("  %% Theme Styles");
    lines.push(`  classDef completed ${mermaidThemeStyles.completed},font-size:10.5px;`);
    lines.push(`  classDef in_progress ${mermaidThemeStyles.in_progress},font-size:10.5px;`);
    lines.push(`  classDef blocked ${mermaidThemeStyles.blocked},font-size:10.5px;`);
    lines.push(`  classDef todo ${mermaidThemeStyles.todo},font-size:10.5px;`);
    lines.push("");

    // Group cards inside subgraphs matching their parent Planka status lists
    if (groupByLanes) {
      lists.forEach(list => {
        const listCards = parsedCards.filter(c => c.listId === list.id);
        if (listCards.length > 0) {
          // Use unquoted identifiers for subgraphs to avoid Mermaid parse errors
          lines.push(`  subgraph lane_${list.id} ["${list.name}"]`);
          listCards.forEach(card => {
            lines.push(`    c_${card.id}`);
          });
          lines.push("  end");
        }
      });
      lines.push("");
    }

    // Declare shapes as rich visual HTML labels
    parsedCards.forEach(card => {
      // Escape title special characters
      const cleanTitle = card.name.replace(/"/g, "'");
      const id = `c_${card.id}`;
      const isNextStep = card.id === nextStepCardId;
      
      // Determine status display values
      let statusColor = "bg-neutral-500";
      let statusText = "To Do";
      if (card.status === "completed") {
        statusColor = "bg-emerald-500";
        statusText = "Completed";
      } else if (card.status === "in_progress") {
        statusColor = "bg-sky-500";
        statusText = "In Progress";
      } else if (card.status === "blocked") {
        statusColor = "bg-amber-500";
        statusText = "Blocked";
      }

      // Build metadata icon indicators
      const icons: string[] = [];
      if (card.description && card.description.trim().length > 0) {
        icons.push("📝");
      }
      if (card.metadata.recurring && card.metadata.recurring !== "none") {
        icons.push("🔁");
      }
      if (card.metadata.location) {
        icons.push("📍");
      }
      if (card.metadata.collections && card.metadata.collections.length > 0) {
        icons.push("🏷️");
      }
      const iconsHtml = icons.length > 0 
        ? `<div class='flex items-center gap-1 opacity-70'>${icons.join("")}</div>` 
        : "";

      const highlightStyles = isNextStep 
        ? "border-color: var(--tertiary); box-shadow: 0 0 10px var(--tertiary); border-width: 1.5px;" 
        : "border-color: var(--border);";
      
      const badgeHtml = isNextStep
        ? `<span class='text-[7.5px] font-mono px-1 py-0.5 rounded text-neutral bg-tertiary font-bold animate-pulse' style='background-color: var(--tertiary); color: var(--neutral);'>👉 NEXT</span>`
        : `<span class='text-[7.5px] font-mono px-1 py-0.5 rounded text-secondary' style='background-color: var(--neutral); color: var(--secondary);'>#${card.rank}</span>`;

      // Construct a premium card component HTML string based on shape type
      let htmlLabel = "";
      if (card.shape === "terminal") {
        // Pill-shaped terminal node
        htmlLabel = `
          <div class='px-4 py-2.5 rounded-full border bg-card text-left transition-all hover:scale-[1.02] shadow-sm flex items-center justify-between gap-3 border-border' style='width: 190px; ${highlightStyles} background-color: var(--card);'>
            <div class='flex items-center gap-2 truncate'>
              <span class='w-2 h-2 rounded-full ${statusColor} shrink-0'></span>
              <span class='text-[9px] font-bold text-primary truncate' style='color: var(--primary);'>${cleanTitle}</span>
            </div>
            ${isNextStep ? badgeHtml : `<span class='text-[7px] font-mono uppercase tracking-wider text-secondary/60 shrink-0' style='color: var(--secondary); opacity: 0.6;'>Terminal</span>`}
          </div>
        `.replace(/\s+/g, " ").trim();
      } else if (card.shape === "decision") {
        // Decision Gate styled card
        htmlLabel = `
          <div class='p-3.5 rounded-xl border bg-card text-left transition-all hover:scale-[1.02] shadow-sm flex flex-col gap-2' style='width: 190px; min-height: 85px; border-color: ${isNextStep ? "var(--tertiary)" : "var(--accent, var(--tertiary))"}; background-color: var(--card); border-width: ${isNextStep ? "2px" : "1.5px"}; ${isNextStep ? "box-shadow: 0 0 10px var(--tertiary);" : ""}' >
            <div class='flex items-center justify-between'>
              <div class='flex items-center gap-1.5'>
                <span class='w-2 h-2 rounded-full' style='background-color: var(--accent, var(--tertiary));'></span>
                <span class='text-[7.5px] font-mono font-bold uppercase tracking-wider' style='color: var(--accent, var(--tertiary));'>Decision Gate</span>
              </div>
              ${badgeHtml}
            </div>
            <div class='text-[10px] font-bold text-primary leading-snug line-clamp-2' style='color: var(--primary);'>${cleanTitle}</div>
            <div class='flex items-center justify-between text-[7px] font-mono text-secondary mt-1 border-t pt-1.5' style='border-color: var(--border); color: var(--secondary);'>
              <span>Priority: ${card.score}</span>
              ${iconsHtml}
            </div>
          </div>
        `.replace(/\s+/g, " ").trim();
      } else {
        // Standard Process card
        htmlLabel = `
          <div class='p-3.5 rounded-xl border bg-card text-left transition-all hover:scale-[1.02] shadow-sm flex flex-col gap-2 border-border' style='width: 190px; min-height: 85px; ${highlightStyles} background-color: var(--card);'>
            <div class='flex items-center justify-between'>
              <div class='flex items-center gap-1.5'>
                <span class='w-2 h-2 rounded-full ${statusColor}'></span>
                <span class='text-[7.5px] font-mono font-bold uppercase tracking-wider text-secondary' style='color: var(--secondary);'>${statusText}</span>
              </div>
              ${badgeHtml}
            </div>
            <div class='text-[10px] font-bold text-primary leading-snug line-clamp-2' style='color: var(--primary);'>${cleanTitle}</div>
            <div class='flex items-center justify-between text-[7px] font-mono text-secondary mt-1 border-t pt-1.5' style='border-color: var(--border); color: var(--secondary);'>
              <span>Priority: ${card.score}</span>
              ${iconsHtml}
            </div>
          </div>
        `.replace(/\s+/g, " ").trim();
      }

      if (card.shape === "decision") {
        lines.push(`  ${id}{"${htmlLabel}"}`);
      } else if (card.shape === "terminal") {
        lines.push(`  ${id}(["${htmlLabel}"])`);
      } else {
        lines.push(`  ${id}["${htmlLabel}"]`);
      }
    });

    lines.push("");
    
    // 1) Draw strict manual dependencies ALWAYS
    // Edges INTO the current/next step use a
    // thick arrow (==>) so the "do this next" direction is unmistakable.
    parsedCards.forEach(card => {
      card.dependencies.forEach(depId => {
        if (parsedCardMap.has(depId)) {
          const label = card.linkLabels?.[depId];
          const arrow = card.id === nextStepCardId ? "==>" : "-->";
          if (label) {
            lines.push(`  c_${depId} ${arrow}|"${label}"| c_${card.id}`);
          } else {
            lines.push(`  c_${depId} ${arrow} c_${card.id}`);
          }
        }
      });
    });

    // 2) Draw suggested path if toggled on
    if (showSuggestedPath) {
      // Sort non-completed cards by rank
      const activeSequence = parsedCards
        .filter(c => c.status !== "completed")
        .sort((a, b) => a.rank - b.rank);
      
      for (let i = 0; i < activeSequence.length - 1; i++) {
        const fromCard = activeSequence[i];
        const toCard = activeSequence[i + 1];
        lines.push(`  c_${fromCard.id} -.->|"(suggested)"| c_${toCard.id}`);
      }
    }

    lines.push("");

    // Assign status classes
    parsedCards.forEach(card => {
      lines.push(`  class c_${card.id} ${card.status};`);
    });

    lines.push("");

    // Assign click events
    parsedCards.forEach(card => {
      lines.push(`  click c_${card.id} onMermaidNodeClick`);
    });
    lines.push("");



    return lines.join("\n");
  }, [parsedCards, parsedCardMap, layoutDir, mermaidThemeStyles, groupByLanes, lists, nextStepCardId, showSuggestedPath]);



  // Render Mermaid code into SVG (Bypassed in favor of custom React/SVG layout calculations)
  useEffect(() => {
    // Left empty since we now calculate node coordinates and draw paths in native React/SVG
  }, []);

  // Register passive-false wheel listener on canvasRef to handle scroll zoom without page scrolling
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || diagramMode === "ascii") return;

    const handleWheelEvent = (e: WheelEvent) => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        const zoomFactor = 0.08;
        const direction = e.deltaY < 0 ? 1 : -1;
        setScale(prev => {
          const next = prev + direction * zoomFactor;
          return Math.min(Math.max(next, 0.25), 3);
        });
      } else {
        setOffset(prev => ({
          x: prev.x - e.deltaX,
          y: prev.y - e.deltaY
        }));
      }
    };

    canvas.addEventListener("wheel", handleWheelEvent, { passive: false });
    return () => {
      canvas.removeEventListener("wheel", handleWheelEvent);
    };
  }, [diagramMode]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0 || diagramMode === "ascii") return;
    const target = e.target as HTMLElement;
    if (
      target.closest(".cursor-pointer") || 
      target.closest("button") || 
      target.closest("input") || 
      target.closest("select")
    ) {
      return;
    }
    setIsPanning(true);
    setPanStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;
    setOffset({
      x: e.clientX - panStart.x,
      y: e.clientY - panStart.y
    });
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  // Copy code helper
  const handleCopyCode = () => {
    let textToCopy = "";
    if (diagramMode === "ascii") {
      textToCopy = asciiGridCode;
    } else if (diagramMode === "mindmap") {
      textToCopy = mindmapCode;
    } else {
      textToCopy = mermaidCode;
    }
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleToggleDependency = async (targetCardId: string, depId: string) => {
    const card = parsedCardMap.get(targetCardId);
    if (!card) return;

    const currentDeps = card.dependencies;
    let newDeps: string[];

    if (currentDeps.includes(depId)) {
      newDeps = currentDeps.filter(id => id !== depId);
    } else {
      newDeps = [...currentDeps, depId];
    }

    const updatedMetadata: KenbunMetadata = {
      ...card.metadata,
      dependencies: newDeps.length > 0 ? newDeps : undefined
    };

    const newDescription = injectCardMetadata(card.description, updatedMetadata);
    await onUpdateCardDesc(targetCardId, newDescription);
  };

  const handleUpdateLinkLabel = async (targetCardId: string, depId: string, newLabel: string) => {
    const card = parsedCardMap.get(targetCardId);
    if (!card) return;

    const currentLabels = card.metadata.linkLabels || {};
    const updatedLabels = { ...currentLabels };

    if (newLabel.trim()) {
      updatedLabels[depId] = newLabel.trim();
    } else {
      delete updatedLabels[depId];
    }

    const updatedMetadata: KenbunMetadata = {
      ...card.metadata,
      linkLabels: Object.keys(updatedLabels).length > 0 ? updatedLabels : undefined
    };

    const newDescription = injectCardMetadata(card.description, updatedMetadata);
    await onUpdateCardDesc(targetCardId, newDescription);
  };

  const handleUpdateShape = async (targetCardId: string, newShape: ShapeType) => {
    const card = parsedCardMap.get(targetCardId);
    if (!card) return;

    const updatedMetadata: KenbunMetadata = {
      ...card.metadata,
      shape: newShape
    };

    const newDescription = injectCardMetadata(card.description, updatedMetadata);
    await onUpdateCardDesc(targetCardId, newDescription);
  };

  const handleCreateStepSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCardName.trim() || !newCardListId) return;

    await onCreateCard(newCardName.trim(), newCardListId, 120, 120);
    
    setNewCardName("");
    setIsAddingStep(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed": return "text-emerald-400";
      case "in_progress": return "text-sky-400";
      case "blocked": return "text-amber-400";
      default: return "text-secondary";
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] relative border border-border rounded-md overflow-hidden select-none bg-neutral">
      <style dangerouslySetInnerHTML={{ __html: `
        /* ---- Flowchart edges & arrows (theme-adaptive, high-visibility) ---- */
        .wf-mode-flowchart .flowchart-link {
          stroke: var(--secondary) !important;
          stroke-opacity: 0.55 !important;
          stroke-width: 1.6px !important;
          transition: stroke 0.2s ease, stroke-width 0.2s ease !important;
        }
        .wf-mode-flowchart .flowchart-link:hover {
          stroke: var(--tertiary) !important;
          stroke-opacity: 1 !important;
          stroke-width: 2.4px !important;
        }
        /* Thick edges (==>) point into the current/next step — make them pop */
        .wf-mode-flowchart .flowchart-link.edge-thickness-thick {
          stroke: var(--tertiary) !important;
          stroke-opacity: 1 !important;
          stroke-width: 3px !important;
        }
        /* Dashed 'suggested path' edges flow toward the next step */
        .wf-mode-flowchart .flowchart-link.edge-pattern-dotted,
        .wf-mode-flowchart .flowchart-link.edge-pattern-dashed {
          stroke: var(--tertiary) !important;
          stroke-opacity: 0.85 !important;
          animation: wfDashFlow 0.9s linear infinite !important;
        }
        @keyframes wfDashFlow { to { stroke-dashoffset: -18; } }
        /* Arrowheads: clay/tertiary so they read on every theme */
        .marker, marker path, .arrowMarkerPath, #arrowhead path {
          fill: var(--tertiary) !important;
          stroke: var(--tertiary) !important;
          stroke-width: 1px !important;
        }
        .edgeLabel {
          background-color: var(--card) !important;
          color: var(--secondary) !important;
          font-family: Space Mono, monospace !important;
          font-size: 8px !important;
          padding: 2px 6px !important;
          border-radius: 4px !important;
          border: 1px solid var(--border) !important;
        }
        .cluster rect {
          fill: var(--card) !important;
          fill-opacity: 0.35 !important;
          stroke: var(--border) !important;
          stroke-width: 1px !important;
          rx: 12px !important;
          ry: 12px !important;
        }
        .cluster span {
          color: var(--primary) !important;
          font-family: Space Mono, monospace !important;
          font-size: 9px !important;
          font-weight: 700 !important;
          text-transform: uppercase !important;
          letter-spacing: 0.12em !important;
          opacity: 0.55 !important;
        }
        /* Flowchart ONLY: hide backing SVG shapes since we render HTML cards.
           Scoped so it never blanks mindmap section fills. */
        .wf-mode-flowchart .node rect, .wf-mode-flowchart .node polygon,
        .wf-mode-flowchart .node circle, .wf-mode-flowchart .node path {
          fill: none !important;
          stroke: none !important;
          stroke-width: 0px !important;
        }

        /* ---- Mindmap: clean themed chips ----
           Mermaid's mindmap themeVariables are unreliable, so we override the
           emitted .section-* classes directly. Every colour is mixed from the
           user's chosen theme (--tertiary / --card / --primary), so it stays on
           brand and readable on every preset — never dark-on-dark or light-on-light. */
        .wf-mode-mindmap g[class*="section-"] text,
        .wf-mode-mindmap g[class*="section-"] tspan,
        .wf-mode-mindmap g[class*="section-"] span,
        .wf-mode-mindmap .mindmap-node text,
        .wf-mode-mindmap .mindmap-node-label {
          fill: var(--primary) !important;
          color: var(--primary) !important;
          font-family: Space Mono, monospace !important;
          font-size: 14px !important;
          font-weight: 600 !important;
        }
        /* Leaf/card chips — subtle clay tint of the active theme */
        .wf-mode-mindmap g[class*="section-"] rect,
        .wf-mode-mindmap g[class*="section-"] polygon {
          fill: color-mix(in srgb, var(--tertiary) 8%, var(--card)) !important;
          stroke: color-mix(in srgb, var(--tertiary) 28%, transparent) !important;
          stroke-width: 1.25px !important;
          rx: 11px !important;
          ry: 11px !important;
        }
        /* Branch/column chips ([]) — read as headers: stronger tint + caps */
        .wf-mode-mindmap g[class*="section-"] > .node-bkg[class*="rect"],
        .wf-mode-mindmap .section--1 rect,
        .wf-mode-mindmap g[class*="section-"] rect.node-square {
          fill: color-mix(in srgb, var(--tertiary) 16%, var(--card)) !important;
          stroke: color-mix(in srgb, var(--tertiary) 42%, transparent) !important;
        }
        /* Root pill: clay bg + paper text — contrasts on every theme */
        .wf-mode-mindmap .section-root circle,
        .wf-mode-mindmap .section-root path,
        .wf-mode-mindmap .section-root rect,
        .wf-mode-mindmap .section-root polygon {
          fill: var(--tertiary) !important;
          stroke: var(--tertiary) !important;
        }
        .wf-mode-mindmap .section-root text,
        .wf-mode-mindmap .section-root tspan,
        .wf-mode-mindmap .section-root span {
          fill: var(--neutral) !important;
          color: var(--neutral) !important;
          font-weight: 700 !important;
        }
        /* Branch lines — subtle clay curves that echo the theme accent */
        .wf-mode-mindmap .edge,
        .wf-mode-mindmap path.edge,
        .wf-mode-mindmap [class*="section-edge-"] {
          stroke: color-mix(in srgb, var(--tertiary) 55%, transparent) !important;
          stroke-opacity: 0.7 !important;
          stroke-width: 1.75px !important;
          fill: none !important;
        }

        /* Custom styled native select dropdowns to match theme colors and override default OS chevrons */
        select {
          appearance: none !important;
          -webkit-appearance: none !important;
          -moz-appearance: none !important;
          background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%23888888' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3E%3C/svg%3E") !important;
          background-position: right 0.75rem center !important;
          background-repeat: no-repeat !important;
          background-size: 1em 1em !important;
          padding-right: 2.2rem !important;
          background-color: var(--neutral) !important;
          color: var(--primary) !important;
        }
        select option {
          background-color: var(--card) !important;
          color: var(--primary) !important;
        }
      ` }} />
      
      {/* ============ HEADER — identity + primary actions ============ */}
      <div className="flex items-center justify-between gap-4 px-5 py-3.5 border-b border-border shrink-0 z-30 bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <GitBranch className="w-4 h-4 text-tertiary shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold leading-none mb-1">
              Workflow
            </div>
            <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-primary leading-none truncate">
              {diagramMode === "mindmap" ? "Mind Map" : diagramMode === "ascii" ? "ASCII Board" : "Flowchart"}
            </h2>
          </div>
          {diagramMode === "mindmap" ? (
            <span className="hidden sm:inline text-[9px] font-mono text-secondary px-2 py-1">
              root → columns → cards
            </span>
          ) : (
            <span className="hidden sm:inline text-[9px] font-mono text-secondary px-2 py-1 bg-primary/[0.04] border border-border rounded-md">
              {parsedCards.length} steps · auto-generated
            </span>
          )}
        </div>

        {/* Primary actions */}
        <div className="flex items-center gap-2 shrink-0">
          {diagramMode !== "ascii" && (
            <div className="hidden sm:flex items-center gap-1 bg-primary/[0.04] border border-border rounded-md px-1.5 py-1">
              <button
                onClick={() => setScale(prev => Math.max(prev - 0.15, 0.25))}
                className="p-1 hover:bg-primary/5 rounded text-secondary hover:text-primary transition-colors cursor-pointer"
                title="Zoom Out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }}
                className="px-1 w-10 text-center text-[9px] font-mono font-bold text-secondary hover:text-primary cursor-pointer"
                title="Reset zoom & fit canvas"
              >
                {Math.round(scale * 100)}%
              </button>
              <button
                onClick={() => setScale(prev => Math.min(prev + 0.15, 3))}
                className="p-1 hover:bg-primary/5 rounded text-secondary hover:text-primary transition-colors cursor-pointer"
                title="Zoom In"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }}
                className="p-1 hover:bg-primary/5 rounded text-secondary hover:text-primary transition-colors cursor-pointer border-l border-border ml-0.5 pl-1.5"
                title="Recenter Canvas"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <CustomSelect
            label="Mode"
            value={diagramMode}
            onChange={setDiagramMode}
            options={[
              { value: "flowchart", label: "Flowchart" },
              { value: "mindmap", label: "Mindmap" },
              { value: "ascii", label: "ASCII Board" }
            ]}
          />

          <button
            onClick={handleCopyCode}
            className="px-2.5 py-1.5 bg-primary/[0.04] hover:bg-primary/[0.08] border border-border rounded-md text-[9px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-all flex items-center gap-1.5 cursor-pointer"
            title="Copy diagram source"
          >
            <Copy className="w-3.5 h-3.5" />
            <span className="hidden md:inline">{copied ? "Copied!" : "Copy"}</span>
          </button>

          <button
            onClick={() => setIsAddingStep(true)}
            className="px-3 py-1.5 bg-primary text-neutral hover:bg-primary/90 rounded-md text-[9px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Add step</span>
          </button>
        </div>
      </div>

      {/* ============ SECONDARY STRIP — flowchart view options + legend ============ */}
      {diagramMode === "flowchart" && (
        <div className="absolute top-4 left-4 z-30">
          <div className="relative">
            <button
              onClick={() => setShowViewSettings(!showViewSettings)}
              className={`px-5 py-2 bg-card/85 backdrop-blur-md border rounded-lg shadow-sm text-[10px] font-mono font-bold uppercase tracking-wider transition-all flex items-center gap-2 cursor-pointer ${
                showViewSettings ? "border-tertiary text-tertiary" : "border-border/80 text-secondary hover:text-primary hover:border-border"
              }`}
            >
              <Settings className="w-3.5 h-3.5" />
              View Settings
            </button>

            <AnimatePresence>
              {showViewSettings && (
                <>
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-40"
                    onClick={() => setShowViewSettings(false)}
                  />
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute top-full left-0 mt-2 w-64 bg-card/95 backdrop-blur-xl border border-border/80 rounded-xl shadow-2xl overflow-hidden z-50 flex flex-col p-4 gap-4"
                  >
                    <div className="flex flex-col gap-3">
                      <span className="text-[8px] font-mono text-secondary uppercase tracking-[0.2em] font-bold border-b border-border pb-2">
                        Layout Engine
                      </span>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-primary font-medium">Lanes</span>
                        <button
                          onClick={() => setGroupByLanes(prev => !prev)}
                          className={`px-2.5 py-1 rounded text-[10px] font-mono font-bold uppercase tracking-wider transition-all cursor-pointer ${
                            groupByLanes
                              ? "bg-tertiary/10 text-tertiary"
                              : "bg-primary/[0.04] text-secondary hover:text-primary"
                          }`}
                        >
                          {groupByLanes ? "On" : "Off"}
                        </button>
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-xs text-primary font-medium">Direction</span>
                        <button
                          onClick={() => setLayoutDir(prev => prev === "LR" ? "TD" : "LR")}
                          className="px-2.5 py-1 rounded bg-primary/[0.04] hover:bg-primary/[0.08] text-[10px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-all cursor-pointer"
                        >
                          {layoutDir === "LR" ? "Horizontal" : "Vertical"}
                        </button>
                      </div>
                    </div>

                    <div className="flex flex-col gap-3 pt-2">
                      <span className="text-[8px] font-mono text-secondary uppercase tracking-[0.2em] font-bold border-b border-border pb-2">
                        Routing
                      </span>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-primary font-medium">Auto-Paths</span>
                        <button
                          onClick={() => setShowSuggestedPath(prev => !prev)}
                          className={`px-2.5 py-1 rounded text-[10px] font-mono font-bold uppercase tracking-wider transition-all cursor-pointer ${
                            showSuggestedPath
                              ? "bg-tertiary/10 text-tertiary"
                              : "bg-primary/[0.04] text-secondary hover:text-primary"
                          }`}
                        >
                          {showSuggestedPath ? "On" : "Off"}
                        </button>
                      </div>

                      <div className="flex flex-col gap-1.5 mt-1">
                        <span className="text-[10px] font-mono uppercase text-secondary/60">Edge Style</span>
                        <div className="flex bg-neutral/50 p-1 rounded-md">
                          {[
                            { value: "basis", label: "Curved" },
                            { value: "step", label: "Ortho" },
                            { value: "linear", label: "Straight" }
                          ].map(opt => (
                            <button
                              key={opt.value}
                              onClick={() => setLineStyle(opt.value as any)}
                              className={`flex-1 py-1 text-[9px] font-bold uppercase tracking-wider rounded transition-colors cursor-pointer ${
                                lineStyle === opt.value 
                                  ? "bg-card text-primary shadow-sm" 
                                  : "text-secondary hover:text-primary"
                              }`}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* Main split-screen workspace */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Mindmap: its own dedicated component. Flowchart / ASCII: the canvas below. */}
        {diagramMode === "mindmap" ? (
          <MindmapView 
            cards={cards} 
            lists={lists} 
            onSelectCard={setSelectedCardId} 
            scale={scale}
            setScale={setScale}
            offset={offset}
            setOffset={setOffset}
          />
        ) : (
        <div
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          className={`wf-mode-${diagramMode} flex-1 relative flex items-center justify-center overflow-hidden select-none`}
          style={{
            backgroundColor: "var(--neutral)",
            backgroundImage: "radial-gradient(var(--border) 1px, transparent 0)",
            backgroundSize: "20px 20px",
            cursor: diagramMode !== "ascii" ? (isPanning ? "grabbing" : "grab") : "default"
          }}
        >
          {isRendering && (
            <div className="absolute inset-0 bg-neutral/70 backdrop-blur-xs flex items-center justify-center gap-2.5 z-40">
              <RefreshCw className="w-4 h-4 text-tertiary animate-spin" />
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] font-bold text-secondary">
                Rendering diagram…
              </span>
            </div>
          )}

          {diagramMode === "ascii" ? (
            <div className="w-full h-full flex flex-col justify-stretch p-4 min-w-[700px] overflow-auto select-text">
              <pre className="font-mono text-[10px] p-6 bg-card border border-border text-primary rounded-xl leading-relaxed whitespace-pre select-text">
                {asciiGridCode}
              </pre>
            </div>
          ) : layout.nodes.length > 0 ? (
            <div 
              className="absolute overflow-visible pointer-events-none"
              style={{
                width: 1,
                height: 1,
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
                transformOrigin: "center center",
                transition: isPanning ? "none" : "transform 0.1s ease-out",
              }}
            >
              {/* SVG Overlay for Connections */}
              <svg className="absolute overflow-visible pointer-events-none" style={{ left: 0, top: 0, width: 1, height: 1 }}>
                <defs>
                  {/* Fixed-size, notched arrowheads that read clearly on any theme */}
                  <marker
                    id="custom-arrowhead"
                    viewBox="0 0 12 12"
                    refX="10"
                    refY="6"
                    markerWidth="13"
                    markerHeight="13"
                    markerUnits="userSpaceOnUse"
                    orient="auto-start-reverse"
                  >
                    <path d="M 1 1 L 11 6 L 1 11 L 4 6 z" fill="var(--tertiary)" />
                  </marker>
                  <marker
                    id="suggested-arrowhead"
                    viewBox="0 0 12 12"
                    refX="10"
                    refY="6"
                    markerWidth="11"
                    markerHeight="11"
                    markerUnits="userSpaceOnUse"
                    orient="auto-start-reverse"
                  >
                    <path d="M 1 1.5 L 10 6 L 1 10.5 L 3.5 6 z" fill="var(--secondary)" opacity="0.9" />
                  </marker>
                  {/* Per-edge directional gradient: faded at the source, solid at the
                      target, so which way a connection points reads at a glance. */}
                  {layout.edges.filter(e => e.label !== "suggested").map(edge => (
                    <linearGradient
                      key={`grad_${edge.id}`}
                      id={`grad_${edge.id}`}
                      gradientUnits="userSpaceOnUse"
                      x1={edge.fromX} y1={edge.fromY} x2={edge.toX} y2={edge.toY}
                    >
                      <stop offset="0%" stopColor="var(--tertiary)" stopOpacity="0.22" />
                      <stop offset="55%" stopColor="var(--tertiary)" stopOpacity="0.75" />
                      <stop offset="100%" stopColor="var(--tertiary)" stopOpacity="1" />
                    </linearGradient>
                  ))}
                </defs>

                {/* Swimlanes background containers */}
                {layout.lanes.map(lane => (
                  <g key={lane.id} className="opacity-40">
                    <rect
                      x={lane.minX}
                      y={lane.minY}
                      width={lane.maxX - lane.minX}
                      height={lane.maxY - lane.minY}
                      fill="var(--card)"
                      fillOpacity="0.08"
                      stroke="var(--border)"
                      strokeWidth="1.5"
                      strokeDasharray="4 4"
                      rx="16"
                    />
                    <rect
                      x={lane.minX}
                      y={lane.minY}
                      width={lane.maxX - lane.minX}
                      height="35"
                      fill="var(--card)"
                      fillOpacity="0.12"
                      rx="16"
                      clipPath="inset(0 0 16px 0)"
                    />
                    <text
                      x={lane.minX + 16}
                      y={lane.minY + 22}
                      fill="var(--primary)"
                      fontSize="9"
                      fontWeight="bold"
                      fontFamily="Space Mono, monospace"
                      letterSpacing="0.1em"
                      className="uppercase opacity-70"
                    >
                      {lane.name}
                    </text>
                  </g>
                ))}

                {/* Connection lines */}
                {layout.edges.map(edge => {
                  const isDotted = edge.style === "dotted";
                  const isSuggested = edge.label === "suggested";

                  // Use explicit orientation to route curves flawlessly
                  const GAP = 0; // flush with the node edge
                  const orientation = (edge as any).orientation || "horizontal";
                  
                  let endX = edge.toX;
                  let endY = edge.toY;

                  if (orientation === "horizontal") {
                    endX = edge.toX - (edge.toX > edge.fromX ? GAP : -GAP);
                  } else {
                    endY = edge.toY - (edge.toY > edge.fromY ? GAP : -GAP);
                  }

                  const dx = endX - edge.fromX;
                  const dy = endY - edge.fromY;
                  const absDx = Math.abs(dx);
                  const absDy = Math.abs(dy);

                  // Route the edge per the active Curve control (lineStyle):
                  let pathD = "";
                  if (lineStyle === "linear") {
                    pathD = `M ${edge.fromX} ${edge.fromY} L ${endX} ${endY}`;
                  } else if (lineStyle === "step") {
                    if (diagramMode === "flowchart") {
                      const r = 12; // 12px border radius for sleek look
                      const x1 = edge.fromX, y1 = edge.fromY;
                      const x2 = endX, y2 = endY;
                      
                      if (orientation === "horizontal") {
                        if (Math.abs(y2 - y1) < 1) {
                          pathD = `M ${x1} ${y1} L ${x2} ${y2}`;
                        } else {
                          const midX = (x1 + x2) / 2;
                          const dirX = Math.sign(midX - x1);
                          const dirY = Math.sign(y2 - y1);
                          const maxR = Math.min(r, Math.abs(midX - x1), Math.abs(y2 - y1) / 2);
                          
                          pathD = `M ${x1} ${y1} ` +
                                  `L ${midX - maxR * dirX} ${y1} ` +
                                  `Q ${midX} ${y1} ${midX} ${y1 + maxR * dirY} ` +
                                  `L ${midX} ${y2 - maxR * dirY} ` +
                                  `Q ${midX} ${y2} ${midX + maxR * dirX} ${y2} ` +
                                  `L ${x2} ${y2}`;
                        }
                      } else {
                        if (Math.abs(x2 - x1) < 1) {
                          pathD = `M ${x1} ${y1} L ${x2} ${y2}`;
                        } else {
                          const midY = (y1 + y2) / 2;
                          const dirX = Math.sign(x2 - x1);
                          const dirY = Math.sign(midY - y1);
                          const maxR = Math.min(r, Math.abs(midY - y1), Math.abs(x2 - x1) / 2);
                          
                          pathD = `M ${x1} ${y1} ` +
                                  `L ${x1} ${midY - maxR * dirY} ` +
                                  `Q ${x1} ${midY} ${x1 + maxR * dirX} ${midY} ` +
                                  `L ${x2 - maxR * dirX} ${midY} ` +
                                  `Q ${x2} ${midY} ${x2} ${midY + maxR * dirY} ` +
                                  `L ${x2} ${y2}`;
                        }
                      };
                    } else if (orientation === "horizontal") {
                      const midX = (edge.fromX + endX) / 2;
                      pathD = `M ${edge.fromX} ${edge.fromY} L ${midX} ${edge.fromY} L ${midX} ${endY} L ${endX} ${endY}`;
                    } else {
                      const midY = (edge.fromY + endY) / 2;
                      pathD = `M ${edge.fromX} ${edge.fromY} L ${edge.fromX} ${midY} L ${endX} ${midY} L ${endX} ${endY}`;
                    }
                  } else if (orientation === "horizontal") {
                    // Curved, horizontal travel (perfect cubic S-curve)
                    const cpx = Math.max(absDx * 0.5, 40);
                    const sign = dx > 0 ? 1 : -1;
                    pathD = `M ${edge.fromX} ${edge.fromY} C ${edge.fromX + cpx * sign} ${edge.fromY}, ${endX - cpx * sign} ${endY}, ${endX} ${endY}`;
                  } else {
                    // Curved, vertical travel (perfect cubic S-curve)
                    const cpy = Math.max(absDy * 0.5, 40);
                    const sign = dy > 0 ? 1 : -1;
                    pathD = `M ${edge.fromX} ${edge.fromY} C ${edge.fromX} ${edge.fromY + cpy * sign}, ${endX} ${endY - cpy * sign}, ${endX} ${endY}`;
                  }

                  const markerEnd = diagramMode === "flowchart"
                    ? (isSuggested ? "url(#suggested-arrowhead)" : "url(#custom-arrowhead)")
                    : undefined;

                  return (
                    <g key={edge.id} className="transition-all duration-200">
                      {/* Casing — a moat in the canvas colour so the line stays
                          legible where it crosses lane fills and other edges. */}
                      <path
                        d={pathD}
                        fill="none"
                        stroke="var(--neutral)"
                        strokeWidth={isSuggested ? 4.5 : 6}
                        strokeOpacity="0.92"
                        strokeLinecap="round"
                      />
                      {/* The connection itself */}
                      <path
                        d={pathD}
                        fill="none"
                        stroke={isSuggested ? "var(--secondary)" : `url(#grad_${edge.id})`}
                        strokeWidth={isSuggested ? 1.75 : 2.4}
                        strokeOpacity={isSuggested ? 0.75 : 1}
                        strokeDasharray={isDotted ? "6 5" : undefined}
                        strokeLinecap="round"
                        markerEnd={markerEnd}
                        className="transition-all duration-200"
                      />
                      {edge.label && edge.label !== "suggested" && (
                        <foreignObject
                          x={(edge.fromX + endX) / 2 - 45}
                          y={(edge.fromY + endY) / 2 - 11}
                          width="90"
                          height="22"
                          className="overflow-visible"
                        >
                          <div className="flex justify-center select-none pointer-events-none">
                            <span
                              className="px-2 py-0.5 rounded-full text-[8px] font-mono font-bold border text-primary bg-card select-none whitespace-nowrap shadow-sm"
                              style={{ borderColor: 'var(--border)' }}
                            >
                              {edge.label}
                            </span>
                          </div>
                        </foreignObject>
                      )}
                    </g>
                  );
                })}
              </svg>

              {/* Render HTML Nodes */}
              {layout.nodes.map(node => {
                if (node.type === "root") {
                  return (
                    <div
                      key={node.id}
                      className="absolute flex items-center justify-center rounded-2xl border text-center font-bold text-[10px] tracking-wider uppercase text-primary select-none pointer-events-auto"
                      style={{
                        left: node.x,
                        top: node.y,
                        width: node.width,
                        height: node.height,
                        borderColor: "var(--border)",
                        backgroundColor: "var(--card)",
                        boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
                      }}
                    >
                      <div className="px-3 truncate">
                        {node.label}
                      </div>
                    </div>
                  );
                }

                if (node.type === "list") {
                  return (
                    <div
                      key={node.id}
                      className="absolute flex items-center justify-center rounded-xl border text-center font-bold text-[9px] tracking-wider uppercase text-secondary/80 select-none pointer-events-auto"
                      style={{
                        left: node.x,
                        top: node.y,
                        width: node.width,
                        height: node.height,
                        borderColor: "var(--border)",
                        backgroundColor: "var(--card)",
                        boxShadow: "0 2px 6px rgba(0,0,0,0.05)"
                      }}
                    >
                      {node.label}
                    </div>
                  );
                }

                const card = node.cardData;
                const blocked = !!card.blocked;
                const isNextStep = card.id === nextStepCardId;
                const cleanTitle = card.name;
                const statusColor = getStatusColorClass(card.status);
                const statusText = getStatusText(card.status);
                const iconsHtml = getCardIcons(card);

                // Blocked (a dependency isn't done) > Next > plain rank.
                const rankBadge = blocked ? (
                  <span
                    className="text-[7.5px] font-mono px-1 py-0.5 rounded font-bold flex items-center gap-0.5"
                    style={{ backgroundColor: "var(--neutral)", color: "#B8422E", border: "1px solid rgba(184,66,46,0.4)" }}
                    title="Blocked — a predecessor isn't done yet"
                  >
                    ⛔ #{card.rank}
                  </span>
                ) : isNextStep ? (
                  <span className="text-[7.5px] font-mono px-1 py-0.5 rounded font-bold animate-pulse" style={{ backgroundColor: "var(--tertiary)", color: "var(--neutral)" }}>👉 NEXT</span>
                ) : (
                  <span className="text-[7.5px] font-mono px-1 py-0.5 rounded text-secondary" style={{ backgroundColor: "var(--neutral)" }}>#{card.rank}</span>
                );

                return (
                  <motion.div
                    key={node.id}
                    onClick={() => setSelectedCardId(card.id)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ type: "spring", bounce: 0.2, duration: 0.4 }}
                    className={`absolute ${card.status === 'completed' ? 'rounded-sm' : 'rounded-xl'} border bg-card text-left shadow-sm flex flex-col gap-2 cursor-pointer pointer-events-auto`}
                    style={{
                      left: node.x,
                      top: node.y,
                      width: node.width,
                      height: node.height,
                      backgroundColor: "var(--card)",
                      opacity: blocked && !isNextStep ? 0.6 : 1,
                      borderColor: selectedCardId === card.id || isNextStep ? "var(--tertiary)" : "var(--border)",
                      borderWidth: selectedCardId === card.id || isNextStep ? 1.5 : 1,
                      borderStyle: blocked ? "dashed" : "solid",
                      boxShadow: selectedCardId === card.id 
                        ? "0 0 0 2px rgba(var(--tertiary-rgb), 0.15), 0 4px 12px rgba(0,0,0,0.15)" 
                        : isNextStep 
                          ? "0 0 12px rgba(184,66,46,0.30)" 
                          : "0 2px 8px rgba(0,0,0,0.05)"
                    }}
                  >
                    {card.shape === "terminal" ? (
                      <div className={`px-4 py-2.5 h-full ${card.status === 'completed' ? 'rounded-sm' : 'rounded-full'} flex items-center justify-between gap-3 select-none`}>
                        <div className="flex items-center gap-2 truncate">
                          <span className={`w-2 h-2 rounded-full ${statusColor} shrink-0`}></span>
                          <span className="text-[9px] font-bold text-primary truncate">{cleanTitle}</span>
                        </div>
                        {rankBadge}
                      </div>
                    ) : card.shape === "decision" ? (
                      <div className="p-3 h-full flex flex-col gap-1.5 justify-between select-none">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--accent, var(--tertiary))" }}></span>
                            <span className="text-[7.5px] font-mono font-bold uppercase tracking-wider" style={{ color: "var(--accent, var(--tertiary))" }}>Decision Gate</span>
                          </div>
                          {rankBadge}
                        </div>
                        <div className="text-[10px] font-bold text-primary leading-snug line-clamp-2">{cleanTitle}</div>
                        <div className="flex items-center justify-between text-[7px] font-mono text-secondary mt-1 border-t border-border pt-1">
                          <span>Priority: {card.score}</span>
                          <div className="flex gap-1">{iconsHtml}</div>
                        </div>
                      </div>
                    ) : (
                      <div className="p-3 h-full flex flex-col gap-1.5 justify-between select-none">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <span className={`w-1.5 h-1.5 rounded-full ${statusColor}`}></span>
                            <span className="text-[7.5px] font-mono font-bold uppercase tracking-wider text-secondary">{statusText}</span>
                          </div>
                          {rankBadge}
                        </div>
                        <div className="text-[10px] font-bold text-primary leading-snug line-clamp-2">{cleanTitle}</div>
                        <div className="flex items-center justify-between text-[7px] font-mono text-secondary mt-1 border-t border-border pt-1">
                          <span>Priority: {card.score}</span>
                          <div className="flex gap-1">{iconsHtml}</div>
                        </div>
                      </div>
                    )}

                    {/* Floating Context Action Bar (Bento-Box Toolbar) */}
                    <AnimatePresence>
                      {selectedCardId === card.id && (
                        <motion.div
                          initial={{ opacity: 0, y: 10, scale: 0.9 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 10, scale: 0.9 }}
                          className="absolute -top-12 left-1/2 -translate-x-1/2 bg-card/90 backdrop-blur-md border border-border rounded-xl shadow-xl flex items-center p-1 gap-1 z-50 pointer-events-auto cursor-default"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button 
                            className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${card.shape === 'process' || !card.shape ? 'bg-secondary/10 text-primary' : 'hover:bg-neutral hover:text-primary text-secondary'}`} 
                            title="Process Shape"
                          >
                            <Square className="w-3.5 h-3.5" />
                          </button>
                          <button 
                            className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${card.shape === 'decision' ? 'bg-secondary/10 text-primary' : 'hover:bg-neutral hover:text-primary text-secondary'}`} 
                            title="Decision Shape"
                          >
                            <Diamond className="w-3.5 h-3.5" />
                          </button>
                          <div className="w-px h-5 bg-border/50 mx-1"></div>
                          <button 
                            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-red-500/10 hover:text-red-500 text-secondary transition-colors" 
                            title="Delete Node"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 text-center px-8">
              <GitBranch className="w-10 h-10 text-secondary/25" />
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] font-bold text-secondary">
                No steps on this board yet
              </p>
              <p className="text-[10px] text-secondary/70 max-w-[220px]">
                Cards the AI adds to the board render here automatically.
              </p>
            </div>
          )}
          
          {/* Floating Legend */}
          {diagramMode === "flowchart" && (
            <div className="absolute bottom-6 right-6 hidden lg:flex items-center gap-3 text-[8.5px] font-mono text-secondary bg-card/85 backdrop-blur-md px-4 py-2 border border-border/60 rounded-full shadow-lg z-30 pointer-events-auto">
              {[
                { c: "bg-neutral-400", l: "To do" },
                { c: "bg-sky-500", l: "In progress" },
                { c: "bg-amber-500", l: "Blocked" },
                { c: "bg-emerald-500", l: "Done" }
              ].map(s => (
                <span key={s.l} className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${s.c}`} />
                  {s.l}
                </span>
              ))}
              <span className="flex items-center gap-1.5 border-l border-border pl-3">
                <span className="w-2.5 h-2.5 rotate-45 border border-tertiary/50 bg-tertiary/10" />
                Gate
              </span>
            </div>
          )}
        </div>
        )}

        {/* Right Side: Interactive Shape Designer Toolbar & Editor Panel */}
        <AnimatePresence>
          {selectedCardId && (
            <motion.div 
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="absolute right-0 top-0 bottom-0 w-80 border-l border-border flex flex-col shrink-0 z-40 bg-card/95 backdrop-blur-xl shadow-2xl"
            >
              <button 
                onClick={() => setSelectedCardId(null)}
                className="absolute top-2 left-2 p-1.5 bg-neutral/80 hover:bg-neutral rounded-full text-secondary hover:text-primary z-50 cursor-pointer border border-border transition-colors"
                title="Close panel"
              >
                <X className="w-4 h-4" />
              </button>
              
              {/* Tab bar header */}
              <div className="flex border-b border-border shrink-0 bg-transparent pl-12">
            <button
              onClick={() => setActiveSidebarTab("details")}
              className={`flex-1 py-3 text-[9px] font-bold uppercase tracking-widest transition-colors cursor-pointer border-b ${
                activeSidebarTab === "details"
                  ? "text-tertiary border-tertiary"
                  : "text-secondary hover:text-primary border-transparent"
              }`}
            >
              Step Details
            </button>
            <button
              onClick={() => setActiveSidebarTab("code")}
              className={`flex-1 py-3 text-[9px] font-bold uppercase tracking-widest transition-colors cursor-pointer border-b ${
                activeSidebarTab === "code"
                  ? "text-tertiary border-tertiary"
                  : "text-secondary hover:text-primary border-transparent"
              }`}
            >
              Mermaid Code
            </button>
          </div>

          {/* Tab contents */}
          <div className="flex-1 overflow-y-auto p-5 custom-scrollbar">
            
            {activeSidebarTab === "code" ? (
              /* CODE VIEW PANEL */
              <div className="space-y-4 text-left h-full flex flex-col">
                <p className="text-[10px] text-secondary font-mono leading-relaxed">
                  Below is the generated **Mermaid.js** code representing this diagram. It tracks in Git and displays natively in GitHub markdown:
                </p>
                <div className="flex-1 bg-neutral p-4 rounded-xl border border-border font-mono text-[9.5px] leading-relaxed text-secondary select-all whitespace-pre overflow-auto h-72 custom-scrollbar">
                  {mermaidCode}
                </div>
              </div>
            ) : (
              /* SHAPES DETAILS PANEL */
              <div className="space-y-6 text-left">
                {!selectedCard ? (
                  <div className="text-center py-16 text-secondary space-y-3 font-mono">
                    <Layout className="w-8 h-8 mx-auto text-secondary/35 stroke-[1.2]" />
                    <p className="text-[10px] uppercase tracking-wider">
                      Select a shape node in the canvas flowchart to view details or update connections.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Header */}
                    <div className="space-y-1 pb-4 border-b border-border">
                      <div className="flex justify-between items-start gap-2">
                        <span className="text-[9px] font-mono font-bold text-tertiary bg-tertiary/10 border border-tertiary/20 px-1.5 py-0.5 rounded uppercase">
                          {selectedCard.shape}
                        </span>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => onOpenCard(selectedCard)}
                            className="p-1 text-secondary hover:text-primary hover:bg-primary/5 rounded transition-all cursor-pointer"
                            title="Edit task text & description"
                          >
                            <FileText className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              onDeleteCard(selectedCard.id);
                              setSelectedCardId(null);
                            }}
                            className="p-1 text-[#B8422E] hover:bg-[#B8422E]/10 rounded transition-all cursor-pointer"
                            title="Remove step from flowchart"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <h3 className="font-bold text-xs text-primary pt-1.5 leading-snug">
                        {selectedCard.name}
                      </h3>
                      <span className={`inline-flex items-center gap-1.5 text-[8.5px] font-mono mt-1 ${getStatusColor(selectedCard.status)}`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        Rank #{selectedCard.rank} · {selectedCard.status.toUpperCase()}
                      </span>
                    </div>

                    {/* Shape Configuration */}
                    <div className="space-y-2">
                      <label className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                        Shape Styling
                      </label>
                      <div className="grid grid-cols-3 gap-1 bg-primary/[0.03] rounded p-0.5 border border-border">
                        {(["process", "decision", "terminal"] as const).map(s => (
                          <button
                            key={s}
                            onClick={() => handleUpdateShape(selectedCard.id, s)}
                            className={`py-1.5 text-[8px] font-mono font-bold uppercase tracking-wider rounded transition-colors cursor-pointer ${
                              selectedCard.shape === s
                                ? "bg-tertiary/10 text-tertiary"
                                : "text-secondary hover:text-primary"
                            }`}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Description */}
                    {selectedCard.cleanDescription && (
                      <div className="space-y-1.5">
                        <span className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                          Step Description
                        </span>
                        <div className="bg-primary/[0.03] p-3 rounded-lg border border-border">
                          <ReactMarkdown 
                            remarkPlugins={[remarkGfm]}
                            components={markdownComponents}
                          >
                            {decodeHtmlEntities(selectedCard.cleanDescription)}
                          </ReactMarkdown>
                        </div>
                      </div>
                    )}

                    {/* Connection Dependencies */}
                    <div className="space-y-2 pb-4">
                      <span className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                        Incoming Connections (Predecessors)
                      </span>
                      <div className="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar pr-1">
                        {parsedCards
                          .filter(c => c.id !== selectedCard.id) // exclude self
                          .map(item => {
                            const isLinked = selectedCard.dependencies.includes(item.id);
                            const labelValue = selectedCard.linkLabels?.[item.id] || "";
                            return (
                              <div
                                key={item.id}
                                className={`w-full flex flex-col gap-2 p-2.5 rounded-lg border text-left transition-colors ${
                                  isLinked
                                    ? "bg-tertiary/10 border-tertiary/30 text-primary"
                                    : "bg-primary/[0.03] border-border text-secondary"
                                }`}
                              >
                                <div 
                                  onClick={() => handleToggleDependency(selectedCard.id, item.id)}
                                  className="flex items-center justify-between cursor-pointer"
                                >
                                  <span className="text-[10px] font-medium leading-tight truncate mr-2">
                                    {item.name}
                                  </span>
                                  <ChevronRight className={`w-3.5 h-3.5 shrink-0 transition-transform ${isLinked ? "rotate-90 text-tertiary" : "text-secondary/40"}`} />
                                </div>

                                {isLinked && (
                                  <div className="flex items-center gap-2 pt-1.5 border-t border-border">
                                    <span className="text-[8px] font-mono text-secondary uppercase tracking-wider">Label:</span>
                                    <input
                                      type="text"
                                      value={labelValue}
                                      onChange={(e) => handleUpdateLinkLabel(selectedCard.id, item.id, e.target.value)}
                                      placeholder="e.g. Yes, No, Fail"
                                      className="flex-1 px-1.5 py-0.5 bg-neutral border border-border rounded text-[9px] text-primary focus:outline-none focus:border-tertiary/40"
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                  </div>
                                )}
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

          </div>
        </motion.div>
      )}
    </AnimatePresence>

      </div>

      {/* Shapes Designer Card Creation Prompt */}
      <AnimatePresence>
        {isAddingStep && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-base/80 backdrop-blur-xs flex items-center justify-center p-6 z-50"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-sm bg-card border border-border p-6 rounded-2xl shadow-xl flex flex-col"
            >
              <div className="flex justify-between items-center pb-4 border-b border-border mb-4">
                <h3 className="font-mono text-xs uppercase tracking-widest text-primary font-bold">
                  Add Flowchart Step
                </h3>
                <button
                  type="button"
                  onClick={() => setIsAddingStep(false)}
                  className="p-1 text-secondary hover:text-primary rounded hover:bg-primary/5 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreateStepSubmit} className="space-y-4 text-left">
                <div className="space-y-1.5">
                  <label htmlFor="flowchart_step_name_input" className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                    Step / Label Title
                  </label>
                  <input
                    id="flowchart_step_name_input"
                    type="text"
                    required
                    value={newCardName}
                    onChange={(e) => setNewCardName(e.target.value)}
                    placeholder="e.g. Verify Telephony Config"
                    className="w-full px-3 py-2 bg-neutral border border-border rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label htmlFor="flowchart_step_shape_select" className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                      Shape type
                    </label>
                    <select
                      id="flowchart_step_shape_select"
                      value={newCardShape}
                      onChange={(e) => setNewCardShape(e.target.value as ShapeType)}
                      className="w-full px-3 py-2 bg-neutral border border-border rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40 cursor-pointer"
                    >
                      <option value="process">Process (Box)</option>
                      <option value="decision">Decision (Diamond)</option>
                      <option value="terminal">Terminal (Pill)</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="flowchart_step_list_select" className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                      Status column
                    </label>
                    <select
                      id="flowchart_step_list_select"
                      value={newCardListId}
                      onChange={(e) => setNewCardListId(e.target.value)}
                      className="w-full px-3 py-2 bg-neutral border border-border rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40 cursor-pointer"
                    >
                      {lists.map(list => (
                        <option key={list.id} value={list.id}>
                          {list.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddingStep(false)}
                    className="px-4 py-2 border border-border hover:bg-primary/5 rounded text-[9px] font-bold uppercase tracking-widest text-secondary hover:text-primary transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-primary text-neutral hover:bg-primary/95 rounded text-[9px] font-bold uppercase tracking-widest transition-colors cursor-pointer"
                  >
                    Create Shape
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
