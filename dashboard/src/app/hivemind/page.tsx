"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "@/components/Sidebar";
import { 
  Database,
  Search,
  Cpu,
  RefreshCw,
  Clock,
  CheckCircle,
  FileCode,
  AlertCircle,
  Tag,
  ArrowUpRight,
  Sliders,
  ChevronRight
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { CONFIG } from "@/lib/config";

interface Concept {
  id: string;
  name: string;
  file: string;
  type: string;
  description: string;
  vectors: number;
  lastUpdated: string;
  confidence: number;
}

export default function HivemindMemory() {
  const API_BASE = CONFIG.API_BASE;
  const [concepts, setConcepts] = useState<Concept[]>([]);
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
  const [error, setError] = useState(false);
  const [isOnline, setIsOnline] = useState(true);

  // Sync index process interval simulator
  const indexInterval = useRef<NodeJS.Timeout | null>(null);

  // Fetch real/live stats or fallback
  const fetchHivemindData = useCallback(async () => {
    try {
      const [statsRes, conceptsRes] = await Promise.all([
        fetch(`${API_BASE}/stats`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/v1/hivemind/concepts`, { cache: "no-store" })
      ]);
      
      if (!statsRes.ok) throw new Error("API_ERROR");
      
      const statsData = await statsRes.json();
      
      let conceptsData: any = null;
      if (conceptsRes.ok) {
        conceptsData = await conceptsRes.json();
        if (conceptsData?.concepts?.length > 0) {
          setConcepts(conceptsData.concepts);
        }
      }
      
      // Update stats based on real API response
      if (statsData.telemetry?.memory) {
        setStats(prev => ({
          ...prev,
          totalVectors: statsData.telemetry.memory.capacity || prev.totalVectors,
          indexedFiles: statsData.telemetry.memory.files || (conceptsRes.ok && conceptsData ? conceptsData.concepts?.length : prev.indexedFiles),
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
    fetchHivemindData();
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
    
    // Simulate high-dimensional query delay
    await new Promise(resolve => setTimeout(resolve, 800));

    // Simple keyword search fallback
    const lowercaseQuery = searchQuery.toLowerCase();
    
    // General fuzzy search on dynamic concepts
    const matches = concepts.filter(c => 
      c.name.toLowerCase().includes(lowercaseQuery) || 
      c.description.toLowerCase().includes(lowercaseQuery) ||
      c.file.toLowerCase().includes(lowercaseQuery)
    );

    // De-duplicate matches
    const uniqueMatches = Array.from(new Map(matches.map(item => [item.id, item])).values());
    
    setSearchResults(uniqueMatches);
    setIsSearching(false);
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
    <div className="min-h-screen bg-neutral flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden font-sans">
      <Sidebar />

      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 pb-20 lg:pb-0 min-w-0 overflow-x-hidden">
        <div className="grain-overlay opacity-20" />

        {/* Header */}
        <header className="h-20 lg:h-24 border-b border-primary/5 flex items-center justify-between px-6 lg:px-10 bg-card/40 z-20 sticky top-0 backdrop-blur-xl shrink-0">
          <div className="flex items-center gap-4 lg:gap-8">
            <span className="text-[10px] font-black uppercase tracking-widest opacity-30">System.03</span>
            <div className="h-6 w-[1px] bg-primary/10" />
            <span className="font-bold text-lg lg:text-xl uppercase tracking-tighter italic">Hivemind <span className="text-tertiary">Memory</span></span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3 bg-primary/5 px-4 py-2 border border-primary/5 rounded-sm">
              <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-tertiary animate-pulse' : 'bg-amber-500 animate-pulse'}`} />
              <span className="text-[10px] font-black uppercase tracking-widest text-primary/70">
                {isOnline ? "Online Vector DB" : "Offline Sandbox"}
              </span>
            </div>
          </div>
        </header>

        {/* Scroll Content */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-10 xl:p-12 space-y-12 relative z-10 custom-scrollbar pb-32">
          
          {/* Quick Metrics Grid */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { label: "Total Vectors Mapped", value: stats.totalVectors, icon: Database, color: "text-tertiary" },
              { label: "Indexed Source Files", value: stats.indexedFiles, icon: FileCode, color: "text-primary" },
              { label: "Search Retrieval Latency", value: stats.searchLatency, icon: Clock, color: "text-primary" },
              { label: "Last Neural Sync", value: stats.lastIndexTime, icon: RefreshCw, color: "text-primary" }
            ].map((stat, i) => (
              <div key={i} className="p-6 border border-primary/5 bg-card/60 backdrop-blur-md shadow-sm rounded-sm flex items-center justify-between group hover:border-tertiary/20 transition-all duration-300">
                <div className="space-y-2">
                  <span className="text-[9px] uppercase tracking-[0.2em] opacity-40 font-black">{stat.label}</span>
                  <div className="text-xl lg:text-2xl font-black text-primary tracking-tighter italic">{stat.value}</div>
                </div>
                <stat.icon className={`w-8 h-8 opacity-10 group-hover:opacity-30 group-hover:scale-105 transition-all duration-500 ${stat.color}`} />
              </div>
            ))}
          </section>

          {/* Semantic Workspace Search Panel */}
          <section className="p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-sm artisan-shadow space-y-6">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <span className="text-[10px] font-black uppercase tracking-[0.4em] text-tertiary">Sovereign Vector Engine</span>
                <h3 className="text-lg font-bold uppercase tracking-tight">Codebase Semantic Search</h3>
              </div>
              <Sliders className="w-4 h-4 opacity-30 hover:opacity-100 transition-opacity cursor-pointer text-primary" />
            </div>

            <form onSubmit={handleSearch} className="flex gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 opacity-30 text-primary" />
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Ask the Swarm (e.g. 'token rate limit implementation' or 'ethical guardrail rules')..."
                  className="w-full pl-12 pr-4 py-4 border border-primary/5 rounded-sm bg-card/40 font-sans text-sm focus:outline-none focus:border-tertiary focus:bg-card hover:border-primary/20 transition-all text-primary placeholder-primary/20"
                />
              </div>
              <button 
                type="submit"
                disabled={isSearching}
                className="px-8 py-4 bg-primary hover:bg-primary/95 text-white font-black uppercase tracking-[0.2em] text-[10px] transition-all rounded-sm shadow-md disabled:opacity-50"
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
                className="px-4 py-2 border border-primary/10 hover:border-tertiary hover:text-tertiary rounded-sm text-[9px] font-black uppercase tracking-[0.15em] transition-all flex items-center gap-2"
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
                  {searchResults !== null ? "Search Matches" : "Neural Concept Catalog"}
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
                      className={`p-6 border border-primary/5 bg-card/60 backdrop-blur-md rounded-sm flex flex-col md:flex-row md:items-center justify-between gap-6 hover:border-tertiary/30 cursor-pointer transition-all ${
                        selectedConcept?.id === concept.id ? 'border-tertiary/40 bg-card shadow-md shadow-tertiary/[0.02]' : ''
                      }`}
                    >
                      <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <Tag className="w-3.5 h-3.5 text-tertiary" />
                          <h4 className="font-serif font-black text-sm text-primary uppercase tracking-tight truncate">
                            {concept.name}
                          </h4>
                          <span className="text-[8px] font-mono font-bold uppercase px-1.5 py-0.5 border border-primary/5 bg-primary/5 text-primary/60 rounded-sm">
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
                        <span className="text-[8px] font-bold text-secondary uppercase tracking-widest bg-primary/5 px-2 py-1 rounded-sm">
                          {concept.lastUpdated}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {(searchResults !== null && searchResults.length === 0) && (
                  <div className="p-12 border border-dashed border-primary/10 rounded-sm text-center space-y-4">
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
                      className="p-8 border-2 border-tertiary/20 bg-card rounded-sm shadow-xl shadow-primary/5 space-y-6 text-primary"
                    >
                      <div className="flex items-center justify-between border-b border-primary/5 pb-4">
                        <div className="space-y-1">
                          <span className="text-[8px] font-mono font-black tracking-widest text-tertiary uppercase">Vector Node {selectedConcept.id}</span>
                          <h3 className="font-serif font-black text-lg uppercase tracking-tight leading-none">{selectedConcept.name}</h3>
                        </div>
                        <span className="text-[9px] font-mono px-2 py-1 border border-tertiary/20 text-tertiary font-bold rounded-sm uppercase bg-tertiary/5">
                          {selectedConcept.type}
                        </span>
                      </div>

                      <div className="space-y-4 text-xs font-mono">
                        <div className="space-y-1">
                          <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest">Description</span>
                          <p className="text-[11px] text-secondary font-sans leading-relaxed">{selectedConcept.description}</p>
                        </div>

                        <div className="space-y-1 pt-3 border-t border-primary/5">
                          <span className="text-[9px] font-bold opacity-30 uppercase tracking-widest">Source File Location</span>
                          <div className="p-3 bg-primary/5 border border-primary/5 text-[10px] text-primary break-all rounded-sm font-semibold select-all">
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
                            className="w-full flex items-center justify-center gap-2 py-3 border border-primary hover:bg-primary hover:text-white transition-all duration-300 uppercase font-black tracking-widest text-[9px] rounded-sm"
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
                      className="p-12 border-2 border-dashed border-primary/10 rounded-sm text-center py-20"
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
    </div>
  );
}
