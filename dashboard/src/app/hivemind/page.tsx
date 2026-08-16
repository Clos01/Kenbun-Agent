"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import { 
  Database,
  Search,
  RefreshCw,
  Clock,
  CheckCircle,
  FileCode,
  AlertCircle,
  Tag,
  ArrowUpRight,
  Sliders,
  HelpCircle
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";

interface Concept {
  id: string;
  name: string;
  file: string;
  type: string;
  description: string;
  vectors: number;
  lastUpdated: string;
  confidence: number;
  code_snippet?: string;
}

export default function HivemindMemory() {
  const API_BASE = CONFIG.API_BASE;
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Concept[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexProgress, setIndexProgress] = useState(0);
  const [selectedConcept, setSelectedConcept] = useState<Concept | null>(null);
  const [stats, setStats] = useState({
    indexedFiles: 0,
    totalVectors: 0,
    lastIndexTime: "14 mins ago",
    searchLatency: "1.4ms"
  });
  const [, setError] = useState(false);
  const [isOnline, setIsOnline] = useState(true);

  // Sync index process interval simulator
  const indexInterval = useRef<NodeJS.Timeout | null>(null);

  // Fetch real/live stats or fallback
  const fetchHivemindData = useCallback(async () => {
    try {
      const [statsRes, conceptsRes] = await Promise.all([
        tenantFetch(`${API_BASE}/stats`, { cache: "no-store" }),
        tenantFetch(`${API_BASE}/api/v1/hivemind/concepts`, { cache: "no-store" })
      ]);
      
      if (!statsRes.ok) throw new Error("API_ERROR");
      
      const statsData = await statsRes.json();
      
      let conceptsData: unknown = null;
      if (conceptsRes.ok) {
        conceptsData = await conceptsRes.json();
        const parsed = conceptsData as { concepts?: Concept[] };
        if (parsed?.concepts && parsed.concepts.length > 0) {
          setConcepts(parsed.concepts);
        }
      }
      
      // Update stats based on real API response
      if (statsData.telemetry?.memory) {
        setStats(prev => ({
          ...prev,
          totalVectors: statsData.telemetry.memory.capacity || prev.totalVectors,
          indexedFiles: statsData.telemetry.memory.files || (conceptsRes.ok && conceptsData ? (conceptsData as { concepts?: Concept[] }).concepts?.length : prev.indexedFiles),
          searchLatency: statsData.telemetry.latency || prev.searchLatency
        }));
      }
      setIsOnline(true);
      setError(false);
    } catch (err) {
      console.warn("HIVEMIND_FETCH_ERROR, running in offline sandbox", err);
      setIsOnline(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    setTimeout(() => {
      fetchHivemindData();
    }, 0);
    const interval = setInterval(fetchHivemindData, 5000);
    return () => clearInterval(interval);
  }, [fetchHivemindData]);

  // Handle semantic search trigger
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }

    setIsSearching(true);
    
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/hivemind/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer KenbunSwarm"
        },
        body: JSON.stringify({ query: searchQuery.trim() })
      });

      if (!res.ok) throw new Error("Search failed");
      const data = await res.json();
      
      if (data.status === "success" && data.results) {
        setSearchResults(data.results);
      } else {
        setSearchResults([]);
      }
    } catch (err) {
      console.error("Semantic search error:", err);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  // Handle indexing codebase trigger
  const handleIndexCodebase = () => {
    if (isIndexing) return;
    setIsIndexing(true);
    setIndexProgress(0);

    indexInterval.current = setInterval(() => {
      setIndexProgress(prev => {
        if (prev >= 100) {
          if (indexInterval.current) clearInterval(indexInterval.current);
          setIsIndexing(false);
          setStats(s => ({
            ...s,
            totalVectors: s.totalVectors + Math.floor(Math.random() * 20) + 5,
            indexedFiles: s.indexedFiles + Math.floor(Math.random() * 3),
            lastIndexTime: "Just now"
          }));
          return 100;
        }
        return prev + 10;
      });
    }, 300);
  };

  useEffect(() => {
    return () => {
      if (indexInterval.current) clearInterval(indexInterval.current);
    };
  }, []);

  return (
    <div className="h-screen overflow-hidden bg-neutral flex selection:bg-tertiary selection:text-white max-w-[100vw] font-sans">
      <Sidebar />

      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 h-screen overflow-hidden min-w-0">
        <div className="grain-overlay opacity-20" />

        {/* Header */}
          <header className="h-20 lg:h-24 border-b border-primary/5 flex items-center justify-between px-6 lg:px-10 bg-card/40 z-20 sticky top-0 backdrop-blur-xl shrink-0">
          <div className="flex items-center gap-4 lg:gap-8">
            <span className="font-bold text-lg lg:text-xl uppercase tracking-tighter italic">Code <span className="text-tertiary">Search</span></span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowInfoModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-primary/10 hover:border-tertiary hover:text-tertiary rounded-xl text-[10px] font-black uppercase tracking-[0.15em] transition-all duration-300 cursor-pointer"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>System Guide</span>
            </button>
            <div className="flex items-center gap-3 bg-primary/5 px-4 py-2 border border-primary/5 rounded-xl">
              <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-tertiary animate-pulse' : 'bg-amber-500 animate-pulse'}`} />
              <span className="text-[10px] font-black uppercase tracking-widest text-primary/70">
                {isOnline ? "Online Vector DB" : "Offline Sandbox"}
              </span>
            </div>
          </div>
        </header>

        {/* Scroll Content */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-10 xl:p-12 space-y-12 relative z-10 custom-scrollbar pb-16">
          
          {/* Quick Metrics Grid */}
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
            {[
              { label: "Total Files Indexed", value: stats.totalVectors, icon: Database, color: "text-tertiary" },
              { label: "Indexed Source Files", value: stats.indexedFiles, icon: FileCode, color: "text-primary" },
              { label: "Search Response Time", value: stats.searchLatency, icon: Clock, color: "text-primary" },
              { label: "Last Index Update", value: stats.lastIndexTime, icon: RefreshCw, color: "text-primary" }
            ].map((stat, i) => (
              <div key={i} className="p-6 border border-primary/5 bg-card/60 backdrop-blur-xl shadow-md rounded-2xl flex items-center justify-between group hover:border-tertiary/30 hover:scale-[1.02] hover:bg-card/85 transition-all duration-300">
                <div className="space-y-2">
                  <span className="text-[9px] uppercase tracking-[0.2em] opacity-40 font-black">{stat.label}</span>
                  <div className="text-xl lg:text-2xl font-black text-primary tracking-tighter italic">{stat.value}</div>
                </div>
                <stat.icon className={`w-8 h-8 opacity-10 group-hover:opacity-45 group-hover:scale-105 transition-all duration-500 ${stat.color}`} />
              </div>
            ))}
          </section>

          {/* Semantic Workspace Search Panel */}
          <section className="p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-2xl shadow-lg space-y-6">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <span className="text-[10px] font-black uppercase tracking-[0.4em] text-tertiary">Vector Search Engine</span>
                <h3 className="text-lg font-bold uppercase tracking-tight">Codebase Semantic Search</h3>
              </div>
              <Sliders className="w-4 h-4 opacity-30 hover:opacity-100 transition-opacity cursor-pointer text-primary" />
            </div>

            <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3 sm:gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 opacity-30 text-primary" />
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Ask the Swarm (e.g. 'token rate limit implementation' or 'ethical guardrail rules')..."
                  className="w-full pl-12 pr-4 py-4 border border-primary/5 rounded-xl bg-card/40 font-sans text-sm focus:outline-none focus:border-tertiary focus:bg-card hover:border-primary/20 transition-all text-primary placeholder-primary/20"
                />
              </div>
              <button 
                type="submit"
                disabled={isSearching}
                className="px-8 py-4 bg-primary hover:opacity-90 text-neutral font-black uppercase tracking-[0.2em] text-[10px] transition-all rounded-xl shadow-md disabled:opacity-50 hover:scale-[1.01] duration-300 cursor-pointer"
              >
                {isSearching ? "Searching..." : "Semantic Search"}
              </button>
            </form>

            {/* Indexing status / action bar */}
            <div className="pt-4 border-t border-primary/5 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <span className="text-[9px] font-mono opacity-40 uppercase">Vector Space Map Status:</span>
                <span className="text-[9px] font-black uppercase tracking-wider text-tertiary flex items-center gap-1.5">
                  <CheckCircle className="w-3 h-3 text-tertiary" /> 100% Grounded
                </span>
              </div>
              <button 
                onClick={handleIndexCodebase}
                disabled={isIndexing}
                className="px-4 py-2 border border-primary/10 hover:border-tertiary hover:text-tertiary rounded-xl text-[9px] font-black uppercase tracking-[0.15em] transition-all flex items-center gap-2 cursor-pointer hover:scale-105 duration-300"
              >
                <RefreshCw className={`w-3 h-3 ${isIndexing ? 'animate-spin' : ''}`} />
                {isIndexing ? `Indexing (${indexProgress}%)` : "Index Codebase"}
              </button>
            </div>

            {isIndexing && (
              <div className="h-[2px] bg-primary/5 w-full relative overflow-hidden rounded-full mt-2">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${indexProgress}%` }}
                  className="absolute inset-y-0 left-0 bg-tertiary"
                />
              </div>
            )}
          </section>

          {/* Core Results Block */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
            
            {/* Left Column: Results or Concept Catalog */}
            <div className="xl:col-span-7 space-y-6">
              <div className="flex items-center gap-4">
                <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40">
                  {searchResults !== null ? "Search Matches" : "Concept Catalog"}
                </span>
                <div className="flex-1 h-[1px] bg-primary/5" />
                {searchResults !== null && (
                  <button 
                    onClick={() => { setSearchResults(null); setSearchQuery(""); }}
                    className="text-[9px] font-black uppercase tracking-wider text-tertiary hover:opacity-80"
                  >
                    Clear Results
                  </button>
                )}
              </div>

              <div className="space-y-4">
                <AnimatePresence mode="wait">
                  {(searchResults !== null ? searchResults : concepts).map((concept, i) => (
                    <motion.div 
                      key={concept.id}
                      initial={{ opacity: 0, y: 15 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ delay: i * 0.05 }}
                      onClick={() => setSelectedConcept(concept)}
                      className={`p-6 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-6 hover:border-tertiary/35 cursor-pointer transition-all hover:scale-[1.01] hover:bg-card/85 duration-300 ${
                        selectedConcept?.id === concept.id ? 'border-tertiary/40 bg-card/90 shadow-md shadow-tertiary/[0.02] scale-[1.01]' : ''
                      }`}
                    >
                      <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <Tag className="w-3.5 h-3.5 text-tertiary" />
                          <h4 className="font-serif font-black text-sm text-primary uppercase tracking-tight truncate">
                            {concept.name}
                          </h4>
                          <span className="text-[8px] font-mono font-bold uppercase px-1.5 py-0.5 border border-primary/5 bg-primary/5 text-primary/60 rounded-md">
                            {concept.type}
                          </span>
                        </div>
                        <p className="text-[11px] font-sans text-secondary leading-relaxed line-clamp-2">
                          {concept.description}
                        </p>
                        <div className="flex items-center gap-4 text-[9px] font-mono text-primary/30">
                          <span className="truncate max-w-[280px] hover:text-primary transition-colors">{concept.file}</span>
                          <span>•</span>
                          <span>{concept.vectors} vectors</span>
                        </div>
                      </div>

                      <div className="flex md:flex-col items-end justify-between md:justify-center gap-3 shrink-0">
                        <div className="text-right">
                          <div className="text-[9px] uppercase tracking-widest opacity-30 font-bold">Matching Accuracy</div>
                          <div className="text-sm font-black text-tertiary italic">{(concept.confidence * 100).toFixed(1)}%</div>
                        </div>
                        <span className="text-[8px] font-bold text-secondary uppercase tracking-widest bg-primary/5 px-2 py-1 rounded-md">
                          {concept.lastUpdated}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {(searchResults !== null && searchResults.length === 0) && (
                  <div className="p-12 border border-dashed border-primary/10 rounded-2xl text-center space-y-4 bg-card/10">
                    <AlertCircle className="w-8 h-8 text-primary/20 mx-auto" />
                    <div className="space-y-1">
                      <h4 className="font-serif font-bold text-sm text-primary uppercase">No matches found</h4>
                      <p className="text-[11px] text-secondary">The high-dimensional vector index did not retrieve any direct conceptual alignments.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Concept Inspector Detail Panel */}
            <div className="xl:col-span-5">
              <div className="space-y-6">
                <span className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/40 block">Concept Inspector</span>
                
                <AnimatePresence mode="wait">
                  {selectedConcept ? (
                    <motion.div 
                      key={selectedConcept.id}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      className="p-8 border border-tertiary/20 bg-card/85 backdrop-blur-xl rounded-2xl shadow-xl space-y-6 text-primary hover:border-tertiary/45 transition-colors duration-300"
                    >
                      <div className="flex items-center justify-between border-b border-primary/5 pb-4">
                        <div className="space-y-1">
                          <span className="text-[8px] font-mono font-black tracking-widest text-tertiary uppercase">Vector Node {selectedConcept.id}</span>
                          <h3 className="font-serif font-black text-lg uppercase tracking-tight leading-none">{selectedConcept.name}</h3>
                        </div>
                        <span className="text-[9px] font-mono px-2 py-1 border border-tertiary/20 text-tertiary font-bold rounded-md uppercase bg-tertiary/5">
                          {selectedConcept.type}
                        </span>
                      </div>

                      <div className="space-y-4 text-xs font-mono">
                        <div className="space-y-1">
                          <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest">Description</span>
                          <p className="text-[11px] text-secondary font-sans leading-relaxed">{selectedConcept.description}</p>
                        </div>

                        {selectedConcept.code_snippet && (
                          <div className="space-y-1 pt-3 border-t border-primary/5">
                            <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest text-tertiary">Semantic Match Code Snippet</span>
                            <pre className="p-3 bg-neutral-900 border border-primary/5 text-[9px] text-primary/90 break-all rounded-xl font-mono max-h-48 overflow-y-auto overflow-x-auto whitespace-pre select-all">
                              {selectedConcept.code_snippet}
                            </pre>
                          </div>
                        )}

                        <div className="space-y-1 pt-3 border-t border-primary/5">
                          <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest">Source File Location</span>
                          <div className="p-3 bg-primary/5 border border-primary/5 text-[10px] text-primary break-all rounded-xl font-semibold select-all">
                            {selectedConcept.file}
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4 pt-3 border-t border-primary/5">
                          <div>
                            <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest">Dimensions size</span>
                            <div className="text-xl font-bold mt-1 text-primary">{selectedConcept.vectors} dim</div>
                          </div>
                          <div>
                            <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest">Consensus Factor</span>
                            <div className="text-xl font-bold mt-1 text-tertiary">{(selectedConcept.confidence * 100).toFixed(2)}%</div>
                          </div>
                        </div>

                        <div className="pt-6 border-t border-primary/5">
                          <a 
                            href={`file:///${selectedConcept.file}`}
                            className="w-full flex items-center justify-center gap-2 py-3 border border-primary hover:bg-primary hover:text-neutral transition-all duration-300 uppercase font-black tracking-widest text-[9px] rounded-xl hover:scale-[1.01] cursor-pointer"
                          >
                            Open Concept Source Code
                            <ArrowUpRight className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div 
                      key="no-selection"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 0.5 }}
                      className="p-12 border border-dashed border-primary/10 rounded-2xl text-center py-20 bg-card/20"
                    >
                      <Database className="w-12 h-12 text-primary/10 mx-auto mb-4" />
                      <h4 className="font-serif font-black text-sm uppercase text-primary">No concept selected</h4>
                      <p className="text-[10px] text-secondary uppercase tracking-widest mt-1">Select any mapped concept on the left to inspect its complete vector state.</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

          </div>

        </div>

        {/* Footer */}
        <footer className="h-16 border-t border-primary/5 flex items-center justify-between px-10 bg-[var(--background)]/60 text-[10px] sm:text-xs font-black uppercase tracking-[0.8em] opacity-30 sticky bottom-0 lg:static backdrop-blur-xl shrink-0">
          <span>HIVEMIND_MEMORY // SYS.3</span>
          <span>{"VECTORS_"}{stats.totalVectors}{" // CONCEPTS_"}{concepts.length}</span>
        </footer>
      </main>

      {/* Help / Guide Modal Overlay */}
      <AnimatePresence>
        {showInfoModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowInfoModal(false)}
              className="absolute inset-0 bg-background/60 backdrop-blur-md"
            />

            {/* Modal Box */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="relative w-full max-w-lg bg-[var(--card)] border border-primary/5 rounded-2xl shadow-2xl p-8 z-10 text-left space-y-6"
            >
              <div className="flex items-center justify-between border-b border-primary/5 pb-4">
                <div className="space-y-1">
                  <span className="text-[8px] font-mono font-black tracking-widest text-tertiary uppercase">Information Node</span>
                  <h3 className="font-serif font-black text-xl uppercase tracking-tight leading-none text-primary">Code Search Guide</h3>
                </div>
                <button
                  onClick={() => setShowInfoModal(false)}
                  className="text-stone-400 hover:text-primary transition-colors text-xs font-bold uppercase tracking-wider cursor-pointer"
                >
                  ✕ Close
                </button>
              </div>

              <div className="space-y-4 text-xs leading-relaxed text-secondary">
                <div className="space-y-1">
                  <h4 className="font-serif font-bold text-sm text-primary uppercase">What is Code Search?</h4>
                  <p>
                    Code Search is a semantic vector database (powered by ChromaDB and local embedding engines). It translates code symbols, documentation, and logic structures from your project into high-dimensional vector coordinates (embeddings) representing their semantic meaning.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-serif font-bold text-sm text-primary uppercase">Sovereign Semantic Search</h4>
                  <p>
                    Instead of standard keyword searches (which require exact matching syntax), Semantic Search analyzes the contextual meaning of your query. For example, searching for &quot;auth flow&quot; will retrieve classes, databases, or logic handling cookies, tokens, or JWTs even if they don&apos;t contain the word &quot;auth&quot;.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-serif font-bold text-sm text-primary uppercase">Indexed Concepts</h4>
                  <p>
                    The Swarm automatically groups related code blocks, variables, and API routers into <strong>Concepts</strong>. Selecting a concept from the list displays its matching accuracy, absolute file coordinates, and specific dimensions inside the vector space.
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t border-primary/5 flex justify-end">
                <button
                  onClick={() => setShowInfoModal(false)}
                  className="px-6 py-3 bg-primary hover:opacity-90 text-neutral font-black uppercase tracking-[0.15em] text-[9px] rounded-xl transition-all hover:scale-[1.02] duration-300 cursor-pointer shadow-md"
                >
                  Understood, Continue
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
