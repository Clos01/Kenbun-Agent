"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import {
  Columns,
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
  RefreshCw
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";

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

interface KenbunMetadata {
  location?: string;
  recurring?: "none" | "daily" | "weekly" | "monthly";
  collections?: string[];
}

// Helpers for metadata parsing
function parseCardMetadata(description: string): { cleanDescription: string; metadata: KenbunMetadata } {
  if (!description) {
    return { cleanDescription: "", metadata: {} };
  }
  const regex = /<!--\s*kenbun_metadata:\s*({[\s\S]*?})\s*-->/;
  const match = description.match(regex);
  if (match) {
    try {
      const metadata = JSON.parse(match[1]);
      const cleanDescription = description.replace(regex, "").trim();
      return { cleanDescription, metadata };
    } catch (e) {
      console.error("Failed to parse kenbun_metadata:", e);
    }
  }
  return { cleanDescription: description, metadata: {} };
}

function injectCardMetadata(description: string, metadata: KenbunMetadata): string {
  const { cleanDescription } = parseCardMetadata(description);
  const jsonStr = JSON.stringify(metadata);
  const metadataComment = `\n\n<!-- kenbun_metadata: ${jsonStr} -->`;
  return cleanDescription + metadataComment;
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

  // Active view tab: kanban | calendar | messaging
  const [activeTab, setActiveTab] = useState<"kanban" | "calendar" | "messaging">("kanban");

  const hasRestoredBoard = useRef(false);

  // Persistence helpers
  const changeTab = (tab: "kanban" | "calendar" | "messaging") => {
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

  // Load saved tab from localStorage on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedTab = localStorage.getItem("board_active_tab");
      if (savedTab === "kanban" || savedTab === "calendar" || savedTab === "messaging") {
        setActiveTab(savedTab);
      }
    }
  }, []);

  // Filters State
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");
  const [filterLocation, setFilterLocation] = useState("");
  const [selectedCollection, setSelectedCollection] = useState("");

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
    !!c.dueDate && !isDoneCard(c) && new Date(c.dueDate).getTime() < Date.now();

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

      <main className="flex-1 relative z-10 flex flex-col min-w-0 overflow-x-hidden pb-20 lg:pb-0">
        {/* ============ HEADER — single calm row ============ */}
        <header className="h-16 border-b border-primary/10 bg-neutral/85 backdrop-blur-sm sticky top-0 z-30 shrink-0 flex items-center justify-between px-6 lg:px-10 gap-6">
          <div className="flex items-center gap-4 min-w-0">
            {selectedBoard ? (
              <button
                onClick={() => {
                  selectBoard(null);
                  changeTab("kanban");
                }}
                className="p-1.5 -ml-1.5 text-secondary hover:text-primary transition-colors rounded cursor-pointer"
                aria-label="Back to projects"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            ) : (
              <Columns className="w-4 h-4 text-tertiary shrink-0" />
            )}
            <div className="min-w-0">
              <div className={LABEL_CAPS + " leading-none mb-0.5"}>
                {selectedBoard ? "Kanban Board" : "Workspaces"}
              </div>
              <h1 className="font-serif italic text-lg font-bold text-primary leading-tight truncate">
                {selectedBoard ? selectedBoard.name : "Mission Board"}
              </h1>
            </div>

            {/* Tabs live in the header — no second nav row */}
            {selectedBoard && (
              <nav className="hidden md:flex items-center gap-1 ml-6 border-l border-primary/10 pl-6 h-full">
                {([
                  { key: "kanban", label: "Board", icon: Columns },
                  { key: "calendar", label: "Calendar", icon: Calendar },
                  { key: "messaging", label: "Feed", icon: MessageSquare },
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
            {syncing && (
              <span className="hidden sm:flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider text-secondary mr-2">
                <span className="w-1.5 h-1.5 bg-tertiary rounded-full animate-pulse" />
                Syncing
              </span>
            )}
            {selectedBoard ? (
              <>
                <button
                  onClick={() => setActiveAddingListForBoard(true)}
                  className="px-3 py-1.5 bg-primary text-neutral hover:bg-primary/90 rounded text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Column
                </button>
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

        {/* Mobile tabs (header hides them under md) */}
        {selectedBoard && (
          <div className="md:hidden flex border-b border-primary/10 px-6">
            {([
              { key: "kanban", label: "Board" },
              { key: "calendar", label: "Calendar" },
              { key: "messaging", label: "Feed" },
            ] as const).map(t => (
              <button
                key={t.key}
                onClick={() => changeTab(t.key)}
                className={`py-2.5 px-3 text-[10px] font-bold uppercase tracking-widest border-b-2 -mb-px cursor-pointer ${
                  activeTab === t.key ? "border-tertiary text-tertiary" : "border-transparent text-secondary"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}

        {/* ============ FILTER STRIP — one quiet row ============ */}
        {selectedBoard && (
          <div className="border-b border-primary/10 px-6 lg:px-10 py-2 flex flex-wrap items-center gap-x-5 gap-y-2 bg-neutral/85 backdrop-blur-sm sticky top-16 z-20 shrink-0">
            <div className="flex items-center gap-2 flex-1 min-w-[180px]">
              <Search className="w-3.5 h-3.5 text-secondary shrink-0" />
              <input
                type="text"
                placeholder="Search cards…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent text-xs text-primary placeholder-secondary/50 focus:outline-none py-1 w-full"
              />
              {searchQuery && (
                <button onClick={() => setSearchQuery("")} className="text-secondary hover:text-primary cursor-pointer" aria-label="Clear search"><X className="w-3 h-3" /></button>
              )}
            </div>

            <label className="flex items-center gap-1.5 text-[9px] font-mono text-secondary uppercase tracking-wider">
              From
              <input
                type="date"
                value={filterStartDate}
                onChange={(e) => setFilterStartDate(e.target.value)}
                className="bg-transparent text-[10px] text-primary focus:outline-none cursor-pointer border-b border-border focus:border-tertiary py-0.5"
                aria-label="Start date filter"
              />
            </label>

            <label className="flex items-center gap-1.5 text-[9px] font-mono text-secondary uppercase tracking-wider">
              To
              <input
                type="date"
                value={filterEndDate}
                onChange={(e) => setFilterEndDate(e.target.value)}
                className="bg-transparent text-[10px] text-primary focus:outline-none cursor-pointer border-b border-border focus:border-tertiary py-0.5"
                aria-label="End date filter"
              />
            </label>

            <label className="flex items-center gap-1.5">
              <MapPin className="w-3 h-3 text-secondary" />
              <input
                type="text"
                placeholder="Location"
                value={filterLocation}
                onChange={(e) => setFilterLocation(e.target.value)}
                className="bg-transparent text-[10px] text-primary placeholder-secondary/50 focus:outline-none w-20 border-b border-border focus:border-tertiary py-0.5"
              />
            </label>

            <label className="flex items-center gap-1.5">
              <Tag className="w-3 h-3 text-secondary" />
              <select
                value={selectedCollection}
                onChange={(e) => setSelectedCollection(e.target.value)}
                className="bg-transparent text-[10px] text-primary focus:outline-none cursor-pointer border-b border-border focus:border-tertiary py-0.5 w-24"
                aria-label="Collection filter"
              >
                <option value="">Collections</option>
                {allCollections.map(col => (
                  <option key={col} value={col}>{col}</option>
                ))}
              </select>
            </label>

            {hasActiveFilters && (
              <button
                onClick={() => {
                  setSearchQuery("");
                  setFilterStartDate("");
                  setFilterEndDate("");
                  setFilterLocation("");
                  setSelectedCollection("");
                }}
                className="text-[9px] font-mono font-bold uppercase tracking-wider text-tertiary hover:underline cursor-pointer"
              >
                Clear filters
              </button>
            )}
          </div>
        )}

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
                /* ---- KANBAN — open lanes with hairline separators ---- */
                <motion.div
                  key="board-kanban"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex overflow-x-auto items-stretch h-[calc(100vh-8rem)] min-h-[480px] custom-scrollbar"
                >
                  {lists.map((list, listIdx) => {
                    const columnCards = filteredCards.filter(c => c.listId === list.id);
                    return (
                      <div
                        key={list.id}
                        className={`w-[300px] shrink-0 flex flex-col px-4 pt-5 pb-4 ${listIdx > 0 ? "border-l border-primary/10" : ""}`}
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
                              return (
                                <motion.div
                                  layoutId={`card-${card.id}`}
                                  key={card.id}
                                  className={`p-3.5 bg-card border rounded-lg cursor-pointer relative group/card transition-all duration-200 hover:shadow-md ${
                                    selectedCard?.id === card.id
                                      ? "border-tertiary/50 shadow-sm"
                                      : "border-primary/10 hover:border-primary/25"
                                  }`}
                                  onClick={() => handleOpenCard(card)}
                                >
                                  <div className="flex justify-between items-start gap-2">
                                    <h4 className="font-semibold text-primary text-[13px] leading-snug">
                                      {card.name}
                                    </h4>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleCloseCard(card.id);
                                      }}
                                      className="opacity-0 group-hover/card:opacity-100 p-1 -m-1 text-secondary/60 hover:text-[#B8422E] transition-all cursor-pointer shrink-0"
                                      title="Archive card"
                                      aria-label="Archive card"
                                    >
                                      <Trash2 className="w-3 h-3" />
                                    </button>
                                  </div>

                                  {cleanDescription && (
                                    <p className="mt-1.5 text-[11px] text-secondary line-clamp-2 leading-relaxed">
                                      {cleanDescription}
                                    </p>
                                  )}

                                  {/* Metadata chips — quiet, uniform; overdue is the one accent */}
                                  {(card.dueDate || metadata.location || (metadata.recurring && metadata.recurring !== "none") || (metadata.collections || []).length > 0) && (
                                    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2.5 items-center">
                                      {card.dueDate && (
                                        <span className={`flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider ${
                                          overdue ? "text-[#B8422E] font-bold" : "text-secondary"
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
                                    className="mt-2 pt-2 border-t border-primary/5 hidden group-hover/card:flex items-center justify-between"
                                    onClick={e => e.stopPropagation()}
                                  >
                                    <span className="text-[8px] font-mono text-secondary/60 uppercase tracking-widest">Move to</span>
                                    <select
                                      onChange={(e) => handleMoveCard(card.id, e.target.value)}
                                      value={card.listId}
                                      className="text-[10px] bg-transparent text-secondary hover:text-primary cursor-pointer outline-none font-mono text-right"
                                      aria-label="Move card column"
                                    >
                                      {lists.map(l => (
                                        <option key={l.id} value={l.id}>{l.name}</option>
                                      ))}
                                    </select>
                                  </div>
                                </motion.div>
                              );
                            })}
                          </AnimatePresence>

                          {/* Inline add-card */}
                          {activeAddingCardForListId === list.id ? (
                            <div className="p-3 bg-card border border-tertiary/30 rounded-lg space-y-2">
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

                  <div className="grid grid-cols-7 gap-1.5 min-h-[420px]">
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
                          className={`relative min-h-[110px] p-2 border rounded-md flex flex-col transition-colors ${
                            cell.isCurrentMonth ? "bg-card/60 border-primary/10" : "bg-transparent border-primary/5 opacity-40"
                          } ${isToday ? "border-tertiary/50" : ""} ${isDoneExpanded || isActiveExpanded ? "z-40 opacity-100" : ""}`}
                        >
                          <div className="flex justify-between items-center">
                            <span className={`text-[10px] font-mono tabular-nums ${isToday ? "text-tertiary font-bold" : "text-secondary"}`}>
                              {cell.day}
                            </span>
                            {isToday && (
                              <span className="w-1.5 h-1.5 bg-tertiary rounded-full" />
                            )}
                          </div>

                          {/* Compact active-work indicator — one dot per active target, click to expand */}
                          {cellCards.length > 0 && (
                            <button
                              onClick={() => setExpandedActiveKey(isActiveExpanded ? null : doneKey)}
                              aria-expanded={isActiveExpanded}
                              aria-label={`${cellCards.length} active targets — view details`}
                              title={`${cellCards.length} active targets`}
                              className="group mt-1.5 self-start flex items-center gap-1 h-[18px] px-2 rounded-full border border-primary/15 bg-primary/[0.04] hover:border-primary/35 hover:bg-primary/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 cursor-pointer transition-all duration-200"
                            >
                              {cellCards.slice(0, 4).map(c => (
                                <span
                                  key={c.id}
                                  className="w-[5px] h-[5px] rounded-full bg-primary/60 group-hover:bg-primary transition-colors duration-200"
                                />
                              ))}
                              {cellCards.length > 4 && (
                                <span className="pl-0.5 text-[8px] font-mono leading-none tabular-nums text-primary/70 group-hover:text-primary transition-colors duration-200">
                                  +{cellCards.length - 4}
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
                              className="group mt-1.5 self-start flex items-center gap-1 h-[18px] px-2 rounded-full border border-tertiary/15 bg-tertiary/[0.06] hover:border-tertiary/35 hover:bg-tertiary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tertiary/40 cursor-pointer transition-all duration-200"
                            >
                              {completedCards.slice(0, 4).map(c => (
                                <span
                                  key={c.id}
                                  className="w-[5px] h-[5px] rounded-full bg-tertiary/60 group-hover:bg-tertiary transition-colors duration-200"
                                />
                              ))}
                              {completedCards.length > 4 && (
                                <span className="pl-0.5 text-[8px] font-mono leading-none tabular-nums text-tertiary/70 group-hover:text-tertiary transition-colors duration-200">
                                  +{completedCards.length - 4}
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
                                className={`absolute z-50 w-[310px] bg-card border border-primary/10 rounded-xl shadow-2xl shadow-primary/10 overflow-hidden ${
                                  Math.floor(idx / 7) < 2 ? "top-full mt-1.5" : "bottom-8 mb-1"
                                } ${idx % 7 >= 4 ? "right-0" : "left-0"}`}
                              >
                                <div className="flex items-start justify-between gap-2 px-4 pt-3.5 pb-2.5 border-b border-primary/5">
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
                                className={`absolute z-50 w-[310px] bg-card border border-primary/10 rounded-xl shadow-2xl shadow-primary/10 overflow-hidden ${
                                  Math.floor(idx / 7) < 2 ? "top-full mt-1.5" : "bottom-8 mb-1"
                                } ${idx % 7 >= 4 ? "right-0" : "left-0"}`}
                              >
                                <div className="flex items-start justify-between gap-2 px-4 pt-3.5 pb-2.5 border-b border-primary/5">
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
              ) : (
                /* ---- FEED (mail & messaging) ---- */
                <motion.div
                  key="board-messaging"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start px-6 lg:px-10 py-6 h-[calc(100vh-8rem)] min-h-[480px]"
                >
                  <div className="lg:col-span-2 bg-card border border-primary/10 rounded-lg flex flex-col h-full overflow-hidden">
                    <div className="flex justify-between items-center border-b border-primary/10 px-5 py-4 shrink-0">
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
                          <div key={comment.id} className="flex gap-3.5 items-start text-left border-b border-primary/5 pb-4 last:border-b-0">
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
                              <p className="text-xs text-primary leading-relaxed break-words">{comment.text}</p>

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

                  <div className="bg-card border border-primary/10 p-5 rounded-lg space-y-4 text-left">
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
                          className={FIELD + " cursor-pointer"}
                        >
                          <option value="">— Choose active card —</option>
                          {cards.map(c => (
                            <option key={c.id} value={c.id}>{c.name}</option>
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
                          className={FIELD + " h-24 resize-none"}
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
          <div className="fixed inset-0 bg-primary/25 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ scale: 0.97, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.97, opacity: 0 }}
              className="w-full max-w-md bg-neutral border border-primary/15 rounded-lg p-6 shadow-xl text-left"
            >
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-base font-serif italic text-primary font-bold">Create Project Workspace</h3>
                <button onClick={() => setIsAddingProject(false)} className="text-secondary hover:text-primary cursor-pointer" aria-label="Close"><X className="w-4 h-4" /></button>
              </div>

              <form onSubmit={handleCreateProject} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="proj_name" className={LABEL_CAPS}>Project Name</label>
                  <input
                    id="proj_name"
                    type="text"
                    placeholder="e.g. Kenbun Swarm Client"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    className={FIELD}
                    autoFocus
                  />
                </div>

                <div className="flex gap-3 justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddingProject(false)}
                    className="px-4 py-2 border border-border text-xs font-bold uppercase tracking-wider rounded text-secondary hover:text-primary hover:bg-sand cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2 bg-primary text-neutral hover:bg-primary/90 text-xs font-bold rounded cursor-pointer"
                  >
                    Create Project
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ============ CARD SIDE PANEL (replaces the centered modal) ============ */}
      <AnimatePresence>
        {selectedCard && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.25 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedCard(null)}
              className="fixed inset-0 bg-primary z-40"
            />
            <motion.aside
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 260 }}
              className="fixed right-0 top-0 bottom-0 w-full sm:w-[460px] bg-neutral border-l border-primary/15 z-50 flex flex-col shadow-2xl text-left"
            >
              {/* Panel header */}
              <div className="px-6 pt-5 pb-4 border-b border-primary/10 shrink-0">
                <div className="flex items-center justify-between gap-3 mb-3">
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
                  <button onClick={() => setSelectedCard(null)} className="text-secondary hover:text-primary cursor-pointer" aria-label="Close card panel">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <input
                  type="text"
                  value={editingCardName}
                  onChange={(e) => setEditingCardName(e.target.value)}
                  className="w-full bg-transparent font-serif italic font-bold text-primary text-xl leading-tight focus:outline-none border-b border-transparent focus:border-tertiary transition-colors pb-1"
                  aria-label="Card title"
                />
              </div>

              {/* Panel body */}
              <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6 custom-scrollbar">
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

                {/* Description — always editable */}
                <div className="space-y-2">
                  <span className={LABEL_CAPS}>Description</span>
                  <textarea
                    placeholder="Add details about this task…"
                    value={editingCardDesc}
                    onChange={(e) => setEditingCardDesc(e.target.value)}
                    className={FIELD + " h-28 resize-none leading-relaxed"}
                  />
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
                  <div className="flex items-center gap-2 text-secondary pt-4">
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

                  <div className="space-y-3.5">
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
                            <p className="text-xs text-primary leading-relaxed border-l-2 border-primary/10 pl-3">{comment.text}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Panel footer — Save closes the panel */}
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
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
