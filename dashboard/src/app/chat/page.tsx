"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import { Send, Terminal, Cpu, CheckCircle, Plus, Trash2, MessageSquare, ChevronDown, Check, Menu, Folder, FolderOpen, Code, Sparkles, Flame, ShieldAlert, Edit2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";

interface ChatMessage {
  id: string;
  sender: "user" | "kenbun";
  content: string;
  timestamp: string;
}

interface ChatSession {
  id: string;
  title: string;
  timestamp: string;
  last_message: string;
}

function parseInlineMarkdown(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index} className="font-extrabold text-primary">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index} className="px-1.5 py-0.5 bg-neutral/80 border border-border/20 rounded font-mono text-[11px] text-tertiary">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

function parseMarkdown(text: string): React.ReactNode {
  if (!text) return null;

  // Split by code blocks first to isolate them
  const parts = text.split(/(```[a-z]*\n[\s\S]*?\n```)/g);

  return parts.map((part, index) => {
    if (part.startsWith("```")) {
      const match = part.match(/```([a-z]*)\n([\s\S]*?)\n```/);
      const code = match ? match[2] : part.slice(3, -3);

      return (
        <pre key={index} className="bg-neutral/40 border border-border/20 rounded-lg p-3.5 my-3.5 font-mono text-[11px] text-primary overflow-x-auto max-w-full">
          <code className="block whitespace-pre">{code}</code>
        </pre>
      );
    }

    const lines = part.split("\n");
    const elements: React.ReactNode[] = [];
    let listItems: string[] = [];

    const flushList = (keyPrefix: number) => {
      if (listItems.length > 0) {
        elements.push(
          <ul key={`list-${keyPrefix}`} className="list-disc pl-5 my-2 flex flex-col gap-1">
            {listItems.map((item, idx) => (
              <li key={idx} className="text-sm text-primary/80 font-sans leading-relaxed">
                {parseInlineMarkdown(item)}
              </li>
            ))}
          </ul>
        );
        listItems = [];
      }
    };

    lines.forEach((line, lineIdx) => {
      const trimmed = line.trim();

      if (trimmed.startsWith("### ")) {
        flushList(lineIdx);
        elements.push(
          <h4 key={lineIdx} className="text-base font-normal italic text-tertiary mt-6 mb-2.5 font-heading">
            {parseInlineMarkdown(trimmed.slice(4))}
          </h4>
        );
      } else if (trimmed.startsWith("## ")) {
        flushList(lineIdx);
        elements.push(
          <h3 key={lineIdx} className="text-xl font-semibold tracking-normal text-primary/95 mt-8 mb-3.5 font-heading">
            {parseInlineMarkdown(trimmed.slice(3))}
          </h3>
        );
      } else if (trimmed.startsWith("# ")) {
        flushList(lineIdx);
        elements.push(
          <h2 key={lineIdx} className="text-2xl font-bold tracking-tight text-primary mt-9 mb-4 font-heading">
            {parseInlineMarkdown(trimmed.slice(2))}
          </h2>
        );
      } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        listItems.push(trimmed.slice(2));
      } else if (trimmed === "") {
        flushList(lineIdx);
      } else {
        flushList(lineIdx);
        elements.push(
          <p key={lineIdx} className="text-sm text-primary/85 leading-relaxed font-sans mb-2.5 last:mb-0">
            {parseInlineMarkdown(line)}
          </p>
        );
      }
    });

    flushList(lines.length);
    return <React.Fragment key={index}>{elements}</React.Fragment>;
  });
}

