"use client";

import React, { useMemo } from "react";
import { motion } from "framer-motion";
import { Calendar, CheckCircle2, Clock } from "lucide-react";

interface Card {
  id: string;
  listId: string;
  name: string;
  description: string;
  position: number;
  isClosed: boolean;
  dueDate?: string;
}

interface List {
  id: string;
  boardId: string;
  name: string;
  position: number;
}

interface TimelineGanttViewProps {
  cards: Card[];
  lists: List[];
  onClose: () => void;
  onOpenCard?: (card: Card) => void;
}

export default function TimelineGanttView({ cards, lists, onOpenCard }: TimelineGanttViewProps) {
  const sortedCards = useMemo(() => {
    return [...cards].sort((a, b) => a.position - b.position);
  }, [cards]);

  const listMap = useMemo(() => {
    const map = new Map<string, string>();
    lists.forEach(l => map.set(l.id, l.name));
    return map;
  }, [lists]);

  return (
    <div className="w-full h-full flex flex-col bg-background text-primary overflow-hidden select-none p-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase bg-primary/10 text-tertiary border border-border">
              Diagram Design Studio
            </span>
            <span className="text-[11px] font-mono text-secondary">
              Cathryn Lavery Editorial Timeline Layout
            </span>
          </div>
          <h1 className="text-xl font-bold text-primary tracking-tight">
            Project Milestones & Execution Sequence
          </h1>
        </div>

        <div className="flex items-center gap-2 text-[10px] font-mono text-secondary">
          <Calendar className="w-3.5 h-3.5 text-tertiary" />
          <span>Sequential Order: 1 to {sortedCards.length}</span>
        </div>
      </div>

      {/* Timeline Stream Container */}
      <div className="flex-1 bg-card border border-border rounded-xl p-6 overflow-y-auto shadow-sm">
        <div className="relative border-l-2 border-border/80 ml-4 space-y-6">
          {sortedCards.map((card, index) => {
            const listName = listMap.get(card.listId) || "Backlog";
            const isDone = listName.toLowerCase().includes("done") || listName.toLowerCase().includes("complete") || card.isClosed;

            return (
              <motion.div
                key={card.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.04 }}
                className="relative pl-6 group"
              >
                {/* Timeline Dot */}
                <div
                  className={`absolute -left-[9px] top-1.5 w-4 h-4 rounded-full border-2 bg-background flex items-center justify-center transition-all ${
                    isDone
                      ? "border-emerald-500 text-emerald-400"
                      : "border-tertiary text-tertiary"
                  }`}
                >
                  <div
                    className={`w-1.5 h-1.5 rounded-full ${
                      isDone ? "bg-emerald-400" : "bg-tertiary"
                    }`}
                  />
                </div>

                {/* Milestone Card */}
                <div
                  onClick={() => onOpenCard && onOpenCard(card)}
                  className="bg-background/60 hover:bg-background border border-border hover:border-tertiary/60 rounded-xl p-4 transition-all cursor-pointer shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 rounded text-[8px] font-mono font-bold uppercase bg-primary/5 border border-border text-secondary">
                        Step #{index + 1}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[8px] font-mono font-bold uppercase bg-tertiary/10 text-tertiary">
                        {listName}
                      </span>
                    </div>
                    <h3 className="text-xs font-bold text-primary truncate">
                      {card.name}
                    </h3>
                    {card.description && (
                      <p className="text-[10px] text-secondary line-clamp-1 mt-0.5">
                        {card.description}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-3 shrink-0 text-[9px] font-mono text-secondary">
                    {isDone ? (
                      <span className="flex items-center gap-1 text-emerald-400 font-bold">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Completed</span>
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-amber-400 font-bold">
                        <Clock className="w-3.5 h-3.5" />
                        <span>In Queue</span>
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
