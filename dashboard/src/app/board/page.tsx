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
  Maximize2,
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

  // Dialogs / Inputs for Card Details
  const [selectedCard, setSelectedCard] = useState<Card | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [newCommentText, setNewCommentText] = useState("");
  const [isAddingProject, setIsAddingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [isAddingBoard, setIsAddingBoard] = useState(false);
  const [newBoardName, setNewBoardName] = useState("");
  const [selectedProjectIdForBoard, setSelectedProjectIdForBoard] = useState("");
  
  const [activeAddingListForBoard, setActiveAddingListForBoard] = useState(false);
  const [newListName, setNewListName] = useState("");
  const [activeAddingCardForListId, setActiveAddingCardForListId] = useState<string | null>(null);
  const [newCardName, setNewCardName] = useState("");

  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [editingCardName, setEditingCardName] = useState("");
  const [editingCardDesc, setEditingCardDesc] = useState("");

  // Custom metadata input states in Modal
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

  // Handle card selection & modal opening
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

  const handleCreateBoard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBoardName.trim() || !selectedProjectIdForBoard) return;
    try {
      setSyncing(true);
      const res = await tenantFetch(`${API_BASE}/api/v1/planka/projects/${selectedProjectIdForBoard}/boards`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newBoardName.trim() })
      });
      if (res.ok) {
        setNewBoardName("");
        setIsAddingBoard(false);
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
        setEditingCardId(null);
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
    <div className="min-h-screen bg-neutral text-primary flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden relative font-sans">
      <div className="grain-overlay opacity-20" />
      
      {/* Heritage Style Subtle Aura Grid overlay */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-20%] left-[-10%] w-[60vw] h-[60vw] bg-tertiary/[0.03] rounded-full blur-[160px] animate-pulse duration-[8s]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50vw] h-[50vw] bg-[#B8422E]/[0.02] rounded-full blur-[140px] animate-pulse duration-[12s]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] opacity-30" />
      </div>

      <Sidebar />

      <main className="flex-1 p-0 relative flex flex-col z-10 transition-all duration-500 pb-20 lg:pb-0 min-w-0 overflow-x-hidden">
        {/* Top Status Sync Indicator */}
        <div className="absolute top-4 right-6 z-50 flex items-center gap-2">
          {syncing && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-1.5 px-3 py-1 bg-tertiary/10 border border-tertiary/20 rounded-full text-[9px] uppercase tracking-wider text-tertiary font-mono shadow-sm"
            >
              <span className="w-1.5 h-1.5 bg-tertiary rounded-full animate-ping" />
              Syncing
            </motion.div>
          )}
        </div>

        {/* HEADER */}
        <header className="h-20 lg:h-24 border-b border-primary/5 flex items-center justify-between px-6 lg:px-10 bg-card/45 backdrop-blur-xl sticky top-0 z-30 shrink-0">
          <div className="flex items-center gap-4 lg:gap-8">
            {selectedBoard ? (
              <button 
                onClick={() => {
                  selectBoard(null);
                  changeTab("kanban");
                }}
                className="p-2 border border-border bg-card hover:bg-sand text-secondary hover:text-primary transition-all rounded hover:border-tertiary/35 group flex items-center justify-center shrink-0 cursor-pointer"
                aria-label="Back to projects"
              >
                <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
              </button>
            ) : (
              <div className="w-8 h-8 border border-tertiary flex items-center justify-center bg-tertiary/10 rounded-sm shrink-0">
                <Columns className="w-4 h-4 text-tertiary" />
              </div>
            )}
            <div className="h-6 w-[1px] bg-primary/10" />
            <div className="flex flex-col">
              <span className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] leading-none mb-1">
                {selectedBoard ? "Active Kanban Board" : "Sovereign Workspaces"}
              </span>
              <AnimatePresence mode="wait">
                <motion.span 
                  key={selectedBoard ? selectedBoard.id : "projects"}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  className="font-serif italic text-lg lg:text-xl font-bold text-primary tracking-tight"
                >
                  {selectedBoard ? selectedBoard.name : "Mission Board"}
                </motion.span>
              </AnimatePresence>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {selectedBoard && (
              <>
                <button 
                  onClick={() => {
                    setEditBoardName(selectedBoard.name);
                    setIsSettingsOpen(true);
                  }}
                  className="p-2 border border-border bg-card hover:bg-sand text-secondary hover:text-primary transition-all rounded hover:border-tertiary/35 cursor-pointer flex items-center justify-center"
                  aria-label="Board Settings"
                  title="Board Settings"
                >
                  <Settings className="w-4.5 h-4.5" />
                </button>
                <button 
                  onClick={() => setActiveAddingListForBoard(true)}
                  className="px-4 py-2 border border-tertiary/30 bg-tertiary/10 hover:bg-tertiary/20 hover:border-tertiary/50 text-tertiary transition-all rounded-md font-bold text-[10px] uppercase tracking-wider flex items-center gap-2 cursor-pointer shadow-sm"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Column
                </button>
              </>
            )}
            
            {!selectedBoard && (
              <div className="flex gap-2">
                <button 
                  onClick={() => setIsAddingProject(true)}
                  className="px-3 py-1.5 border border-border bg-card/40 hover:bg-sand text-[10px] font-bold uppercase tracking-widest rounded-md transition-all cursor-pointer text-secondary hover:text-primary"
                >
                  New Project
                </button>
                <button 
                  onClick={() => {
                    if (projects.length > 0) {
                      setSelectedProjectIdForBoard(projects[0].id);
                      setIsAddingBoard(true);
                    }
                  }}
                  className="px-3 py-1.5 border border-tertiary/30 bg-tertiary/10 hover:bg-tertiary/20 text-[10px] font-bold uppercase tracking-widest rounded-md text-tertiary transition-all cursor-pointer"
                >
                  New Board
                </button>
              </div>
            )}
          </div>
        </header>

        {/* SUB-NAVIGATION TABS */}
        {selectedBoard && (
          <div className="h-12 border-b border-primary/5 bg-card/25 backdrop-blur-xl flex items-center px-6 lg:px-10 gap-6 sticky top-20 lg:top-24 z-20 shrink-0">
            <button 
              onClick={() => changeTab("kanban")}
              className={`h-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 border-b-2 cursor-pointer transition-all ${
                activeTab === "kanban" 
                  ? "border-tertiary text-tertiary" 
                  : "border-transparent text-secondary hover:text-primary"
              }`}
            >
              <Columns className="w-3.5 h-3.5" />
              Kanban Layout
            </button>
            
            <button 
              onClick={() => changeTab("calendar")}
              className={`h-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 border-b-2 cursor-pointer transition-all ${
                activeTab === "calendar" 
                  ? "border-tertiary text-tertiary" 
                  : "border-transparent text-secondary hover:text-primary"
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              Calendar Grid
            </button>

            <button 
              onClick={() => changeTab("messaging")}
              className={`h-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-2 border-b-2 cursor-pointer transition-all ${
                activeTab === "messaging" 
                  ? "border-tertiary text-tertiary" 
                  : "border-transparent text-secondary hover:text-primary"
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Mail & Messaging
            </button>
          </div>
        )}

        {/* FILTER & SEARCH BAR */}
        {selectedBoard && (
          <div className="sticky z-20 shrink-0 bg-neutral/85 backdrop-blur-md border-b border-primary/5 px-6 lg:px-10 py-3 flex flex-wrap items-center justify-between gap-4">
            {/* Global fuzzy search */}
            <div className="flex items-center gap-2 flex-1 min-w-[200px]">
              <Search className="w-4 h-4 text-secondary" />
              <input 
                type="text"
                placeholder="Global fuzzy search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent border-b border-border hover:border-tertiary/50 focus:border-tertiary text-xs text-primary placeholder-secondary/50 focus:outline-none py-1 w-full transition-colors"
              />
              {searchQuery && (
                <button onClick={() => setSearchQuery("")} className="text-secondary hover:text-primary"><X className="w-3.5 h-3.5" /></button>
              )}
            </div>

            {/* Filter Dropdowns and Inputs */}
            <div className="flex flex-wrap items-center gap-3">
              {/* Date Range Start */}
              <div className="flex items-center gap-1.5 border border-border rounded px-2 py-1 bg-card">
                <span className="text-[9px] font-mono text-secondary uppercase font-bold">Start:</span>
                <input 
                  type="date"
                  value={filterStartDate}
                  onChange={(e) => setFilterStartDate(e.target.value)}
                  className="bg-transparent text-[10px] text-primary focus:outline-none cursor-pointer"
                  aria-label="Start date filter"
                />
                {filterStartDate && (
                  <button onClick={() => setFilterStartDate("")} className="text-secondary hover:text-primary"><X className="w-3.5 h-3.5" /></button>
                )}
              </div>

              {/* Date Range End */}
              <div className="flex items-center gap-1.5 border border-border rounded px-2 py-1 bg-card">
                <span className="text-[9px] font-mono text-secondary uppercase font-bold">End:</span>
                <input 
                  type="date"
                  value={filterEndDate}
                  onChange={(e) => setFilterEndDate(e.target.value)}
                  className="bg-transparent text-[10px] text-primary focus:outline-none cursor-pointer"
                  aria-label="End date filter"
                />
                {filterEndDate && (
                  <button onClick={() => setFilterEndDate("")} className="text-secondary hover:text-primary"><X className="w-3.5 h-3.5" /></button>
                )}
              </div>

              {/* Location search */}
              <div className="flex items-center gap-1.5 border border-border rounded px-2 py-1 bg-card">
                <MapPin className="w-3.5 h-3.5 text-secondary" />
                <input 
                  type="text"
                  placeholder="Location..."
                  value={filterLocation}
                  onChange={(e) => setFilterLocation(e.target.value)}
                  className="bg-transparent text-[10px] text-primary placeholder-secondary/50 focus:outline-none w-20"
                />
                {filterLocation && (
                  <button onClick={() => setFilterLocation("")} className="text-secondary hover:text-primary"><X className="w-3.5 h-3.5" /></button>
                )}
              </div>

              {/* Collections Tag Selector */}
              <div className="flex items-center gap-1.5 border border-border rounded px-2 py-1 bg-card">
                <Tag className="w-3.5 h-3.5 text-secondary" />
                <select
                  value={selectedCollection}
                  onChange={(e) => setSelectedCollection(e.target.value)}
                  className="bg-transparent text-[10px] text-primary focus:outline-none cursor-pointer outline-none w-24"
                  aria-label="Collection filter"
                >
                  <option value="">Collections</option>
                  {allCollections.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                {selectedCollection && (
                  <button onClick={() => setSelectedCollection("")} className="text-secondary hover:text-primary"><X className="w-3.5 h-3.5" /></button>
                )}
              </div>

              {/* Clear all filters */}
              {(searchQuery || filterStartDate || filterEndDate || filterLocation || selectedCollection) && (
                <button 
                  onClick={() => {
                    setSearchQuery("");
                    setFilterStartDate("");
                    setFilterEndDate("");
                    setFilterLocation("");
                    setSelectedCollection("");
                  }}
                  className="px-2.5 py-1 text-[9px] font-mono font-bold uppercase tracking-wider text-red-500 hover:text-red-600 bg-red-500/5 hover:bg-red-500/10 border border-red-500/20 rounded cursor-pointer transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        )}

        {/* WORKSPACE AREA */}
        <div className="flex-1 p-6 lg:p-10 xl:p-12 overflow-y-auto">
          {error && (
            <div className="mb-8 p-5 border border-red-500/20 bg-red-500/5 rounded flex items-center gap-4 text-red-600">
              <span className="w-2 h-2 bg-red-500 rounded-full animate-ping shrink-0" />
              <div className="text-xs font-bold uppercase tracking-wider">{error}</div>
            </div>
          )}

          {loading ? (
            <div className="h-96 flex flex-col items-center justify-center gap-4">
              <div className="relative w-10 h-10 border border-tertiary bg-tertiary/5 rounded-sm animate-spin duration-[4s]">
                <div className="absolute inset-1.5 bg-tertiary rounded-xs animate-ping" />
              </div>
              <span className="text-[10px] font-mono text-secondary uppercase tracking-[0.25em]">Synchronizing Board State</span>
            </div>
          ) : (
            <AnimatePresence mode="wait">
              {!selectedBoard ? (
                /* PROJECTS AND BOARDS SELECTOR - Bento Grid Style */
                <motion.div 
                  key="selector"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.4 }}
                  className="space-y-12"
                >
                  {projects.length === 0 ? (
                    <div className="h-80 border border-dashed border-border rounded-xl flex flex-col items-center justify-center gap-4 max-w-xl mx-auto bg-card/20">
                      <Folder className="w-8 h-8 text-secondary/40" />
                      <div className="text-center space-y-1">
                        <h4 className="font-bold text-primary text-sm">No work projects found</h4>
                        <p className="text-xs text-secondary max-w-xs">Create your first project or board to get started with Kenbun Swarm Kanban.</p>
                      </div>
                      <button 
                        onClick={() => setIsAddingProject(true)}
                        className="px-4 py-2 bg-tertiary text-white text-xs font-bold rounded-md hover:bg-tertiary/90 transition-all cursor-pointer uppercase tracking-wider"
                      >
                        Create Project
                      </button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
                      {projects.map((proj, projIdx) => {
                        const isEven = projIdx % 2 === 0;
                        const colSpan = isEven ? "md:col-span-4" : "md:col-span-2";
                        return (
                          <motion.div
                            key={proj.id}
                            initial={{ opacity: 0, scale: 0.98 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: projIdx * 0.05 }}
                            className={`${colSpan} bg-card/60 backdrop-blur-xl border border-primary/5 p-6 rounded-xl relative overflow-hidden group shadow-md hover:shadow-lg transition-all duration-300`}
                          >
                            <div className="absolute inset-0 bg-[radial-gradient(circle_at_var(--x,50%)_var(--y,50%),rgba(0,136,95,0.03)_0%,transparent_50%)] opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />

                            <div className="flex items-center gap-3 mb-6 relative z-10">
                              <div className="w-8 h-8 rounded-lg bg-neutral border border-border flex items-center justify-center">
                                <Folder className="w-4 h-4 text-tertiary" />
                              </div>
                              <div>
                                <h3 className="font-serif italic font-black text-primary text-base leading-none">{proj.name}</h3>
                                <span className="text-[8px] font-mono text-secondary uppercase tracking-[0.2em]">Project Workspace</span>
                              </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 relative z-10">
                              {(proj.boards || []).map((board) => (
                                <button
                                  key={board.id}
                                  onClick={() => selectBoard(board)}
                                  className="p-4 bg-card hover:bg-sand border border-border hover:border-tertiary/30 rounded-lg text-left transition-all duration-300 group/board cursor-pointer flex flex-col justify-between h-28 relative overflow-hidden shadow-sm"
                                >
                                  <div className="space-y-1">
                                    <div className="font-bold text-primary text-sm line-clamp-1">{board.name}</div>
                                    <span className="text-[8px] font-mono text-secondary uppercase tracking-[0.2em]">{board.type || "Kanban"}</span>
                                  </div>
                                  <div className="flex justify-between items-center text-[9px] text-secondary group-hover/board:text-tertiary font-bold uppercase tracking-widest transition-colors">
                                    <span>Open Board</span>
                                    <ChevronRight className="w-3.5 h-3.5 group-hover/board:translate-x-1 transition-transform" />
                                  </div>
                                </button>
                              ))}

                              <button
                                onClick={() => {
                                  setSelectedProjectIdForBoard(proj.id);
                                  setIsAddingBoard(true);
                                }}
                                className="p-4 border border-dashed border-border hover:border-tertiary/50 bg-card/20 hover:bg-sand rounded-lg text-center transition-all duration-300 text-secondary hover:text-tertiary cursor-pointer flex flex-col items-center justify-center gap-1.5 h-28"
                              >
                                <Plus className="w-4 h-4" />
                                <span className="text-xs font-bold uppercase tracking-wider">New Board</span>
                              </button>
                            </div>
                          </motion.div>
                        );
                      })}
                    </div>
                  )}
                </motion.div>
              ) : activeTab === "kanban" ? (
                /* KANBAN BOARD CONTAINER */
                <motion.div 
                  key="board-kanban"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="flex gap-6 overflow-x-auto pb-6 pt-2 items-start h-[calc(100vh-270px)] min-h-[500px] custom-scrollbar"
                >
                  {lists.map((list) => (
                    <motion.div
                      layout
                      key={list.id}
                      className="w-80 shrink-0 bg-card/65 border border-primary/5 p-4 rounded-lg flex flex-col max-h-full artisan-shadow relative group/column"
                    >
                      {/* Column Header */}
                      <div className="flex items-center justify-between mb-4 pb-2 border-b border-primary/5">
                        <div className="flex items-center gap-2">
                          <h3 className="font-bold text-primary text-[10px] uppercase tracking-widest">{list.name}</h3>
                          <span className="px-2 py-0.5 bg-neutral border border-border rounded-full text-[9px] font-mono text-secondary">
                            {filteredCards.filter(c => c.listId === list.id).length}
                          </span>
                        </div>

                        <div className="opacity-0 group-hover/column:opacity-100 transition-opacity">
                          <button 
                            onClick={() => {
                              setActiveAddingCardForListId(list.id);
                              setNewCardName("");
                            }}
                            className="p-1 hover:text-tertiary text-secondary transition-colors rounded hover:bg-neutral cursor-pointer"
                            title="Add card"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Card List Area */}
                      <div className="flex-1 overflow-y-auto space-y-3 pr-1 custom-scrollbar min-h-[50px]">
                        <AnimatePresence mode="popLayout">
                          {filteredCards
                            .filter(c => c.listId === list.id)
                            .map((card) => {
                              const { metadata } = parseCardMetadata(card.description || "");
                              return (
                                <motion.div
                                  layoutId={`card-${card.id}`}
                                  key={card.id}
                                  className="p-4 bg-neutral/80 hover:bg-card border border-primary/5 hover:border-tertiary/30 rounded-lg transition-all duration-300 cursor-pointer relative group/card shadow-sm hover:shadow-md text-left"
                                  onClick={() => handleOpenCard(card)}
                                >
                                  <div className="space-y-2">
                                    <div className="flex justify-between items-start gap-2">
                                      <h4 className="font-bold text-primary text-xs leading-normal">
                                        {card.name}
                                      </h4>
                                      <button 
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleCloseCard(card.id);
                                        }}
                                        className="opacity-0 group-hover/card:opacity-100 p-1 text-secondary hover:text-red-600 hover:bg-red-500/10 rounded transition-all cursor-pointer shrink-0"
                                        title="Archive card"
                                      >
                                        <Trash2 className="w-3 h-3" />
                                      </button>
                                    </div>

                                    {card.description && (
                                      <p className="text-[10px] text-secondary line-clamp-2 leading-relaxed">
                                        {parseCardMetadata(card.description).cleanDescription}
                                      </p>
                                    )}

                                    {/* Badges */}
                                    <div className="flex flex-wrap gap-1 pt-1.5">
                                      {card.dueDate && (
                                        <span className="flex items-center gap-0.5 text-[#B8422E] bg-[#B8422E]/5 border border-[#B8422E]/10 px-1.5 py-0.5 rounded-sm font-mono text-[9px] uppercase tracking-wider font-bold">
                                          <Clock className="w-2.5 h-2.5" />
                                          {new Date(card.dueDate).toLocaleDateString([], { month: "short", day: "numeric" })}
                                        </span>
                                      )}
                                      {metadata.location && (
                                        <span className="flex items-center gap-0.5 text-tertiary bg-tertiary/5 border border-tertiary/10 px-1.5 py-0.5 rounded-sm font-mono text-[9px] uppercase tracking-wider font-bold">
                                          <MapPin className="w-2.5 h-2.5" />
                                          {metadata.location}
                                        </span>
                                      )}
                                      {metadata.recurring && metadata.recurring !== "none" && (
                                        <span className="flex items-center gap-0.5 text-amber-600 bg-amber-500/5 border border-amber-500/10 px-1.5 py-0.5 rounded-sm font-mono text-[9px] uppercase tracking-wider font-bold">
                                          <RefreshCw className="w-2.5 h-2.5 animate-spin duration-[15s]" />
                                          {metadata.recurring}
                                        </span>
                                      )}
                                      {(metadata.collections || []).map(col => (
                                        <span key={col} className="flex items-center gap-0.5 text-blue-600 bg-blue-500/5 border border-blue-500/10 px-1.5 py-0.5 rounded-sm font-mono text-[9px] uppercase tracking-wider font-bold">
                                          <Tag className="w-2.5 h-2.5" />
                                          {col}
                                        </span>
                                      ))}
                                    </div>
                                  </div>

                                  {/* Quick Move Selector */}
                                  <div className="absolute right-3 bottom-3 opacity-0 group-hover/card:opacity-100 transition-opacity flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
                                    <select 
                                      onChange={(e) => handleMoveCard(card.id, e.target.value)}
                                      value={card.listId}
                                      className="text-[9px] bg-neutral border border-border text-secondary rounded px-1.5 py-0.5 font-mono cursor-pointer outline-none focus:border-tertiary"
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

                        {/* Inline Adding Card form */}
                        {activeAddingCardForListId === list.id ? (
                          <div className="p-3 bg-card border border-border rounded-lg space-y-2">
                            <input 
                              type="text" 
                              placeholder="Card title..."
                              value={newCardName}
                              onChange={(e) => setNewCardName(e.target.value)}
                              className="w-full bg-neutral border border-border text-primary rounded p-2 text-xs focus:outline-none focus:border-tertiary"
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
                                className="px-3 py-1 bg-tertiary hover:bg-tertiary/95 text-white text-[10px] uppercase font-bold tracking-wider rounded cursor-pointer"
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
                            className="w-full py-2 border border-dashed border-border hover:border-tertiary/30 rounded-lg text-center text-[10px] text-secondary hover:text-tertiary font-bold uppercase transition-all cursor-pointer flex items-center justify-center gap-1.5 bg-card/10 hover:bg-sand"
                          >
                            <Plus className="w-3 h-3" />
                            Add Card
                          </button>
                        )}
                      </div>
                    </motion.div>
                  ))}

                  {/* Add Column Inline form */}
                  {activeAddingListForBoard ? (
                    <div className="w-80 shrink-0 bg-card border border-border rounded-lg p-4 space-y-3 shadow-sm">
                      <h4 className="text-[10px] font-mono text-secondary uppercase tracking-[0.2em]">New Column</h4>
                      <form onSubmit={handleCreateList} className="space-y-2">
                        <input 
                          type="text"
                          placeholder="Column name..."
                          value={newListName}
                          onChange={(e) => setNewListName(e.target.value)}
                          className="w-full bg-neutral border border-border text-primary rounded p-2.5 text-xs focus:outline-none focus:border-tertiary"
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
                            className="px-4 py-1.5 bg-tertiary hover:bg-tertiary/95 text-white text-xs font-bold rounded cursor-pointer"
                          >
                            Create
                          </button>
                        </div>
                      </form>
                    </div>
                  ) : (
                    <button 
                      onClick={() => setActiveAddingListForBoard(true)}
                      className="w-80 shrink-0 h-14 border border-dashed border-border hover:border-tertiary/40 bg-card/40 hover:bg-sand rounded-lg text-secondary hover:text-tertiary font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-all duration-300 cursor-pointer"
                    >
                      <Plus className="w-4 h-4" />
                      <span className="font-semibold">Add Column</span>
                    </button>
                  )}
                </motion.div>
              ) : activeTab === "calendar" ? (
                /* CALENDAR MONTH VIEW */
                <motion.div
                  key="board-calendar"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="bg-card/45 backdrop-blur-xl border border-primary/5 p-6 rounded-xl space-y-6 text-left"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <h3 className="font-serif italic font-bold text-primary text-lg">
                        {new Date(currentYear, currentMonth).toLocaleDateString([], { month: "long", year: "numeric" })}
                      </h3>
                      <div className="flex gap-1 border border-border rounded p-0.5 bg-neutral">
                        <button 
                          onClick={() => {
                            if (currentMonth === 0) {
                              setCurrentMonth(11);
                              setCurrentYear(prev => prev - 1);
                            } else {
                              setCurrentMonth(prev => prev - 1);
                            }
                          }}
                          className="px-2.5 py-1 text-xs text-secondary hover:text-primary hover:bg-sand rounded cursor-pointer"
                        >
                          &larr;
                        </button>
                        <button 
                          onClick={() => {
                            const today = new Date();
                            setCurrentMonth(today.getMonth());
                            setCurrentYear(today.getFullYear());
                          }}
                          className="px-2.5 py-1 text-xs text-secondary hover:text-primary hover:bg-sand rounded cursor-pointer"
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
                          className="px-2.5 py-1 text-xs text-secondary hover:text-primary hover:bg-sand rounded cursor-pointer"
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

                  <div className="grid grid-cols-7 gap-2 text-center text-[10px] font-mono text-secondary uppercase tracking-widest border-b border-primary/5 pb-2">
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

                  <div className="grid grid-cols-7 gap-2 min-h-[420px]">
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
                          className={`relative min-h-[115px] p-2 border border-primary/5 rounded-md flex flex-col transition-colors ${
                            cell.isCurrentMonth ? "bg-neutral/45" : "bg-neutral/10 opacity-30"
                          } ${isToday ? "border-tertiary/40 bg-tertiary/[0.02]" : ""} ${isDoneExpanded || isActiveExpanded ? "z-40 opacity-100" : ""}`}
                        >
                          <div className="flex justify-between items-center">
                            <span className={`text-[10px] font-mono ${isToday ? "text-tertiary font-bold" : "text-secondary"}`}>
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
                                className={`absolute z-50 w-[310px] bg-card/95 backdrop-blur-xl border border-primary/5 ring-1 ring-primary/5 rounded-xl shadow-2xl shadow-primary/10 overflow-hidden ${
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
                                className={`absolute z-50 w-[310px] bg-card/90 backdrop-blur-xl border border-primary/5 ring-1 ring-primary/5 rounded-xl shadow-2xl shadow-primary/10 overflow-hidden ${
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
                /* MAIL & MESSAGING BOARD FEED */
                <motion.div
                  key="board-messaging"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start h-[calc(100vh-270px)] min-h-[500px]"
                >
                  <div className="lg:col-span-2 bg-card/65 border border-primary/5 p-6 rounded-xl flex flex-col h-full overflow-hidden">
                    <div className="flex justify-between items-center border-b border-primary/5 pb-4 mb-4 shrink-0">
                      <div className="flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-tertiary" />
                        <h3 className="font-serif italic font-bold text-primary text-base">Board Signal Feed</h3>
                      </div>
                      <button 
                        onClick={() => fetchBoardComments()}
                        disabled={loadingComments}
                        className="px-2.5 py-1 border border-border bg-card hover:bg-sand rounded text-[9px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-colors flex items-center gap-1 cursor-pointer"
                      >
                        <RefreshCw className={`w-2.5 h-2.5 ${loadingComments ? "animate-spin" : ""}`} />
                        Reload Feed
                      </button>
                    </div>

                    <div className="flex-1 overflow-y-auto space-y-4 pr-1 custom-scrollbar">
                      {loadingComments ? (
                        <div className="h-60 flex flex-col items-center justify-center gap-2">
                          <RefreshCw className="w-6 h-6 text-tertiary animate-spin" />
                          <span className="text-[9px] font-mono text-secondary uppercase tracking-wider font-bold">Synchronizing Feed Logs</span>
                        </div>
                      ) : boardComments.length === 0 ? (
                        <div className="text-center text-[10px] font-mono text-secondary py-12">No recent signal notes recorded on this board.</div>
                      ) : (
                        boardComments.map(comment => (
                          <div key={comment.id} className="flex gap-3.5 items-start text-left bg-neutral/45 p-3 rounded-lg border border-primary/5">
                            <div className="w-7 h-7 bg-tertiary/10 border border-tertiary/25 rounded-full flex items-center justify-center shrink-0">
                              <span className="text-tertiary text-[10px] font-mono font-black uppercase">A</span>
                            </div>
                            <div className="flex-1 space-y-1 min-w-0">
                              <div className="flex justify-between items-center flex-wrap gap-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-[10px] font-bold text-primary">Agent Supervisor</span>
                                  <span className="text-[8px] font-mono text-secondary uppercase bg-neutral border border-border px-1.5 py-0.5 rounded">
                                    Card: {comment.cardName}
                                  </span>
                                </div>
                                <span className="text-[8px] font-mono text-secondary">
                                  {new Date(comment.createdAt).toLocaleDateString([], { month: "short", day: "numeric" })} at {new Date(comment.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                </span>
                              </div>
                              <p className="text-xs text-primary leading-relaxed break-words">{comment.text}</p>
                              
                              <div className="pt-2 flex justify-end">
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

                  <div className="bg-card/65 border border-primary/5 p-6 rounded-xl space-y-4 text-left">
                    <div className="space-y-1">
                      <h3 className="font-serif italic font-bold text-primary text-base">Broadcast Update</h3>
                      <p className="text-[10px] text-secondary leading-normal">Publish comments and signal logs to any active card from this central board panel.</p>
                    </div>

                    <form onSubmit={handleAddFeedComment} className="space-y-4">
                      <div className="space-y-1.5">
                        <label htmlFor="feed_card_select" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold">Select Target Card</label>
                        <select 
                          id="feed_card_select"
                          value={feedSelectedCardId}
                          onChange={(e) => setFeedSelectedCardId(e.target.value)}
                          className="w-full bg-neutral border border-border rounded p-3 text-xs text-primary focus:outline-none focus:border-tertiary outline-none cursor-pointer"
                        >
                          <option value="">-- Choose active card --</option>
                          {cards.map(c => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-1.5">
                        <label htmlFor="feed_comment_input" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold">Signal Comment</label>
                        <textarea
                          id="feed_comment_input"
                          placeholder="Enter comment text..."
                          value={feedCommentText}
                          onChange={(e) => setFeedCommentText(e.target.value)}
                          className="w-full bg-neutral border border-border text-primary text-xs rounded p-3 h-24 focus:outline-none focus:border-tertiary outline-none resize-none"
                        />
                      </div>

                      <button 
                        type="submit"
                        disabled={!feedCommentText.trim() || !feedSelectedCardId}
                        className="w-full py-2 bg-tertiary hover:bg-tertiary/95 disabled:bg-neutral disabled:text-secondary/40 text-white text-xs font-bold rounded cursor-pointer transition-colors"
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

      {/* SETTINGS PANEL DRAWER */}
      <AnimatePresence>
        {isSettingsOpen && selectedBoard && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.4 }}
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
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed right-0 top-0 bottom-0 w-80 sm:w-96 bg-card border-l border-border z-50 p-6 flex flex-col justify-between shadow-2xl text-left"
            >
              <div className="space-y-6">
                <div className="flex justify-between items-center border-b border-primary/5 pb-4">
                  <div className="flex items-center gap-2">
                    <Settings className="w-4 h-4 text-tertiary animate-spin duration-[10s]" />
                    <h3 className="font-serif italic font-bold text-primary text-base">Board Settings</h3>
                  </div>
                  <button 
                    onClick={() => {
                      setIsSettingsOpen(false);
                      setConfirmDeleteBoard(false);
                    }}
                    className="text-secondary hover:text-primary cursor-pointer"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleUpdateBoard} className="space-y-4">
                  <div className="space-y-1.5">
                    <label htmlFor="board_rename_input" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold">Rename Board</label>
                    <input 
                      id="board_rename_input"
                      type="text" 
                      value={editBoardName}
                      onChange={(e) => setEditBoardName(e.target.value)}
                      className="w-full bg-neutral border border-border rounded p-3 text-sm text-primary focus:outline-none focus:border-tertiary"
                    />
                  </div>
                  <button 
                    type="submit"
                    className="w-full py-2 bg-tertiary hover:bg-tertiary/95 text-white text-xs font-bold rounded cursor-pointer transition-colors"
                  >
                    Save Rename
                  </button>
                </form>

                <div className="space-y-2">
                  <span className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold block">Board Theme Style</span>
                  <div className="flex gap-2">
                    <div className="w-8 h-8 rounded-full border border-tertiary bg-tertiary/10 cursor-pointer flex items-center justify-center" title="Lime Green (Default)">
                      <Check className="w-4 h-4 text-tertiary" />
                    </div>
                    <div className="w-8 h-8 rounded-full border border-border bg-[#B8422E]/10 cursor-pointer flex items-center justify-center animate-pulse" title="Clay Red">
                      <div className="w-3 h-3 rounded-full bg-[#B8422E]" />
                    </div>
                    <div className="w-8 h-8 rounded-full border border-border bg-blue-500/10 cursor-pointer flex items-center justify-center" title="Slate Blue">
                      <div className="w-3 h-3 rounded-full bg-blue-500" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="border-t border-primary/5 pt-4 space-y-3">
                <span className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold block">Danger Zone</span>
                {confirmDeleteBoard ? (
                  <div className="space-y-2 p-3 border border-red-500/20 bg-red-500/5 rounded">
                    <div className="flex items-start gap-2 text-red-600 text-xs">
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
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-[10px] font-bold uppercase rounded cursor-pointer"
                      >
                        Delete Permanently
                      </button>
                    </div>
                  </div>
                ) : (
                  <button 
                    onClick={() => setConfirmDeleteBoard(true)}
                    className="w-full py-2 border border-red-500/20 hover:border-red-500 bg-red-500/5 hover:bg-red-500 text-red-500 hover:text-white text-xs font-bold uppercase tracking-wider rounded transition-all cursor-pointer"
                  >
                    Delete Board
                  </button>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* POPUP: NEW PROJECT MODAL */}
      <AnimatePresence>
        {isAddingProject && (
          <div className="fixed inset-0 bg-primary/20 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-md bg-card border border-[var(--border)] rounded-md p-6 shadow-xl text-left"
            >
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-base font-serif italic text-primary font-bold">Create Project Workspace</h3>
                <button onClick={() => setIsAddingProject(false)} className="text-secondary hover:text-primary cursor-pointer"><X className="w-4 h-4" /></button>
              </div>

              <form onSubmit={handleCreateProject} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="proj_name" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold">Project Name</label>
                  <input 
                    id="proj_name"
                    type="text" 
                    placeholder="e.g. Kenbun Swarm Client"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    className="w-full bg-neutral border border-border rounded p-3 text-sm text-primary focus:outline-none focus:border-tertiary"
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
                    className="px-5 py-2 bg-tertiary hover:bg-tertiary/95 text-white text-xs font-bold rounded cursor-pointer"
                  >
                    Create Project
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* POPUP: NEW BOARD MODAL */}
      <AnimatePresence>
        {isAddingBoard && (
          <div className="fixed inset-0 bg-primary/20 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-md bg-card border border-[var(--border)] rounded-md p-6 shadow-xl text-left"
            >
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-base font-serif italic text-primary font-bold">Create New Kanban Board</h3>
                <button onClick={() => setIsAddingBoard(false)} className="text-secondary hover:text-primary cursor-pointer"><X className="w-4 h-4" /></button>
              </div>

              <form onSubmit={handleCreateBoard} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="target_proj" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold">Select Workspace</label>
                  <select 
                    id="target_proj"
                    value={selectedProjectIdForBoard}
                    onChange={(e) => setSelectedProjectIdForBoard(e.target.value)}
                    className="w-full bg-neutral border border-border rounded p-3 text-sm text-primary focus:outline-none focus:border-tertiary outline-none cursor-pointer"
                  >
                    {projects.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="board_name" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold">Board Title</label>
                  <input 
                    id="board_name"
                    type="text" 
                    placeholder="e.g. Sprint Backlog"
                    value={newBoardName}
                    onChange={(e) => setNewBoardName(e.target.value)}
                    className="w-full bg-neutral border border-border rounded p-3 text-sm text-primary focus:outline-none focus:border-tertiary"
                    autoFocus
                  />
                </div>

                <div className="flex gap-3 justify-end pt-2">
                  <button 
                    type="button" 
                    onClick={() => setIsAddingBoard(false)}
                    className="px-4 py-2 border border-border text-xs font-bold uppercase tracking-wider rounded text-secondary hover:text-primary hover:bg-sand cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    className="px-5 py-2 bg-tertiary hover:bg-tertiary/95 text-white text-xs font-bold rounded cursor-pointer"
                  >
                    Create Board
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* POPUP: CARD DETAILS & COMMENTS MODAL */}
      <AnimatePresence>
        {selectedCard && (
          <div className="fixed inset-0 bg-primary/20 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <motion.div 
              initial={{ scale: 0.97, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.97, opacity: 0, y: 10 }}
              className="w-full max-w-2xl bg-card border border-[var(--border)] rounded-md overflow-hidden shadow-xl flex flex-col max-h-[85vh] text-left"
            >
              {/* Modal Header */}
              <div className="p-6 border-b border-primary/5 flex justify-between items-start gap-4">
                <div className="space-y-1.5 flex-1">
                  {editingCardId === selectedCard.id ? (
                    <div className="flex gap-2">
                      <input 
                        type="text" 
                        value={editingCardName}
                        onChange={(e) => setEditingCardName(e.target.value)}
                        className="bg-neutral border border-border text-primary font-bold text-base rounded p-2 flex-1 focus:outline-none focus:border-tertiary"
                        autoFocus
                      />
                      <button 
                        onClick={handleUpdateCardDetails}
                        className="px-3 bg-tertiary hover:bg-tertiary/90 text-white rounded text-xs font-bold cursor-pointer"
                      >
                        Save
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-bold text-primary leading-tight">{selectedCard.name}</h2>
                      <button 
                        onClick={() => {
                          setEditingCardId(selectedCard.id);
                          setEditingCardName(selectedCard.name);
                          const { cleanDescription } = parseCardMetadata(selectedCard.description || "");
                          setEditingCardDesc(cleanDescription);
                        }}
                        className="p-1 hover:text-tertiary hover:bg-neutral rounded text-[9px] text-secondary uppercase tracking-widest transition-colors cursor-pointer"
                      >
                        Edit
                      </button>
                    </div>
                  )}
                  <div className="flex items-center gap-3 text-[10px] text-secondary font-mono">
                    <span>Column: {lists.find(l => l.id === selectedCard.listId)?.name}</span>
                    {selectedCard.dueDate && (
                      <span className="flex items-center gap-1 text-[#B8422E]">
                        <Clock className="w-3 h-3" />
                        Due {new Date(selectedCard.dueDate).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}
                      </span>
                    )}
                  </div>
                </div>
                <button onClick={() => setSelectedCard(null)} className="text-secondary hover:text-primary cursor-pointer"><X className="w-5 h-5" /></button>
              </div>

              {/* Modal Body */}
              <div className="p-6 space-y-6 overflow-y-auto flex-1 custom-scrollbar">
                {/* Description */}
                <div className="space-y-2">
                  <span className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold">Description</span>
                  {editingCardId === selectedCard.id ? (
                    <textarea
                      placeholder="Add details about this task..."
                      value={editingCardDesc}
                      onChange={(e) => setEditingCardDesc(e.target.value)}
                      className="w-full bg-neutral border border-border text-primary text-xs rounded p-3 h-24 focus:outline-none focus:border-tertiary outline-none"
                    />
                  ) : (
                    <div className="bg-neutral border border-border rounded p-4 text-xs leading-relaxed text-primary whitespace-pre-wrap">
                      {parseCardMetadata(selectedCard.description || "").cleanDescription || "No description provided."}
                    </div>
                  )}
                </div>

                {/* Custom Metadata Editing Inputs */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-neutral border border-border p-4 rounded-md">
                  {/* Location */}
                  <div className="space-y-1.5">
                    <label htmlFor="card_loc" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold flex items-center gap-1">
                      <MapPin className="w-3 h-3 text-tertiary" />
                      Location
                    </label>
                    <input 
                      id="card_loc"
                      type="text"
                      placeholder="e.g. Geneva"
                      value={cardLocation}
                      onChange={(e) => setCardLocation(e.target.value)}
                      className="w-full bg-card border border-border rounded p-2 text-xs text-primary focus:outline-none focus:border-tertiary outline-none"
                    />
                  </div>

                  {/* Collections */}
                  <div className="space-y-1.5">
                    <label htmlFor="card_colls" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold flex items-center gap-1">
                      <Tag className="w-3 h-3 text-tertiary" />
                      Collections
                    </label>
                    <input 
                      id="card_colls"
                      type="text"
                      placeholder="e.g. Dev, QA"
                      value={cardCollections}
                      onChange={(e) => setCardCollections(e.target.value)}
                      className="w-full bg-card border border-border rounded p-2 text-xs text-primary focus:outline-none focus:border-tertiary outline-none"
                    />
                  </div>

                  {/* Recurrence */}
                  <div className="space-y-1.5">
                    <label htmlFor="card_recur" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold flex items-center gap-1">
                      <RefreshCw className="w-3 h-3 text-tertiary" />
                      Recurrence
                    </label>
                    <select
                      id="card_recur"
                      value={cardRecurrence}
                      onChange={(e) => setCardRecurrence(e.target.value as "none" | "daily" | "weekly" | "monthly")}
                      className="w-full bg-card border border-border rounded p-2 text-xs text-primary focus:outline-none focus:border-tertiary outline-none cursor-pointer"
                    >
                      <option value="none">None</option>
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="monthly">Monthly</option>
                    </select>
                  </div>
                </div>

                {/* Due Date Targets Editing */}
                <div className="space-y-1.5 bg-neutral border border-border p-4 rounded-md">
                  <label htmlFor="card_due_date" className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] font-bold flex items-center gap-1">
                    <Clock className="w-3 h-3 text-[#B8422E]" />
                    Due Date Target
                  </label>
                  <div className="flex gap-2 items-center">
                    <input 
                      id="card_due_date"
                      type="date"
                      value={cardDueDate}
                      onChange={(e) => setCardDueDate(e.target.value)}
                      className="bg-card border border-border rounded p-2 text-xs text-primary focus:outline-none focus:border-tertiary outline-none cursor-pointer"
                    />
                    {cardDueDate && (
                      <button 
                        type="button"
                        onClick={() => setCardDueDate("")}
                        className="px-2.5 py-2 border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 text-red-500 rounded text-xs uppercase tracking-wider font-bold transition-all cursor-pointer"
                      >
                        Clear Due Date
                      </button>
                    )}
                  </div>
                </div>

                {/* Move card quickly inside modal */}
                <div className="flex items-center gap-4 bg-neutral border border-border p-4 rounded-md">
                  <div className="flex items-center gap-2">
                    <Maximize2 className="w-4 h-4 text-secondary" />
                    <span className="text-xs text-secondary font-bold">Change status:</span>
                  </div>
                  <div className="flex gap-2">
                    {lists.map(list => {
                      const isActive = list.id === selectedCard.listId;
                      return (
                        <button
                          key={list.id}
                          onClick={() => handleMoveCard(selectedCard.id, list.id).then(() => {
                            setSelectedCard(prev => prev ? { ...prev, listId: list.id } : null);
                          })}
                          className={`px-3 py-1.5 border rounded text-[10px] font-bold uppercase transition-all cursor-pointer ${
                            isActive 
                              ? "bg-tertiary/10 border-tertiary/30 text-tertiary" 
                              : "bg-card border-border text-secondary hover:text-primary hover:bg-sand"
                          }`}
                        >
                          {list.name}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Comments Section */}
                <div className="space-y-4 pt-2">
                  <div className="flex items-center gap-2 text-secondary">
                    <MessageSquare className="w-4 h-4" />
                    <span className="text-xs font-bold">Discussion</span>
                  </div>

                  {/* Add Comment */}
                  <form onSubmit={handleAddComment} className="flex gap-3">
                    <input
                      type="text"
                      placeholder="Ask a question or post an update..."
                      value={newCommentText}
                      onChange={(e) => setNewCommentText(e.target.value)}
                      className="flex-1 bg-neutral border border-border rounded px-4 py-2.5 text-xs text-primary focus:outline-none focus:border-tertiary"
                    />
                    <button 
                      type="submit"
                      disabled={!newCommentText.trim()}
                      className="px-4 bg-tertiary hover:bg-tertiary/95 disabled:bg-neutral disabled:text-secondary/40 text-white text-xs font-bold rounded cursor-pointer transition-all"
                    >
                      Post
                    </button>
                  </form>

                  {/* Comments Feed */}
                  <div className="space-y-3.5 pt-2">
                    {comments.length === 0 ? (
                      <div className="text-center text-[10px] text-secondary font-mono py-4">No comments posted yet.</div>
                    ) : (
                      comments.map((comment) => (
                        <div key={comment.id} className="flex gap-3.5 items-start text-left">
                          <div className="w-7 h-7 bg-tertiary/10 border border-tertiary/25 rounded-full flex items-center justify-center shrink-0">
                            <span className="text-tertiary text-[10px] font-mono font-black uppercase">A</span>
                          </div>
                          <div className="flex-1 space-y-1 bg-neutral border border-border px-4 py-3 rounded">
                            <div className="flex justify-between items-center">
                              <span className="text-[10px] font-bold text-primary">Agent Supervisor</span>
                              <span className="text-[8px] font-mono text-secondary">
                                {new Date(comment.createdAt).toLocaleDateString([], { month: "short", day: "numeric" })} at {new Date(comment.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                              </span>
                            </div>
                            <p className="text-xs text-primary leading-relaxed">{comment.text}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="p-6 bg-neutral border-t border-border flex justify-between">
                <button 
                  onClick={() => handleCloseCard(selectedCard.id)}
                  className="px-4 py-2 border border-red-500/20 hover:border-red-500 bg-red-500/5 hover:bg-red-500 text-red-500 hover:text-white text-xs font-bold uppercase tracking-wider rounded transition-all cursor-pointer"
                >
                  Archive Card
                </button>
                <div className="flex gap-2">
                  <button 
                    onClick={handleUpdateCardDetails}
                    className="px-5 py-2 bg-tertiary hover:bg-tertiary/90 text-white text-xs font-bold uppercase tracking-wider rounded cursor-pointer"
                  >
                    Save Changes
                  </button>
                  <button 
                    onClick={() => setSelectedCard(null)}
                    className="px-5 py-2 bg-card border border-border hover:bg-sand text-xs font-bold uppercase tracking-wider rounded text-secondary hover:text-primary cursor-pointer"
                  >
                    Close
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
