"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Play, 
  Check, 
  Clock, 
  AlertTriangle, 
  Link as LinkIcon, 
  X, 
  Calendar, 
  Eye, 
  Plus,
  GitBranch,
  ZoomIn,
  ZoomOut,
  Maximize2,
  HelpCircle,
  HelpCircle as QuestionIcon
} from "lucide-react";
import { parseCardMetadata, injectCardMetadata, KenbunMetadata } from "../app/board/page";
import { computeWorkOrder } from "../lib/prioritize";

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
  onMoveCard: (cardId: string, newListId: string) => Promise<void>;
  onUpdateCardDesc: (cardId: string, newDescription: string) => Promise<void>;
  onCreateCard: (name: string, listId: string, x: number, y: number) => Promise<void>;
}

export default function WorkflowView({
  cards,
  lists,
  onOpenCard,
  onMoveCard,
  onUpdateCardDesc,
  onCreateCard
}: WorkflowViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Pan & Zoom state
  const [zoom, setZoom] = useState<number>(0.95);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 30, y: 10 });
  const [isDraggingCanvas, setIsDraggingCanvas] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Hover states & editor selectors
  const [hoveredCardId, setHoveredCardId] = useState<string | null>(null);
  const [editingDepsCardId, setEditingDepsCardId] = useState<string | null>(null);
  const [isMobileTimeline, setIsMobileTimeline] = useState(false);

  // Connection drawing state
  const [drawingFromId, setDrawingFromId] = useState<string | null>(null);
  const [drawingCoords, setDrawingCoords] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null);
  const [hoveredPortId, setHoveredPortId] = useState<string | null>(null);

  // New Node creation coordinates
  const [creatingNodeCoords, setCreatingNodeCoords] = useState<{ x: number; y: number } | null>(null);
  const [newNodeName, setNewNodeName] = useState<string>("");
  const [newNodeListId, setNewNodeListId] = useState<string>(lists[0]?.id || "");

  // Auto-detect mobile screen width
  useEffect(() => {
    const handleResize = () => {
      setIsMobileTimeline(window.innerWidth < 768);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Compute Priority ranks & scores using prioritization model
  const workOrder = useMemo(() => {
    return computeWorkOrder(cards, lists);
  }, [cards, lists]);

  const listMap = useMemo(() => {
    return new Map(lists.map(l => [l.id, l]));
  }, [lists]);

  // Parse metadata layout & dependencies for each card
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

        // Logic check: Decision Gates start with Gate/Decision or mention gate/check/decision/audit
        const isDecisionGate = 
          card.name.toLowerCase().startsWith("gate:") || 
          card.name.toLowerCase().startsWith("decision:") || 
          card.name.toLowerCase().includes("check") || 
          card.name.toLowerCase().includes("audit") || 
          card.name.toLowerCase().includes("gate");

        return {
          ...card,
          cleanDescription,
          metadata,
          dependencies: metadata.dependencies || [],
          layout: metadata.layout,
          status,
          isDecisionGate,
          score: workOrder.score.get(card.id) || 0,
          rank: workOrder.rank.get(card.id) || 999
        };
      });
  }, [cards, listMap, workOrder]);

  const parsedCardMap = useMemo(() => {
    return new Map(parsedCards.map(c => [c.id, c]));
  }, [parsedCards]);

  // Compute initial topological layers (only used as a fallback if custom coordinates are missing)
  const layers = useMemo(() => {
    const cardLayer = new Map<string, number>();
    const activeCardIds = new Set(parsedCards.map(c => c.id));

    parsedCards.forEach(c => cardLayer.set(c.id, 0));

    let changed = true;
    let iteration = 0;
    const maxIterations = parsedCards.length;

    while (changed && iteration < maxIterations) {
      changed = false;
      iteration++;

      for (const card of parsedCards) {
        const currentLayer = cardLayer.get(card.id) || 0;
        let maxDepLayer = -1;

        for (const depId of card.dependencies) {
          if (activeCardIds.has(depId)) {
            const depLayer = cardLayer.get(depId) || 0;
            if (depLayer > maxDepLayer) {
              maxDepLayer = depLayer;
            }
          }
        }

        if (maxDepLayer >= currentLayer) {
          cardLayer.set(card.id, maxDepLayer + 1);
          changed = true;
        }
      }
    }

    const layerGroups: typeof parsedCards[] = [];
    cardLayer.forEach((layer, cardId) => {
      const card = parsedCardMap.get(cardId);
      if (card) {
        if (!layerGroups[layer]) {
          layerGroups[layer] = [];
        }
        layerGroups[layer].push(card);
      }
    });

    return layerGroups
      .filter(l => l && l.length > 0)
      .map(l => l.sort((a, b) => a.rank - b.rank));
  }, [parsedCards, parsedCardMap]);

  // Nodes Dimension and Gap config
  const nodeWidth = 260;
  const nodeHeight = 110;
  const colGap = 160;
  const rowGap = 32;

  // Final coordinates map: uses custom layouts if saved, else falls back to topological sorting layouts
  const nodeCoords = useMemo(() => {
    const coords = new Map<string, { x: number; y: number }>();
    
    // 1. Calculate fallback coordinates
    const fallbackCoords = new Map<string, { x: number; y: number }>();
    layers.forEach((layerCards, layerIdx) => {
      const x = layerIdx * (nodeWidth + colGap) + 40;
      const startY = 80;
      layerCards.forEach((card, cardIdx) => {
        const y = startY + cardIdx * (nodeHeight + rowGap);
        fallbackCoords.set(card.id, { x, y });
      });
    });

    // 2. Map coordinates
    parsedCards.forEach(card => {
      if (card.layout) {
        coords.set(card.id, card.layout);
      } else {
        coords.set(card.id, fallbackCoords.get(card.id) || { x: 40, y: 80 });
      }
    });

    return coords;
  }, [layers, parsedCards]);

  // Generate connection links
  const links = useMemo(() => {
    const edgeList: Array<{ from: string; to: string; active: boolean; type: "requires" | "blocks" }> = [];
    
    parsedCards.forEach(card => {
      card.dependencies.forEach(depId => {
        if (parsedCardMap.has(depId)) {
          const isHovered = hoveredCardId === card.id || hoveredCardId === depId;
          edgeList.push({
            from: depId,
            to: card.id,
            active: isHovered,
            type: hoveredCardId === card.id ? "requires" : "blocks"
          });
        }
      });
    });
    
    return edgeList;
  }, [parsedCards, parsedCardMap, hoveredCardId]);

  // Highlights predecessor & successor sets
  const relatedCardIds = useMemo(() => {
    if (!hoveredCardId) return new Set<string>();
    const related = new Set<string>([hoveredCardId]);
    
    const hoverCard = parsedCardMap.get(hoveredCardId);
    if (hoverCard) {
      hoverCard.dependencies.forEach(d => related.add(d));
    }
    
    parsedCards.forEach(c => {
      if (c.dependencies.includes(hoveredCardId)) {
        related.add(c.id);
      }
    });

    return related;
  }, [hoveredCardId, parsedCards, parsedCardMap]);

  // --- INTERACTIVE DRAG-PAN-ZOOM HANDLERS ---
  const handleCanvasMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    // Only pan on left-click on background (not node/links interaction)
    if (e.button !== 0 || drawingFromId || editingDepsCardId || creatingNodeCoords) return;
    
    const target = e.target as HTMLElement;
    if (target.closest(".draggable-node") || target.closest(".port-handle") || target.closest("button") || target.closest("input")) return;
    
    setIsDraggingCanvas(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isDraggingCanvas) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }

    // Dynamic line drawing cursor follower
    if (drawingFromId && containerRef.current && canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const x2 = (e.clientX - rect.left) / zoom;
      const y2 = (e.clientY - rect.top) / zoom;
      
      setDrawingCoords(prev => {
        if (!prev) return null;
        return { ...prev, x2, y2 };
      });
    }
  };

  const handleCanvasMouseUp = () => {
    setIsDraggingCanvas(false);
    if (drawingFromId) {
      setDrawingFromId(null);
      setDrawingCoords(null);
      setHoveredPortId(null);
    }
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    // Prevent document scroll only if scrolling inside graph
    e.preventDefault();
    const zoomFactor = 0.04;
    const nextZoom = e.deltaY < 0 ? zoom + zoomFactor : zoom - zoomFactor;
    setZoom(Math.max(0.4, Math.min(1.8, nextZoom)));
  };

  // Node drag offset save trigger
  const handleNodeDragEnd = async (cardId: string, info: any) => {
    const card = parsedCardMap.get(cardId);
    const coords = nodeCoords.get(cardId);
    if (!card || !coords) return;

    // Apply scale delta
    const nextX = coords.x + info.offset.x / zoom;
    const nextY = coords.y + info.offset.y / zoom;

    const updatedMetadata: KenbunMetadata = {
      ...card.metadata,
      layout: { x: Math.round(nextX), y: Math.round(nextY) }
    };

    const newDescription = injectCardMetadata(card.description, updatedMetadata);
    await onUpdateCardDesc(cardId, newDescription);
  };

  // --- CONNECT PORT HANDLERS ---
  const handlePortMouseDown = (e: React.MouseEvent, cardId: string, isOutput: boolean) => {
    e.stopPropagation();
    e.preventDefault();
    
    const coord = nodeCoords.get(cardId);
    if (!coord) return;

    const portX = isOutput ? coord.x + nodeWidth : coord.x;
    const portY = coord.y + nodeHeight / 2;

    setDrawingFromId(cardId);
    setDrawingCoords({
      x1: portX,
      y1: portY,
      x2: portX,
      y2: portY
    });
  };

  const handlePortMouseUp = async (e: React.MouseEvent, targetCardId: string, isInput: boolean) => {
    e.stopPropagation();
    if (!drawingFromId || drawingFromId === targetCardId) return;

    // Output dragging dropped onto input -> creates targetCardId depends on drawingFromId
    if (isInput) {
      await handleToggleDependency(targetCardId, drawingFromId);
    }

    setDrawingFromId(null);
    setDrawingCoords(null);
    setHoveredPortId(null);
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

  // --- CANVAS CARD INSTANTIATION ---
  const handleCanvasDoubleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest(".draggable-node") || target.closest(".port-handle") || target.closest("button") || target.closest("input")) return;
    if (drawingFromId || editingDepsCardId) return;

    if (canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const clickX = (e.clientX - rect.left) / zoom;
      const clickY = (e.clientY - rect.top) / zoom;
      
      setCreatingNodeCoords({ x: Math.round(clickX), y: Math.round(clickY) });
    }
  };

  const handleCreateNodeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNodeName.trim() || !creatingNodeCoords || !newNodeListId) return;

    await onCreateCard(newNodeName, newNodeListId, creatingNodeCoords.x, creatingNodeCoords.y);
    setNewNodeName("");
    setCreatingNodeCoords(null);
  };

  const getStatusConfig = (status: "todo" | "in_progress" | "blocked" | "completed") => {
    switch (status) {
      case "completed":
        return { label: "Done", icon: Check, color: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20" };
      case "in_progress":
        return { label: "In Progress", icon: Clock, color: "text-sky-500 bg-sky-500/10 border-sky-500/20" };
      case "blocked":
        return { label: "Blocked", icon: AlertTriangle, color: "text-amber-500 bg-amber-500/10 border-amber-500/20" };
      default:
        return { label: "To Do", icon: Play, color: "text-neutral-400 bg-neutral-400/10 border-neutral-400/20" };
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] relative overflow-hidden bg-base/20 border border-white/5 rounded-2xl select-none">
      {/* Top Controls Bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-card/10 backdrop-blur-sm shrink-0 z-30">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-tertiary animate-pulse" />
          <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-primary">
            Interactive Flowchart Canvas
          </h2>
          <span className="text-[10px] font-mono text-secondary px-2 py-0.5 bg-white/5 rounded">
            {parsedCards.length} nodes
          </span>
        </div>

        {/* Toolbar Helpers */}
        <div className="hidden sm:flex items-center gap-4 text-[10px] font-mono text-secondary">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-card border border-white/10" />
            Standard
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rotate-45 bg-amber-500/5 border border-amber-500/20" />
            Decision Gate
          </div>
          <div className="text-[9px] text-tertiary">
            💡 Tip: Double-click empty canvas to add a step, or drag ports to link!
          </div>
        </div>

        {/* Zoom & View Controls */}
        <div className="flex items-center gap-4 z-40">
          <div className="flex items-center gap-1 bg-white/5 rounded p-0.5 border border-white/5">
            <button
              onClick={() => setZoom(prev => Math.min(1.8, prev + 0.1))}
              className="p-1 text-secondary hover:text-primary rounded hover:bg-white/5 cursor-pointer transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <span className="text-[9px] font-mono text-secondary w-10 text-center select-none font-bold">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom(prev => Math.max(0.4, prev - 0.1))}
              className="p-1 text-secondary hover:text-primary rounded hover:bg-white/5 cursor-pointer transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => { setZoom(0.95); setPan({ x: 30, y: 10 }); }}
              className="p-1 text-secondary hover:text-primary rounded hover:bg-white/5 cursor-pointer transition-colors border-l border-white/5 pl-1.5 ml-0.5"
              title="Reset View"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex gap-1 bg-white/5 rounded p-0.5 border border-white/5">
            <button
              onClick={() => setIsMobileTimeline(false)}
              className={`px-3 py-1 text-[9px] font-bold uppercase tracking-wider rounded transition-colors ${
                !isMobileTimeline
                  ? "bg-tertiary/10 text-tertiary"
                  : "text-secondary hover:text-primary cursor-pointer"
              }`}
            >
              Canvas
            </button>
            <button
              onClick={() => setIsMobileTimeline(true)}
              className={`px-3 py-1 text-[9px] font-bold uppercase tracking-wider rounded transition-colors ${
                isMobileTimeline
                  ? "bg-tertiary/10 text-tertiary"
                  : "text-secondary hover:text-primary cursor-pointer"
              }`}
            >
              Timeline Checklist
            </button>
          </div>
        </div>
      </div>

      {/* Main Graph Viewport */}
      {isMobileTimeline ? (
        /* ---- MOBILE TIMELINE VIEW ---- */
        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          {layers.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <GitBranch className="w-12 h-12 text-secondary/20 mb-4" />
              <p className="font-mono text-xs uppercase tracking-wider text-secondary">
                No active tasks found on this board.
              </p>
            </div>
          ) : (
            layers.map((layerCards, idx) => (
              <div key={idx} className="relative pl-6 border-l border-white/5 space-y-4">
                <div className="absolute -left-1.5 top-1.5 w-3 h-3 bg-base border border-tertiary rounded-full shadow-lg shadow-tertiary/30" />
                <h3 className="font-mono text-[10px] font-bold uppercase tracking-widest text-tertiary flex items-center gap-2">
                  Phase {idx + 1}
                  {idx === 0 && <span className="text-[8px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 rounded font-normal uppercase tracking-normal">Unblocked</span>}
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {layerCards.map(card => {
                    const statusCfg = getStatusConfig(card.status);
                    return (
                      <div
                        key={card.id}
                        onClick={() => onOpenCard(card)}
                        className={`flex flex-col p-4 bg-card/45 hover:bg-card/75 border rounded-xl transition-all duration-300 cursor-pointer group ${
                          card.isDecisionGate ? "border-amber-500/20 bg-amber-500/[0.02]" : "border-white/5"
                        }`}
                      >
                        <div className="flex justify-between items-start gap-4 mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-[9px] font-mono font-bold text-tertiary bg-tertiary/10 border border-tertiary/20 px-1.5 py-0.5 rounded">
                              #{card.rank}
                            </span>
                            <span className={`text-[8px] font-bold uppercase tracking-wider px-2 py-0.5 border rounded-sm flex items-center gap-1 ${statusCfg.color}`}>
                              <statusCfg.icon className="w-2.5 h-2.5" />
                              {statusCfg.label}
                            </span>
                          </div>
                          {card.dueDate && (
                            <span className="text-[9px] font-mono text-secondary flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {card.dueDate.split("T")[0]}
                            </span>
                          )}
                        </div>
                        <h4 className="text-xs font-bold text-primary mb-1 group-hover:text-tertiary transition-colors">
                          {card.isDecisionGate && "🔶 "}{card.name}
                        </h4>
                        {card.cleanDescription && (
                          <p className="text-[10px] text-secondary line-clamp-2 mb-3">
                            {card.cleanDescription}
                          </p>
                        )}
                        {card.dependencies.length > 0 && (
                          <div className="mt-auto pt-3 border-t border-white/5 flex items-center gap-1.5">
                            <LinkIcon className="w-3 h-3 text-secondary" />
                            <span className="text-[9px] font-mono text-secondary">
                              Requires: {card.dependencies.map(dId => parsedCardMap.get(dId)?.name || "Unknown").join(", ")}
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* ---- CANVAS INFINITE WORKFLOW VIEW ---- */
        <div
          ref={containerRef}
          onMouseDown={handleCanvasMouseDown}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onWheel={handleWheel}
          onDoubleClick={handleCanvasDoubleClick}
          className={`flex-1 overflow-hidden relative cursor-grab active:cursor-grabbing ${
            isDraggingCanvas ? "dragging" : ""
          }`}
          style={{
            backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.015) 1.5px, transparent 0)",
            backgroundSize: "28px 28px",
            backgroundPosition: `${pan.x}px ${pan.y}px`,
            backgroundColor: "rgba(10, 10, 10, 0.15)"
          }}
        >
          {/* Scrollable transform canvas viewport */}
          <div
            ref={canvasRef}
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: "0 0",
              width: "5000px",
              height: "5000px"
            }}
            className="absolute inset-0 pointer-events-none select-none"
          >
            {/* SVG Connector lines layer */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
              <defs>
                <marker
                  id="arrow-blocks-active"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 2 L 8 5 L 0 8 z" fill="oklch(65% 0.22 45)" />
                </marker>
                <marker
                  id="arrow-requires-active"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 2 L 8 5 L 0 8 z" fill="oklch(55% 0.18 260)" />
                </marker>
                <marker
                  id="arrow-std"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 2 L 8 5 L 0 8 z" fill="rgba(255, 255, 255, 0.15)" />
                </marker>
              </defs>

              {/* Render existing links */}
              {links.map((link, idx) => {
                const fromCoord = nodeCoords.get(link.from);
                const toCoord = nodeCoords.get(link.to);
                
                if (!fromCoord || !toCoord) return null;

                const x1 = fromCoord.x + nodeWidth;
                const y1 = fromCoord.y + nodeHeight / 2;
                
                const x2 = toCoord.x;
                const y2 = toCoord.y + nodeHeight / 2;

                const ctrlX1 = x1 + colGap / 2;
                const ctrlY1 = y1;
                const ctrlX2 = x2 - colGap / 2;
                const ctrlY2 = y2;

                const pathStr = `M ${x1} ${y1} C ${ctrlX1} ${ctrlY1}, ${ctrlX2} ${ctrlY2}, ${x2} ${y2}`;

                let strokeColor = "rgba(255, 255, 255, 0.08)";
                let marker = "url(#arrow-std)";
                let strokeWidth = 1.2;
                let animateDash = false;

                if (link.active) {
                  strokeWidth = 2.2;
                  if (link.type === "requires") {
                    strokeColor = "oklch(55% 0.18 260)"; // Blue glow
                    marker = "url(#arrow-requires-active)";
                  } else {
                    strokeColor = "oklch(65% 0.22 45)"; // Orange glow
                    marker = "url(#arrow-blocks-active)";
                    animateDash = true;
                  }
                }

                return (
                  <path
                    key={idx}
                    d={pathStr}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    markerEnd={marker}
                    strokeDasharray={animateDash ? "5, 5" : undefined}
                    style={{
                      animation: animateDash ? "dash 0.6s linear infinite" : undefined
                    }}
                    className="transition-all duration-300"
                  />
                );
              })}

              {/* Render dynamic line drawer */}
              {drawingCoords && (
                <path
                  d={`M ${drawingCoords.x1} ${drawingCoords.y1} C ${(drawingCoords.x1 + drawingCoords.x2) / 2} ${drawingCoords.y1}, ${(drawingCoords.x1 + drawingCoords.x2) / 2} ${drawingCoords.y2}, ${drawingCoords.x2} ${drawingCoords.y2}`}
                  fill="none"
                  stroke="oklch(65% 0.22 45)"
                  strokeWidth="2"
                  strokeDasharray="4, 4"
                  className="animate-[dash_0.4s_linear_infinite]"
                />
              )}
            </svg>

            {/* Draggable Nodes layer */}
            {parsedCards.map(card => {
              const coords = nodeCoords.get(card.id) || { x: 40, y: 80 };
              const isHovered = hoveredCardId === card.id;
              const isRelated = hoveredCardId === null || relatedCardIds.has(card.id);
              const statusCfg = getStatusConfig(card.status);
              const isDrawingTarget = drawingFromId !== null && drawingFromId !== card.id;

              return (
                <motion.div
                  key={card.id}
                  drag
                  dragMomentum={false}
                  onDragEnd={(event, info) => handleNodeDragEnd(card.id, info)}
                  initial={false}
                  animate={{ 
                    opacity: isRelated ? 1 : 0.2, 
                    scale: isHovered ? 1.02 : 1,
                    x: coords.x,
                    y: coords.y
                  }}
                  transition={{ type: "spring", stiffness: 380, damping: 28 }}
                  onMouseEnter={() => setHoveredCardId(card.id)}
                  onMouseLeave={() => setHoveredCardId(null)}
                  style={{
                    width: `${nodeWidth}px`,
                    height: `${nodeHeight}px`,
                    position: "absolute"
                  }}
                  className="draggable-node pointer-events-auto group/node z-10 p-3 bg-card/65 backdrop-blur-md rounded-xl border flex flex-col justify-between select-none cursor-grab active:cursor-grabbing border-white/5 hover:border-tertiary/30 hover:shadow-lg hover:shadow-tertiary/5"
                >
                  {/* Left Connection Port (Input/Requires) */}
                  <div
                    onMouseUp={(e) => handlePortMouseUp(e, card.id, true)}
                    onMouseEnter={() => setHoveredPortId(`${card.id}-in`)}
                    onMouseLeave={() => setHoveredPortId(null)}
                    className={`port-handle absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border bg-base flex items-center justify-center cursor-crosshair z-20 transition-all duration-300 ${
                      isDrawingTarget && hoveredPortId === `${card.id}-in`
                        ? "border-emerald-500 scale-125 bg-emerald-500/10"
                        : "border-white/10 opacity-0 group-hover/node:opacity-100 hover:scale-125 hover:border-tertiary"
                    }`}
                    title="Connect target as dependency"
                  >
                    <span className="w-1.5 h-1.5 bg-secondary rounded-full" />
                  </div>

                  {/* Standard vs Decision Gate inner layout */}
                  <div className="flex flex-col gap-1 w-full h-full justify-between">
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono font-bold text-tertiary bg-tertiary/10 border border-tertiary/20 px-1.5 py-0.5 rounded">
                          #{card.rank}
                        </span>
                        
                        <span className={`text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 border rounded-sm flex items-center gap-1 ${statusCfg.color}`}>
                          <statusCfg.icon className="w-2 h-2" />
                          {statusCfg.label}
                        </span>
                      </div>
                      
                      <h3 className="text-[11px] font-bold text-primary line-clamp-2 mt-1.5 leading-snug">
                        {card.isDecisionGate ? (
                          <span className="text-amber-500 font-mono tracking-wider font-bold">🔸 {card.name}</span>
                        ) : card.name}
                      </h3>
                    </div>

                    {/* Node controls */}
                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5 z-20">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenCard(card);
                        }}
                        className="p-1 text-secondary hover:text-primary transition-colors hover:bg-white/5 rounded flex items-center gap-1 text-[8px] font-bold uppercase tracking-widest cursor-pointer"
                      >
                        <Eye className="w-3 h-3" />
                        Open
                      </button>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingDepsCardId(card.id);
                        }}
                        className="p-1 text-secondary hover:text-primary transition-colors hover:bg-white/5 rounded flex items-center gap-1 text-[8px] font-bold uppercase tracking-widest cursor-pointer"
                        title="Link Predecessors"
                      >
                        <LinkIcon className="w-3 h-3" />
                        Link
                      </button>
                    </div>
                  </div>

                  {/* Right Connection Port (Output/Blocks) */}
                  <div
                    onMouseDown={(e) => handlePortMouseDown(e, card.id, true)}
                    className="port-handle absolute -right-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border border-white/10 bg-base flex items-center justify-center cursor-crosshair z-20 opacity-0 group-hover/node:opacity-100 hover:scale-125 hover:border-tertiary transition-all duration-300"
                    title="Drag to create dependency link"
                  >
                    <Plus className="w-2.5 h-2.5 text-secondary hover:text-primary" />
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* Instant Double-Click Card Creation Prompt */}
      <AnimatePresence>
        {creatingNodeCoords && (
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
              className="w-full max-w-sm bg-card border border-white/10 p-6 rounded-2xl shadow-xl flex flex-col"
            >
              <div className="flex justify-between items-center pb-4 border-b border-white/5 mb-4">
                <h3 className="font-mono text-xs uppercase tracking-widest text-primary font-bold">
                  Add Step on Canvas
                </h3>
                <button
                  type="button"
                  onClick={() => setCreatingNodeCoords(null)}
                  className="p-1 text-secondary hover:text-primary rounded hover:bg-white/5 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreateNodeSubmit} className="space-y-4 text-left">
                <div className="space-y-1.5">
                  <label htmlFor="workflow_card_name_input" className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                    Step Title
                  </label>
                  <input
                    id="workflow_card_name_input"
                    type="text"
                    required
                    value={newNodeName}
                    onChange={(e) => setNewNodeName(e.target.value)}
                    placeholder="e.g. Phase 1 Audit, Gate: Verify Setup"
                    className="w-full px-3 py-2 bg-neutral border border-white/10 rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40"
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="workflow_card_list_select" className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                    Workflow status
                  </label>
                  <select
                    id="workflow_card_list_select"
                    value={newNodeListId}
                    onChange={(e) => setNewNodeListId(e.target.value)}
                    className="w-full px-3 py-2 bg-neutral border border-white/10 rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40 cursor-pointer"
                  >
                    {lists.map(list => (
                      <option key={list.id} value={list.id}>
                        {list.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setCreatingNodeCoords(null)}
                    className="px-4 py-2 border border-white/10 hover:bg-white/5 rounded text-[9px] font-bold uppercase tracking-widest text-secondary hover:text-primary transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-primary text-neutral hover:bg-primary/95 rounded text-[9px] font-bold uppercase tracking-widest transition-colors cursor-pointer"
                  >
                    Create Step
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Edit Dependencies Drawer/Modal Overlay */}
      <AnimatePresence>
        {editingDepsCardId && (() => {
          const card = parsedCardMap.get(editingDepsCardId);
          if (!card) return null;

          return (
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
                transition={{ type: "spring", stiffness: 350, damping: 25 }}
                className="w-full max-w-md bg-card border border-white/10 p-6 rounded-2xl shadow-xl flex flex-col max-h-[80vh]"
              >
                {/* Modal Header */}
                <div className="flex justify-between items-center pb-4 border-b border-white/5">
                  <div className="flex flex-col gap-0.5">
                    <h3 className="font-mono text-xs uppercase tracking-widest text-primary font-bold">
                      Set Task Dependencies
                    </h3>
                    <p className="text-[10px] text-secondary line-clamp-1">
                      {card.name}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setEditingDepsCardId(null)}
                    className="p-1 text-secondary hover:text-primary rounded hover:bg-white/5 cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Checklist Content */}
                <div className="flex-1 overflow-y-auto py-4 space-y-2 custom-scrollbar pr-1">
                  <p className="text-[10px] text-secondary mb-3">
                    Check the tasks that must be completed **before** starting this task:
                  </p>
                  {parsedCards
                    .filter(c => c.id !== editingDepsCardId) // exclude self
                    .map(item => {
                      const isChecked = card.dependencies.includes(item.id);
                      return (
                        <label
                          key={item.id}
                          className={`flex items-center justify-between p-3 rounded-lg border transition-all duration-200 cursor-pointer ${
                            isChecked
                              ? "bg-tertiary/10 border-tertiary/30 text-primary"
                              : "bg-white/2 hover:bg-white/5 border-white/5 text-secondary hover:text-primary"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => handleToggleDependency(card.id, item.id)}
                              className="w-3.5 h-3.5 accent-tertiary border-white/10 rounded focus:ring-0 cursor-pointer"
                            />
                            <div className="flex flex-col gap-0.5">
                              <span className="text-xs font-medium leading-tight">
                                {item.name}
                              </span>
                              <span className="text-[8px] font-mono tracking-wider uppercase text-secondary">
                                Rank #{item.rank} • {getStatusConfig(item.status).label}
                              </span>
                            </div>
                          </div>
                        </label>
                      );
                    })}

                  {parsedCards.filter(c => c.id !== editingDepsCardId).length === 0 && (
                    <p className="text-center py-6 text-xs text-secondary font-mono">
                      No other active cards on this board.
                    </p>
                  )}
                </div>

                {/* Footer */}
                <div className="pt-4 border-t border-white/5 flex justify-end">
                  <button
                    type="button"
                    onClick={() => setEditingDepsCardId(null)}
                    className="px-4 py-2 bg-primary text-neutral hover:bg-primary/95 transition-colors rounded text-[10px] font-bold uppercase tracking-widest cursor-pointer"
                  >
                    Done
                  </button>
                </div>
              </motion.div>
            </motion.div>
          );
        })()}
      </AnimatePresence>
    </div>
  );
}
