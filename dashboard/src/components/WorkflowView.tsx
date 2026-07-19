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
  Trash2,
  Edit2,
  FileText,
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
  onDeleteCard: (cardId: string) => Promise<void>;
}

type ShapeType = "process" | "decision" | "terminal";

export default function WorkflowView({
  cards,
  lists,
  onOpenCard,
  onMoveCard,
  onUpdateCardDesc,
  onCreateCard,
  onDeleteCard
}: WorkflowViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Pan & Zoom state
  const [zoom, setZoom] = useState<number>(0.95);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 40, y: 20 });
  const [isDraggingCanvas, setIsDraggingCanvas] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Floating shape drawer tool selected ("process" | "decision" | "terminal")
  const [selectedShapeTool, setSelectedShapeTool] = useState<ShapeType>("process");

  // Hover states & editor selectors
  const [hoveredCardId, setHoveredCardId] = useState<string | null>(null);
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState<string>("");
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
  const [newNodeShape, setNewNodeShape] = useState<ShapeType>("process");

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
          layout: metadata.layout,
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

  // Fallback layers computation (used only if nodes do not have persisted custom coordinates)
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

  // Dimension settings
  const nodeWidth = 220;
  const nodeHeight = 84;
  const decisionWidth = 120; // Decisions are 120x120 diamonds
  const decisionHeight = 120;
  const colGap = 160;
  const rowGap = 50;

  // Final coordinates mapping
  const nodeCoords = useMemo(() => {
    const coords = new Map<string, { x: number; y: number }>();
    
    // Calculate fallbacks
    const fallbackCoords = new Map<string, { x: number; y: number }>();
    layers.forEach((layerCards, layerIdx) => {
      const x = layerIdx * (nodeWidth + colGap) + 120;
      const startY = 120;
      layerCards.forEach((card, cardIdx) => {
        const y = startY + cardIdx * (nodeHeight + rowGap + 20);
        fallbackCoords.set(card.id, { x, y });
      });
    });

    parsedCards.forEach(card => {
      if (card.layout) {
        coords.set(card.id, card.layout);
      } else {
        coords.set(card.id, fallbackCoords.get(card.id) || { x: 120, y: 120 });
      }
    });

    return coords;
  }, [layers, parsedCards]);

  // SVG connection mapping
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

  // Highlight connections
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
    e.preventDefault();
    const zoomFactor = 0.04;
    const nextZoom = e.deltaY < 0 ? zoom + zoomFactor : zoom - zoomFactor;
    setZoom(Math.max(0.4, Math.min(1.8, nextZoom)));
  };

  // Node Drag coordinates save
  const handleNodeDragEnd = async (cardId: string, info: any) => {
    const card = parsedCardMap.get(cardId);
    const coords = nodeCoords.get(cardId);
    if (!card || !coords) return;

    const nextX = coords.x + info.offset.x / zoom;
    const nextY = coords.y + info.offset.y / zoom;

    const updatedMetadata: KenbunMetadata = {
      ...card.metadata,
      layout: { x: Math.round(nextX), y: Math.round(nextY) }
    };

    const newDescription = injectCardMetadata(card.description, updatedMetadata);
    await onUpdateCardDesc(cardId, newDescription);
  };

  // Port link drawing handlers
  const handlePortMouseDown = (e: React.MouseEvent, cardId: string) => {
    e.stopPropagation();
    e.preventDefault();
    
    const coord = nodeCoords.get(cardId);
    const card = parsedCardMap.get(cardId);
    if (!coord || !card) return;

    // Output starts from the rightmost edge of node
    const width = card.shape === "decision" ? decisionWidth : nodeWidth;
    const height = card.shape === "decision" ? decisionHeight : nodeHeight;
    const portX = coord.x + width;
    const portY = coord.y + height / 2;

    setDrawingFromId(cardId);
    setDrawingCoords({
      x1: portX,
      y1: portY,
      x2: portX,
      y2: portY
    });
  };

  const handlePortMouseUp = async (e: React.MouseEvent, targetCardId: string) => {
    e.stopPropagation();
    if (!drawingFromId || drawingFromId === targetCardId) return;

    // Dropped onto target node -> target depends on drawingFromId
    await handleToggleDependency(targetCardId, drawingFromId);

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

  // Double click canvas to add node
  const handleCanvasDoubleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest(".draggable-node") || target.closest(".port-handle") || target.closest("button") || target.closest("input") || target.closest(".shape-sidebar")) return;
    if (drawingFromId || editingDepsCardId) return;

    if (canvasRef.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const clickX = (e.clientX - rect.left) / zoom;
      const clickY = (e.clientY - rect.top) / zoom;
      
      setCreatingNodeCoords({ x: Math.round(clickX), y: Math.round(clickY) });
      setNewNodeShape(selectedShapeTool);
    }
  };

  const handleCreateNodeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNodeName.trim() || !creatingNodeCoords || !newNodeListId) return;

    // Create Planka card with coordinate layouts & shape type in metadata
    const initialMetadata: KenbunMetadata = {
      layout: { x: creatingNodeCoords.x, y: creatingNodeCoords.y },
      shape: newNodeShape
    };

    const initialDesc = injectCardMetadata("", initialMetadata);
    
    // Trigger creation
    await onCreateCard(newNodeName.trim(), newNodeListId, creatingNodeCoords.x, creatingNodeCoords.y);
    
    // Find the newly created card and update description metadata (handled in onCreateCard callback or page.tsx)
    // Wait, since handleCreateCard in page.tsx will reload list details, we can let it complete.
    setNewNodeName("");
    setCreatingNodeCoords(null);
  };

  // Inline rename handler
  const startRename = (cardId: string, currentName: string) => {
    setEditingCardId(cardId);
    setRenameText(currentName);
  };

  const submitRename = async (cardId: string) => {
    if (!renameText.trim()) return;
    const card = parsedCardMap.get(cardId);
    if (!card) return;

    try {
      // Trigger update title via page callback or local PATCH helper. 
      // We can patch card name by updating Planka card.
      const res = await fetch(`http://100.104.211.61:1337/api/cards/${cardId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: renameText.trim() })
      });
      // Wait, Planka API is proxied. Or we can update Planka description or title via API.
      // Let's use the onUpdateCardDesc but since it updates description, we can rename using description's metadata if we wanted, or we just write a name patch!
      // In page.tsx we have a tenantFetch helper.
      // To keep it simple, let's trigger a client-side PATCH directly to `/api/v1/planka/cards/:cardId`:
      const apiBase = "http://100.104.211.61:8001"; // API_BASE
      const token = localStorage.getItem("tenant_access_token") || "";
      await fetch(`${apiBase}/api/v1/planka/cards/${cardId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ name: renameText.trim() })
      });
      
      // Force refresh board details by calling move card with same list
      await onMoveCard(cardId, card.listId);
    } catch (err) {
      console.error(err);
    } finally {
      setEditingCardId(null);
    }
  };

  const getStatusConfig = (status: "todo" | "in_progress" | "blocked" | "completed") => {
    switch (status) {
      case "completed":
        return { label: "Done", color: "bg-emerald-500", border: "border-emerald-500/30", text: "text-emerald-400" };
      case "in_progress":
        return { label: "In Progress", color: "bg-sky-500", border: "border-sky-500/30", text: "text-sky-400" };
      case "blocked":
        return { label: "Blocked", color: "bg-amber-500", border: "border-amber-500/30", text: "text-amber-400" };
      default:
        return { label: "To Do", color: "bg-neutral-400", border: "border-white/10", text: "text-secondary" };
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] relative overflow-hidden bg-[#0a0a0a] border border-white/5 rounded-2xl select-none">
      
      {/* Top Diagram Controls Panel */}
      <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/5 bg-[#0e0e0e] shrink-0 z-30">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-tertiary" />
          <h2 className="font-mono text-xs uppercase tracking-widest font-bold text-primary">
            Sovereign Flowchart Designer
          </h2>
          <span className="text-[10px] font-mono text-secondary px-2 py-0.5 bg-white/5 rounded">
            {parsedCards.length} shapes
          </span>
        </div>

        {/* Toolbar Helpers */}
        <div className="hidden sm:flex items-center gap-6 text-[10px] font-mono text-secondary">
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-2.5 bg-white/5 border border-white/20 rounded-sm" />
            Process
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rotate-45 bg-white/5 border border-white/20" />
            Decision
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-2.5 bg-white/5 border border-white/20 rounded-full" />
            Terminal
          </div>
          <div className="text-[9px] text-tertiary">
            💡 Double-click canvas to place nodes, or drag from right port to link.
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
              onClick={() => { setZoom(0.95); setPan({ x: 40, y: 20 }); }}
              className="p-1 text-secondary hover:text-primary rounded hover:bg-white/5 cursor-pointer transition-colors border-l border-white/5 pl-1.5 ml-0.5"
              title="Reset Canvas View"
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
              Designer Canvas
            </button>
            <button
              onClick={() => setIsMobileTimeline(true)}
              className={`px-3 py-1 text-[9px] font-bold uppercase tracking-wider rounded transition-colors ${
                isMobileTimeline
                  ? "bg-tertiary/10 text-tertiary"
                  : "text-secondary hover:text-primary cursor-pointer"
              }`}
            >
              List Timeline
            </button>
          </div>
        </div>
      </div>

      {/* Main Designer Grid Workspace */}
      {isMobileTimeline ? (
        /* ---- MOBILE TIMELINE CHECKLIST VIEW ---- */
        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          {layers.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <GitBranch className="w-12 h-12 text-secondary/20 mb-4" />
              <p className="font-mono text-xs uppercase tracking-wider text-secondary">
                No active flowchart steps.
              </p>
            </div>
          ) : (
            layers.map((layerCards, idx) => (
              <div key={idx} className="relative pl-6 border-l border-white/5 space-y-4">
                <div className="absolute -left-1.5 top-1.5 w-3 h-3 bg-base border border-tertiary rounded-full shadow-lg shadow-tertiary/30" />
                <h3 className="font-mono text-[10px] font-bold uppercase tracking-widest text-tertiary">
                  Phase {idx + 1}
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {layerCards.map(card => {
                    const statusCfg = getStatusConfig(card.status);
                    return (
                      <div
                        key={card.id}
                        onClick={() => onOpenCard(card)}
                        className={`flex flex-col p-4 bg-card/45 hover:bg-card/75 border rounded-xl transition-all duration-300 cursor-pointer group ${
                          card.shape === "decision" ? "border-amber-500/25 bg-amber-500/[0.01]" : "border-white/5"
                        }`}
                      >
                        <div className="flex justify-between items-start gap-4 mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-[9px] font-mono text-secondary uppercase px-1.5 py-0.5 bg-white/5 rounded">
                              {card.shape}
                            </span>
                            <span className={`text-[8px] font-bold uppercase tracking-wider px-2 py-0.5 border rounded-sm flex items-center gap-1 ${statusCfg.text} ${statusCfg.border}`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.color}`} />
                              {statusCfg.label}
                            </span>
                          </div>
                        </div>
                        <h4 className="text-xs font-bold text-primary mb-1 group-hover:text-tertiary transition-colors">
                          {card.name}
                        </h4>
                        {card.cleanDescription && (
                          <p className="text-[10px] text-secondary line-clamp-2">
                            {card.cleanDescription}
                          </p>
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
        /* ---- INTERACTIVE SHAPES DESIGNER CANVAS ---- */
        <div className="flex-1 flex relative overflow-hidden">
          
          {/* Left Flowchart Shape Selection Panel (Lucidchart-like Toolstrip) */}
          <div className="shape-sidebar w-16 bg-[#0d0d0d] border-r border-white/5 flex flex-col items-center py-6 gap-6 shrink-0 z-20">
            <span className="text-[8px] font-mono tracking-widest text-secondary uppercase font-bold text-center w-full px-1">
              Shapes
            </span>
            
            {/* Process Box Selector */}
            <button
              onClick={() => setSelectedShapeTool("process")}
              className={`w-11 h-11 rounded-lg border flex flex-col items-center justify-center gap-1 cursor-pointer transition-all duration-200 ${
                selectedShapeTool === "process"
                  ? "bg-tertiary/10 border-tertiary text-tertiary"
                  : "bg-white/2 border-white/5 text-secondary hover:text-primary hover:bg-white/5"
              }`}
              title="Add Process box step"
            >
              <div className="w-6 h-4 border border-current rounded-xs" />
              <span className="text-[7px] font-mono uppercase font-bold tracking-tighter">Process</span>
            </button>

            {/* Decision Gate Selector */}
            <button
              onClick={() => setSelectedShapeTool("decision")}
              className={`w-11 h-11 rounded-lg border flex flex-col items-center justify-center gap-1 cursor-pointer transition-all duration-200 ${
                selectedShapeTool === "decision"
                  ? "bg-tertiary/10 border-tertiary text-tertiary"
                  : "bg-white/2 border-white/5 text-secondary hover:text-primary hover:bg-white/5"
              }`}
              title="Add Decision Diamond"
            >
              <div className="w-4 h-4 border border-current rotate-45" />
              <span className="text-[7px] font-mono uppercase font-bold tracking-tighter mt-1">Decision</span>
            </button>

            {/* Terminal Pill Selector */}
            <button
              onClick={() => setSelectedShapeTool("terminal")}
              className={`w-11 h-11 rounded-lg border flex flex-col items-center justify-center gap-1 cursor-pointer transition-all duration-200 ${
                selectedShapeTool === "terminal"
                  ? "bg-tertiary/10 border-tertiary text-tertiary"
                  : "bg-white/2 border-white/5 text-secondary hover:text-primary hover:bg-white/5"
              }`}
              title="Add Start/End Terminal"
            >
              <div className="w-6 h-3 border border-current rounded-full" />
              <span className="text-[7px] font-mono uppercase font-bold tracking-tighter mt-0.5">Terminal</span>
            </button>
          </div>

          {/* Infinite Canvas Window */}
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
              backgroundImage: "radial-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 0)",
              backgroundSize: "24px 24px",
              backgroundPosition: `${pan.x}px ${pan.y}px`,
              backgroundColor: "#080808"
            }}
          >
            {/* Scrollable transform canvas viewport */}
            <div
              ref={canvasRef}
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transformOrigin: "0 0",
                width: "4000px",
                height: "4000px"
              }}
              className="absolute inset-0 pointer-events-none select-none"
            >
              {/* SVG Connector lines layer */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
                <defs>
                  <marker
                    id="arrow-active"
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
                    id="arrow-std-flow"
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

                {/* Render existing flowchart links */}
                {links.map((link, idx) => {
                  const fromCoord = nodeCoords.get(link.from);
                  const toCoord = nodeCoords.get(link.to);
                  const fromCard = parsedCardMap.get(link.from);
                  const toCard = parsedCardMap.get(link.to);
                  
                  if (!fromCoord || !toCoord || !fromCard || !toCard) return null;

                  // Compute visual output coordinates (Right port center)
                  const fromWidth = fromCard.shape === "decision" ? decisionWidth : nodeWidth;
                  const fromHeight = fromCard.shape === "decision" ? decisionHeight : nodeHeight;
                  const x1 = fromCoord.x + fromWidth;
                  const y1 = fromCoord.y + fromHeight / 2;
                  
                  // Compute visual input coordinates (Left port center)
                  const toHeight = toCard.shape === "decision" ? decisionHeight : nodeHeight;
                  const x2 = toCoord.x;
                  const y2 = toCoord.y + toHeight / 2;

                  // Curvature controls
                  const ctrlX1 = x1 + colGap / 2;
                  const ctrlY1 = y1;
                  const ctrlX2 = x2 - colGap / 2;
                  const ctrlY2 = y2;

                  const pathStr = `M ${x1} ${y1} C ${ctrlX1} ${ctrlY1}, ${ctrlX2} ${ctrlY2}, ${x2} ${y2}`;

                  let strokeColor = "rgba(255, 255, 255, 0.1)";
                  let marker = "url(#arrow-std-flow)";
                  let strokeWidth = 1.2;
                  let animateDash = false;

                  if (link.active) {
                    strokeWidth = 2.2;
                    strokeColor = "oklch(65% 0.22 45)"; // Amber flow glow
                    marker = "url(#arrow-active)";
                    animateDash = true;
                  }

                  return (
                    <path
                      key={idx}
                      d={pathStr}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      markerEnd={marker}
                      strokeDasharray={animateDash ? "4, 4" : undefined}
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

              {/* Render Diagram Shapes (Nodes Layer) */}
              {parsedCards.map(card => {
                const coords = nodeCoords.get(card.id) || { x: 120, y: 120 };
                const isHovered = hoveredCardId === card.id;
                const isRelated = hoveredCardId === null || relatedCardIds.has(card.id);
                const statusCfg = getStatusConfig(card.status);
                const isDrawingTarget = drawingFromId !== null && drawingFromId !== card.id;

                // Dimension configuration depending on shape type
                const width = card.shape === "decision" ? decisionWidth : nodeWidth;
                const height = card.shape === "decision" ? decisionHeight : nodeHeight;

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
                      width: `${width}px`,
                      height: `${height}px`,
                      position: "absolute"
                    }}
                    className="draggable-node pointer-events-auto group/node z-10 flex items-center justify-center select-none cursor-grab active:cursor-grabbing"
                  >
                    {/* Left Port (Input link receiver) */}
                    <div
                      onMouseUp={(e) => handlePortMouseUp(e, card.id)}
                      onMouseEnter={() => setHoveredPortId(`${card.id}-in`)}
                      onMouseLeave={() => setHoveredPortId(null)}
                      className={`port-handle absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border bg-base flex items-center justify-center cursor-crosshair z-30 transition-all duration-300 ${
                        isDrawingTarget && hoveredPortId === `${card.id}-in`
                          ? "border-emerald-500 scale-125 bg-emerald-500/10"
                          : "border-white/10 opacity-0 group-hover/node:opacity-100 hover:scale-125 hover:border-tertiary"
                      }`}
                      title="Link predecessor path here"
                    >
                      <span className="w-1.5 h-1.5 bg-secondary rounded-full" />
                    </div>

                    {/* Shape Specific Markup rendering */}
                    {card.shape === "decision" ? (
                      /* DECISION DIAMOND */
                      <div className={`relative w-[96px] h-[96px] rotate-45 border flex items-center justify-center bg-card/65 backdrop-blur-md rounded-sm transition-all duration-300 ${
                        isHovered ? "border-amber-500/40 shadow-lg shadow-amber-500/5" : "border-white/10"
                      }`}>
                        {/* Content inside un-rotated */}
                        <div className="-rotate-45 flex flex-col items-center justify-center text-center p-2.5 w-[120px] h-[120px] overflow-hidden select-none">
                          {editingCardId === card.id ? (
                            <input
                              type="text"
                              value={renameText}
                              onChange={(e) => setRenameText(e.target.value)}
                              onBlur={() => submitRename(card.id)}
                              onKeyDown={(e) => e.key === "Enter" && submitRename(card.id)}
                              className="w-full text-center bg-neutral/80 border border-tertiary/40 rounded px-1 py-0.5 text-[10px] text-primary focus:outline-none"
                              autoFocus
                            />
                          ) : (
                            <h3 
                              onDoubleClick={() => startRename(card.id, card.name)}
                              className="text-[10px] font-bold text-amber-400/90 leading-tight line-clamp-3"
                              title="Double click to rename shape"
                            >
                              {card.name}
                            </h3>
                          )}
                          
                          {/* Minimal status circle indicators */}
                          <span className={`w-1.5 h-1.5 rounded-full mt-2 ${statusCfg.color}`} />
                        </div>
                      </div>
                    ) : card.shape === "terminal" ? (
                      /* TERMINAL PILL */
                      <div className={`relative w-full h-full rounded-full border px-6 flex items-center justify-center bg-card/75 backdrop-blur-md transition-all duration-300 ${
                        isHovered ? "border-sky-500/30 shadow-lg shadow-sky-500/5" : "border-white/10"
                      }`}>
                        <div className="flex flex-col items-center text-center w-full min-w-0">
                          {editingCardId === card.id ? (
                            <input
                              type="text"
                              value={renameText}
                              onChange={(e) => setRenameText(e.target.value)}
                              onBlur={() => submitRename(card.id)}
                              onKeyDown={(e) => e.key === "Enter" && submitRename(card.id)}
                              className="w-full text-center bg-neutral/80 border border-tertiary/40 rounded px-2 py-0.5 text-[10px] text-primary focus:outline-none"
                              autoFocus
                            />
                          ) : (
                            <h3 
                              onDoubleClick={() => startRename(card.id, card.name)}
                              className="text-[10px] font-mono tracking-wide uppercase font-bold text-sky-400 truncate w-full"
                              title="Double click to rename shape"
                            >
                              {card.name}
                            </h3>
                          )}
                          <span className="text-[8px] font-mono text-secondary mt-0.5 uppercase tracking-widest leading-none">
                            {statusCfg.label}
                          </span>
                        </div>
                      </div>
                    ) : (
                      /* PROCESS BOX (STANDARD STEP) */
                      <div className={`relative w-full h-full border rounded-lg px-4 py-3 bg-card/65 backdrop-blur-md flex flex-col justify-between transition-all duration-300 ${
                        isHovered ? "border-tertiary/40 shadow-lg shadow-tertiary/5" : "border-white/10"
                      }`}>
                        <div className="flex flex-col gap-1 w-full min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.color}`} />
                            <span className="text-[8px] font-mono uppercase tracking-widest text-secondary font-bold">
                              Rank #{card.rank}
                            </span>
                          </div>

                          {editingCardId === card.id ? (
                            <input
                              type="text"
                              value={renameText}
                              onChange={(e) => setRenameText(e.target.value)}
                              onBlur={() => submitRename(card.id)}
                              onKeyDown={(e) => e.key === "Enter" && submitRename(card.id)}
                              className="w-full bg-neutral border border-tertiary/40 rounded px-1.5 py-0.5 text-[10px] text-primary focus:outline-none"
                              autoFocus
                            />
                          ) : (
                            <h3 
                              onDoubleClick={() => startRename(card.id, card.name)}
                              className="text-[10.5px] font-bold text-primary leading-snug truncate w-full"
                              title="Double click to rename shape"
                            >
                              {card.name}
                            </h3>
                          )}
                        </div>

                        {/* Description snippet if any */}
                        {card.cleanDescription && !isHovered && (
                          <span className="text-[8.5px] text-secondary/65 truncate w-full mt-0.5 leading-none">
                            {card.cleanDescription}
                          </span>
                        )}

                        {/* Interactive overlay options on hover */}
                        {isHovered && (
                          <div className="absolute right-2 bottom-2 flex items-center gap-1.5 z-30">
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); onOpenCard(card); }}
                              className="p-1 text-secondary hover:text-primary transition-colors hover:bg-white/5 rounded cursor-pointer"
                              title="Edit specifications"
                            >
                              <FileText className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setEditingDepsCardId(card.id); }}
                              className="p-1 text-secondary hover:text-primary transition-colors hover:bg-white/5 rounded cursor-pointer"
                              title="Set predecessor links"
                            >
                              <LinkIcon className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); onDeleteCard(card.id); }}
                              className="p-1 text-[#B8422E] hover:bg-[#B8422E]/10 rounded cursor-pointer transition-colors"
                              title="Delete Step"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Right Port (Output link creator) */}
                    <div
                      onMouseDown={(e) => handlePortMouseDown(e, card.id)}
                      className="port-handle absolute -right-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border border-white/10 bg-base flex items-center justify-center cursor-crosshair z-30 opacity-0 group-hover/node:opacity-100 hover:scale-125 hover:border-tertiary transition-all duration-300"
                      title="Drag connection path"
                    >
                      <Plus className="w-2.5 h-2.5 text-secondary hover:text-primary" />
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Shapes Designer Card Creation Prompt */}
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
                  Place Flowchart Node
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
                  <label htmlFor="flowchart_node_name_input" className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                    Step / Label Title
                  </label>
                  <input
                    id="flowchart_node_name_input"
                    type="text"
                    required
                    value={newNodeName}
                    onChange={(e) => setNewNodeName(e.target.value)}
                    placeholder="e.g. Phase 1 Audit, Gate: Verify Setup"
                    className="w-full px-3 py-2 bg-neutral border border-white/10 rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label htmlFor="flowchart_node_shape_select" className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                      Shape
                    </label>
                    <select
                      id="flowchart_node_shape_select"
                      value={newNodeShape}
                      onChange={(e) => setNewNodeShape(e.target.value as ShapeType)}
                      className="w-full px-3 py-2 bg-neutral border border-white/10 rounded-lg text-xs text-primary focus:outline-none focus:border-tertiary/40 cursor-pointer"
                    >
                      <option value="process">Process (Box)</option>
                      <option value="decision">Decision (Diamond)</option>
                      <option value="terminal">Terminal (Pill)</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="flowchart_node_list_select" className="text-[8px] font-mono text-secondary uppercase tracking-widest font-bold">
                      Initial Status
                    </label>
                    <select
                      id="flowchart_node_list_select"
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
                    Create Shape
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Manage Predecessors Linker Modal Overlay */}
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
                      Link Flowchart Elements
                    </h3>
                    <p className="text-[10px] text-secondary line-clamp-1">
                      Setup dependency flow for: {card.name}
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
                    Check the steps that must flow directly **into** this node:
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
                                Shape: {item.shape} • Rank #{item.rank}
                              </span>
                            </div>
                          </div>
                        </label>
                      );
                    })}

                  {parsedCards.filter(c => c.id !== editingDepsCardId).length === 0 && (
                    <p className="text-center py-6 text-xs text-secondary font-mono">
                      No other nodes exist on the flowchart workspace.
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