export default function KenbunChat() {
  const API_BASE = CONFIG.API_BASE;
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [activeModel, setActiveModel] = useState<string>("Detecting Brain...");
  const [workflow, setWorkflow] = useState<string>("chat");
  const [wfOpen, setWfOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showBrainHint, setShowBrainHint] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wfRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize composer textarea height based on typing lines
  useEffect(() => {
    const textarea = inputRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
    }
  }, [input]);

  // Folder Organization State
  interface Folder {
    id: string;
    name: string;
    sessionIds: string[];
    isExpanded?: boolean;
  }
  const [folders, setFolders] = useState<Folder[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("kenbun_chat_folders");
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch (err) {
          console.error(err);
        }
      }
    }
    return [];
  });

  // Text Preview Sanitization Helper
  const cleanPreview = (text: string) => {
    if (!text) return "";
    return text
      .replace(/[#*`_\-]/g, "")
      .replace(/\[SYSTEM OUT.*?\]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  };



  // Save folders to localStorage on update
  const saveFolders = (updatedFolders: Folder[]) => {
    setFolders(updatedFolders);
    localStorage.setItem("kenbun_chat_folders", JSON.stringify(updatedFolders));
  };

  interface ModalState {
    isOpen: boolean;
    type: "create_folder" | "rename_folder" | "rename_session";
    targetId: string | null;
    value: string;
  }
  const [modal, setModal] = useState<ModalState>({
    isOpen: false,
    type: "create_folder",
    targetId: null,
    value: ""
  });

  const handleModalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedVal = modal.value.trim();
    if (!trimmedVal) return;

    if (modal.type === "create_folder") {
      const newFolder: Folder = {
        id: "folder-" + Date.now(),
        name: trimmedVal,
        sessionIds: [],
        isExpanded: true,
      };
      saveFolders([...folders, newFolder]);
    } else if (modal.type === "rename_folder") {
      saveFolders(folders.map(f => f.id === modal.targetId ? { ...f, name: trimmedVal } : f));
    } else if (modal.type === "rename_session") {
      try {
        const res = await tenantFetch(`${API_BASE}/api/v1/chat/sessions/${modal.targetId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: trimmedVal })
        });
        if (res.ok) {
          setSessions(prev => prev.map(s => s.id === modal.targetId ? { ...s, title: trimmedVal } : s));
        }
      } catch (err) {
        console.error(err);
      }
    }

    setModal({ isOpen: false, type: "create_folder", targetId: null, value: "" });
  };

  const handleCreateFolder = () => {
    setModal({ isOpen: true, type: "create_folder", targetId: null, value: "" });
  };

  const handleDeleteFolder = (folderId: string) => {
    if (confirm("Are you sure you want to delete this folder? (Chats inside will not be deleted)")) {
      saveFolders(folders.filter(f => f.id !== folderId));
    }
  };

  const toggleFolderExpand = (folderId: string) => {
    saveFolders(folders.map(f => {
      if (f.id === folderId) {
        return { ...f, isExpanded: !f.isExpanded };
      }
      return f;
    }));
  };

  // Orchestrator workflows selectable from the composer. "chat" = normal conversation.
  const WORKFLOWS = [
    { id: "chat", label: "Chat", desc: "General assistant discussion", icon: MessageSquare },
    { id: "research_implement", label: "Research & Build", desc: "Scan codebase and build features", icon: Terminal },
    { id: "bug_fix", label: "Bug Fix", desc: "Identify root causes and fix errors", icon: ShieldAlert },
    { id: "code_review", label: "Code Review", desc: "Perform security audit and checks", icon: Code },
    { id: "shadow_test", label: "Shadow Test", desc: "Execute dry-runs in a sandbox", icon: Flame },
    { id: "design_ui", label: "Design UI", desc: "Create high-fidelity styling tokens", icon: Sparkles }
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isTyping && activeSessionId) {
        handleSend(e as unknown as React.FormEvent);
      }
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // 3. Create a New Session
  const handleCreateSession = useCallback(async () => {
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/chat/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ title: "New Transmissions" })
      });
      if (res.ok) {
        const newSession = await res.json();
        // Insert at the top of the list
        setSessions(prev => [
          {
            id: newSession.id,
            title: newSession.title,
            timestamp: newSession.timestamp,
            last_message: "No transmissions yet..."
          },
          ...prev
        ]);
        setActiveSessionId(newSession.id);
      }
    } catch (err) {
      console.error("Failed to instantiate chat session:", err);
    }
  }, [API_BASE]);

  // 1. Fetch Sessions List on Mount
  const fetchSessions = useCallback(async () => {
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/chat/sessions`);
      if (res.ok) {
        const data = await res.json();
        
        // Auto-prune sessions older than 30 days
        const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
        const active = [];
        
        for (const s of data) {
          const lastActiveDate = new Date(s.timestamp);
          if (lastActiveDate < thirtyDaysAgo) {
            console.log(`Auto-pruning stale session: ${s.id}`);
            tenantFetch(`${API_BASE}/api/v1/chat/sessions/${s.id}`, { method: "DELETE" }).catch(() => {});
          } else {
            active.push(s);
          }
        }

        setSessions(active);
        if (active.length > 0) {
          setActiveSessionId(active[0].id);
        } else {
          // If no sessions, automatically instantiate a new one
          handleCreateSession();
        }
      }
    } catch (err) {
      console.error("Failed to fetch chat sessions:", err);
    }
  }, [API_BASE, handleCreateSession]);

  // 2. Fetch Full History for the Active Session
  const loadSessionDetails = useCallback(async (id: string) => {
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/chat/sessions/${id}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages);
      }
    } catch (err) {
      console.error("Failed to load chat messages:", err);
    }
  }, [API_BASE]);

  const fetchActiveModel = useCallback(async () => {
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/active-model`);
      if (res.ok) {
        const data = await res.json();
        if (data.model) {
          setActiveModel(data.model);
        } else {
          setActiveModel("Ollama Llama3.2");
        }
      }
    } catch {
      setActiveModel("Offline Node");
    }
  }, [API_BASE]);

  useEffect(() => {
    setTimeout(() => {
      fetchSessions();
      fetchActiveModel();
    }, 0);
  }, [fetchSessions, fetchActiveModel]);

  useEffect(() => {
    if (activeSessionId) {
      setTimeout(() => {
        loadSessionDetails(activeSessionId);
      }, 0);
    }
  }, [activeSessionId, loadSessionDetails]);

  // Close the workflow dropdown on outside click
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (wfRef.current && !wfRef.current.contains(e.target as Node)) {
        setWfOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  // 4. Delete an Existing Session
  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); // Avoid switching to the session we are deleting
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/chat/sessions/${id}`, {
        method: "DELETE"
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== id));
        if (activeSessionId === id) {
          const remaining = sessions.filter(s => s.id !== id);
          if (remaining.length > 0) {
            setActiveSessionId(remaining[0].id);
          } else {
            setActiveSessionId(null);
            // If no chats left, create a fresh default one
            handleCreateSession();
          }
        }
      }
    } catch (err) {
      console.error("Failed to prune chat session:", err);
    }
  };

  // Update a single message's content by id (used by orchestration polling).
  const updateMessageContent = (id: string, content: string) => {
    setMessages(prev => prev.map(m => (m.id === id ? { ...m, content } : m)));
  };

  // Poll GET /orchestrate/status/{job_id} until the job completes or fails,
  // updating the placeholder message in place.
  const pollOrchestration = (jobId: string, wf: string, msgId: string) => {
    let attempts = 0;
    const maxAttempts = 200; // ~10 min at 3s intervals
    const tick = async () => {
      attempts++;
      try {
        const res = await tenantFetch(`${API_BASE}/orchestrate/status/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === "completed") {
            updateMessageContent(msgId, `✅ "${wf}" complete:\n\n${data.result || "(no output)"}`);
            return;
          }
          if (data.status === "failed") {
            updateMessageContent(msgId, `❌ "${wf}" failed: ${data.error || "unknown error"}`);
            return;
          }
        }
      } catch {
        // Transient network blip — keep polling.
      }
      if (attempts >= maxAttempts) {
        updateMessageContent(msgId, `⏱️ "${wf}" is still running (job ${jobId}). Stopped polling after ~10 min — check the Build Console activity log.`);
        return;
      }
      updateMessageContent(msgId, `🔮 "${wf}" running… (${attempts * 3}s elapsed)`);
      setTimeout(tick, 3000);
    };
    setTimeout(tick, 3000);
  };

  // 5. Send Message to Session
  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping || !activeSessionId) return;

    const userMessageContent = input.trim();
    setInput("");
    setIsTyping(true);

    // Optimistically append user message to the feed
    const tempUserMsg: ChatMessage = {
      id: "temp-" + Date.now(),
      sender: "user",
      content: userMessageContent,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMsg]);

    // Orchestrator launch path: when a workflow (not plain chat) is selected,
    // fire the background pipeline instead of a normal chat turn.
    if (workflow !== "chat") {
      const msgId = "orch-" + Date.now();
      try {
        const res = await tenantFetch(`${API_BASE}/orchestrate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workflow, task: userMessageContent })
        });
        const data = await res.json();
        const launched = res.ok && data.status === "initiated" && data.job_id;
        if (!launched) {
          setMessages(prev => [...prev, {
            id: msgId,
            sender: "kenbun",
            content: `⚠️ ${data.message || data.details || "Failed to launch workflow."}`,
            timestamp: new Date().toISOString()
          }]);
        } else {
          // Placeholder message that polling will update in place.
          setMessages(prev => [...prev, {
            id: msgId,
            sender: "kenbun",
            content: `🔮 Launched "${data.workflow}" workflow (job ${data.job_id}). Running…`,
            timestamp: new Date().toISOString()
          }]);
          pollOrchestration(data.job_id, data.workflow, msgId);
        }
      } catch {
        setMessages(prev => [...prev, {
          id: msgId,
          sender: "kenbun",
          content: "Error: connection lost. Unable to reach the orchestrator.",
          timestamp: new Date().toISOString()
        }]);
      } finally {
        setIsTyping(false);
      }
      return;
    }

    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/chat/sessions/${activeSessionId}/message`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: userMessageContent })
      });

      if (!res.ok) throw new Error("Kenbun linkage failed");
      
      const data = await res.json();
      
      // Update chat feed with canonical database history
      setMessages(data.session.messages);
      
      // Synchronize state and title change in the sidebar list
      setSessions(prev => prev.map(s => {
        if (s.id === activeSessionId) {
          return {
            ...s,
            title: data.session.title,
            last_message: userMessageContent.substring(0, 50) + (userMessageContent.length > 50 ? "..." : "")
          };
        }
        return s;
      }));
    } catch {
      setMessages(prev => [...prev, {
        id: "error-" + Date.now(),
        sender: "kenbun",
        content: "Error: connection lost. Unable to reach the orchestrator.",
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden font-sans">
      <Sidebar />

      {/* Backdrop overlay for mobile sidebar */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-primary/25 backdrop-blur-xs z-25 md:hidden"
        />
      )}

      {/* Session History Sidebar */}
      <aside className={`fixed md:static inset-y-0 left-0 w-64 lg:w-72 border-r border-primary/5 bg-card/95 md:bg-card/25 shrink-0 h-screen flex flex-col z-30 transition-transform duration-300 backdrop-blur-xl md:translate-x-0 ${
        sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
      }`}>
        <div className="grain-overlay opacity-5" />
        
        {/* Sidebar Header */}
        <div className="p-6 border-b border-primary/5 flex items-center justify-between shrink-0">
          <span className="text-[10px] font-black uppercase tracking-widest opacity-40 flex items-center gap-2">
            <MessageSquare className="w-3 h-3 text-tertiary" /> Transmission Logs
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCreateFolder}
              className="p-1.5 bg-neutral/60 hover:bg-neutral text-secondary hover:text-primary transition-all rounded-sm flex items-center justify-center border border-border/40"
              title="Create Folder"
            >
              <Folder className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleCreateSession}
              className="p-1.5 bg-tertiary/10 hover:bg-tertiary hover:text-white text-tertiary transition-all rounded-sm flex items-center justify-center artisan-shadow border border-tertiary/20"
              title="Create New Session"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Sessions & Folders List */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 custom-scrollbar">
          {/* Folders List */}
          <div className="flex flex-col gap-3">
            {folders.map((folder) => {
              const sessionsInFolder = sessions.filter(s => folder.sessionIds.includes(s.id));
              return (
                <div key={folder.id} className="flex flex-col gap-1.5">
                  {/* Folder Header */}
                  <div 
                    onClick={() => toggleFolderExpand(folder.id)}
                    className="flex items-center justify-between px-2 py-1 bg-primary/5 hover:bg-primary/10 rounded border border-primary/5 cursor-pointer group/folder transition-all"
                  >
                    <div className="flex items-center gap-2 truncate pr-2">
                      {folder.isExpanded ? (
                        <FolderOpen className="w-3.5 h-3.5 text-tertiary shrink-0" />
                      ) : (
                        <Folder className="w-3.5 h-3.5 text-secondary shrink-0" />
                      )}
                      <span className="text-xs font-bold truncate text-primary/80 group-hover/folder:text-primary">
                        {folder.name}
                      </span>
                      <span className="text-[9px] font-mono opacity-40">({sessionsInFolder.length})</span>
                    </div>
                    
                    <div className="opacity-0 group-hover/folder:opacity-100 flex items-center gap-1.5 transition-all">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setModal({ isOpen: true, type: "rename_folder", targetId: folder.id, value: folder.name });
                        }}
                        className="p-1 hover:bg-primary/10 text-primary/30 hover:text-primary rounded transition-all"
                        title="Rename Folder"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteFolder(folder.id);
                        }}
                        className="p-1 hover:bg-red-500/10 text-primary/30 hover:text-red-500 rounded transition-all"
                        title="Delete Folder"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  {/* Folder Contents */}
                  {folder.isExpanded && (
                    <div className="pl-3 flex flex-col gap-2 border-l border-primary/5 ml-3.5">
                      {sessionsInFolder.length === 0 ? (
                        <span className="text-[10px] text-primary/35 py-1 block italic pl-2">Empty Folder</span>
                      ) : (
                        sessionsInFolder.map((session) => (
                          <motion.div
                            key={session.id}
                            initial={{ opacity: 0, y: 5 }}
                            animate={{ opacity: 1, y: 0 }}
                            onClick={() => setActiveSessionId(session.id)}
                            className={`group p-2.5 rounded border cursor-pointer transition-all duration-300 relative overflow-hidden flex flex-col gap-1 ${
                              activeSessionId === session.id
                                ? "bg-tertiary/10 border-tertiary/25 shadow-[0_0_10px_rgba(var(--tertiary-rgb),0.02)]"
                                : "bg-card/25 border-primary/5 hover:bg-card/50 hover:border-primary/10"
                            }`}
                          >
                            <div className="flex items-center justify-between w-full gap-2">
                              <span className={`text-xs font-bold truncate pr-1 ${
                                activeSessionId === session.id ? "text-tertiary" : "text-primary/70 group-hover:text-primary"
                              }`}>
                                {session.title}
                              </span>

                              {/* Actions on Hover */}
                              <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1.5 transition-all duration-300 shrink-0">
                                <select
                                  value={folder.id}
                                  onClick={(e) => e.stopPropagation()}
                                  onChange={(e) => {
                                    const targetFolderId = e.target.value;
                                    const updated = folders.map(f => {
                                      const sessionIds = f.sessionIds.filter(id => id !== session.id);
                                      if (f.id === targetFolderId) {
                                        sessionIds.push(session.id);
                                      }
                                      return { ...f, sessionIds };
                                    });
                                    saveFolders(updated);
                                  }}
                                  className="text-[9px] bg-neutral/95 text-primary/60 border border-border/20 rounded px-1 py-0.5 cursor-pointer max-w-[80px] focus:outline-none"
                                >
                                  <option value="">Move out</option>
                                  {folders.map(f => (
                                    <option key={f.id} value={f.id}>{f.name}</option>
                                  ))}
                                </select>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setModal({ isOpen: true, type: "rename_session", targetId: session.id, value: session.title });
                                  }}
                                  className="p-1 hover:bg-primary/10 text-primary/30 hover:text-primary rounded transition-all"
                                  title="Rename Chat Log"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={(e) => handleDeleteSession(e, session.id)}
                                  className="p-1 hover:bg-red-500/10 text-primary/30 hover:text-red-500 rounded transition-all"
                                  title="Delete Chat Log"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                            <span className="text-[10px] text-primary/45 truncate block leading-none">
                              {cleanPreview(session.last_message)}
                            </span>
                          </motion.div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Uncategorized Chats List */}
          <div className="flex flex-col gap-2 border-t border-primary/5 pt-3">
            <span className="text-[9px] font-black uppercase tracking-widest text-primary/30 px-2 block mb-1">
              Uncategorized Chats
            </span>
            <AnimatePresence>
              {sessions
                .filter(s => !folders.some(f => f.sessionIds.includes(s.id)))
                .map((session) => (
                  <motion.div
                    key={session.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    onClick={() => setActiveSessionId(session.id)}
                    className={`group p-3 rounded-md border cursor-pointer transition-all duration-300 relative overflow-hidden flex flex-col gap-1 ${
                      activeSessionId === session.id
                        ? "bg-tertiary/10 border-tertiary/25 shadow-[0_0_15px_rgba(var(--tertiary-rgb),0.02)]"
                        : "bg-card/35 border-primary/5 hover:bg-card/60 hover:border-primary/10"
                    }`}
                  >
                    <div className="flex items-center justify-between w-full gap-2">
                      <span className={`text-xs font-bold truncate pr-1 ${
                        activeSessionId === session.id ? "text-tertiary" : "text-primary/70 group-hover:text-primary"
                      }`}>
                        {session.title}
                      </span>
                      
                      {/* Actions on Hover */}
                      <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1.5 transition-all duration-300 shrink-0">
                        <select
                          value=""
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => {
                            const targetFolderId = e.target.value;
                            if (targetFolderId) {
                              const updated = folders.map(f => {
                                const sessionIds = f.sessionIds.filter(id => id !== session.id);
                                if (f.id === targetFolderId) {
                                  sessionIds.push(session.id);
                                }
                                return { ...f, sessionIds };
                              });
                              saveFolders(updated);
                            }
                          }}
                          className="text-[9px] bg-neutral/95 text-primary/60 border border-border/20 rounded px-1 py-0.5 cursor-pointer max-w-[80px] focus:outline-none"
                        >
                          <option value="">Move to...</option>
                          {folders.map(f => (
                            <option key={f.id} value={f.id}>{f.name}</option>
                          ))}
                        </select>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setModal({ isOpen: true, type: "rename_session", targetId: session.id, value: session.title });
                          }}
                          className="p-1 hover:bg-primary/10 text-primary/30 hover:text-primary rounded transition-all"
                          title="Rename Chat Log"
                        >
                          <Edit2 className="w-3 h-3" />
                        </button>
                        <button
                          onClick={(e) => handleDeleteSession(e, session.id)}
                          className="p-1 hover:bg-red-500/10 text-primary/30 hover:text-red-500 rounded transition-all"
                          title="Delete Chat Log"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <span className="text-[10px] text-primary/45 truncate block leading-none">
                      {cleanPreview(session.last_message)}
                    </span>
                  </motion.div>
                ))}
            </AnimatePresence>
          </div>
        </div>
      </aside>

      {/* Main Chat Frame */}
      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 h-screen min-w-0 overflow-hidden">
        <div className="grain-overlay opacity-20" />

        {/* Header */}
        <header className="h-14 lg:h-16 border-b border-primary/5 flex items-center justify-between px-6 bg-card/40 z-20 shrink-0 backdrop-blur-xl">
          <div className="flex items-center gap-4 lg:gap-8">
            <button
              onClick={() => setSidebarOpen(o => !o)}
              className="md:hidden p-2 text-secondary hover:text-primary transition-colors hover:bg-primary/5 rounded-sm cursor-pointer shrink-0"
              title="Toggle Logs"
              aria-label="Toggle Transmission Logs"
            >
              <Menu className="w-5 h-5" />
            </button>
            <span className="font-bold text-lg lg:text-xl uppercase tracking-tighter italic flex items-center gap-3">
              Kenbun <span className="text-tertiary">Chat</span>
            </span>
          </div>

          {(() => {
            const isOffline = activeModel === "Offline Node" || activeModel === "Detecting Brain...";
            return (
              <div 
                onClick={() => setShowBrainHint(o => !o)}
                className="relative flex items-center gap-3 bg-primary/5 px-4 py-2 border border-primary/5 rounded-sm cursor-pointer hover:bg-primary/10 transition-colors shrink-0"
              >
                <div className={`w-2 h-2 rounded-full ${isOffline ? "bg-[#B8422E] animate-pulse" : "bg-emerald-500 animate-pulse"}`} />
                <span className="text-[10px] font-black uppercase tracking-widest text-primary/70 select-none">
                  Brain: {activeModel}
                </span>
                <AnimatePresence>
                  {showBrainHint && (
                    <motion.div
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 5 }}
                      className="absolute right-0 top-full mt-2 w-64 bg-card/95 backdrop-blur-md border border-border/80 p-3 rounded-md shadow-xl text-left z-30"
                    >
                      <span className="font-mono text-[9px] text-tertiary uppercase tracking-wider block mb-1">System Node Status</span>
                      <p className="text-[10px] text-primary/80 leading-relaxed normal-case tracking-normal">
                        {isOffline 
                          ? "🔴 Connection is currently offline or unreachable. Check container logs or local Ollama endpoint status."
                          : "🟢 Connection is active. System is fully operational, processing directives using neural pipeline configurations."}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })()}
        </header>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-10 custom-scrollbar relative z-10 flex flex-col gap-6">
          <AnimatePresence initial={false}>
            {messages.map((msg) => {
              if (msg.sender === "user") {
                return (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex w-full justify-end"
                  >
                    <div 
                      onDoubleClick={() => {
                        setInput(msg.content);
                        inputRef.current?.focus();
                      }}
                      className="bg-neutral/45 border border-border/25 hover:bg-neutral/60 hover:border-primary/20 transition-all duration-200 rounded-2xl px-4 py-2.5 max-w-[85%] lg:max-w-[70%] artisan-shadow cursor-pointer select-text"
                      title="Double click to edit/re-send"
                    >
                      <p className="text-sm font-sans text-primary/95 leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </p>
                    </div>
                  </motion.div>
                );
              }

              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex w-full justify-start"
                >
                  <div className="max-w-[90%] lg:max-w-[80%] flex flex-col gap-2">
                    {/* Assistant Header */}
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded-md shrink-0 flex items-center justify-center border bg-tertiary/10 border-tertiary/30 text-tertiary">
                        <Cpu className="w-2.5 h-2.5 opacity-80" />
                      </div>
                      <span className="text-[10px] font-black uppercase tracking-widest text-tertiary/80">
                        Kenbun
                      </span>
                      <span className="text-[9px] font-medium text-primary/30" suppressHydrationWarning>
                        {new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                      </span>
                    </div>

                    {/* Assistant Content */}
                    <div className="pl-7 select-text">
                      {parseMarkdown(msg.content)}

                      {/* Action Bar */}
                      <div className="flex items-center gap-3.5 mt-3 text-primary/30">
                        <button 
                          onClick={() => navigator.clipboard.writeText(msg.content)}
                          className="p-1 hover:text-primary transition-colors cursor-pointer" 
                          title="Copy Response"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 002 2h2a2 2 0 002-2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                          </svg>
                        </button>
                        <button 
                          onClick={() => {
                            const userMsgs = messages.filter(m => m.sender === "user");
                            if (userMsgs.length > 0) {
                              setInput(userMsgs[userMsgs.length - 1].content);
                              inputRef.current?.focus();
                            }
                          }}
                          className="p-1 hover:text-primary transition-colors cursor-pointer" 
                          title="Regenerate"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 6H16" />
                          </svg>
                        </button>
                        <button className="p-1 hover:text-primary transition-colors cursor-pointer" title="Share">
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M8.684 10.742l4.684-2.342m0 0l4.684 2.342m-9.368 0L8.684 13.06m4.684 2.342l4.684-2.342" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>

          {isTyping && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex w-full justify-start"
            >
              <div className="flex flex-col gap-2 max-w-[70%]">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-md shrink-0 flex items-center justify-center border bg-tertiary/10 border-tertiary/30 text-tertiary">
                    <Cpu className="w-2.5 h-2.5 opacity-80 animate-spin" style={{ animationDuration: "3s" }} />
                  </div>
                  <span className="text-[10px] font-black uppercase tracking-widest text-tertiary/60">
                    Kenbun is thinking
                  </span>
                </div>
                <div className="pl-7 pt-1">
                  <div className="p-3 py-2 rounded-lg border bg-card/65 border-tertiary/10 flex items-center gap-2 w-max">
                    <div className="w-1.5 h-1.5 bg-tertiary/60 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="w-1.5 h-1.5 bg-tertiary/60 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="w-1.5 h-1.5 bg-tertiary/60 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 pb-24 lg:pb-6 lg:p-6 bg-background/80 backdrop-blur-xl shrink-0 z-20">
          <div className="max-w-4xl mx-auto">
            <form
              onSubmit={handleSend}
              className="bg-card/45 backdrop-blur-xl border border-border/40 focus-within:border-tertiary/30 focus-within:shadow-[0_0_30px_rgba(var(--tertiary-rgb),0.03)] rounded-2xl p-3.5 flex flex-col gap-3 relative artisan-shadow transition-all duration-300"
            >
              {/* Chat Input Field */}
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={workflow === "chat" ? "Ask Kenbun anything..." : "Describe the task to orchestrate..."}
                className="w-full bg-transparent border-0 font-sans text-xs sm:text-sm focus:outline-none text-primary placeholder-primary/30 px-1 py-1 focus:ring-0 resize-none max-h-40 overflow-y-auto custom-scrollbar"
                disabled={isTyping || !activeSessionId}
                style={{ height: "auto" }}
              />

              {/* Bottom Row controls */}
              <div className="flex items-center justify-between border-t border-primary/5 pt-2">
                {/* Left group of pills */}
                <div className="flex items-center gap-2">
                  {/* Workflow / Mode Dropdown Selector */}
                  <div ref={wfRef} className="relative shrink-0">
                    <button
                      type="button"
                      onClick={() => setWfOpen((o) => !o)}
                      disabled={isTyping || !activeSessionId}
                      title="Choose Chat or an orchestrator workflow"
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/5 hover:bg-primary/10 border border-primary/5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider text-secondary hover:text-primary transition-all disabled:opacity-30 cursor-pointer"
                    >
                      {(() => {
                        const wf = WORKFLOWS.find((w) => w.id === workflow) || WORKFLOWS[0];
                        const Icon = wf.icon;
                        return (
                          <>
                            <Icon className="w-3.5 h-3.5 text-tertiary shrink-0" />
                            <span className="truncate max-w-[120px] font-bold">
                              {wf.label}
                            </span>
                          </>
                        );
                      })()}
                      <ChevronDown className={`w-3 h-3 text-tertiary transition-transform duration-300 ${wfOpen ? "rotate-180" : ""}`} />
                    </button>
 
                    <AnimatePresence>
                      {wfOpen && (
                        <motion.div
                          initial={{ opacity: 0, y: 8, scale: 0.98 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 8, scale: 0.98 }}
                          transition={{ duration: 0.15 }}
                          className="absolute bottom-full left-0 mb-3 w-80 overflow-hidden rounded-2xl border border-border/40 bg-card/98 backdrop-blur-xl shadow-[0_15px_40px_rgba(26,28,30,0.12)] z-30"
                        >
                          <div className="px-4 py-3 border-b border-primary/5">
                            <span className="text-[9px] font-black uppercase tracking-[0.2em] text-primary/30">
                              Select Directive
                            </span>
                          </div>
                          <div className="flex flex-col p-1.5 gap-0.5">
                            {WORKFLOWS.map((w) => {
                              const active = w.id === workflow;
                              const Icon = w.icon;
                              return (
                                <button
                                  key={w.id}
                                  type="button"
                                  onClick={() => { setWorkflow(w.id); setWfOpen(false); }}
                                  className={`flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl text-left transition-all group/item ${
                                    active
                                      ? "bg-tertiary/10 text-tertiary"
                                      : "text-primary/70 hover:bg-primary/5 hover:text-primary hover:translate-x-0.5"
                                  }`}
                                >
                                  <div className="flex items-center gap-3 truncate">
                                    <div className={`p-1.5 rounded-lg border shrink-0 transition-colors ${
                                      active 
                                        ? "bg-tertiary/20 border-tertiary/30 text-tertiary" 
                                        : "bg-primary/5 border-primary/5 text-primary/45 group-hover/item:border-primary/10 group-hover/item:text-primary"
                                    }`}>
                                      <Icon className="w-3.5 h-3.5" />
                                    </div>
                                    <div className="flex flex-col min-w-0">
                                      <span className="text-xs font-bold truncate leading-snug">{w.label}</span>
                                      <span className="text-[9px] opacity-50 truncate leading-none mt-0.5">{w.desc}</span>
                                    </div>
                                  </div>
                                  {active && <Check className="w-3.5 h-3.5 shrink-0 text-tertiary" />}
                                </button>
                              );
                            })}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Context Pill (replaces standard separator, indicates active local context) */}
                  <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-primary/5 border border-primary/5 rounded-full text-[10px] font-bold uppercase tracking-wider text-primary/40">
                    <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
                    System Context Active
                  </div>
                </div>

                {/* Send Button */}
                <button
                  type="submit"
                  disabled={!input.trim() || isTyping || !activeSessionId}
                  className="p-2 bg-tertiary text-neutral hover:bg-tertiary/90 transition-all rounded-full disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-tertiary cursor-pointer shrink-0"
                >
                  <Send className="w-4 h-4 text-white" />
                </button>
              </div>
            </form>

            <div className="text-center mt-2.5 flex items-center justify-center gap-1.5">
              <CheckCircle className="w-3 h-3 text-tertiary/40" />
              <span className="text-[9px] font-black uppercase tracking-widest text-primary/30">
                End-to-end Encryption Active
              </span>
            </div>
          </div>
        </div>
      </main>

      {/* Custom Form / Modal Popover (Luxury UI/UX) */}
      <AnimatePresence>
        {modal.isOpen && (
          <div className="fixed inset-0 bg-primary/45 backdrop-blur-md z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.2 }}
              className="bg-card/95 backdrop-blur-xl border border-border/40 rounded-2xl p-6 w-96 shadow-[0_20px_50px_rgba(26,28,30,0.25)] flex flex-col gap-4 relative animate-in fade-in zoom-in-95"
            >
              {/* Header */}
              <div className="flex flex-col gap-1">
                <span className="text-[9px] font-black uppercase tracking-[0.25em] text-tertiary">
                  Transmission Config
                </span>
                <h3 className="text-base font-extrabold text-primary/90 font-sans tracking-tight">
                  {modal.type === "create_folder" && "Create Folder"}
                  {modal.type === "rename_folder" && "Rename Folder"}
                  {modal.type === "rename_session" && "Rename Session"}
                </h3>
              </div>

              {/* Form Input */}
              <form onSubmit={handleModalSubmit} className="flex flex-col gap-4">
                <input
                  type="text"
                  required
                  autoFocus
                  value={modal.value}
                  onChange={(e) => setModal({ ...modal, value: e.target.value })}
                  placeholder={
                    modal.type === "create_folder" || modal.type === "rename_folder"
                      ? "Enter folder name..."
                      : "Enter session title..."
                  }
                  className="w-full bg-primary/5 border border-primary/5 focus:border-tertiary/30 focus:ring-0 rounded-xl px-4 py-2.5 text-xs text-primary focus:outline-none transition-all duration-300"
                />

                {/* Footer Buttons */}
                <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-primary/5">
                  <button
                    type="button"
                    onClick={() => setModal({ isOpen: false, type: "create_folder", targetId: null, value: "" })}
                    className="px-4 py-2 bg-primary/5 hover:bg-primary/10 text-primary/70 rounded-xl text-xs font-bold transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-tertiary text-white hover:bg-tertiary/90 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-[0_2px_10px_rgba(var(--tertiary-rgb),0.1)]"
                  >
                    Confirm
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
