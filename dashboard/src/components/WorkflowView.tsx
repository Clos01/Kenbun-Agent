"use client";

import React, { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  X, 
  Plus,
  GitBranch,
  Copy,
  ChevronRight,
  Layout,
  RefreshCw,
  Trash2,
  FileText
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
  onUpdateCardDesc: (cardId: string, newDescription: string) => Promise<void>;
  onCreateCard: (name: string, listId: string, x: number, y: number) => Promise<void>;
  onDeleteCard: (cardId: string) => Promise<void>;
}

type ShapeType = "process" | "decision" | "terminal";
type LayoutDir = "TD" | "LR";

export default function WorkflowView({
  cards,
  lists,
  onOpenCard,
  onUpdateCardDesc,
  onCreateCard,
  onDeleteCard
}: WorkflowViewProps) {
  const [layoutDir, setLayoutDir] = useState<LayoutDir>("LR");
  const [svgCode, setSvgCode] = useState<string>("");
  const [isRendering, setIsRendering] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

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
          shape,
          status,
          score: workOrder.score.get(card.id) || 0,
          rank: workOrder.rank.get(card.id) || 999
        };
      });
  }, [cards, listMap, workOrder]);

  const parsedCardMap = useMemo(() => {
    return new Map(parsedCards.map(c => [c.id, c]));
  }, [parsedCards]);

  const selectedCard = useMemo(() => {
    if (!selectedCardId) return null;
    return parsedCardMap.get(selectedCardId) || null;
  }, [selectedCardId, parsedCardMap]);

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
    lines.push("  classDef completed fill:#0f1d16,stroke:#10b981,stroke-width:1.5px,color:#34d399,font-size:10.5px;");
    lines.push("  classDef in_progress fill:#0b192c,stroke:#0284c7,stroke-width:1.5px,color:#38bdf8,font-size:10.5px;");
    lines.push("  classDef blocked fill:#211406,stroke:#f59e0b,stroke-width:1.5px,color:#fbbf24,font-size:10.5px;");
    lines.push("  classDef todo fill:#161616,stroke:#374151,stroke-width:1.2px,color:#9ca3af,font-size:10.5px;");
    lines.push("");

    // Declare shapes
    parsedCards.forEach(card => {
      // Escape title special characters
      const cleanTitle = card.name.replace(/"/g, "'");
      const titleWithRank = `[#${card.rank}] ${cleanTitle}`;
      const id = `c_${card.id}`;
      
      if (card.shape === "decision") {
        lines.push(`  ${id}{"${titleWithRank}"}`);
      } else if (card.shape === "terminal") {
        lines.push(`  ${id}(["${titleWithRank}"])`);
      } else {
        lines.push(`  ${id}["${titleWithRank}"]`);
      }
    });

    lines.push("");
    
    // Declare links
    parsedCards.forEach(card => {
      card.dependencies.forEach(depId => {
        if (parsedCardMap.has(depId)) {
          lines.push(`  c_${depId} --> c_${card.id}`);
        }
      });
    });

    lines.push("");

    // Assign status classes
    parsedCards.forEach(card => {
      lines.push(`  class c_${card.id} ${card.status};`);
    });

    lines.push("");

    // Assign click events
    parsedCards.forEach(card => {
      lines.push(`  click c_${card.id} call onMermaidNodeClick`);
    });

    return lines.join("\n");
  }, [parsedCards, parsedCardMap, layoutDir]);

  // Render Mermaid code into SVG
  useEffect(() => {
    let isMounted = true;

    async function renderMermaid() {
      if (isMounted) {
        setIsRendering(true);
      }
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          securityLevel: "loose",
          fontFamily: "Space Mono, monospace",
          flowchart: {
            htmlLabels: true,
            curve: "basis"
          }
        });

        const id = `mermaid-canvas-${Math.random().toString(36).substring(2, 9)}`;
        const { svg } = await mermaid.render(id, mermaidCode);

        if (isMounted) {
          setSvgCode(svg);
        }
      } catch (err) {
        console.error("Mermaid parsing/rendering error:", err);
      } finally {
        if (isMounted) {
          setIsRendering(false);
        }
      }
    }

    renderMermaid();

    return () => {
      isMounted = false;
    };
  }, [mermaidCode]);

  // Copy code helper
  const handleCopyCode = () => {
    navigator.clipboard.writeText(mermaidCode);
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
      case "completed": return "bg-emerald-500 border-emerald-500/20 text-emerald-400";
      case "in_progress": return "bg-sky-500 border-sky-500/20 text-sky-400";
      case "blocked": return "bg-amber-500 border-amber-500/20 text-amber-400";
      default: return "bg-neutral-400 border-white/5 text-secondary";
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] relative bg-[#070707] border border-white/5 rounded-2xl overflow-hidden select-none">
      
      {/* Top Header controls bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-[#0b0b0b] shrink-0 z-30">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-tertiary" />
          <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-primary">
            Sovereign Mermaid-Driven Flowchart Maker
          </h2>
          <span className="text-[10px] font-mono text-secondary px-2 py-0.5 bg-white/5 rounded">
            Auto-Generated
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setLayoutDir(prev => prev === "LR" ? "TD" : "LR")}
            className="px-2.5 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded text-[9px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-all flex items-center gap-1.5 cursor-pointer"
            title="Toggle Flowchart Layout Direction"
          >
            <Layout className="w-3.5 h-3.5" />
            Orientation: {layoutDir === "LR" ? "Left-to-Right" : "Top-to-Bottom"}
          </button>
          
          <button
            onClick={handleCopyCode}
            className="px-2.5 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded text-[9px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-all flex items-center gap-1.5 cursor-pointer"
            title="Copy Mermaid.js Markdown Source"
          >
            <Copy className="w-3.5 h-3.5" />
            {copied ? "Copied!" : "Copy code"}
          </button>

          <button
            onClick={() => setIsAddingStep(true)}
            className="px-3 py-1.5 bg-primary text-neutral hover:bg-primary/95 rounded text-[9px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add step
          </button>
        </div>
      </div>

      {/* Main split-screen workspace */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Side: Dynamic Interactive Mermaid Canvas */}
        <div className="flex-1 overflow-auto relative p-8 flex items-center justify-center bg-[#080808]"
          style={{
            backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 0)",
            backgroundSize: "20px 20px"
          }}
        >
          {isRendering && (
            <div className="absolute inset-0 bg-[#080808]/70 backdrop-blur-xs flex items-center justify-center gap-2.5 z-40">
              <RefreshCw className="w-4 h-4 text-tertiary animate-spin" />
              <span className="font-mono text-xs uppercase tracking-wider text-secondary">
                Rendering diagram...
              </span>
            </div>
          )}

          {svgCode ? (
            <div 
              className="w-full flex items-center justify-center p-4 min-w-[700px] overflow-auto select-none pointer-events-auto"
              dangerouslySetInnerHTML={{ __html: svgCode }}
            />
          ) : (
            <div className="font-mono text-xs uppercase text-secondary">
              No flowchart schema active.
            </div>
          )}
        </div>

        {/* Right Side: Interactive Shape Designer Toolbar & Editor Panel */}
        <div className="w-80 border-l border-white/5 bg-[#0a0a0a] flex flex-col shrink-0 z-20">
          
          {/* Tab bar header */}
          <div className="flex border-b border-white/5 bg-[#0e0e0e] shrink-0">
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
                <div className="flex-1 bg-neutral p-4 rounded-xl border border-white/5 font-mono text-[9.5px] leading-relaxed text-secondary select-all whitespace-pre overflow-auto h-72 custom-scrollbar">
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
                    <div className="space-y-1 pb-4 border-b border-white/5">
                      <div className="flex justify-between items-start gap-2">
                        <span className="text-[9px] font-mono font-bold text-tertiary bg-tertiary/10 border border-tertiary/20 px-1.5 py-0.5 rounded uppercase">
                          {selectedCard.shape}
                        </span>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => onOpenCard(selectedCard)}
                            className="p-1 text-secondary hover:text-primary hover:bg-white/5 rounded transition-all cursor-pointer"
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
                      <div className="grid grid-cols-3 gap-1 bg-white/2 rounded p-0.5 border border-white/5">
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
                        <p className="text-[10px] text-secondary leading-relaxed bg-white/2 p-3 rounded-lg border border-white/5">
                          {selectedCard.cleanDescription}
                        </p>
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
                            return (
                              <button
                                key={item.id}
                                onClick={() => handleToggleDependency(selectedCard.id, item.id)}
                                className={`w-full flex items-center justify-between p-2.5 rounded-lg border text-left transition-colors cursor-pointer ${
                                  isLinked
                                    ? "bg-tertiary/10 border-tertiary/30 text-primary"
                                    : "bg-white/2 hover:bg-white/5 border-white/5 text-secondary hover:text-primary"
                                }`}
                              >
                                <span className="text-[10px] font-medium leading-tight truncate mr-2">
                                  {item.name}
                                </span>
                                <ChevronRight className={`w-3.5 h-3.5 shrink-0 transition-transform ${isLinked ? "rotate-90 text-tertiary" : "text-secondary/40"}`} />
                              </button>
                            );
                          })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

          </div>
        </div>

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
              className="w-full max-w-sm bg-card border border-white/10 p-6 rounded-2xl shadow-xl flex flex-col"
            >
              <div className="flex justify-between items-center pb-4 border-b border-white/5 mb-4">
                <h3 className="font-mono text-xs uppercase tracking-widest text-primary font-bold">
                  Add Flowchart Step
                </h3>
                <button
                  type="button"
                  onClick={() => setIsAddingStep(false)}
                  className="p-1 text-secondary hover:text-primary rounded hover:bg-white/5 cursor-pointer"
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
                    className="w-full px-3 py-2 bg-neutral border border-white/10 rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40"
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
                      className="w-full px-3 py-2 bg-neutral border border-white/10 rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40 cursor-pointer"
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
                      className="w-full px-3 py-2 bg-neutral border border-white/10 rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40 cursor-pointer"
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
                    className="px-4 py-2 border border-white/10 hover:bg-white/5 rounded text-[9px] font-bold uppercase tracking-widest text-secondary hover:text-primary transition-colors cursor-pointer"
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
