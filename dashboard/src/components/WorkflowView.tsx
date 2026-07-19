"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Play, 
  Check, 
  Clock, 
  AlertTriangle, 
  Link, 
  X, 
  Calendar, 
  Eye, 
  Plus,
  GitBranch,
  ArrowRight
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
}

export default function WorkflowView({
  cards,
  lists,
  onOpenCard,
  onMoveCard,
  onUpdateCardDesc
}: WorkflowViewProps) {
  const [hoveredCardId, setHoveredCardId] = useState<string | null>(null);
  const [editingDepsCardId, setEditingDepsCardId] = useState<string | null>(null);
  const [isMobileTimeline, setIsMobileTimeline] = useState(false);

  // Auto-detect mobile screen width
  React.useEffect(() => {
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

  // Parse metadata dependencies for each card
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

        return {
          ...card,
          cleanDescription,
          metadata,
          dependencies: metadata.dependencies || [],
          status,
          score: workOrder.score.get(card.id) || 0,
          rank: workOrder.rank.get(card.id) || 999
        };
      });
  }, [cards, listMap, workOrder]);

  const parsedCardMap = useMemo(() => {
    return new Map(parsedCards.map(c => [c.id, c]));
  }, [parsedCards]);

  // Compute dependency layers (Sugiyama-style topological sorting)
  const layers = useMemo(() => {
    const cardLayer = new Map<string, number>();
    const activeCardIds = new Set(parsedCards.map(c => c.id));

    // Initialize all to Layer 0
    parsedCards.forEach(c => cardLayer.set(c.id, 0));

    // Iteratively push layers forward to resolve dependencies
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

    // Group cards into layer arrays
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

    // Clean empty layers and sort within each layer by rank (highest score first)
    return layerGroups
      .filter(l => l && l.length > 0)
      .map(l => l.sort((a, b) => a.rank - b.rank));
  }, [parsedCards, parsedCardMap]);

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

  // Coordinates mapping
  const nodeWidth = 260;
  const nodeHeight = 110;
  const colGap = 160;
  const rowGap = 32;

  const nodeCoords = useMemo(() => {
    const coords = new Map<string, { x: number; y: number }>();
    
    layers.forEach((layerCards, layerIdx) => {
      const x = layerIdx * (nodeWidth + colGap) + 40;
      const layerHeight = layerCards.length * (nodeHeight + rowGap) - rowGap;
      const startY = 60; // top offset

      layerCards.forEach((card, cardIdx) => {
        const y = startY + cardIdx * (nodeHeight + rowGap);
        coords.set(card.id, { x, y });
      });
    });

    return coords;
  }, [layers]);

  // Highlight direct ancestor & descendant relations
  const relatedCardIds = useMemo(() => {
    if (!hoveredCardId) return new Set<string>();
    const related = new Set<string>([hoveredCardId]);
    
    // Direct predecessors
    const hoverCard = parsedCardMap.get(hoveredCardId);
    if (hoverCard) {
      hoverCard.dependencies.forEach(d => related.add(d));
    }
    
    // Direct successors
    parsedCards.forEach(c => {
      if (c.dependencies.includes(hoveredCardId)) {
        related.add(c.id);
      }
    });

    return related;
  }, [hoveredCardId, parsedCards, parsedCardMap]);

  // Toggle dependency link
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

  const getStatusConfig = (status: "todo" | "in_progress" | "blocked" | "completed") => {
    switch (status) {
      case "completed":
        return { label: "Done", icon: Check, color: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20" };
      case "in_progress":
        return { label: "In Progress", icon: Clock, color: "text-sky-500 bg-sky-500/10 border-sky-500/20" };
      case "blocked":
        return { label: "Blocked", icon: AlertTriangle, color: "text-amber-500 bg-amber-500/10 border-amber-500/20 animate-pulse" };
      default:
        return { label: "To Do", icon: Play, color: "text-neutral-400 bg-neutral-400/10 border-neutral-400/20" };
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] relative overflow-hidden bg-base/20 border border-white/5 rounded-2xl">
      {/* Top Controls Bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-card/10 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-tertiary" />
          <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-primary">
            Dependency Flow Diagram
          </h2>
          <span className="text-[10px] font-mono text-secondary px-2 py-0.5 bg-white/5 rounded">
            {parsedCards.length} Tasks
          </span>
        </div>

        {/* View Toggle */}
        <div className="flex gap-1 bg-white/5 rounded p-0.5 border border-white/5">
          <button
            type="button"
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
            type="button"
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

      {/* Main Viewport */}
      {isMobileTimeline ? (
        /* ---- TIMELINE CHECKLIST (Mobile / Linear view) ---- */
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
                {/* Connector Dot */}
                <div className="absolute -left-1.5 top-1.5 w-3 h-3 bg-base border border-tertiary rounded-full shadow-lg shadow-tertiary/30" />
                
                <h3 className="font-mono text-[10px] font-bold uppercase tracking-widest text-tertiary flex items-center gap-2">
                  Phase {idx + 1}
                  {idx === 0 && <span className="text-[8px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 rounded font-normal uppercase tracking-normal">Unblocked & Ready</span>}
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {layerCards.map(card => {
                    const statusCfg = getStatusConfig(card.status);
                    return (
                      <div
                        key={card.id}
                        onClick={() => onOpenCard(card)}
                        className="flex flex-col p-4 bg-card/40 hover:bg-card/60 border border-white/5 rounded-xl transition-all duration-300 cursor-pointer group"
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
                          {card.name}
                        </h4>

                        {card.cleanDescription && (
                          <p className="text-[10px] text-secondary line-clamp-2 mb-3">
                            {card.cleanDescription}
                          </p>
                        )}

                        {/* Dependencies display */}
                        {card.dependencies.length > 0 && (
                          <div className="mt-auto pt-3 border-t border-white/5 flex items-center gap-1.5">
                            <Link className="w-3 h-3 text-secondary" />
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
        /* ---- CANVAS INTERACTIVE WORKFLOW GRAPH (SVG + Absolute positioning) ---- */
        <div className="flex-1 overflow-auto relative p-8 custom-scrollbar scroll-smooth">
          {layers.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <GitBranch className="w-12 h-12 text-secondary/20 mb-4" />
              <p className="font-mono text-xs uppercase tracking-wider text-secondary">
                No active tasks found on this board.
              </p>
            </div>
          ) : (
            <div 
              style={{
                width: `${layers.length * (nodeWidth + colGap) + 120}px`,
                height: `${Math.max(...layers.map(l => l.length)) * (nodeHeight + rowGap) + 200}px`,
                backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 0)",
                backgroundSize: "24px 24px"
              }}
              className="relative"
            >
              {/* SVG Connector lines layer */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
                <defs>
                  <marker
                    id="arrow-blocks"
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
                    id="arrow-requires"
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
                    id="arrow-default"
                    viewBox="0 0 10 10"
                    refX="6"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 2 L 8 5 L 0 8 z" fill="rgba(255, 255, 255, 0.12)" />
                  </marker>
                </defs>

                {links.map((link, idx) => {
                  const fromCoord = nodeCoords.get(link.from);
                  const toCoord = nodeCoords.get(link.to);
                  
                  if (!fromCoord || !toCoord) return null;

                  const x1 = fromCoord.x + nodeWidth;
                  const y1 = fromCoord.y + nodeHeight / 2;
                  
                  const x2 = toCoord.x;
                  const y2 = toCoord.y + nodeHeight / 2;

                  const ctrlX1 = x1 + colGap / 3;
                  const ctrlY1 = y1;
                  const ctrlX2 = x2 - colGap / 3;
                  const ctrlY2 = y2;

                  const pathStr = `M ${x1} ${y1} C ${ctrlX1} ${ctrlY1}, ${ctrlX2} ${ctrlY2}, ${x2} ${y2}`;

                  let strokeColor = "rgba(255, 255, 255, 0.08)";
                  let marker = "url(#arrow-default)";
                  let strokeWidth = 1.5;
                  let animateDash = false;

                  if (link.active) {
                    strokeWidth = 2.5;
                    if (link.type === "requires") {
                      strokeColor = "oklch(55% 0.18 260)"; // requirements/ancestors highlighted in blue
                      marker = "url(#arrow-requires)";
                    } else {
                      strokeColor = "oklch(65% 0.22 45)"; // successor path highlighted in orange
                      marker = "url(#arrow-blocks)";
                      animateDash = true;
                    }
                  }

                  return (
                    <g key={idx}>
                      <path
                        d={pathStr}
                        fill="none"
                        stroke={strokeColor}
                        strokeWidth={strokeWidth}
                        markerEnd={marker}
                        strokeDasharray={animateDash ? "5, 5" : undefined}
                        className={animateDash ? "animate-[dash_10s_linear_infinite]" : "transition-all duration-300"}
                        style={{
                          animation: animateDash ? "dash 0.6s linear infinite" : undefined
                        }}
                      />
                      {/* CSS Keyframes for animated dashes */}
                      <style>{`
                        @keyframes dash {
                          to {
                            stroke-dashoffset: -20;
                          }
                        }
                      `}</style>
                    </g>
                  );
                })}
              </svg>

              {/* Card Nodes Layer */}
              <AnimatePresence>
                {layers.flatMap((layerCards, layerIdx) => 
                  layerCards.map(card => {
                    const coords = nodeCoords.get(card.id);
                    if (!coords) return null;

                    const isHovered = hoveredCardId === card.id;
                    const isRelated = hoveredCardId === null || relatedCardIds.has(card.id);
                    const statusCfg = getStatusConfig(card.status);

                    return (
                      <motion.div
                        key={card.id}
                        initial={{ opacity: 0, y: coords.y + 20 }}
                        animate={{ 
                          opacity: isRelated ? 1 : 0.2, 
                          scale: isHovered ? 1.02 : 1,
                          x: coords.x,
                          y: coords.y
                        }}
                        transition={{ type: "spring", stiffness: 350, damping: 25 }}
                        onMouseEnter={() => setHoveredCardId(card.id)}
                        onMouseLeave={() => setHoveredCardId(null)}
                        style={{
                          width: `${nodeWidth}px`,
                          height: `${nodeHeight}px`,
                          position: "absolute"
                        }}
                        className={`group z-10 p-3 bg-card/60 backdrop-blur-md rounded-xl border flex flex-col justify-between transition-shadow duration-300 cursor-pointer ${
                          isHovered 
                            ? "border-tertiary/40 shadow-lg shadow-tertiary/5" 
                            : "border-white/5"
                        }`}
                      >
                        {/* Card Title & Priority */}
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
                          
                          <h3 className="text-[11px] font-bold text-primary line-clamp-2 mt-1.5 group-hover:text-tertiary transition-colors">
                            {card.name}
                          </h3>
                        </div>

                        {/* Node Footer Actions */}
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

                          <div className="flex items-center gap-1">
                            {/* Edit Dependencies Link Button */}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingDepsCardId(card.id);
                              }}
                              className="p-1 text-secondary hover:text-primary transition-colors hover:bg-white/5 rounded flex items-center gap-1 text-[8px] font-bold uppercase tracking-widest cursor-pointer"
                              title="Edit Dependencies"
                            >
                              <Link className="w-3 h-3" />
                              Link
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      )}

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
                    className="p-1 text-secondary hover:text-primary transition-colors rounded hover:bg-white/5 cursor-pointer"
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
