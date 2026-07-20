"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { DragDropContext, Droppable, Draggable, DropResult } from "@hello-pangea/dnd";
import { motion, AnimatePresence } from "framer-motion";

interface Card {
  id: string;
  listId: string;
  name: string;
  description: string;
  position: number;
  isClosed: boolean;
  dueDate?: string;
  status?: string;
  rank?: number;
  dependencies: string[];
}

interface List {
  id: string;
  boardId: string;
  name: string;
  position: number;
  type: string;
}

interface KanbanViewProps {
  cards: Card[];
  lists: List[];
  selectedCardId: string | null;
  onSelectCard: (cardId: string) => void;
  onMoveCard: (cardId: string, newListId: string) => Promise<void>;
}

export default function KanbanView({
  cards,
  lists,
  selectedCardId,
  onSelectCard,
  onMoveCard
}: KanbanViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState<{ id: string; x1: number; y1: number; x2: number; y2: number }[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  // Measure card positions to draw dependency lines
  const updateEdges = useCallback(() => {
    if (!containerRef.current || isDragging) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const newEdges: typeof edges = [];

    cards.forEach(card => {
      const targetEl = document.getElementById(`kanban_card_${card.id}`);
      if (!targetEl) return;
      const targetRect = targetEl.getBoundingClientRect();

      card.dependencies.forEach(depId => {
        const sourceEl = document.getElementById(`kanban_card_${depId}`);
        if (!sourceEl) return;
        const sourceRect = sourceEl.getBoundingClientRect();

        // Calculate center points relative to container
        const x1 = sourceRect.left + sourceRect.width / 2 - containerRect.left;
        const y1 = sourceRect.top + sourceRect.height / 2 - containerRect.top;
        const x2 = targetRect.left + targetRect.width / 2 - containerRect.left;
        const y2 = targetRect.top + targetRect.height / 2 - containerRect.top;

        newEdges.push({
          id: `${depId}_to_${card.id}`,
          x1, y1, x2, y2
        });
      });
    });

    setEdges(newEdges);
  }, [cards, isDragging]);

  // Update edges on mount, data change, or window resize
  useEffect(() => {
    updateEdges();
    window.addEventListener("resize", updateEdges);
    // Observe scroll within the container to update edges
    const container = containerRef.current;
    if (container) {
      container.addEventListener("scroll", updateEdges, { passive: true });
      // Also observe column scrolling
      const cols = container.querySelectorAll(".kanban-col-scroll");
      cols.forEach(col => col.addEventListener("scroll", updateEdges, { passive: true }));
    }

    // Small delay to ensure DOM is settled
    const timeout = setTimeout(updateEdges, 100);

    return () => {
      window.removeEventListener("resize", updateEdges);
      if (container) {
        container.removeEventListener("scroll", updateEdges);
        const cols = container.querySelectorAll(".kanban-col-scroll");
        cols.forEach(col => col.removeEventListener("scroll", updateEdges));
      }
      clearTimeout(timeout);
    };
  }, [updateEdges]);

  const onDragStart = () => {
    setIsDragging(true);
    setEdges([]); // Hide lines while dragging to avoid messy reflows
  };

  const onDragEnd = async (result: DropResult) => {
    setIsDragging(false);
    updateEdges();

    const { destination, source, draggableId } = result;

    if (!destination) return;
    if (destination.droppableId === source.droppableId && destination.index === source.index) return;

    // Call the parent handler to update Planka
    const cardId = draggableId.replace("kanban_card_", "");
    await onMoveCard(cardId, destination.droppableId);
  };

  return (
    <div ref={containerRef} className="relative w-full h-full flex overflow-x-auto overflow-y-hidden bg-background p-6 gap-6 items-start">
      
      {/* SVG Canvas for logic arrows */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-10" style={{ minWidth: "100%", minHeight: "100%" }}>
        <AnimatePresence>
          {!isDragging && edges.map(e => {
            // Cubic bezier for a smooth curved line between columns
            const dx = Math.abs(e.x2 - e.x1);
            const cx = dx * 0.5;
            const d = `M ${e.x1} ${e.y1} C ${e.x1 + cx} ${e.y1}, ${e.x2 - cx} ${e.y2}, ${e.x2} ${e.y2}`;
            
            const isSelected = selectedCardId && e.id.includes(selectedCardId);
            
            return (
              <g key={e.id}>
                <motion.path
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  exit={{ opacity: 0 }}
                  d={d}
                  fill="none"
                  stroke={isSelected ? "var(--tertiary)" : "var(--border)"}
                  strokeWidth={isSelected ? 2 : 1.5}
                  strokeOpacity={isSelected ? 0.8 : 0.4}
                />
                {isSelected && (
                  <path
                    d={d}
                    fill="none"
                    className="tron-line"
                  />
                )}
              </g>
            );
          })}
        </AnimatePresence>
      </svg>

      <DragDropContext onDragStart={onDragStart} onDragEnd={onDragEnd}>
        {lists.map(list => {
          const listCards = cards.filter(c => c.listId === list.id).sort((a, b) => a.position - b.position);
          
          return (
            <div key={list.id} className="flex flex-col w-[320px] shrink-0 max-h-full h-full rounded-2xl bg-card border border-border/50 shadow-sm backdrop-blur-xl z-20 overflow-hidden">
              <div className="p-4 border-b border-border/50 bg-primary/[0.02]">
                <h3 className="font-mono text-[11px] font-bold uppercase tracking-widest text-primary truncate">
                  {list.name}
                </h3>
                <div className="text-[9px] font-mono text-secondary mt-1">
                  {listCards.length} cards
                </div>
              </div>
              
              <Droppable droppableId={list.id}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`flex-1 overflow-y-auto p-4 flex flex-col gap-3 kanban-col-scroll ${snapshot.isDraggingOver ? 'bg-primary/[0.02]' : ''}`}
                  >
                    {listCards.map((card, index) => {
                      const isSelected = selectedCardId === card.id;
                      
                      return (
                        <Draggable key={card.id} draggableId={`kanban_card_${card.id}`} index={index}>
                          {(provided, snapshot) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              id={`kanban_card_${card.id}`}
                              onClick={() => onSelectCard(card.id)}
                              className={`group relative p-4 rounded-xl border bg-card transition-all cursor-grab active:cursor-grabbing
                                ${snapshot.isDragging ? 'shadow-2xl scale-105 border-tertiary/50 z-50 rotate-2' : 'shadow-sm hover:scale-[1.02]'}
                                ${isSelected ? 'border-tertiary shadow-[0_0_15px_rgba(var(--tertiary-rgb),0.3)]' : 'border-border'}
                              `}
                            >
                              <div className="flex flex-col gap-2 relative z-10">
                                <div className="text-xs font-bold text-primary line-clamp-2">
                                  {card.name}
                                </div>
                                <div className="flex items-center justify-between mt-1 pt-2 border-t border-border/50">
                                  <span className="text-[9px] font-mono text-secondary uppercase tracking-wider">
                                    Priority: {card.rank || 0}
                                  </span>
                                  {card.dependencies.length > 0 && (
                                    <span className="text-[9px] font-mono text-tertiary bg-tertiary/10 px-1.5 py-0.5 rounded">
                                      {card.dependencies.length} deps
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          )}
                        </Draggable>
                      );
                    })}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </div>
          );
        })}
      </DragDropContext>
    </div>
  );
}
