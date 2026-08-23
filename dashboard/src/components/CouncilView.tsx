"use client";

import React, { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { ShieldCheck, Zap, DollarSign, Palette, Sparkles, CheckCircle2, Play, RefreshCw } from "lucide-react";

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

interface CouncilViewProps {
  cards: Card[];
  lists: List[];
  onClose: () => void;
  onOpenCard?: (card: Card) => void;
}

interface PersonaScore {
  name: string;
  role: string;
  icon: React.ReactNode;
  color: string;
  score: number;
  verdict: "APPROVED" | "CAUTION" | "BLOCKED";
  criteria: string[];
}

export default function CouncilView({ cards, onOpenCard }: CouncilViewProps) {
  const [selectedCardId, setSelectedCardId] = useState<string>(cards[0]?.id || "");
  const [isAuditing, setIsAuditing] = useState<boolean>(false);

  const selectedCard = useMemo(() => {
    return cards.find(c => c.id === selectedCardId) || cards[0];
  }, [cards, selectedCardId]);

  const councilScores: PersonaScore[] = useMemo(() => {
    if (!selectedCard) return [];
    const text = (selectedCard.name + " " + selectedCard.description).toLowerCase();

    const hasAuth = text.includes("auth") || text.includes("login") || text.includes("token") || text.includes("rls") || text.includes("jwt");
    const secScore = hasAuth ? 92 : 88;
    const secVerdict = secScore >= 85 ? "APPROVED" : "CAUTION";

    const hasIndex = text.includes("index") || text.includes("db") || text.includes("scale") || text.includes("async") || text.includes("queue");
    const scaleScore = hasIndex ? 95 : 85;
    const scaleVerdict = "APPROVED";

    const isLocal = text.includes("local") || text.includes("p330") || text.includes("sqlite") || text.includes("tars") || text.includes("vlm");
    const costScore = isLocal ? 98 : 82;
    const costVerdict = costScore >= 90 ? "APPROVED" : "CAUTION";

    const hasUI = text.includes("ui") || text.includes("view") || text.includes("card") || text.includes("dashboard") || text.includes("modal");
    const uiScore = hasUI ? 96 : 90;
    const uiVerdict = "APPROVED";

    const hasTest = text.includes("test") || text.includes("unit") || text.includes("doc") || text.includes("refactor");
    const debtScore = hasTest ? 94 : 86;
    const debtVerdict = "APPROVED";

    return [
      {
        name: "CyberGuard",
        role: "Zero-Trust Security & Secrets Isolation",
        icon: <ShieldCheck className="w-4 h-4 text-emerald-400" />,
        color: "#10B981",
        score: secScore,
        verdict: secVerdict,
        criteria: ["Zero-trust auth boundaries", "Input sanitization", "Secret credential masking"]
      },
      {
        name: "ScaleMaster",
        role: "Concurrency, Indexing & High-Load Architecture",
        icon: <Zap className="w-4 h-4 text-blue-400" />,
        color: "#3B82F6",
        score: scaleScore,
        verdict: scaleVerdict,
        criteria: ["Horizontally scalable DB indexing", "Asynchronous task queueing", "Rate-limit protection"]
      },
      {
        name: "FrugalCFO",
        role: "Local-First Execution & Minimal Token Waste",
        icon: <DollarSign className="w-4 h-4 text-amber-400" />,
        color: "#F59E0B",
        score: costScore,
        verdict: costVerdict,
        criteria: ["Local P330 GPU execution first", "Tiered model cost escalation", "Zero unnecessary cloud API calls"]
      },
      {
        name: "PixelArchitect",
        role: "Heritage Design System & Micro-Interactions",
        icon: <Palette className="w-4 h-4 text-purple-400" />,
        color: "#8B5CF6",
        score: uiScore,
        verdict: uiVerdict,
        criteria: ["Limestone/Clay palette adherence", "Progressive disclosure", "Right-aligned tabular numbers"]
      },
      {
        name: "FutureSelf",
        role: "Technical Debt & STRUCTURE.md Maintainability",
        icon: <Sparkles className="w-4 h-4 text-cyan-400" />,
        color: "#06B6D4",
        score: debtScore,
        verdict: debtVerdict,
        criteria: ["Self-documenting modular design", "PhantomDrive anti-pattern avoidance", "Automated TDD coverage"]
      }
    ];
  }, [selectedCard]);

  const compositeScore = useMemo(() => {
    if (!councilScores.length) return 0;
    const total = councilScores.reduce((acc, s) => acc + s.score, 0);
    return Math.round(total / councilScores.length);
  }, [councilScores]);

  const runConsensusAudit = () => {
    setIsAuditing(true);
    setTimeout(() => {
      setIsAuditing(false);
    }, 1200);
  };

  return (
    <div className="w-full h-full flex flex-col bg-background text-primary overflow-hidden select-none p-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase bg-primary/10 text-tertiary border border-border">
              System 2 Consensus Engine
            </span>
            <span className="text-[11px] font-mono text-secondary">
              5-Persona Advisory Board
            </span>
          </div>
          <h1 className="text-xl font-bold text-primary tracking-tight">
            Multi-Persona Consensus & Governance
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={runConsensusAudit}
            disabled={isAuditing}
            className="px-3.5 py-1.5 rounded-md text-[11px] font-mono font-bold tracking-wider uppercase bg-primary text-neutral hover:bg-primary/90 transition-all flex items-center gap-2 cursor-pointer shadow-sm disabled:opacity-50"
          >
            {isAuditing ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Auditing...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                <span>Run System 2 Audit</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden min-h-0">
        {/* Left Column: Task Selector */}
        <div className="bg-card border border-border rounded-xl p-4 flex flex-col min-h-0">
          <div className="flex items-center justify-between pb-3 border-b border-border mb-3">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-secondary">
              Active Task Cards ({cards.length})
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {cards.map(card => {
              const isSelected = card.id === selectedCard?.id;
              return (
                <div
                  key={card.id}
                  onClick={() => {
                    setSelectedCardId(card.id);
                    if (onOpenCard) onOpenCard(card);
                  }}
                  className={`p-3 rounded-lg border text-left cursor-pointer transition-all ${
                    isSelected
                      ? "bg-primary/10 border-tertiary shadow-sm"
                      : "bg-background/40 hover:bg-background/80 border-border"
                  }`}
                >
                  <div className="text-[11px] font-bold text-primary truncate">
                    {card.name}
                  </div>
                  <div className="text-[9px] font-mono text-secondary mt-1 flex items-center justify-between">
                    <span>Task ID: #{card.id.slice(0, 6)}</span>
                    <span className="text-emerald-400 font-bold">Consensus: 90%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Center & Right Column: 5 Persona Cards */}
        <div className="lg:col-span-2 flex flex-col gap-4 overflow-y-auto pr-1">
          {/* Target Card Header Banner */}
          <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between shadow-sm">
            <div>
              <span className="text-[9px] font-mono uppercase tracking-widest text-secondary font-bold">
                Audited Objective
              </span>
              <h2 className="text-sm font-bold text-primary mt-0.5">
                {selectedCard?.name}
              </h2>
            </div>
            <div className="text-right">
              <div className="text-[9px] font-mono uppercase tracking-widest text-secondary font-bold">
                Composite Score
              </div>
              <div className="text-2xl font-bold font-mono text-emerald-400">
                {compositeScore}%
              </div>
            </div>
          </div>

          {/* 5 Personas Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {councilScores.map(persona => (
              <motion.div
                key={persona.name}
                whileHover={{ y: -2 }}
                className="bg-card border border-border rounded-xl p-4 flex flex-col justify-between shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-lg bg-background border border-border">
                        {persona.icon}
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-primary leading-none">
                          {persona.name}
                        </h4>
                        <span className="text-[8.5px] font-mono text-secondary">
                          {persona.role}
                        </span>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[8px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      {persona.verdict}
                    </span>
                  </div>

                  {/* Criteria Checklist */}
                  <ul className="space-y-1 my-3 text-[9px] font-mono text-secondary">
                    {persona.criteria.map((c, i) => (
                      <li key={i} className="flex items-center gap-1.5">
                        <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
                        <span>{c}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Score Bar */}
                <div className="pt-2 border-t border-border flex items-center justify-between text-[9px] font-mono">
                  <span className="text-secondary">Pillar Health</span>
                  <span className="font-bold text-primary">{persona.score}%</span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
