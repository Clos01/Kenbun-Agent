"use client";

import React, { useState, useMemo, useEffect, useRef } from "react";
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
  FileText,
  ZoomIn,
  ZoomOut,
  Maximize2
} from "lucide-react";
import { parseCardMetadata, injectCardMetadata, KenbunMetadata } from "../app/board/page";
import { computeWorkOrder } from "../lib/prioritize";
import { useTheme } from "../context/ThemeContext";

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
  const { preset } = useTheme();
  const [layoutDir, setLayoutDir] = useState<LayoutDir>("LR");
  const [svgCode, setSvgCode] = useState<string>("");
  const [isRendering, setIsRendering] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [groupByLanes, setGroupByLanes] = useState<boolean>(true);
  const [lineStyle, setLineStyle] = useState<"basis" | "step" | "linear">("basis");
  const [diagramMode, setDiagramMode] = useState<"flowchart" | "mindmap" | "ascii">("flowchart");

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
          score: workOrder.score.get(card.id) || 0,
          rank: workOrder.rank.get(card.id) || 999
        };
      });
  }, [cards, listMap, workOrder]);

  const parsedCardMap = useMemo(() => {
    return new Map(parsedCards.map(c => [c.id, c]));
  }, [parsedCards]);

  // Mindmap code builder
  const mindmapCode = useMemo(() => {
    const lines: string[] = [];
    lines.push("mindmap");
    lines.push("  root((Project Board))");
    
    lists.forEach(list => {
      const listCards = parsedCards.filter(c => c.listId === list.id);
      if (listCards.length > 0) {
        const safeListName = list.name.replace(/[^a-zA-Z0-9\s]/g, "");
        lines.push(`    ${safeListName}`);
        listCards.forEach(card => {
          const safeCardName = card.name.replace(/[^a-zA-Z0-9\s]/g, "");
          lines.push(`      ${safeCardName}`);
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
      
      const border = "+----------------------+";
      const headerText = `|  ${list.name.toUpperCase().padEnd(18).substring(0, 18)}  |`;
      colLines.push(border);
      colLines.push(headerText);
      colLines.push(border);
      colLines.push("|                      |");
      
      listCards.forEach(card => {
        const cleanName = card.name.replace(/[\r\n\t]/g, " ");
        const titleLine = `| [#${card.rank}] ${cleanName.padEnd(14).substring(0, 14)} |`;
        const scoreLine = `| Priority: ${String(card.score).padEnd(10).substring(0, 10)} |`;
        colLines.push("+----------------------+");
        colLines.push(titleLine);
        colLines.push(scoreLine);
        colLines.push("+----------------------+");
        colLines.push("|                      |");
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

      // Construct a premium card component HTML string based on shape type
      let htmlLabel = "";
      if (card.shape === "terminal") {
        // Pill-shaped terminal node
        htmlLabel = `
          <div class='px-4 py-2.5 rounded-full border bg-card text-left transition-all hover:scale-[1.02] shadow-sm flex items-center justify-between gap-3 border-border' style='width: 190px; border-color: var(--border); background-color: var(--card);'>
            <div class='flex items-center gap-2 truncate'>
              <span class='w-2 h-2 rounded-full ${statusColor} shrink-0'></span>
              <span class='text-[9px] font-bold text-primary truncate' style='color: var(--primary);'>${cleanTitle}</span>
            </div>
            <span class='text-[7px] font-mono uppercase tracking-wider text-secondary/60 shrink-0' style='color: var(--secondary); opacity: 0.6;'>Terminal</span>
          </div>
        `.replace(/\s+/g, " ").trim();
      } else if (card.shape === "decision") {
        // Decision Gate styled card
        htmlLabel = `
          <div class='p-3.5 rounded-xl border bg-card text-left transition-all hover:scale-[1.02] shadow-sm flex flex-col gap-2' style='width: 190px; min-height: 85px; border-color: var(--accent, var(--tertiary)); background-color: var(--card); border-width: 1.5px;'>
            <div class='flex items-center justify-between'>
              <div class='flex items-center gap-1.5'>
                <span class='w-2 h-2 rounded-full' style='background-color: var(--accent, var(--tertiary));'></span>
                <span class='text-[7.5px] font-mono font-bold uppercase tracking-wider' style='color: var(--accent, var(--tertiary));'>Decision Gate</span>
              </div>
              <span class='text-[7.5px] font-mono px-1 py-0.5 rounded text-secondary' style='background-color: var(--neutral); color: var(--secondary);'>#${card.rank}</span>
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
          <div class='p-3.5 rounded-xl border bg-card text-left transition-all hover:scale-[1.02] shadow-sm flex flex-col gap-2 border-border' style='width: 190px; min-height: 85px; border-color: var(--border); background-color: var(--card);'>
            <div class='flex items-center justify-between'>
              <div class='flex items-center gap-1.5'>
                <span class='w-2 h-2 rounded-full ${statusColor}'></span>
                <span class='text-[7.5px] font-mono font-bold uppercase tracking-wider text-secondary' style='color: var(--secondary);'>${statusText}</span>
              </div>
              <span class='text-[7.5px] font-mono px-1 py-0.5 rounded text-secondary' style='background-color: var(--neutral); color: var(--secondary);'>#${card.rank}</span>
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
    
    // Declare links with edge labels
    parsedCards.forEach(card => {
      card.dependencies.forEach(depId => {
        if (parsedCardMap.has(depId)) {
          const label = card.linkLabels?.[depId];
          if (label) {
            lines.push(`  c_${depId} -->|"${label}"| c_${card.id}`);
          } else {
            lines.push(`  c_${depId} --> c_${card.id}`);
          }
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
      lines.push(`  click c_${card.id} onMermaidNodeClick`);
    });
    lines.push("");



    return lines.join("\n");
  }, [parsedCards, parsedCardMap, layoutDir, mermaidThemeStyles, groupByLanes, lists]);



  // Render Mermaid code into SVG
  useEffect(() => {
    let isMounted = true;

    async function renderMermaid() {
      const activeCode = diagramMode === "mindmap" ? mindmapCode : mermaidCode;
      
      if (diagramMode === "ascii") {
        setIsRendering(false);
        return;
      }

      if (isMounted) {
        setIsRendering(true);
      }
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: preset === "obsidian" ? "dark" : "default",
          securityLevel: "loose",
          fontFamily: "Space Mono, monospace",
          flowchart: {
            htmlLabels: true,
            curve: lineStyle
          }
        });

        const id = `mermaid-canvas-${Math.random().toString(36).substring(2, 9)}`;
        const { svg } = await mermaid.render(id, activeCode);

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
  }, [mermaidCode, mindmapCode, diagramMode, lineStyle, preset]);

  // Register passive-false wheel listener on canvasRef to handle scroll zoom without page scrolling
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || diagramMode === "ascii") return;

    const handleWheelEvent = (e: WheelEvent) => {
      e.preventDefault();
      const zoomFactor = 0.08;
      const direction = e.deltaY < 0 ? 1 : -1;
      setScale(prev => {
        const next = prev + direction * zoomFactor;
        return Math.min(Math.max(next, 0.25), 3);
      });
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
      case "completed": return "bg-emerald-500 border-emerald-500/20 text-emerald-400";
      case "in_progress": return "bg-sky-500 border-sky-500/20 text-sky-400";
      case "blocked": return "bg-amber-500 border-amber-500/20 text-amber-400";
      default: return "bg-neutral-400 border-white/5 text-secondary";
    }
  };

  return (
    <div 
      className="flex flex-col h-[calc(100vh-8.5rem)] relative border rounded-2xl overflow-hidden select-none"
      style={{ backgroundColor: "var(--neutral)", borderColor: "var(--border)" }}
    >
      <style dangerouslySetInnerHTML={{ __html: `
        .flowchart-link {
          stroke: var(--border) !important;
          stroke-opacity: 0.65 !important;
          stroke-width: 1.5px !important;
          transition: stroke 0.2s ease, stroke-width 0.2s ease !important;
        }
        .flowchart-link:hover {
          stroke: var(--tertiary) !important;
          stroke-opacity: 1 !important;
          stroke-width: 2.2px !important;
        }
        .marker {
          fill: var(--border) !important;
          stroke: var(--border) !important;
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
        /* Make backing SVG shapes fully transparent since we style HTML cards */
        .node rect, .node polygon, .node circle, .node path {
          fill: none !important;
          stroke: none !important;
          stroke-width: 0px !important;
        }
      ` }} />
      
      {/* Top Header controls bar */}
      <div 
        className="flex items-center justify-between px-6 py-4 border-b shrink-0 z-30"
        style={{ backgroundColor: "var(--card)", borderColor: "var(--border)" }}
      >
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
          {/* Zoom controls (Only for non-ASCII diagrams) */}
          {diagramMode !== "ascii" && (
            <div className="flex items-center gap-1 bg-white/5 border border-white/10 rounded px-1.5 py-1">
              <button
                onClick={() => setScale(prev => Math.max(prev - 0.15, 0.25))}
                className="p-1 hover:bg-white/5 rounded text-secondary hover:text-primary transition-colors cursor-pointer"
                title="Zoom Out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }}
                className="px-1 text-[9px] font-mono font-bold text-secondary hover:text-primary cursor-pointer"
                title="Reset zoom & fit canvas"
              >
                {Math.round(scale * 100)}%
              </button>
              <button
                onClick={() => setScale(prev => Math.min(prev + 0.15, 3))}
                className="p-1 hover:bg-white/5 rounded text-secondary hover:text-primary transition-colors cursor-pointer"
                title="Zoom In"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }}
                className="p-1 hover:bg-white/5 rounded text-secondary hover:text-primary transition-colors cursor-pointer border-l border-white/10 ml-0.5 pl-1.5"
                title="Recenter Canvas"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Diagram Mode Selection */}
          <div className="flex items-center gap-1.5 bg-white/5 border border-white/10 rounded px-2 py-1.5">
            <span className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">Mode:</span>
            <select
              value={diagramMode}
              onChange={(e) => setDiagramMode(e.target.value as any)}
              className="bg-transparent text-[9px] font-mono text-primary font-bold uppercase focus:outline-none cursor-pointer"
            >
              <option value="flowchart">Flowchart</option>
              <option value="mindmap">Mindmap</option>
              <option value="ascii">ASCII Board</option>
            </select>
          </div>

          {diagramMode === "flowchart" && (
            <>
              <button
                onClick={() => setGroupByLanes(prev => !prev)}
                className={`px-2.5 py-1.5 border rounded text-[9px] font-mono font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 cursor-pointer ${
                  groupByLanes
                    ? "bg-tertiary/10 border-tertiary/30 text-tertiary"
                    : "bg-white/5 border-white/10 text-secondary hover:text-primary hover:bg-white/10"
                }`}
                title="Group Flowchart Nodes by Kanban Lanes"
              >
                Lanes: {groupByLanes ? "Enabled" : "Disabled"}
              </button>

              <div className="flex items-center gap-1.5 bg-white/5 border border-white/10 rounded px-2 py-1.5">
                <span className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">Curve:</span>
                <select
                  value={lineStyle}
                  onChange={(e) => setLineStyle(e.target.value as any)}
                  className="bg-transparent text-[9px] font-mono text-primary font-bold uppercase focus:outline-none cursor-pointer"
                >
                  <option value="basis">Curved</option>
                  <option value="step">Orthogonal</option>
                  <option value="linear">Straight</option>
                </select>
              </div>

              <button
                onClick={() => setLayoutDir(prev => prev === "LR" ? "TD" : "LR")}
                className="px-2.5 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded text-[9px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-all flex items-center gap-1.5 cursor-pointer"
                title="Toggle Flowchart Layout Direction"
              >
                <Layout className="w-3.5 h-3.5" />
                Orientation: {layoutDir === "LR" ? "Left-to-Right" : "Top-to-Bottom"}
              </button>
            </>
          )}

          <button
            onClick={handleCopyCode}
            className="px-2.5 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded text-[9px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-all flex items-center gap-1.5 cursor-pointer"
            title="Copy Diagram Code/ASCII representation"
          >
            <Copy className="w-3.5 h-3.5" />
            {copied ? "Copied!" : "Copy diagram"}
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
        <div 
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          className="flex-1 relative flex items-center justify-center overflow-hidden select-none"
          style={{
            backgroundColor: "var(--neutral)",
            backgroundImage: "radial-gradient(var(--border) 1px, transparent 0)",
            backgroundSize: "20px 20px",
            cursor: diagramMode !== "ascii" ? (isPanning ? "grabbing" : "grab") : "default"
          }}
        >
          {isRendering && (
            <div 
              className="absolute inset-0 backdrop-blur-xs flex items-center justify-center gap-2.5 z-40"
              style={{ backgroundColor: "rgba(var(--neutral), 0.7)" }}
            >
              <RefreshCw className="w-4 h-4 text-tertiary animate-spin" />
              <span className="font-mono text-xs uppercase tracking-wider text-secondary">
                Rendering diagram...
              </span>
            </div>
          )}

          {diagramMode === "ascii" ? (
            <div className="w-full h-full flex flex-col justify-stretch p-4 min-w-[700px] overflow-auto select-text">
              <pre className="font-mono text-[10px] p-6 bg-card border border-border text-primary rounded-xl leading-relaxed whitespace-pre select-text">
                {asciiGridCode}
              </pre>
            </div>
          ) : svgCode ? (
            <div 
              className="w-full flex items-center justify-center p-4 min-w-[700px]"
              style={{
                transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
                transformOrigin: "center center",
                transition: isPanning ? "none" : "transform 0.1s ease-out",
                pointerEvents: "auto"
              }}
              dangerouslySetInnerHTML={{ __html: svgCode }}
            />
          ) : (
            <div className="font-mono text-xs uppercase text-secondary">
              No flowchart schema active.
            </div>
          )}
        </div>

        {/* Right Side: Interactive Shape Designer Toolbar & Editor Panel */}
        <div 
          className="w-80 border-l flex flex-col shrink-0 z-20"
          style={{ backgroundColor: "var(--card)", borderColor: "var(--border)" }}
        >
          
          {/* Tab bar header */}
          <div 
            className="flex border-b shrink-0"
            style={{ backgroundColor: "var(--card)", borderColor: "var(--border)" }}
          >
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
                            const labelValue = selectedCard.linkLabels?.[item.id] || "";
                            return (
                              <div
                                key={item.id}
                                className={`w-full flex flex-col gap-2 p-2.5 rounded-lg border text-left transition-colors ${
                                  isLinked
                                    ? "bg-tertiary/10 border-tertiary/30 text-primary"
                                    : "bg-white/2 border-white/5 text-secondary"
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
                                  <div className="flex items-center gap-2 pt-1.5 border-t border-white/5">
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
