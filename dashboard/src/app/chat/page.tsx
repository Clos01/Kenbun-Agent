"use client";

import React, { useState, useEffect, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import { Send, Terminal, Cpu, CheckCircle, Plus, Trash2, MessageSquare } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";

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

export default function KenbunChat() {
  const API_BASE = CONFIG.API_BASE;
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [activeModel, setActiveModel] = useState<string>("Detecting Brain...");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // 1. Fetch Sessions List on Mount
  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
        if (data.length > 0) {
          setActiveSessionId(data[0].id);
        } else {
          // If no sessions, automatically instantiate a new one
          handleCreateSession();
        }
      }
    } catch (err) {
      console.error("Failed to fetch chat sessions:", err);
    }
  };

  // 2. Fetch Full History for the Active Session
  const loadSessionDetails = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/sessions/${id}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages);
      }
    } catch (err) {
      console.error("Failed to load chat messages:", err);
    }
  };

  const fetchActiveModel = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/active-model`);
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
  };

  useEffect(() => {
    fetchSessions();
    fetchActiveModel();
  }, []);

  useEffect(() => {
    if (activeSessionId) {
      loadSessionDetails(activeSessionId);
    }
  }, [activeSessionId]);

  // 3. Create a New Session
  const handleCreateSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/sessions`, {
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
  };

  // 4. Delete an Existing Session
  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation(); // Avoid switching to the session we are deleting
    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/sessions/${id}`, {
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

    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/sessions/${activeSessionId}/message`, {
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
    } catch (error) {
      setMessages(prev => [...prev, {
        id: "error-" + Date.now(),
        sender: "kenbun",
        content: "Error: Neural link disconnected. Unable to reach the orchestrator.",
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden font-sans">
      <Sidebar />

      {/* Session History Sidebar */}
      <aside className="w-64 lg:w-72 border-r border-primary/5 bg-card/25 shrink-0 h-screen flex flex-col z-20 relative backdrop-blur-xl">
        <div className="grain-overlay opacity-5" />
        
        {/* Sidebar Header */}
        <div className="p-6 border-b border-primary/5 flex items-center justify-between shrink-0">
          <span className="text-[10px] font-black uppercase tracking-widest opacity-40 flex items-center gap-2">
            <MessageSquare className="w-3 h-3 text-tertiary" /> Transmission Logs
          </span>
          <button
            onClick={handleCreateSession}
            className="p-1.5 bg-tertiary/10 hover:bg-tertiary hover:text-white text-tertiary transition-all rounded-sm flex items-center justify-center artisan-shadow border border-tertiary/20"
            title="Create New Session"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2 custom-scrollbar">
          <AnimatePresence>
            {sessions.map((session) => (
              <motion.div
                key={session.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                onClick={() => setActiveSessionId(session.id)}
                className={`group p-4 rounded-sm border cursor-pointer transition-all duration-300 relative overflow-hidden flex flex-col gap-1.5 ${
                  activeSessionId === session.id
                    ? "bg-tertiary/10 border-tertiary/30 shadow-[0_0_15px_rgba(var(--tertiary-rgb),0.02)]"
                    : "bg-card/40 border-primary/5 hover:bg-card hover:border-primary/10"
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className={`text-xs font-bold truncate pr-3 ${
                    activeSessionId === session.id ? "text-tertiary" : "text-primary/70 group-hover:text-primary"
                  }`}>
                    {session.title}
                  </span>
                  
                  {/* Delete Button */}
                  <button
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/10 text-primary/30 hover:text-red-500 rounded-sm transition-all duration-300"
                    title="Delete Chat Log"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                <span className="text-[10px] text-primary/40 truncate block leading-none">
                  {session.last_message}
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </aside>

      {/* Main Chat Frame */}
      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 h-screen min-w-0 overflow-hidden">
        <div className="grain-overlay opacity-20" />

        {/* Header */}
        <header className="h-20 lg:h-24 border-b border-primary/5 flex items-center justify-between px-6 lg:px-10 bg-card/40 z-20 shrink-0 backdrop-blur-xl">
          <div className="flex items-center gap-4 lg:gap-8">
            <span className="text-[10px] font-black uppercase tracking-widest opacity-30">System.01</span>
            <div className="h-6 w-[1px] bg-primary/10" />
            <span className="font-bold text-lg lg:text-xl uppercase tracking-tighter italic flex items-center gap-3">
              Kenbun <span className="text-tertiary">Interface</span>
            </span>
          </div>

          <div className="flex items-center gap-3 bg-primary/5 px-4 py-2 border border-primary/5 rounded-sm">
            <div className="w-2 h-2 rounded-full bg-tertiary animate-pulse" />
            <span className="text-[10px] font-black uppercase tracking-widest text-primary/70">
              Brain: {activeModel}
            </span>
          </div>
        </header>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-10 custom-scrollbar relative z-10 flex flex-col gap-6">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex w-full ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                <div className={`max-w-[85%] lg:max-w-[70%] flex gap-4 ${msg.sender === "user" ? "flex-row-reverse" : "flex-row"}`}>
                  
                  {/* Avatar */}
                  <div className={`w-10 h-10 rounded-sm shrink-0 flex items-center justify-center border ${
                    msg.sender === "user" 
                      ? "bg-primary/10 border-primary/20 text-primary" 
                      : "bg-tertiary/10 border-tertiary/30 text-tertiary"
                  }`}>
                    {msg.sender === "user" ? <Terminal className="w-5 h-5 opacity-60" /> : <Cpu className="w-5 h-5 opacity-80" />}
                  </div>

                  {/* Message Bubble */}
                  <div className={`p-5 rounded-sm border backdrop-blur-md artisan-shadow ${
                    msg.sender === "user" 
                      ? "bg-primary/5 border-primary/10" 
                      : "bg-card/80 border-tertiary/20 shadow-[0_0_30px_rgba(var(--tertiary-rgb),0.02)]"
                  }`}>
                    <div className={`text-[9px] font-black uppercase tracking-widest mb-2 flex items-center gap-2 ${
                      msg.sender === "user" ? "text-primary/40 justify-end" : "text-tertiary/60"
                    }`}>
                      {msg.sender === "user" ? "You" : "Kenbun"}
                      <span className="opacity-40" suppressHydrationWarning>
                        {new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                      </span>
                    </div>
                    <p className="text-sm font-sans text-primary/90 leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex w-full justify-start"
            >
              <div className="flex gap-4 flex-row max-w-[70%]">
                <div className="w-10 h-10 rounded-sm shrink-0 flex items-center justify-center border bg-tertiary/10 border-tertiary/30 text-tertiary">
                  <Cpu className="w-5 h-5 opacity-80" />
                </div>
                <div className="p-5 rounded-sm border bg-card/80 border-tertiary/20 flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-tertiary/60 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-1.5 h-1.5 bg-tertiary/60 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-1.5 h-1.5 bg-tertiary/60 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-6 lg:p-10 border-t border-primary/5 bg-background/80 backdrop-blur-xl shrink-0 z-20">
          <form onSubmit={handleSend} className="relative max-w-5xl mx-auto">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Transmit directive to Kenbun..."
              className="w-full pl-6 pr-16 py-5 border border-primary/10 rounded-sm bg-card/60 font-sans text-sm focus:outline-none focus:border-tertiary focus:bg-card hover:border-primary/20 transition-all text-primary placeholder-primary/30 shadow-inner"
              disabled={isTyping || !activeSessionId}
            />
            <button
              type="submit"
              disabled={!input.trim() || isTyping || !activeSessionId}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2.5 bg-tertiary/10 hover:bg-tertiary hover:text-white text-tertiary transition-all rounded-sm disabled:opacity-30 disabled:hover:bg-tertiary/10 disabled:hover:text-tertiary"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
          <div className="text-center mt-3 flex items-center justify-center gap-2">
            <CheckCircle className="w-3 h-3 text-tertiary/40" />
            <span className="text-[9px] font-black uppercase tracking-widest text-primary/30">
              End-to-end Neural Encryption Active
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}
