"use client";

import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import Sidebar from "@/components/Sidebar";
import WorkflowView from "@/components/WorkflowView";
import { formatMarkdown } from "@/lib/markdown";
import { computeWorkOrder } from "@/lib/prioritize";
import {
  Columns,
  GitFork,
  Plus,
  Folder,
  ArrowLeft,
  Trash2,
  MessageSquare,
  Clock,
  ChevronRight,
  Check,
  Calendar,
  X,
  Search,
  Settings,
  MapPin,
  Tag,
  AlertTriangle,
  RefreshCw,
  Filter
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";
import { z } from "zod";

// Types
interface Board {
  id: string;
  projectId: string;
  name: string;
  type: string;
}

interface Project {
  id: string;
  name: string;
  type: string;
  boards?: Board[];
}

interface List {
  id: string;
  boardId: string;
  name: string;
  position: number;
  type: string;
}

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

interface Comment {
  id: string;
  cardId: string;
  userId: string;
  text: string;
  createdAt: string;
}

interface BoardComment {
  id: string;
  cardName: string;
  createdAt: string;
  text: string;
  cardId: string;
}

export interface KenbunMetadata {
  location?: string;
  recurring?: "none" | "daily" | "weekly" | "monthly";
  collections?: string[];
  dependencies?: string[];
  layout?: { x: number; y: number };
  shape?: "process" | "decision" | "terminal";
  linkLabels?: Record<string, string>;
}

const KenbunMetadataSchema = z.object({
  location: z.string().max(100).regex(/^[a-zA-Z0-9_\-\s]+$/).optional(),
  recurring: z.enum(["none", "daily", "weekly", "monthly"]).optional(),
  collections: z.array(z.string().max(50).regex(/^[a-zA-Z0-9_\-\s]+$/)).max(30).optional(),
  dependencies: z.array(z.string().max(50).regex(/^[a-zA-Z0-9_\-]+$/)).max(100).optional(),
  layout: z.object({
    x: z.number(),
    y: z.number()
  }).strict().optional(),
  shape: z.enum(["process", "decision", "terminal"]).optional(),
  linkLabels: z.record(z.string().max(50).regex(/^[a-zA-Z0-9_\-]+$/), z.string().max(100)).optional(),
}).strict();

const DescriptionInputSchema = z.string().max(50000).catch("");

function sanitizeText(input: string): string {
  if (typeof input !== "string") return "";
  return input
    .replace(/<[^>]*>?/gm, "")
    .replace(/javascript:/gi, "")
    .replace(/&#039;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

// Helpers for metadata parsing
export function parseCardMetadata(description: string): { cleanDescription: string; metadata: KenbunMetadata } {
  if (typeof description !== "string") {
    return { cleanDescription: "", metadata: {} };
  }
  const inputStr = DescriptionInputSchema.parse(description);
  if (!inputStr) {
    return { cleanDescription: "", metadata: {} };
  }

  const regex = /<!--\s*kenbun_metadata:\s*({[\s\S]*?})\s*-->/;
  const match = inputStr.match(regex);
  
  if (match) {
    try {
      const jsonStr = match[1].trim();
      
      if (jsonStr.length > 5000) {
        throw new Error("Metadata exceeds length limit.");
      }
      if (!jsonStr.startsWith("{") || !jsonStr.endsWith("}")) {
        throw new Error("Metadata is not a valid JSON object.");
      }

      const keysRegex = /"([^"]+)"\s*:/g;
      let keyMatch;
      const allowedKeys = ["location", "recurring", "collections", "dependencies", "layout", "shape", "x", "y", "linkLabels"];
      while ((keyMatch = keysRegex.exec(jsonStr)) !== null) {
        const key = keyMatch[1];
        if (!allowedKeys.includes(key)) {
          throw new Error(`Unauthorized key detected before parsing: ${key}`);
        }
      }
      
      const rawParsed = JSON.parse(jsonStr);
      
      if (!rawParsed || typeof rawParsed !== "object" || Array.isArray(rawParsed)) {
        throw new Error("Parsed metadata is not an object.");
      }
      if (Object.getPrototypeOf(rawParsed) !== Object.prototype) {
        throw new Error("Malformed prototype chain detected.");
      }
      if (
        Object.prototype.hasOwnProperty.call(rawParsed, "__proto__") ||
        Object.prototype.hasOwnProperty.call(rawParsed, "constructor") ||
        Object.prototype.hasOwnProperty.call(rawParsed, "prototype")
      ) {
        throw new Error("Malicious prototype attributes present.");
      }

      const safeParsed = Object.create(null);
      
      if (rawParsed.location !== undefined) {
        if (typeof rawParsed.location !== "string" || rawParsed.location.length > 100) {
          throw new Error("Invalid location field length.");
        }
        safeParsed.location = rawParsed.location;
      }
      
      if (rawParsed.recurring !== undefined) {
        safeParsed.recurring = rawParsed.recurring;
      }
      
      if (rawParsed.collections !== undefined) {
        if (!Array.isArray(rawParsed.collections) || rawParsed.collections.length > 30) {
          throw new Error("Collections exceeds array size boundary.");
        }
        for (let i = 0; i < rawParsed.collections.length; i++) {
          const item = rawParsed.collections[i];
          if (typeof item !== "string" || item.length > 50) {
            throw new Error("Collection item size exceeds safe limit.");
          }
        }
        safeParsed.collections = rawParsed.collections;
      }
      
      if (rawParsed.dependencies !== undefined) {
        if (!Array.isArray(rawParsed.dependencies) || rawParsed.dependencies.length > 100) {
          throw new Error("Dependencies exceeds array size boundary.");
        }
        for (let i = 0; i < rawParsed.dependencies.length; i++) {
          const item = rawParsed.dependencies[i];
          if (typeof item !== "string" || item.length > 50) {
            throw new Error("Dependency item size exceeds safe limit.");
          }
        }
        safeParsed.dependencies = rawParsed.dependencies;
      }

      if (rawParsed.layout !== undefined) {
        if (rawParsed.layout === null || typeof rawParsed.layout !== "object" || Array.isArray(rawParsed.layout)) {
          throw new Error("Invalid layout field type.");
        }
        if (typeof rawParsed.layout.x !== "number" || typeof rawParsed.layout.y !== "number") {
          throw new Error("Layout coordinates must be numbers.");
        }
        safeParsed.layout = {
          x: rawParsed.layout.x,
          y: rawParsed.layout.y
        };
      }

      if (rawParsed.shape !== undefined) {
        if (typeof rawParsed.shape !== "string" || !["process", "decision", "terminal"].includes(rawParsed.shape)) {
          throw new Error("Invalid shape field value.");
        }
        safeParsed.shape = rawParsed.shape;
      }

      if (rawParsed.linkLabels !== undefined) {
        if (typeof rawParsed.linkLabels !== "object" || Array.isArray(rawParsed.linkLabels) || rawParsed.linkLabels === null) {
          throw new Error("Invalid linkLabels field type.");
        }
        const safeLabels: Record<string, string> = {};
        for (const key in rawParsed.linkLabels) {
          if (Object.prototype.hasOwnProperty.call(rawParsed.linkLabels, key)) {
            const val = rawParsed.linkLabels[key];
            if (typeof key !== "string" || key.length > 50 || typeof val !== "string" || val.length > 100) {
              throw new Error("Invalid linkLabel key or value size.");
            }
            safeLabels[key] = val;
          }
        }
        safeParsed.linkLabels = safeLabels;
      }

      const parsed = KenbunMetadataSchema.parse(safeParsed);
      
      const metadata: KenbunMetadata = {
        location: parsed.location ? sanitizeText(parsed.location) : undefined,
        recurring: parsed.recurring,
        collections: parsed.collections ? parsed.collections.map(sanitizeText) : undefined,
        dependencies: parsed.dependencies ? parsed.dependencies.map(sanitizeText) : undefined,
        layout: parsed.layout,
        shape: parsed.shape,
        linkLabels: parsed.linkLabels
      };
      
      const rawClean = inputStr.replace(regex, "");
      const cleanDescription = sanitizeText(rawClean);
      
      return { cleanDescription, metadata };
    } catch (e) {
      console.error("Failed to parse kenbun_metadata:", e);
    }
  }
  
  return { cleanDescription: sanitizeText(inputStr), metadata: {} };
}

export function injectCardMetadata(description: string, metadata: KenbunMetadata): string {
  const { cleanDescription } = parseCardMetadata(description);
  const jsonStr = JSON.stringify(metadata);
  const metadataComment = `\n\n<!-- kenbun_metadata: ${jsonStr} -->`;
  return cleanDescription + metadataComment;
}

function parseDrillContent(description: string) {
  if (!description) return null;

  const hasQuestion = description.includes("**Question:**") || description.toLowerCase().includes("question:");
  const hasAnswer = description.includes("**Answer:**") || description.toLowerCase().includes("answer:");

  if (!hasQuestion && !hasAnswer) return null;

  let questionText = "";
  let answerText = "";

  const qMatch = description.match(/(?:\*\*Question:\*\*|Question:)\s*([\s\S]*?)(?=(?:\*\*Answer:\*\*|Answer:)|$)/i);
  if (qMatch) {
    questionText = qMatch[1].trim();
  } else {
    const qFallback = description.match(/(?:\*\*Question:\*\*|Question:)\s*([\s\S]*)/i);
    if (qFallback) {
      questionText = qFallback[1].trim();
    }
  }

  const aMatch = description.match(/(?:\*\*Answer:\*\*|Answer:)\s*([\s\S]*?)$/i);
  if (aMatch) {
    answerText = aMatch[1].trim();
  }

  if (!questionText && !answerText) return null;

  return {
    question: questionText || description,
    answer: answerText
  };
}

// Shared class fragments (Heritage: hairlines, matte surfaces, label-caps)
const LABEL_CAPS = "text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold";
const FIELD =
  "w-full bg-neutral border border-border rounded p-2.5 text-xs text-primary placeholder-secondary/50 focus:outline-none focus:border-tertiary transition-colors";

export default function BoardPage() {
  const { API_BASE } = CONFIG;

  // Structure & Core state
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedBoard, setSelectedBoard] = useState<Board | null>(null);
  const [lists, setLists] = useState<List[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active view tab: kanban | calendar | messaging | workflow
  const [activeTab, setActiveTab] = useState<"kanban" | "calendar" | "messaging" | "workflow">(() => {
    if (typeof window !== "undefined") {
      const savedTab = localStorage.getItem("board_active_tab");
      if (savedTab === "kanban" || savedTab === "calendar" || savedTab === "messaging" || savedTab === "workflow") {
        return savedTab;
      }
    }
    return "kanban";
  });

  const hasRestoredBoard = useRef(false);

  const [now, setNow] = useState<number>(1700000000000);

  useEffect(() => {
    const t = setTimeout(() => {
      setNow(Date.now());
    }, 0);
    return () => clearTimeout(t);
  }, []);

  // Persistence helpers
  const changeTab = (tab: "kanban" | "calendar" | "messaging" | "workflow") => {
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      localStorage.setItem("board_active_tab", tab);
    }
  };

  const selectBoard = (board: Board | null) => {
    setSelectedBoard(board);
    if (typeof window !== "undefined") {
      if (board) {
        localStorage.setItem("board_selected_board_id", board.id);
      } else {
        localStorage.removeItem("board_selected_board_id");
      }
    }
  };



  // Filters State
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");
  const [filterLocation, setFilterLocation] = useState("");
  const [selectedCollection, setSelectedCollection] = useState("");
  const [showMobileFilters, setShowMobileFilters] = useState(false);
  const [revealedAnswers, setRevealedAnswers] = useState<Record<string, boolean>>({});
  const toggleRevealAnswer = (cardId: string) => {
    setRevealedAnswers(prev => ({
      ...prev,
      [cardId]: !prev[cardId]
    }));
  };

  const [editingDescTab, setEditingDescTab] = useState<"write" | "preview">("preview");

  // Board Settings Drawer State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [editBoardName, setEditBoardName] = useState("");
  const [confirmDeleteBoard, setConfirmDeleteBoard] = useState(false);

  // Calendar View Month/Year navigation
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth());
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  // Calendar: which day's completed-work popover is open (key = "y-m-d")
  const [expandedDoneKey, setExpandedDoneKey] = useState<string | null>(null);
  // Calendar: which day's active-work popover is open (key = "y-m-d")
  const [expandedActiveKey, setExpandedActiveKey] = useState<string | null>(null);

  // Board comments feed state
  const [boardComments, setBoardComments] = useState<BoardComment[]>([]);
  const [loadingComments, setLoadingComments] = useState(false);
  const [feedCommentText, setFeedCommentText] = useState("");
  const [feedSelectedCardId, setFeedSelectedCardId] = useState("");

  // Card side panel state
  const [selectedCard, setSelectedCard] = useState<Card | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [newCommentText, setNewCommentText] = useState("");
  const [isAddingProject, setIsAddingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");

  const [activeAddingListForBoard, setActiveAddingListForBoard] = useState(false);
  const [newListName, setNewListName] = useState("");
  const [activeAddingBoardForProjectId, setActiveAddingBoardForProjectId] = useState<string | null>(null);
  const [newBoardName, setNewBoardName] = useState("");
  const [activeAddingCardForListId, setActiveAddingCardForListId] = useState<string | null>(null);
  const [newCardName, setNewCardName] = useState("");

  const [editingCardName, setEditingCardName] = useState("");
  const [editingCardDesc, setEditingCardDesc] = useState("");

  // Custom metadata input states in the side panel
  const [cardLocation, setCardLocation] = useState("");
  const [cardCollections, setCardCollections] = useState("");
  const [cardRecurrence, setCardRecurrence] = useState<"none" | "daily" | "weekly" | "monthly">("none");
  const [cardDueDate, setCardDueDate] = useState("");

  // Fetch all projects & boards (structure)
  const fetchStructure = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/structure`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`HTTP Error ${res.status}: Failed to retrieve Planka structure`);
      }
      const data = await res.json();

      const items = data.items || [];
      const included = data.included || {};
      const boards = included.boards || [];

      // Associate boards to projects
      const formattedProjects = items.map((proj: { id: string; [key: string]: unknown }) => ({
        ...proj,
        boards: boards.filter((b: { projectId: string; [key: string]: unknown }) => b.projectId === proj.id)
      }));

      setProjects(formattedProjects);

      // Restore selected board from localStorage on initial load
      if (typeof window !== "undefined" && !hasRestoredBoard.current) {
        const savedBoardId = localStorage.getItem("board_selected_board_id");
        if (savedBoardId) {
          let foundBoard = null;
          for (const proj of formattedProjects) {
            const matched = proj.boards.find((b: { id: string }) => b.id === savedBoardId);
            if (matched) {
              foundBoard = matched;
              break;
            }
          }
          if (foundBoard) {
            setSelectedBoard(foundBoard);
            hasRestoredBoard.current = true;
          }
        }
      }
    } catch (err: unknown) {
      console.error(err);
      const message = err instanceof Error ? err.message : String(err);
      setError(message || "Failed to connect to Planka backend");
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  // Fetch full board lists and cards
  const fetchBoardDetails = useCallback(async (boardId: string) => {
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/board/${boardId}`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`Failed to load board details: ${res.status}`);
      }
      const data = await res.json();
      const included = data.included || {};

      // Sort lists
      const activeLists = (included.lists || [])
        .filter((l: { type: string; isClosed: boolean; [key: string]: unknown }) => l.type === "active" && !l.isClosed)
        .sort((a: { position?: number }, b: { position?: number }) => (a.position || 0) - (b.position || 0));

      // Sort cards
      const activeCards = (included.cards || [])
        .filter((c: { isClosed: boolean; [key: string]: unknown }) => !c.isClosed)
        .sort((a: { position?: number }, b: { position?: number }) => (a.position || 0) - (b.position || 0));

      setLists(activeLists);
      setCards(activeCards);
    } catch (err: unknown) {
      console.error(err);
      const message = err instanceof Error ? err.message : String(err);
      setError(`Failed to sync board: ${message}`);
    } finally {
      setSyncing(false);
    }
  }, [API_BASE]);

  // Fetch comments for a specific card
  const fetchComments = useCallback(async (cardId: string) => {
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards/${cardId}/comments`, { cache: "no-store" });
      if (!res.ok) throw new Error("Failed to load comments");
      const data = await res.json();
      const commentsList = (data.items || []).sort(
        (a: { createdAt: string }, b: { createdAt: string }) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      );
      setComments(commentsList);
    } catch (err) {
      console.error("Error loading comments:", err);
    }
  }, [API_BASE]);

  // Fetch comments for all cards on the board to aggregate in feed
  const fetchBoardComments = useCallback(async (silent = false) => {
    if (!selectedBoard || cards.length === 0) return;
    if (!silent) setLoadingComments(true);
    try {
      const allCommentsPromises = cards.map(async (card) => {
        try {
          const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards/${card.id}/comments`, { cache: "no-store" });
          if (!res.ok) return [];
          const data = await res.json();
          return (data.items || []).map((c: Record<string, string | number | boolean | null | undefined>) => ({
            ...c,
            cardName: card.name,
            cardId: card.id,
          }));
        } catch {
          return [];
        }
      });
      const results = await Promise.all(allCommentsPromises);
      const aggregated = (results.flat() as { createdAt: string }[]).sort(
        (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      );
      setBoardComments(aggregated as BoardComment[]);
    } catch (err) {
      console.error("Error loading board feed:", err);
    } finally {
      if (!silent) setLoadingComments(false);
    }
  }, [API_BASE, selectedBoard, cards]);

  // Handle card selection & side panel opening
  const handleOpenCard = useCallback((card: Card) => {
    setSelectedCard(card);
    setEditingCardName(card.name);

    // Parse metadata
    const { cleanDescription, metadata } = parseCardMetadata(card.description || "");
    setEditingCardDesc(cleanDescription);
    setEditingDescTab("preview");
    setCardLocation(metadata.location || "");
    setCardCollections((metadata.collections || []).join(", "));
    setCardRecurrence(metadata.recurring || "none");
    setCardDueDate(card.dueDate ? card.dueDate.split("T")[0] : "");

    fetchComments(card.id);
  }, [fetchComments]);

  // Lifecycle
  useEffect(() => {
    setTimeout(() => {
      fetchStructure();
    }, 0);
  }, [fetchStructure]);

  useEffect(() => {
    if (selectedBoard) {
      setTimeout(() => {
        fetchBoardDetails(selectedBoard.id);
      }, 0);

      // Setup polling for live updates
      const timer = setInterval(() => {
        fetchBoardDetails(selectedBoard.id);
      }, 7000);
      return () => clearInterval(timer);
    }
  }, [selectedBoard, fetchBoardDetails]);

  // Fetch comments feed on feed tab activation
  useEffect(() => {
    if (activeTab === "messaging" && selectedBoard) {
      setTimeout(() => {
        fetchBoardComments();
      }, 0);
      // Live signal feed: silently re-poll comments on the board's cadence
      const timer = setInterval(() => {
        fetchBoardComments(true);
      }, 7000);
      return () => clearInterval(timer);
    }
  }, [activeTab, selectedBoard, fetchBoardComments]);

  // Actions
  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newProjectName.trim(), type: "private" })
      });
      if (res.ok) {
        setNewProjectName("");
        setIsAddingProject(false);
        fetchStructure();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  const handleUpdateBoard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBoard || !editBoardName.trim()) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/boards/${selectedBoard.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editBoardName.trim() })
      });
      if (res.ok) {
        const updated = { ...selectedBoard, name: editBoardName.trim() };
        selectBoard(updated);
        setIsSettingsOpen(false);
        fetchStructure();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteBoard = async () => {
    if (!selectedBoard) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/boards/${selectedBoard.id}`, {
        method: "DELETE"
      });
      if (res.ok) {
        selectBoard(null);
        setIsSettingsOpen(false);
        setConfirmDeleteBoard(false);
        fetchStructure();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  const handleCreateBoard = async (projectId: string) => {
    if (!newBoardName.trim()) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/projects/${projectId}/boards`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newBoardName.trim() })
      });
      if (res.ok) {
        setNewBoardName("");
        setActiveAddingBoardForProjectId(null);
        fetchStructure();
      } else {
        setError(`Failed to create board (HTTP ${res.status})`);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to create board: network error");
    } finally {
      setSyncing(false);
    }
  };

  const handleCreateList = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newListName.trim() || !selectedBoard) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/boards/${selectedBoard.id}/lists`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newListName.trim() })
      });
      if (res.ok) {
        setNewListName("");
        setActiveAddingListForBoard(false);
        fetchBoardDetails(selectedBoard.id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  const handleCreateCard = async (listId: string) => {
    if (!newCardName.trim()) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listId, name: newCardName.trim() })
      });
      if (res.ok) {
        setNewCardName("");
        setActiveAddingCardForListId(null);
        if (selectedBoard) fetchBoardDetails(selectedBoard.id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  const handleMoveCard = async (cardId: string, newListId: string) => {
    try {
      setSyncing(true);
      // Optimistic update
      setCards(prev => prev.map(c => c.id === cardId ? { ...c, listId: newListId } : c));

      const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards/${cardId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listId: newListId })
      });
      if (!res.ok) {
        setError(`Failed to move card (HTTP ${res.status})`);
        if (selectedBoard) fetchBoardDetails(selectedBoard.id);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to move card: network error");
      if (selectedBoard) fetchBoardDetails(selectedBoard.id);
    } finally {
      setSyncing(false);
    }
  };

  const handleUpdateCardDetails = async () => {
    if (!selectedCard) return;
    try {
      setSyncing(true);

      // Construct metadata
      const collectionsArray = cardCollections
        .split(",")
        .map(c => c.trim())
        .filter(c => c.length > 0);

      const metadata: KenbunMetadata = {
        location: cardLocation.trim() || undefined,
        collections: collectionsArray.length > 0 ? collectionsArray : undefined,
        recurring: cardRecurrence !== "none" ? cardRecurrence : undefined
      };

      const fullDescription = injectCardMetadata(editingCardDesc, metadata);

      let formattedDueDate: string | null = null;
      if (cardDueDate) {
        const dateParts = cardDueDate.split("-");
        const d = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]));
        formattedDueDate = d.toISOString();
      }

      const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards/${selectedCard.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editingCardName,
          description: fullDescription,
          dueDate: formattedDueDate
        })
      });

      if (res.ok) {
        const updated = {
          ...selectedCard,
          name: editingCardName,
          description: fullDescription,
          dueDate: formattedDueDate || undefined
        };
        setCards(prev => prev.map(c => c.id === selectedCard.id ? updated : c));
        setSelectedCard(null);
        if (selectedBoard) fetchBoardDetails(selectedBoard.id);
      } else {
        setError(`Failed to save card (HTTP ${res.status})`);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to save card: network error");
    } finally {
      setSyncing(false);
    }
  };

  const handleCloseCard = async (cardId: string) => {
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards/${cardId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        setCards(prev => prev.filter(c => c.id !== cardId));
        if (selectedCard?.id === cardId) {
          setSelectedCard(null);
        }
      } else {
        setError(`Failed to delete card (HTTP ${res.status})`);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to delete card: network error");
    } finally {
      setSyncing(false);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCommentText.trim() || !selectedCard) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards/${selectedCard.id}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: newCommentText.trim() })
      });
      if (res.ok) {
        setNewCommentText("");
        fetchComments(selectedCard.id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  const handleAddFeedComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedCommentText.trim() || !feedSelectedCardId) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards/${feedSelectedCardId}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: feedCommentText.trim() })
      });
      if (res.ok) {
        setFeedCommentText("");
        fetchBoardComments();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  // Global work order: rank every open, actionable card by priority so each
  // card can show where it sits in the "do this first, then next" sequence.
  // Computed over ALL cards (not the search-filtered subset) so ranks stay
  // stable while filtering. Scoring mirrors scripts/prioritize_board.py.
  const workOrder = useMemo(() => computeWorkOrder(cards, lists), [cards, lists]);

  // Filter Cards Logic
  const filteredCards = cards.filter(card => {
    const { cleanDescription, metadata } = parseCardMetadata(card.description || "");

    // 1. Fuzzy query search (name + clean description)
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const nameMatch = card.name.toLowerCase().includes(q);
      const descMatch = cleanDescription.toLowerCase().includes(q);
      if (!nameMatch && !descMatch) return false;
    }

    // 2. Date limits
    if (filterStartDate) {
      if (!card.dueDate) return false;
      const cardDate = new Date(card.dueDate);
      const startDate = new Date(filterStartDate);
      if (cardDate < startDate) return false;
    }
    if (filterEndDate) {
      if (!card.dueDate) return false;
      const cardDate = new Date(card.dueDate);
      const endDate = new Date(filterEndDate);
      endDate.setHours(23, 59, 59, 999);
      if (cardDate > endDate) return false;
    }

    // 3. Location filter
    if (filterLocation) {
      const loc = (metadata.location || "").toLowerCase();
      if (!loc.includes(filterLocation.toLowerCase())) return false;
    }

    // 4. Collection/Tag filter
    if (selectedCollection) {
      const colls = metadata.collections || [];
      if (!colls.includes(selectedCollection)) return false;
    }

    return true;
  });

  // Extract all unique collections dynamically
  const allCollections = Array.from(new Set(
    cards.flatMap(card => {
      const { metadata } = parseCardMetadata(card.description || "");
      return metadata.collections || [];
    })
  ));

  // Completed work detection: cards sitting in a done-type list count as
  // completions, dated by listChangedAt (when Planka moved them there) —
  // no manual due-date entry needed.
  const doneListIds = new Set(
    lists.filter(l => /complet|done|finish|ship/i.test(l.name)).map(l => l.id)
  );
  const isDoneCard = (c: Card) => doneListIds.has(c.listId) && !!c.listChangedAt;
  const completedThisMonth = filteredCards.filter(c => {
    if (!isDoneCard(c)) return false;
    const d = new Date(c.listChangedAt!);
    return d.getMonth() === currentMonth && d.getFullYear() === currentYear;
  }).length;



  const isOverdue = (c: Card) =>
    !!c.dueDate && !isDoneCard(c) && new Date(c.dueDate).getTime() < now;

  const hasActiveFilters = !!(searchQuery || filterStartDate || filterEndDate || filterLocation || selectedCollection);

  // Calendar Math
  const getDaysInMonth = (month: number, year: number) => {
    return new Date(year, month + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (month: number, year: number) => {
    return new Date(year, month, 1).getDay();
  };

  const generateCalendarCells = () => {
    const daysInCurrent = getDaysInMonth(currentMonth, currentYear);
    const firstDayIndex = getFirstDayOfMonth(currentMonth, currentYear);
    const cells = [];

    const prevMonth = currentMonth === 0 ? 11 : currentMonth - 1;
    const prevYear = currentMonth === 0 ? currentYear - 1 : currentYear;
    const daysInPrev = getDaysInMonth(prevMonth, prevYear);
    for (let i = firstDayIndex - 1; i >= 0; i--) {
      cells.push({
        day: daysInPrev - i,
        month: prevMonth,
        year: prevYear,
        isCurrentMonth: false,
      });
    }

    for (let i = 1; i <= daysInCurrent; i++) {
      cells.push({
        day: i,
        month: currentMonth,
        year: currentYear,
        isCurrentMonth: true,
      });
    }

    const totalCells = cells.length;
    const nextMonthPadding = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    const nextMonth = currentMonth === 11 ? 0 : currentMonth + 1;
    const nextYear = currentMonth === 11 ? currentYear + 1 : currentYear;
    for (let i = 1; i <= nextMonthPadding; i++) {
      cells.push({
        day: i,
        month: nextMonth,
        year: nextYear,
        isCurrentMonth: false,
      });
    }

    return cells;
  };

  const isSameDay = (dateStr: string, cell: { day: number; month: number; year: number }) => {
    const d = new Date(dateStr);
    return d.getDate() === cell.day && d.getMonth() === cell.month && d.getFullYear() === cell.year;
  };

  return (
    <div className="min-h-screen bg-neutral text-primary flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden font-sans">
      {/* Heritage backdrop — static drafting grid, faded at the edges, with two matte washes */}
      <div aria-hidden="true" className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] opacity-30 [mask-image:radial-gradient(ellipse_80%_80%_at_50%_30%,black_25%,transparent_100%)]" />
        <div className="absolute top-[-25%] left-[-15%] w-[55vw] h-[55vw] bg-tertiary/[0.04] rounded-full blur-[140px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[45vw] h-[45vw] bg-[#B8422E]/[0.03] rounded-full blur-[120px]" />
      </div>

      <Sidebar />

      <main className="flex-1 relative z-10 flex flex-col min-w-0 pb-20 lg:pb-0">
        {/* ============ HEADER — single calm row ============ */}
        <header className="h-14 sm:h-16 border-b border-primary/10 bg-neutral/85 backdrop-blur-sm sticky top-0 z-30 shrink-0 flex items-center justify-between px-3 sm:px-6 lg:px-10 gap-3 sm:gap-6">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            {selectedBoard ? (
              <button
                onClick={() => {
                  selectBoard(null);
                  changeTab("kanban");
                }}
                className="p-1.5 -ml-1 text-secondary hover:text-primary transition-colors rounded cursor-pointer"
                aria-label="Back to projects"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            ) : (
              <Columns className="w-4 h-4 text-tertiary shrink-0" />
            )}
            <div className="min-w-0">
              <div className={LABEL_CAPS + " leading-none mb-0.5 text-[8px] sm:text-[9px]"}>
                {selectedBoard ? "Kanban Board" : "Workspaces"}
              </div>
              <h1 className="font-serif italic text-base sm:text-lg font-bold text-primary leading-tight truncate">
                {selectedBoard ? selectedBoard.name : "Mission Board"}
              </h1>
            </div>

            {/* Tabs live in the header — no second nav row */}
            {selectedBoard && (
              <nav className="hidden xl:flex items-center gap-1 ml-6 border-l border-primary/10 pl-6 h-full">
                {([
                  { key: "kanban", label: "Board", icon: Columns },
                  { key: "calendar", label: "Calendar", icon: Calendar },
                  { key: "messaging", label: "Feed", icon: MessageSquare },
                  { key: "workflow", label: "Workflow", icon: GitFork },
                ] as const).map(t => (
                  <button
                    key={t.key}
                    onClick={() => changeTab(t.key)}
                    className={`px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer transition-colors ${
                      activeTab === t.key
                        ? "text-tertiary bg-tertiary/10"
                        : "text-secondary hover:text-primary"
                    }`}
                  >
                    <t.icon className="w-3.5 h-3.5" />
                    {t.label}
                  </button>
                ))}
              </nav>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Search and Filters */ }
            {selectedBoard && activeTab === "kanban" && (
              <div className="flex items-center gap-2 mr-2">
                <div className="hidden md:flex items-center gap-2 bg-neutral/40 border border-border rounded-md px-2.5 py-1 w-32 lg:w-48 xl:w-64 transition-all focus-within:border-tertiary/50">
                  <Search className="w-3.5 h-3.5 text-secondary shrink-0" />
                  <input
                    type="text"
                    placeholder="Search cards…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-transparent text-xs text-primary placeholder-secondary/50 focus:outline-none w-full py-0.5"
                  />
                  {searchQuery && (
                    <button onClick={() => setSearchQuery("")} className="text-secondary hover:text-primary cursor-pointer" aria-label="Clear search">
                      <X className="w-3 h-3" />
                    </button>
                  )}
                </div>
                <div className="relative">
                  <button
                    onClick={() => setShowMobileFilters(!showMobileFilters)}
                    className={`p-1.5 rounded-md cursor-pointer transition-all flex items-center justify-center gap-1.5 ${
                      showMobileFilters || hasActiveFilters
                        ? "bg-tertiary/10 text-tertiary"
                        : "text-secondary hover:text-primary hover:bg-card"
                    }`}
                    title="Toggle filters"
                  >
                    <Filter className="w-4 h-4" />
                    {hasActiveFilters && (
                      <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-tertiary rounded-full animate-pulse" />
                    )}
                  </button>

                  <AnimatePresence>
                    {showMobileFilters && (
                      <>
                        <motion.div 
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="fixed inset-0 z-40"
                          onClick={() => setShowMobileFilters(false)}
                        />
                        <motion.div
                          initial={{ opacity: 0, y: 8, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 8, scale: 0.95 }}
                          className="absolute top-full right-0 mt-2 w-72 bg-card/95 backdrop-blur-xl border border-border/80 rounded-xl shadow-2xl overflow-hidden z-50 flex flex-col p-4 gap-4"
                        >
                          {/* Mobile Search - only shows on mobile */}
                          <div className="md:hidden flex items-center gap-2 bg-neutral/40 border border-border rounded-md px-2.5 py-1 w-full">
                            <Search className="w-3.5 h-3.5 text-secondary shrink-0" />
                            <input
                              type="text"
                              placeholder="Search cards…"
                              value={searchQuery}
                              onChange={(e) => setSearchQuery(e.target.value)}
                              className="bg-transparent text-xs text-primary placeholder-secondary/50 focus:outline-none w-full py-0.5"
                            />
                          </div>

                          <label className="flex items-center justify-between gap-2 text-[9px] font-mono text-secondary uppercase tracking-wider w-full">
                            <span>From</span>
                            <input
                              type="date"
                              value={filterStartDate}
                              onChange={(e) => setFilterStartDate(e.target.value)}
                              className="bg-neutral text-[10px] text-primary focus:outline-none cursor-pointer border border-border focus:border-tertiary rounded px-2 py-1 flex-1 max-w-[140px]"
                            />
                          </label>

                          <label className="flex items-center justify-between gap-2 text-[9px] font-mono text-secondary uppercase tracking-wider w-full">
                            <span>To</span>
                            <input
                              type="date"
                              value={filterEndDate}
                              onChange={(e) => setFilterEndDate(e.target.value)}
                              className="bg-neutral text-[10px] text-primary focus:outline-none cursor-pointer border border-border focus:border-tertiary rounded px-2 py-1 flex-1 max-w-[140px]"
                            />
                          </label>

                          <div className="flex items-center gap-2 w-full">
                            <MapPin className="w-3.5 h-3.5 text-secondary shrink-0" />
                            <input
                              type="text"
                              placeholder="Location"
                              value={filterLocation}
                              onChange={(e) => setFilterLocation(e.target.value)}
                              className="bg-neutral text-[10px] text-primary placeholder-secondary/50 focus:outline-none border border-border focus:border-tertiary rounded px-2.5 py-1 w-full"
                            />
                          </div>

                          <div className="flex items-center gap-2 w-full">
                            <Tag className="w-3.5 h-3.5 text-secondary shrink-0" />
                            <select
                              value={selectedCollection}
                              onChange={(e) => setSelectedCollection(e.target.value)}
                              className="bg-neutral text-[10px] text-primary focus:outline-none cursor-pointer border border-border focus:border-tertiary rounded px-2.5 py-1 w-full"
                            >
                              <option value="" className="bg-card text-primary">Collections</option>
                              {allCollections.map(col => (
                                <option key={col} value={col} className="bg-card text-primary">{col}</option>
                              ))}
                            </select>
                          </div>

                          {hasActiveFilters && (
                            <button
                              onClick={() => {
                                setSearchQuery("");
                                setFilterStartDate("");
                                setFilterEndDate("");
                                setFilterLocation("");
                                setSelectedCollection("");
                              }}
                              className="w-full py-2 mt-1 border border-dashed border-tertiary/40 rounded text-center text-[10px] font-mono font-bold uppercase tracking-wider text-tertiary hover:bg-tertiary/5 cursor-pointer transition-colors"
                            >
                              Clear all filters
                            </button>
                          )}
                        </motion.div>
                      </>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            )}

            {syncing && (
              <span className="hidden sm:flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider text-secondary mr-2">
                <span className="w-1.5 h-1.5 bg-tertiary rounded-full animate-pulse" />
                Syncing
              </span>
            )}
            {selectedBoard ? (
              <>
                {activeTab === "kanban" && (
                  <button
                    onClick={() => setActiveAddingListForBoard(true)}
                    className="px-3 py-1.5 bg-primary text-neutral hover:bg-primary/90 rounded text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Column
                  </button>
                )}
                <button
                  onClick={() => {
                    setEditBoardName(selectedBoard.name);
                    setIsSettingsOpen(true);
                  }}
                  className="p-2 text-secondary hover:text-primary transition-colors rounded cursor-pointer"
                  aria-label="Board Settings"
                  title="Board Settings"
                >
                  <Settings className="w-4 h-4" />
                </button>
              </>
            ) : (
              <button
                onClick={() => setIsAddingProject(true)}
                className="px-3 py-1.5 bg-primary text-neutral hover:bg-primary/90 rounded text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Project
              </button>
            )}
          </div>
        </header>

        {/* Mobile/Tablet Tab Selector Row */}
        {selectedBoard && (
          <div className="xl:hidden flex border-b border-primary/10 px-6 py-4 gap-2 overflow-x-auto no-scrollbar bg-card/20 backdrop-blur-sm shrink-0">
            {([
              { key: "kanban", label: "Board", icon: Columns },
              { key: "calendar", label: "Calendar", icon: Calendar },
              { key: "messaging", label: "Feed", icon: MessageSquare },
              { key: "workflow", label: "Workflow", icon: GitFork },
            ] as const).map(t => (
              <button
                key={t.key}
                onClick={() => changeTab(t.key)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-sm border transition-all duration-300 text-[10px] font-bold uppercase tracking-widest cursor-pointer ${
                  activeTab === t.key 
                    ? "bg-primary text-neutral border-primary shadow-sm" 
                    : "bg-card/40 border-primary/5 text-secondary hover:text-primary hover:bg-card/80"
                }`}
              >
                <t.icon className={`w-3.5 h-3.5 ${activeTab === t.key ? "text-tertiary" : "text-secondary"}`} />
                <span>{t.label}</span>
              </button>
            ))}
          </div>
        )}

        {/* Header replaces old FILTER STRIP entirely */}

        {/* ============ WORKSPACE ============ */}
        <div className="flex-1 overflow-y-auto">
          {error && (
            <div className="mx-6 lg:mx-10 mt-6 px-4 py-3 border border-[#B8422E]/25 bg-[#B8422E]/5 rounded flex items-center justify-between gap-4 text-[#B8422E]">
              <div className="flex items-center gap-3 text-xs font-bold">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                {error}
              </div>
              <button onClick={() => setError(null)} className="cursor-pointer hover:opacity-70" aria-label="Dismiss error">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {loading ? (
            <div className="h-96 flex flex-col items-center justify-center gap-4">
              <RefreshCw className="w-5 h-5 text-tertiary animate-spin" />
              <span className={LABEL_CAPS}>Loading Boards</span>
            </div>
          ) : (
            <AnimatePresence mode="wait">
              {!selectedBoard ? (
                /* ---- PROJECT INDEX — editorial rows, hairline separators ---- */
                <motion.div
                  key="selector"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.25 }}
                  className="max-w-3xl mx-auto w-full px-6 lg:px-10 py-10"
                >
                  {projects.length === 0 ? (
                    <div className="border border-dashed border-border rounded-lg py-20 flex flex-col items-center gap-4">
                      <Folder className="w-7 h-7 text-secondary/40" />
                      <div className="text-center space-y-1">
                        <h4 className="font-bold text-primary text-sm">No projects yet</h4>
                        <p className="text-xs text-secondary">Create your first project to get started.</p>
                      </div>
                      <button
                        onClick={() => setIsAddingProject(true)}
                        className="px-4 py-2 bg-primary text-neutral text-[10px] font-bold uppercase tracking-widest rounded hover:bg-primary/90 transition-colors cursor-pointer"
                      >
                        Create Project
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-10">
                      {projects.map((proj) => (
                        <section key={proj.id}>
                          <div className="flex items-baseline justify-between border-b border-primary/15 pb-2 mb-1">
                            <h2 className="font-serif italic font-bold text-primary text-xl">{proj.name}</h2>
                            <div className="flex items-baseline gap-4">
                              <span className={LABEL_CAPS}>
                                {(proj.boards || []).length} {(proj.boards || []).length === 1 ? "board" : "boards"}
                              </span>
                              <button
                                onClick={() => {
                                  setActiveAddingBoardForProjectId(proj.id);
                                  setNewBoardName("");
                                }}
                                className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-tertiary hover:underline cursor-pointer flex items-center gap-1"
                              >
                                <Plus className="w-3 h-3" />
                                Add Board
                              </button>
                            </div>
                          </div>
                          <div>
                            {activeAddingBoardForProjectId === proj.id && (
                              <div className="flex items-center gap-2 py-3 border-b border-primary/5">
                                <Columns className="w-3.5 h-3.5 text-tertiary shrink-0" />
                                <input
                                  type="text"
                                  placeholder="New board name…"
                                  value={newBoardName}
                                  onChange={(e) => setNewBoardName(e.target.value)}
                                  className="flex-1 bg-transparent text-sm text-primary placeholder-secondary/50 focus:outline-none border-b border-border focus:border-tertiary py-1"
                                  autoFocus
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") handleCreateBoard(proj.id);
                                    if (e.key === "Escape") setActiveAddingBoardForProjectId(null);
                                  }}
                                />
                                <button
                                  onClick={() => setActiveAddingBoardForProjectId(null)}
                                  className="px-2 py-1 text-[10px] uppercase font-bold text-secondary hover:text-primary cursor-pointer"
                                >
                                  Cancel
                                </button>
                                <button
                                  onClick={() => handleCreateBoard(proj.id)}
                                  disabled={!newBoardName.trim()}
                                  className="px-3 py-1 bg-primary text-neutral hover:bg-primary/90 disabled:opacity-40 text-[10px] uppercase font-bold tracking-wider rounded cursor-pointer"
                                >
                                  Create
                                </button>
                              </div>
                            )}
                            {(proj.boards || []).map((board) => (
                              <button
                                key={board.id}
                                onClick={() => selectBoard(board)}
                                className="w-full flex items-center justify-between gap-4 py-3.5 border-b border-primary/5 text-left group cursor-pointer hover:bg-card/70 hover:px-3 rounded-sm transition-all duration-200"
                              >
                                <div className="flex items-center gap-3 min-w-0">
                                  <Columns className="w-3.5 h-3.5 text-secondary group-hover:text-tertiary transition-colors shrink-0" />
                                  <span className="font-semibold text-primary text-sm truncate">{board.name}</span>
                                  <span className="text-[8px] font-mono text-secondary uppercase tracking-[0.2em] shrink-0">
                                    {board.type || "kanban"}
                                  </span>
                                </div>
                                <ChevronRight className="w-4 h-4 text-secondary/40 group-hover:text-tertiary group-hover:translate-x-0.5 transition-all shrink-0" />
                              </button>
                            ))}
                          </div>
                        </section>
                      ))}
                    </div>
                  )}
                </motion.div>
              ) : activeTab === "kanban" ? (
                /* ---- KANBAN — glassmorphic cards and columns ---- */
                <motion.div
                  key="board-kanban"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex overflow-x-auto gap-4 items-start p-4 sm:p-6 pb-24 lg:pb-6 h-[calc(100vh-8rem)] min-h-[480px] custom-scrollbar w-full max-w-full min-w-0 snap-x snap-mandatory scroll-smooth scroll-px-4 md:snap-none"
                >
                  {lists.map((list) => {
                    const columnCards = filteredCards.filter(c => c.listId === list.id);
                    return (
                      <div
                        key={list.id}
                        className="w-[290px] sm:w-[320px] shrink-0 flex flex-col px-4 py-5 bg-card/45 backdrop-blur-xs border border-border/80 rounded-md transition-all duration-300 max-h-[calc(100vh-12rem)] snap-center md:snap-none"
                      >
                        {/* Column header — label-caps + count */}
                        <div className="flex items-center justify-between mb-4 px-1 group/column">
                          <div className="flex items-baseline gap-2">
                            <h3 className="font-mono font-bold text-primary text-[10px] uppercase tracking-[0.2em]">{list.name}</h3>
                            <span className="text-[10px] font-mono tabular-nums text-secondary">{columnCards.length}</span>
                          </div>
                          <button
                            onClick={() => {
                              setActiveAddingCardForListId(list.id);
                              setNewCardName("");
                            }}
                            className="p-1 text-secondary/50 hover:text-tertiary opacity-0 group-hover/column:opacity-100 transition-all rounded cursor-pointer"
                            title="Add card"
                            aria-label={`Add card to ${list.name}`}
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        {/* Cards */}
                        <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar min-h-[50px]">
                          <AnimatePresence mode="popLayout">
                            {columnCards.map((card) => {
                              const { metadata, cleanDescription } = parseCardMetadata(card.description || "");
                              const overdue = isOverdue(card);
                              const drill = parseDrillContent(cleanDescription);
                              const rank = workOrder.rank.get(card.id);
                              return (
                                <motion.div
                                  layoutId={`card-${card.id}`}
                                  key={card.id}
                                  className={`p-4 bg-card/90 border rounded-md cursor-pointer relative group/card transition-all duration-300 hover:shadow-md hover:scale-[1.01] ${
                                    selectedCard?.id === card.id
                                      ? "border-tertiary shadow-sm ring-1 ring-tertiary/20"
                                      : "border-border hover:border-tertiary/30"
                                  }`}
                                  onClick={() => handleOpenCard(card)}
                                >
                                  <div className="flex justify-between items-start gap-2">
                                    <div className="flex items-start gap-2 min-w-0">
                                      {rank !== undefined && (
                                        <span
                                          className={`shrink-0 mt-px flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full font-mono font-bold text-[10px] tabular-nums ring-1 ${
                                            rank <= 3
                                              ? "bg-tertiary/15 text-tertiary ring-tertiary/40"
                                              : "bg-neutral/60 text-secondary ring-border/40"
                                          }`}
                                          title={
                                            rank === 1
                                              ? `Work order #1 of ${workOrder.total} — do this first`
                                              : `Work order #${rank} of ${workOrder.total} (priority score ${workOrder.score.get(card.id)})`
                                          }
                                          aria-label={`Priority rank ${rank} of ${workOrder.total}`}
                                        >
                                          {rank}
                                        </span>
                                      )}
                                      <h4 className="font-semibold text-primary text-[13px] leading-snug">
                                        {card.name}
                                      </h4>
                                    </div>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleCloseCard(card.id);
                                      }}
                                      className="opacity-0 group-hover/card:opacity-100 p-1 -m-1 text-secondary/60 hover:text-tertiary transition-all cursor-pointer shrink-0"
                                      title="Archive card"
                                      aria-label="Archive card"
                                    >
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  </div>

                                  {drill ? (
                                    <div className="mt-2 space-y-2 text-left">
                                      <div className="text-[11px] text-primary leading-relaxed">
                                        <span className="font-semibold text-secondary block text-[8px] uppercase tracking-wider mb-0.5">Question</span>
                                        <div className="bg-neutral/40 border border-border/40 p-2.5 rounded font-medium text-xs break-words">
                                          {formatMarkdown(drill.question)}
                                        </div>
                                      </div>
                                      {drill.answer && (
                                        <div className="text-[11px] leading-relaxed">
                                          <div className="mt-2 space-y-1.5">
                                            <button
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                toggleRevealAnswer(card.id);
                                              }}
                                              className="text-[9px] font-mono font-bold text-tertiary hover:underline uppercase tracking-[0.15em] flex items-center gap-1 cursor-pointer"
                                            >
                                              {revealedAnswers[card.id] ? "Hide Answer" : "Reveal Answer"}
                                            </button>
                                            <AnimatePresence>
                                              {revealedAnswers[card.id] && (
                                                <motion.div
                                                  initial={{ opacity: 0, height: 0 }}
                                                  animate={{ opacity: 1, height: "auto" }}
                                                  exit={{ opacity: 0, height: 0 }}
                                                  transition={{ duration: 0.2 }}
                                                  className="overflow-hidden"
                                                >
                                                  <div className="bg-sand/10 border border-tertiary/20 p-2.5 rounded mt-1 text-xs text-primary leading-relaxed whitespace-pre-wrap break-words">
                                                    <span className="font-semibold text-tertiary block text-[8px] uppercase tracking-wider mb-0.5">Answer</span>
                                                    {formatMarkdown(drill.answer)}
                                                  </div>
                                                </motion.div>
                                              )}
                                            </AnimatePresence>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  ) : cleanDescription && (
                                    <p className="mt-1.5 text-[11px] text-secondary line-clamp-2 leading-relaxed">
                                      {cleanDescription}
                                    </p>
                                  )}

                                  {/* Metadata chips — quiet, uniform; overdue is the one accent */}
                                  {(card.dueDate || metadata.location || (metadata.recurring && metadata.recurring !== "none") || (metadata.collections || []).length > 0) && (
                                    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2.5 items-center">
                                      {card.dueDate && (
                                        <span className={`flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider ${
                                          overdue ? "text-tertiary font-bold" : "text-secondary"
                                        }`}>
                                          <Clock className="w-2.5 h-2.5" />
                                          {new Date(card.dueDate).toLocaleDateString([], { month: "short", day: "numeric" })}
                                        </span>
                                      )}
                                      {metadata.location && (
                                        <span className="flex items-center gap-1 text-secondary font-mono text-[9px] uppercase tracking-wider">
                                          <MapPin className="w-2.5 h-2.5" />
                                          {metadata.location}
                                        </span>
                                      )}
                                      {metadata.recurring && metadata.recurring !== "none" && (
                                        <span className="flex items-center gap-1 text-secondary font-mono text-[9px] uppercase tracking-wider">
                                          <RefreshCw className="w-2.5 h-2.5" />
                                          {metadata.recurring}
                                        </span>
                                      )}
                                      {(metadata.collections || []).map(col => (
                                        <span key={col} className="flex items-center gap-1 text-secondary font-mono text-[9px] uppercase tracking-wider">
                                          <Tag className="w-2.5 h-2.5" />
                                          {col}
                                        </span>
                                      ))}
                                    </div>
                                  )}

                                  {/* Quick move — appears on hover */}
                                  <div
                                    className="mt-2 pt-2 border-t border-border hidden group-hover/card:flex items-center justify-between"
                                    onClick={e => e.stopPropagation()}
                                  >
                                    <span className="text-[8px] font-mono text-secondary/60 uppercase tracking-widest">Move to</span>
                                    <select
                                      onChange={(e) => handleMoveCard(card.id, e.target.value)}
                                      value={card.listId}
                                      className="text-[10px] bg-card text-primary border border-border/20 rounded-xs px-1 py-0.5 cursor-pointer outline-none font-mono text-right"
                                      aria-label="Move card column"
                                    >
                                      {lists.map(l => (
                                        <option key={l.id} value={l.id} className="bg-card text-primary">{l.name}</option>
                                      ))}
                                    </select>
                                  </div>
                                </motion.div>
                              );
                            })}
                          </AnimatePresence>

                          {/* Inline add-card */}
                          {activeAddingCardForListId === list.id ? (
                            <div className="p-3 bg-card border border-tertiary/30 rounded-md space-y-2">
                              <input
                                type="text"
                                placeholder="Card title…"
                                value={newCardName}
                                onChange={(e) => setNewCardName(e.target.value)}
                                className={FIELD}
                                autoFocus
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleCreateCard(list.id);
                                  if (e.key === "Escape") setActiveAddingCardForListId(null);
                                }}
                              />
                              <div className="flex gap-2 justify-end">
                                <button
                                  onClick={() => setActiveAddingCardForListId(null)}
                                  className="px-2 py-1 text-[10px] uppercase font-bold text-secondary hover:text-primary cursor-pointer"
                                >
                                  Cancel
                                </button>
                                <button
                                  onClick={() => handleCreateCard(list.id)}
                                  className="px-3 py-1 bg-primary text-neutral hover:bg-primary/90 text-[10px] uppercase font-bold tracking-wider rounded cursor-pointer"
                                >
                                  Add
                                </button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => {
                                setActiveAddingCardForListId(list.id);
                                setNewCardName("");
                              }}
                              className="w-full py-2 text-[10px] text-secondary/60 hover:text-tertiary font-mono font-bold uppercase tracking-widest transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                            >
                              <Plus className="w-3 h-3" />
                              Add Card
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}

                  {/* Add column lane */}
                  <div className="w-[300px] shrink-0 px-4 pt-5 border-l border-primary/10">
                    {activeAddingListForBoard ? (
                      <div className="space-y-2">
                        <h4 className={LABEL_CAPS}>New Column</h4>
                        <form onSubmit={handleCreateList} className="space-y-2">
                          <input
                            type="text"
                            placeholder="Column name…"
                            value={newListName}
                            onChange={(e) => setNewListName(e.target.value)}
                            className={FIELD}
                            autoFocus
                          />
                          <div className="flex gap-2 justify-end">
                            <button
                              type="button"
                              onClick={() => setActiveAddingListForBoard(false)}
                              className="px-3 py-1.5 text-xs text-secondary hover:text-primary cursor-pointer"
                            >
                              Cancel
                            </button>
                            <button
                              type="submit"
                              className="px-4 py-1.5 bg-primary text-neutral hover:bg-primary/90 text-xs font-bold rounded cursor-pointer"
                            >
                              Create
                            </button>
                          </div>
                        </form>
                      </div>
                    ) : (
                      <button
                        onClick={() => setActiveAddingListForBoard(true)}
                        className="w-full py-2.5 text-secondary/50 hover:text-tertiary font-mono font-bold text-[10px] uppercase tracking-widest flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Add Column
                      </button>
                    )}
                  </div>
                </motion.div>
              ) : activeTab === "calendar" ? (
                /* ---- CALENDAR MONTH VIEW ---- */
                <motion.div
                  key="board-calendar"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="px-6 lg:px-10 py-6 space-y-5 text-left"
                >
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-4">
                      <h3 className="font-serif italic font-bold text-primary text-lg">
                        {new Date(currentYear, currentMonth).toLocaleDateString([], { month: "long", year: "numeric" })}
                      </h3>
                      <div className="flex border border-border rounded overflow-hidden">
                        <button
                          onClick={() => {
                            if (currentMonth === 0) {
                              setCurrentMonth(11);
                              setCurrentYear(prev => prev - 1);
                            } else {
                              setCurrentMonth(prev => prev - 1);
                            }
                          }}
                          className="px-2.5 py-1 text-xs text-secondary hover:text-primary hover:bg-card cursor-pointer"
                          aria-label="Previous month"
                        >
                          &larr;
                        </button>
                        <button
                          onClick={() => {
                            const today = new Date();
                            setCurrentMonth(today.getMonth());
                            setCurrentYear(today.getFullYear());
                          }}
                          className="px-2.5 py-1 text-xs text-secondary hover:text-primary hover:bg-card cursor-pointer border-x border-border"
                        >
                          Today
                        </button>
                        <button
                          onClick={() => {
                            if (currentMonth === 11) {
                              setCurrentMonth(0);
                              setCurrentYear(prev => prev + 1);
                            } else {
                              setCurrentMonth(prev => prev + 1);
                            }
                          }}
                          className="px-2.5 py-1 text-xs text-secondary hover:text-primary hover:bg-card cursor-pointer"
                          aria-label="Next month"
                        >
                          &rarr;
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="flex items-baseline gap-1.5">
                        <span className="font-data font-semibold text-[13px] tabular-nums text-primary leading-none">
                          {filteredCards.filter(c => c.dueDate && !isDoneCard(c)).length}
                        </span>
                        <span className="text-[8px] font-mono text-secondary/80 uppercase tracking-[0.18em]">
                          Active Targets
                        </span>
                      </span>
                      <span aria-hidden="true" className="w-px h-3 bg-primary/10" />
                      <span className="flex items-baseline gap-1.5">
                        <span aria-hidden="true" className="self-center w-1.5 h-1.5 rounded-full bg-tertiary/60" />
                        <span className="font-data font-semibold text-[13px] tabular-nums text-primary leading-none">
                          {completedThisMonth}
                        </span>
                        <span className="text-[8px] font-mono text-secondary/80 uppercase tracking-[0.18em]">
                          Completed
                        </span>
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-7 gap-px text-center text-[10px] font-mono text-secondary uppercase tracking-widest border-b border-primary/10 pb-2">
                    <div>Sun</div>
                    <div>Mon</div>
                    <div>Tue</div>
                    <div>Wed</div>
                    <div>Thu</div>
                    <div>Fri</div>
                    <div>Sat</div>
                  </div>

                  {(expandedDoneKey || expandedActiveKey) && (
                    <div
                      className="fixed inset-0 z-30"
                      onClick={() => {
                        setExpandedDoneKey(null);
                        setExpandedActiveKey(null);
                      }}
                    />
                  )}

                  <div className="grid grid-cols-7 gap-1 sm:gap-1.5 min-h-[300px] sm:min-h-[420px]">
                    {generateCalendarCells().map((cell, idx) => {
                      const cellCards = filteredCards.filter(c => c.dueDate && !isDoneCard(c) && isSameDay(c.dueDate, cell));
                      const completedCards = filteredCards.filter(c => isDoneCard(c) && isSameDay(c.listChangedAt!, cell));
                      const today = new Date();
                      const isToday = today.getDate() === cell.day && today.getMonth() === cell.month && today.getFullYear() === cell.year;
                      const doneKey = `${cell.year}-${cell.month}-${cell.day}`;
                      const isDoneExpanded = expandedDoneKey === doneKey;
                      const isActiveExpanded = expandedActiveKey === doneKey;

                      return (
                        <div
                          key={idx}
                          className={`relative min-h-[65px] sm:min-h-[115px] p-1.5 sm:p-3 border rounded-md flex flex-col transition-all duration-300 ${
                            cell.isCurrentMonth
                              ? "bg-card/45 backdrop-blur-xs border-border/80 hover:bg-card/75 hover:border-tertiary/30"
                              : "bg-transparent border-border/20 opacity-30 pointer-events-none"
                          } ${isToday ? "border-tertiary ring-1 ring-tertiary/20 bg-sand/10" : ""} ${
                            isDoneExpanded || isActiveExpanded ? "z-40 ring-1 ring-tertiary shadow-xl opacity-100" : ""
                          }`}
                        >
                          <div className="flex justify-between items-center">
                            <span className={`text-[9px] sm:text-[10px] font-mono tabular-nums ${isToday ? "text-tertiary font-bold" : "text-secondary"}`}>
                              {cell.day}
                            </span>
                            {isToday && (
                              <span className="w-1 h-1 sm:w-1.5 sm:h-1.5 bg-tertiary rounded-full animate-pulse" />
                            )}
                          </div>

                          {/* Compact active-work indicator — one dot per active target, click to expand */}
                          {cellCards.length > 0 && (
                            <button
                              onClick={() => setExpandedActiveKey(isActiveExpanded ? null : doneKey)}
                              aria-expanded={isActiveExpanded}
                              aria-label={`${cellCards.length} active targets — view details`}
                              title={`${cellCards.length} active targets`}
                              className="group mt-1 self-start flex items-center gap-0.5 sm:gap-1 h-[14px] sm:h-[18px] px-1 sm:px-2 rounded-full border border-border bg-primary/[0.04] hover:border-tertiary/30 hover:bg-sand/10 cursor-pointer transition-all duration-200"
                            >
                              {cellCards.slice(0, 3).map(c => (
                                <span
                                  key={c.id}
                                  className="w-1 h-1 sm:w-[5px] sm:h-[5px] rounded-full bg-primary/60 group-hover:bg-tertiary transition-colors duration-200"
                                />
                              ))}
                              {cellCards.length > 3 && (
                                <span className="pl-0.5 text-[6px] sm:text-[8px] font-mono leading-none tabular-nums text-primary/70 group-hover:text-tertiary transition-colors duration-200">
                                  +{cellCards.length - 3}
                                </span>
                              )}
                            </button>
                          )}

                          {/* Compact completed-work indicator — one dot per completion, click to expand */}
                          {completedCards.length > 0 && (
                            <button
                              onClick={() => setExpandedDoneKey(isDoneExpanded ? null : doneKey)}
                              aria-expanded={isDoneExpanded}
                              aria-label={`${completedCards.length} completed by Kenbun — view details`}
                              title={`${completedCards.length} completed by Kenbun`}
                              className="group mt-1 self-start flex items-center gap-0.5 sm:gap-1 h-[14px] sm:h-[18px] px-1 sm:px-2 rounded-full border border-tertiary/15 bg-tertiary/[0.06] hover:border-tertiary/35 hover:bg-tertiary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tertiary/40 cursor-pointer transition-all duration-200"
                            >
                              {completedCards.slice(0, 3).map(c => (
                                <span
                                  key={c.id}
                                  className="w-1 h-1 sm:w-[5px] sm:h-[5px] rounded-full bg-tertiary/60 group-hover:bg-tertiary transition-colors duration-200"
                                />
                              ))}
                              {completedCards.length > 3 && (
                                <span className="pl-0.5 text-[6px] sm:text-[8px] font-mono leading-none tabular-nums text-tertiary/70 group-hover:text-tertiary transition-colors duration-200">
                                  +{completedCards.length - 3}
                                </span>
                              )}
                            </button>
                          )}

                          <AnimatePresence>
                            {isActiveExpanded && (
                              <motion.div
                                initial={{ opacity: 0, scale: 0.96, y: Math.floor(idx / 7) < 2 ? -6 : 6 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.98, y: Math.floor(idx / 7) < 2 ? -4 : 4 }}
                                transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                                className={`absolute z-50 w-[310px] bg-card/95 backdrop-blur-md border border-border rounded-md shadow-2xl overflow-hidden ${
                                  Math.floor(idx / 7) < 2 ? "top-full mt-1.5" : "bottom-8 mb-1"
                                } ${idx % 7 >= 4 ? "right-0" : "left-0"}`}
                              >
                                <div className="flex items-start justify-between gap-2 px-4 pt-3.5 pb-2.5 border-b border-border">
                                  <div className="min-w-0">
                                    <span className="block font-serif italic font-bold text-primary text-[13px] leading-tight">
                                      Active Targets
                                    </span>
                                    <span className="block mt-1 text-[8px] font-mono text-secondary uppercase tracking-[0.2em]">
                                      {new Date(cell.year, cell.month, cell.day).toLocaleDateString([], { month: "short", day: "numeric" })} · {cellCards.length} {cellCards.length === 1 ? "target" : "targets"}
                                    </span>
                                  </div>
                                  <button
                                    onClick={() => setExpandedActiveKey(null)}
                                    aria-label="Close"
                                    className="shrink-0 -mr-1 -mt-0.5 p-1 rounded-md text-secondary hover:text-primary hover:bg-sand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tertiary/40 cursor-pointer transition-colors"
                                  >
                                    <X className="w-3 h-3" />
                                  </button>
                                </div>
                                <div className="p-2 space-y-1 max-h-72 overflow-y-auto custom-scrollbar">
                                  {cellCards.map((card, cardIdx) => {
                                    const { cleanDescription } = parseCardMetadata(card.description || "");
                                    const cleanName = card.name
                                      .replace(/^🏆\s+Claude Corps:\s*/i, "🏆 ")
                                      .replace(/^Claude Corps:\s*/i, "");

                                    return (
                                      <button
                                        key={card.id}
                                        onClick={() => {
                                          setExpandedActiveKey(null);
                                          handleOpenCard(card);
                                        }}
                                        className="group w-full text-left relative flex items-start gap-3.5 px-3 py-2.5 rounded-lg hover:bg-sand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tertiary/40 cursor-pointer transition-all duration-200"
                                      >
                                        {cardIdx < cellCards.length - 1 && (
                                          <span className="absolute left-[21px] top-8 bottom-0 w-[1px] bg-border" />
                                        )}

                                        <span className="w-5 h-5 rounded-full flex items-center justify-center shrink-0 transition-all duration-200 group-hover:scale-110 bg-primary/5 border border-primary/15 text-secondary group-hover:bg-primary/10">
                                          <span className="w-1.5 h-1.5 rounded-full bg-primary/70" />
                                        </span>

                                        <span className="min-w-0 flex-1">
                                          <span className="block text-[11px] font-semibold text-primary leading-snug group-hover:text-tertiary transition-colors line-clamp-2">
                                            {cleanName}
                                          </span>

                                          {cleanDescription && (
                                            <span className="block mt-1 text-[9px] text-secondary/70 line-clamp-2 font-normal leading-relaxed">
                                              {cleanDescription}
                                            </span>
                                          )}
                                        </span>
                                        <ChevronRight className="w-3.5 h-3.5 text-secondary/40 shrink-0 opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all duration-200 self-center" />
                                      </button>
                                    );
                                  })}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                          <AnimatePresence>
                            {isDoneExpanded && (
                              <motion.div
                                initial={{ opacity: 0, scale: 0.96, y: Math.floor(idx / 7) < 2 ? -6 : 6 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.98, y: Math.floor(idx / 7) < 2 ? -4 : 4 }}
                                transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                                className={`absolute z-50 w-[310px] bg-card/95 backdrop-blur-md border border-border rounded-md shadow-2xl overflow-hidden ${
                                  Math.floor(idx / 7) < 2 ? "top-full mt-1.5" : "bottom-8 mb-1"
                                } ${idx % 7 >= 4 ? "right-0" : "left-0"}`}
                              >
                                <div className="flex items-start justify-between gap-2 px-4 pt-3.5 pb-2.5 border-b border-border">
                                  <div className="min-w-0">
                                    <span className="block font-serif italic font-bold text-primary text-[13px] leading-tight">
                                      Completed Tasks
                                    </span>
                                    <span className="block mt-1 text-[8px] font-mono text-secondary uppercase tracking-[0.2em]">
                                      {new Date(cell.year, cell.month, cell.day).toLocaleDateString([], { month: "short", day: "numeric" })} · {completedCards.length} {completedCards.length === 1 ? "node" : "nodes"}
                                    </span>
                                  </div>
                                  <button
                                    onClick={() => setExpandedDoneKey(null)}
                                    aria-label="Close"
                                    className="shrink-0 -mr-1 -mt-0.5 p-1 rounded-md text-secondary hover:text-primary hover:bg-sand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tertiary/40 cursor-pointer transition-colors"
                                  >
                                    <X className="w-3 h-3" />
                                  </button>
                                </div>
                                <div className="p-2 space-y-1 max-h-72 overflow-y-auto custom-scrollbar">
                                  {completedCards.map((card, cardIdx) => {
                                    const { cleanDescription } = parseCardMetadata(card.description || "");
                                    const isBug = card.name.toLowerCase().startsWith("bug:") || card.name.toLowerCase().startsWith("fix:");
                                    const isFeat = card.name.toLowerCase().startsWith("feat:") || card.name.toLowerCase().startsWith("new:");

                                    let cleanName = card.name;
                                    if (isBug) cleanName = cleanName.replace(/^(bug|fix):\s*/i, "");
                                    if (isFeat) cleanName = cleanName.replace(/^(feat|new):\s*/i, "");

                                    return (
                                      <button
                                        key={card.id}
                                        onClick={() => {
                                          setExpandedDoneKey(null);
                                          handleOpenCard(card);
                                        }}
                                        className="group w-full text-left relative flex items-start gap-3.5 px-3 py-2.5 rounded-lg hover:bg-sand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tertiary/40 cursor-pointer transition-all duration-200"
                                      >
                                        {/* Timeline connector line */}
                                        {cardIdx < completedCards.length - 1 && (
                                          <span className="absolute left-[21px] top-8 bottom-0 w-[1px] bg-border" />
                                        )}

                                        {/* Timeline check node */}
                                        <span className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 transition-all duration-200 group-hover:scale-110 ${
                                          isBug
                                            ? "bg-tertiary/10 border border-tertiary/30 text-tertiary group-hover:bg-tertiary/20"
                                            : isFeat
                                              ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 group-hover:bg-emerald-500/20"
                                              : "bg-primary/5 border border-primary/15 text-secondary group-hover:bg-primary/10"
                                        }`}>
                                          <Check className="w-2.5 h-2.5" />
                                        </span>

                                        <span className="min-w-0 flex-1">
                                          <span className="flex items-center gap-1.5 mb-1">
                                            {isBug && (
                                              <span className="text-[7px] font-mono font-bold uppercase tracking-wider bg-tertiary/10 text-tertiary px-1 py-0.5 rounded-sm">
                                                Bug
                                              </span>
                                            )}
                                            {isFeat && (
                                              <span className="text-[7px] font-mono font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 px-1 py-0.5 rounded-sm">
                                                Feat
                                              </span>
                                            )}
                                            <span className="text-[8px] font-mono tabular-nums text-secondary/60">
                                              {new Date(card.listChangedAt!).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                            </span>
                                          </span>

                                          <span className="block text-[11px] font-semibold text-primary leading-snug group-hover:text-tertiary transition-colors line-clamp-2">
                                            {cleanName}
                                          </span>

                                          {cleanDescription && (
                                            <span className="block mt-1 text-[9px] text-secondary/70 line-clamp-2 font-normal leading-relaxed">
                                              {cleanDescription}
                                            </span>
                                          )}
                                        </span>
                                        <ChevronRight className="w-3.5 h-3.5 text-secondary/40 shrink-0 opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all duration-200 self-center" />
                                      </button>
                                    );
                                  })}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              ) : activeTab === "workflow" ? (
                <motion.div
                  key="board-workflow"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="px-6 lg:px-10 py-6 h-[calc(100vh-8rem)] min-h-[480px] w-full max-w-full min-w-0"
                >
                  <WorkflowView
                    cards={filteredCards}
                    lists={lists}
                    onOpenCard={handleOpenCard}
                    onUpdateCardDesc={async (cardId, newDesc) => {
                      try {
                        setSyncing(true);
                        const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards/${cardId}`, {
                          method: "PATCH",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ description: newDesc })
                        });
                        if (res.ok) {
                          setCards(prev => prev.map(c => c.id === cardId ? { ...c, description: newDesc } : c));
                          if (selectedBoard) fetchBoardDetails(selectedBoard.id);
                        } else {
                          setError(`Failed to save dependency (HTTP ${res.status})`);
                        }
                      } catch (err) {
                        console.error(err);
                        setError("Failed to save dependency: network error");
                      } finally {
                        setSyncing(false);
                      }
                    }}
                    onCreateCard={async (name, listId, x, y) => {
                      try {
                        setSyncing(true);
                        const initialDesc = injectCardMetadata("", { layout: { x, y } });
                        const res = await tenantFetch(`${API_BASE}/api/v1/planka/cards`, {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ listId, name: name.trim(), description: initialDesc })
                        });
                        if (res.ok) {
                          if (selectedBoard) fetchBoardDetails(selectedBoard.id);
                        } else {
                          setError(`Failed to create card (HTTP ${res.status})`);
                        }
                      } catch (err) {
                        console.error(err);
                        setError("Failed to create card: network error");
                      } finally {
                        setSyncing(false);
                      }
                    }}
                    onDeleteCard={handleCloseCard}
                    onMoveCard={handleMoveCard}
                  />
                </motion.div>
              ) : (
                /* ---- FEED (mail & messaging) ---- */
                <motion.div
                  key="board-messaging"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start px-6 lg:px-10 py-6 h-[calc(100vh-8rem)] min-h-[480px] w-full max-w-full min-w-0"
                >
                  <div className="lg:col-span-2 bg-card/45 backdrop-blur-xs border border-border rounded-md flex flex-col h-full overflow-hidden">
                    <div className="flex justify-between items-center border-b border-border px-5 py-4 shrink-0">
                      <div className="flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-tertiary" />
                        <h3 className="font-serif italic font-bold text-primary text-base">Board Signal Feed</h3>
                      </div>
                      <button
                        onClick={() => fetchBoardComments()}
                        disabled={loadingComments}
                        className="px-2.5 py-1 border border-border hover:bg-sand rounded text-[9px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-colors flex items-center gap-1 cursor-pointer"
                      >
                        <RefreshCw className={`w-2.5 h-2.5 ${loadingComments ? "animate-spin" : ""}`} />
                        Reload
                      </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-5 space-y-4 custom-scrollbar">
                      {loadingComments ? (
                        <div className="h-60 flex flex-col items-center justify-center gap-2">
                          <RefreshCw className="w-5 h-5 text-tertiary animate-spin" />
                          <span className={LABEL_CAPS}>Loading Feed</span>
                        </div>
                      ) : boardComments.length === 0 ? (
                        <div className="text-center text-[10px] font-mono text-secondary py-12">No recent signal notes recorded on this board.</div>
                      ) : (
                        boardComments.map(comment => (
                          <div key={comment.id} className="flex gap-3.5 items-start text-left border-b border-border/40 pb-4 last:border-b-0">
                            <div className="w-7 h-7 bg-tertiary/10 border border-tertiary/25 rounded-full flex items-center justify-center shrink-0">
                              <span className="text-tertiary text-[10px] font-mono font-black uppercase">A</span>
                            </div>
                            <div className="flex-1 space-y-1 min-w-0">
                              <div className="flex justify-between items-center flex-wrap gap-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-[10px] font-bold text-primary">Agent Supervisor</span>
                                  <span className="text-[8px] font-mono text-secondary uppercase border border-border px-1.5 py-0.5 rounded">
                                    {comment.cardName}
                                  </span>
                                </div>
                                <span className="text-[8px] font-mono text-secondary">
                                  {new Date(comment.createdAt).toLocaleDateString([], { month: "short", day: "numeric" })} at {new Date(comment.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                </span>
                              </div>
                              <div className="text-xs text-primary leading-relaxed break-words markdown-content">{formatMarkdown(comment.text)}</div>

                              <div className="pt-1 flex justify-end">
                                <button
                                  onClick={() => {
                                    const matchedCard = cards.find(c => c.id === comment.cardId);
                                    if (matchedCard) handleOpenCard(matchedCard);
                                  }}
                                  className="text-[9px] font-mono font-bold text-tertiary hover:underline uppercase tracking-wider cursor-pointer"
                                >
                                  View Details &rarr;
                                </button>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="bg-card/45 backdrop-blur-xs border border-border p-5 rounded-md space-y-4 text-left">
                    <div className="space-y-1">
                      <h3 className="font-serif italic font-bold text-primary text-base">Broadcast Update</h3>
                      <p className="text-[10px] text-secondary leading-normal">Publish comments and signal logs to any active card from this central board panel.</p>
                    </div>

                    <form onSubmit={handleAddFeedComment} className="space-y-4">
                      <div className="space-y-1.5">
                        <label htmlFor="feed_card_select" className={LABEL_CAPS}>Target Card</label>
                        <select
                          id="feed_card_select"
                          value={feedSelectedCardId}
                          onChange={(e) => setFeedSelectedCardId(e.target.value)}
                          className={FIELD + " cursor-pointer bg-card"}
                        >
                          <option value="" className="bg-card text-primary">— Choose active card —</option>
                          {cards.map(c => (
                            <option key={c.id} value={c.id} className="bg-card text-primary">{c.name}</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-1.5">
                        <label htmlFor="feed_comment_input" className={LABEL_CAPS}>Signal Comment</label>
                        <textarea
                          id="feed_comment_input"
                          placeholder="Enter comment text…"
                          value={feedCommentText}
                          onChange={(e) => setFeedCommentText(e.target.value)}
                          className={FIELD + " h-24 resize-none bg-neutral"}
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={!feedCommentText.trim() || !feedSelectedCardId}
                        className="w-full py-2 bg-primary text-neutral hover:bg-primary/90 disabled:bg-neutral disabled:text-secondary/40 disabled:border disabled:border-border text-xs font-bold rounded cursor-pointer transition-colors"
                      >
                        Send Broadcast
                      </button>
                    </form>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          )}
        </div>
      </main>

      {/* ============ BOARD SETTINGS DRAWER ============ */}
      <AnimatePresence>
        {isSettingsOpen && selectedBoard && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.35 }}
              exit={{ opacity: 0 }}
              onClick={() => {
                setIsSettingsOpen(false);
                setConfirmDeleteBoard(false);
              }}
              className="fixed inset-0 bg-primary z-40"
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 260 }}
              className="fixed right-0 top-0 bottom-0 w-80 sm:w-96 bg-neutral border-l border-primary/15 z-50 p-6 flex flex-col justify-between shadow-2xl text-left"
            >
              <div className="space-y-6">
                <div className="flex justify-between items-center border-b border-primary/10 pb-4">
                  <div className="flex items-center gap-2">
                    <Settings className="w-4 h-4 text-tertiary" />
                    <h3 className="font-serif italic font-bold text-primary text-base">Board Settings</h3>
                  </div>
                  <button
                    onClick={() => {
                      setIsSettingsOpen(false);
                      setConfirmDeleteBoard(false);
                    }}
                    className="text-secondary hover:text-primary cursor-pointer"
                    aria-label="Close settings"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleUpdateBoard} className="space-y-4">
                  <div className="space-y-1.5">
                    <label htmlFor="board_rename_input" className={LABEL_CAPS}>Rename Board</label>
                    <input
                      id="board_rename_input"
                      type="text"
                      value={editBoardName}
                      onChange={(e) => setEditBoardName(e.target.value)}
                      className={FIELD}
                    />
                  </div>
                  <button
                    type="submit"
                    className="w-full py-2 bg-primary text-neutral hover:bg-primary/90 text-xs font-bold rounded cursor-pointer transition-colors"
                  >
                    Save Rename
                  </button>
                </form>
              </div>

              <div className="border-t border-primary/10 pt-4 space-y-3">
                <span className={LABEL_CAPS + " block"}>Danger Zone</span>
                {confirmDeleteBoard ? (
                  <div className="space-y-2 p-3 border border-[#B8422E]/25 bg-[#B8422E]/5 rounded">
                    <div className="flex items-start gap-2 text-[#B8422E] text-xs">
                      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                      <span>Deleting this board is permanent and cannot be undone. All lists, cards, and comments will be destroyed.</span>
                    </div>
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => setConfirmDeleteBoard(false)}
                        className="px-3 py-1.5 border border-border text-[10px] font-bold uppercase rounded text-secondary hover:text-primary cursor-pointer bg-card"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleDeleteBoard}
                        className="px-3 py-1.5 bg-[#B8422E] hover:bg-[#a03a28] text-white text-[10px] font-bold uppercase rounded cursor-pointer"
                      >
                        Delete Permanently
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDeleteBoard(true)}
                    className="w-full py-2 border border-[#B8422E]/25 hover:border-[#B8422E] text-[#B8422E] hover:bg-[#B8422E] hover:text-white text-xs font-bold uppercase tracking-wider rounded transition-all cursor-pointer"
                  >
                    Delete Board
                  </button>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ============ NEW PROJECT MODAL ============ */}
      <AnimatePresence>
        {isAddingProject && (
          <div className="fixed inset-0 bg-primary/25 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            {/* Dismiss backdrop on click */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsAddingProject(false)}
              className="absolute inset-0 bg-transparent"
            />
            
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 15 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 15 }}
              className="w-full max-w-md min-w-[320px] sm:min-w-[400px] bg-card/95 backdrop-blur-xl border border-primary/10 rounded-xl p-6 shadow-2xl text-left relative overflow-hidden z-10"
            >
              {/* Top Accent Line */}
              <div className="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-transparent via-tertiary to-transparent" />
              
              {/* Subtle top glow */}
              <div className="absolute -top-[40%] -left-[20%] w-[80%] h-[80%] bg-tertiary/5 rounded-full blur-[80px] pointer-events-none" />

              {/* Modal Header */}
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-primary/5 relative z-10">
                <div className="w-9 h-9 rounded-lg bg-tertiary/10 border border-tertiary/20 flex items-center justify-center text-tertiary shrink-0">
                  <Folder className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-serif italic text-primary font-black leading-none">New Project</h3>
                  <span className="text-[8px] font-mono text-secondary uppercase tracking-[0.2em]">Create Workspace</span>
                </div>
                <button 
                  onClick={() => setIsAddingProject(false)} 
                  className="ml-auto text-secondary hover:text-primary transition-colors cursor-pointer p-1.5 hover:bg-neutral rounded-md"
                  aria-label="Close"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreateProject} className="space-y-5 relative z-10">
                <div className="space-y-1.5">
                  <label htmlFor="proj_name" className={LABEL_CAPS}>Project Name</label>
                  <div className="relative flex items-center">
                    <input
                      id="proj_name"
                      type="text"
                      placeholder="e.g. Kenbun Swarm Client"
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      className="w-full bg-neutral/50 border border-border rounded-lg p-3 pl-10 text-xs text-primary focus:outline-none focus:border-tertiary focus:bg-neutral/80 transition-all font-semibold placeholder-secondary/50"
                      autoFocus
                    />
                    <div className="absolute left-3.5 pointer-events-none text-secondary">
                      <Folder className="w-3.5 h-3.5" />
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 justify-end pt-3 border-t border-primary/5">
                  <button
                    type="button"
                    onClick={() => setIsAddingProject(false)}
                    className="px-4 py-2 border border-border text-[10px] font-bold uppercase tracking-widest rounded-lg text-secondary hover:text-primary hover:bg-neutral transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2 bg-tertiary hover:bg-tertiary/90 text-white text-[10px] font-bold uppercase tracking-widest rounded-lg cursor-pointer transition-all flex items-center gap-1.5 hover:shadow-lg hover:shadow-tertiary/10"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Create Project
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ============ CARD DIALOG MODAL (centered & wide) ============ */}
      <AnimatePresence>
        {selectedCard && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedCard(null)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            />
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-10 pointer-events-none">
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                transition={{ type: "spring", damping: 30, stiffness: 300 }}
                className="w-full max-w-4xl md:max-w-5xl lg:max-w-6xl xl:max-w-7xl max-h-[90dvh] md:max-h-[85dvh] bg-neutral border border-primary/15 rounded-2xl flex flex-col shadow-2xl text-left pointer-events-auto overflow-hidden"
              >
                {/* Panel header */}
                <div className="px-6 pt-5 pb-4 border-b border-primary/10 shrink-0">
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <span className={LABEL_CAPS}>
                      {lists.find(l => l.id === selectedCard.listId)?.name || "Card"}
                      {selectedCard.dueDate && (
                        <span className={`ml-3 normal-case tracking-normal inline-flex items-center gap-1 ${
                          isOverdue(selectedCard) ? "text-[#B8422E]" : "text-secondary"
                        }`}>
                          <Clock className="w-3 h-3" />
                          Due {new Date(selectedCard.dueDate).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}
                        </span>
                      )}
                    </span>
                    <button
                      onClick={() => setSelectedCard(null)}
                      className="flex items-center gap-1.5 text-secondary hover:text-primary cursor-pointer text-[10px] font-bold font-mono uppercase tracking-[0.15em] hover:bg-neutral/45 px-2 py-1 rounded transition-colors"
                      aria-label="Close card panel"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      Back
                    </button>
                  </div>
                  <input
                    type="text"
                    value={editingCardName}
                    onChange={(e) => setEditingCardName(e.target.value)}
                    className="w-full bg-transparent font-serif italic font-bold text-primary text-xl sm:text-2xl leading-tight focus:outline-none border-b border-transparent focus:border-tertiary transition-colors pb-1"
                    aria-label="Card title"
                  />
                </div>

                {/* Panel body (split layout) */}
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-6 p-6">
                    {/* Left Column: Description (Wider, h-full/flexible) */}
                    <div className="md:col-span-7 space-y-6">
                      {/* Description — Edit / Preview tabs */}
                      <div className="space-y-3 flex flex-col h-full min-h-[300px]">
                        <div className="flex items-center justify-between border-b border-border/40 pb-1">
                          <span className={LABEL_CAPS}>Description</span>
                          <div className="flex gap-1.5">
                            <button
                              type="button"
                              onClick={() => setEditingDescTab("write")}
                              className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider transition-colors cursor-pointer ${
                                editingDescTab === "write"
                                  ? "bg-primary text-neutral font-semibold"
                                  : "text-secondary hover:text-primary"
                              }`}
                            >
                              Write
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingDescTab("preview")}
                              className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider transition-colors cursor-pointer ${
                                editingDescTab === "preview"
                                  ? "bg-primary text-neutral font-semibold"
                                  : "text-secondary hover:text-primary"
                              }`}
                            >
                              Preview
                            </button>
                          </div>
                        </div>

                        {editingDescTab === "write" ? (
                          <textarea
                            placeholder="Add details about this task…"
                            value={editingCardDesc}
                            onChange={(e) => setEditingCardDesc(e.target.value)}
                            className={FIELD + " flex-1 min-h-[320px] resize-y leading-relaxed"}
                          />
                        ) : (
                          <div className="bg-neutral/40 border border-border/40 p-4.5 rounded-md flex-1 min-h-[320px] text-xs text-primary leading-relaxed whitespace-pre-wrap break-words overflow-y-auto">
                            {(() => {
                              const drill = parseDrillContent(editingCardDesc);
                              if (drill) {
                                return (
                                  <div className="space-y-4">
                                    <div>
                                      <span className="font-semibold text-secondary block text-[8px] uppercase tracking-wider mb-0.5">Question</span>
                                      <div className="bg-neutral/50 border border-border/40 p-3 rounded font-medium">
                                        {formatMarkdown(drill.question)}
                                      </div>
                                    </div>
                                    {drill.answer && (
                                      <div>
                                        <span className="font-semibold text-tertiary block text-[8px] uppercase tracking-wider mb-0.5">Answer</span>
                                        <div className="bg-sand/10 border border-tertiary/20 p-3 rounded font-normal">
                                          {formatMarkdown(drill.answer)}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                );
                              }
                              return formatMarkdown(editingCardDesc) || <span className="text-secondary italic">No description provided.</span>;
                            })()}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right Column: Status & Metadata (Narrower) */}
                    <div className="md:col-span-5 space-y-6 border-t md:border-t-0 md:border-l border-primary/10 pt-6 md:pt-0 md:pl-6">
                      {/* Status — move between columns */}
                      <div className="space-y-2">
                        <span className={LABEL_CAPS}>Status</span>
                        <div className="flex flex-wrap gap-1.5">
                          {lists.map(list => {
                            const isActive = list.id === selectedCard.listId;
                            return (
                              <button
                                key={list.id}
                                onClick={() => handleMoveCard(selectedCard.id, list.id).then(() => {
                                  setSelectedCard(prev => prev ? { ...prev, listId: list.id } : null);
                                })}
                                className={`px-3 py-1.5 border rounded text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer ${
                                  isActive
                                    ? "bg-primary text-neutral border-primary"
                                    : "bg-card border-border text-secondary hover:text-primary hover:bg-sand"
                                }`}
                              >
                                {list.name}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Metadata */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label htmlFor="card_loc" className={LABEL_CAPS + " flex items-center gap-1"}>
                            <MapPin className="w-3 h-3" />
                            Location
                          </label>
                          <input
                            id="card_loc"
                            type="text"
                            placeholder="e.g. Geneva"
                            value={cardLocation}
                            onChange={(e) => setCardLocation(e.target.value)}
                            className={FIELD}
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label htmlFor="card_recur" className={LABEL_CAPS + " flex items-center gap-1"}>
                            <RefreshCw className="w-3 h-3" />
                            Recurrence
                          </label>
                          <select
                            id="card_recur"
                            value={cardRecurrence}
                            onChange={(e) => setCardRecurrence(e.target.value as "none" | "daily" | "weekly" | "monthly")}
                            className={FIELD + " cursor-pointer"}
                          >
                            <option value="none">None</option>
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="monthly">Monthly</option>
                          </select>
                        </div>

                        <div className="space-y-1.5">
                          <label htmlFor="card_colls" className={LABEL_CAPS + " flex items-center gap-1"}>
                            <Tag className="w-3 h-3" />
                            Collections
                          </label>
                          <input
                            id="card_colls"
                            type="text"
                            placeholder="e.g. Dev, QA"
                            value={cardCollections}
                            onChange={(e) => setCardCollections(e.target.value)}
                            className={FIELD}
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label htmlFor="card_due_date" className={LABEL_CAPS + " flex items-center gap-1"}>
                            <Clock className="w-3 h-3" />
                            Due Date
                          </label>
                          <div className="flex gap-1.5 items-center">
                            <input
                              id="card_due_date"
                              type="date"
                              value={cardDueDate}
                              onChange={(e) => setCardDueDate(e.target.value)}
                              className={FIELD + " cursor-pointer"}
                            />
                            {cardDueDate && (
                              <button
                                type="button"
                                onClick={() => setCardDueDate("")}
                                className="p-2 text-secondary hover:text-[#B8422E] cursor-pointer"
                                title="Clear due date"
                                aria-label="Clear due date"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Discussion */}
                      <div className="space-y-4 pt-2 border-t border-primary/10">
                        <div className="flex items-center gap-2 text-secondary pt-2">
                          <MessageSquare className="w-4 h-4" />
                          <span className="text-xs font-bold">Discussion</span>
                        </div>

                        <form onSubmit={handleAddComment} className="flex gap-2">
                          <input
                            type="text"
                            placeholder="Ask a question or post an update…"
                            value={newCommentText}
                            onChange={(e) => setNewCommentText(e.target.value)}
                            className={FIELD}
                          />
                          <button
                            type="submit"
                            disabled={!newCommentText.trim()}
                            className="px-4 bg-primary text-neutral hover:bg-primary/90 disabled:bg-card disabled:text-secondary/40 disabled:border disabled:border-border text-xs font-bold rounded cursor-pointer transition-all shrink-0"
                          >
                            Post
                          </button>
                        </form>

                        <div className="space-y-3.5 max-h-[220px] overflow-y-auto custom-scrollbar pr-1">
                          {comments.length === 0 ? (
                            <div className="text-center text-[10px] text-secondary font-mono py-4">No comments posted yet.</div>
                          ) : (
                            comments.map((comment) => (
                              <div key={comment.id} className="flex gap-3 items-start text-left">
                                <div className="w-6 h-6 bg-tertiary/10 border border-tertiary/25 rounded-full flex items-center justify-center shrink-0 mt-0.5">
                                  <span className="text-tertiary text-[9px] font-mono font-black uppercase">A</span>
                                </div>
                                <div className="flex-1 space-y-1 min-w-0">
                                  <div className="flex justify-between items-baseline gap-2">
                                    <span className="text-[10px] font-bold text-primary">Agent Supervisor</span>
                                    <span className="text-[8px] font-mono text-secondary shrink-0">
                                      {new Date(comment.createdAt).toLocaleDateString([], { month: "short", day: "numeric" })} · {new Date(comment.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                    </span>
                                  </div>
                                  <div className="text-xs text-primary leading-relaxed border-l-2 border-primary/10 pl-3 markdown-content">{formatMarkdown(comment.text)}</div>
                                </div>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Panel footer */}
                <div className="px-6 py-4 border-t border-primary/10 bg-card flex justify-between items-center shrink-0">
                  <button
                    onClick={() => handleCloseCard(selectedCard.id)}
                    className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-secondary hover:text-[#B8422E] transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Archive
                  </button>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setSelectedCard(null)}
                      className="px-4 py-2 border border-border hover:bg-sand text-xs font-bold uppercase tracking-wider rounded text-secondary hover:text-primary cursor-pointer transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleUpdateCardDetails}
                      className="px-5 py-2 bg-tertiary hover:bg-tertiary/90 text-white text-xs font-bold uppercase tracking-wider rounded cursor-pointer transition-colors"
                    >
                      Save & Close
                    </button>
                  </div>
                </div>
              </motion.div>
            </div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
