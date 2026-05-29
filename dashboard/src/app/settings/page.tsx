"use client";

import React, { useState, useEffect, useId } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Server, Key, Folder, CheckCircle, Activity, Settings as SettingsIcon, X, Network, DollarSign } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { CONFIG } from "@/lib/config";

interface CalibrationCardProps {
  section: {
    id: string;
    title: string;
    icon?: React.ComponentType<{ className?: string }>;
    description: string;
    chapter: number;
  };
  onAccess: () => void;
  disabled?: boolean;
}

const CalibrationCard: React.FC<CalibrationCardProps> = ({ section, onAccess, disabled }) => {
  const Icon = section.icon;
  const titleId = useId();
  const descId = useId();

  return (
    <li className="list-none">
      <div
        className={`group text-left w-full border border-[var(--secondary)]/20 bg-[var(--card)]/40 p-12 lg:p-16 artisan-shadow hover:bg-[var(--tertiary)]/[0.04] hover:border-[var(--tertiary)]/30 focus-within:border-[var(--tertiary)]/50 focus-within:ring-2 focus-within:ring-[var(--tertiary)]/20 transition-all flex flex-col space-y-8 relative rounded-md overflow-hidden min-h-[280px] ${
          disabled ? "opacity-50" : ""
        }`}
      >
        <div className="flex justify-between items-start w-full" aria-hidden="true">
          {Icon ? <Icon className="w-10 h-10 text-[var(--tertiary)]" /> : <div className="w-10 h-10" />}
          <span className="ind-header opacity-20 group-hover:opacity-100 uppercase text-[10px] sm:text-xs font-bold tracking-widest text-[var(--foreground)]">CH.{section.chapter}</span>
        </div>
        
        <div className="space-y-4 w-full">
          <h2 id={titleId} className="text-3xl lg:text-4xl font-serif font-black text-[var(--primary)] select-text">
            {section.title}
          </h2>
          <p id={descId} className="text-xs font-bold text-[var(--secondary)] uppercase tracking-widest leading-relaxed select-text">
            {section.description}
          </p>
        </div>
        
        <button
          onClick={onAccess}
          disabled={disabled}
          aria-label={`Access Module for CH.${section.chapter} ${section.title}`}
          aria-describedby={descId}
          className="mt-auto border border-[var(--secondary)]/20 py-4 text-xs font-black uppercase text-center tracking-[0.4em] text-[var(--foreground)] group-hover:bg-[var(--tertiary)] group-hover:text-white transition-all w-full cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[var(--tertiary)]/70 focus:border-[var(--tertiary)]/50 focus:bg-[var(--tertiary)] focus:text-white rounded-sm"
        >
          Access Module
        </button>
      </div>
    </li>
  );
};

export default function Settings() {
  const API_BASE = CONFIG.API_BASE;
  const [config, setConfig] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [activeSection, setActiveSection] = useState<number | null>(null);
  const [isNavigating, setIsNavigating] = useState(false);

  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/stats`, { cache: 'no-store' });
      setIsOnline(res.ok);
    } catch {
      setIsOnline(false);
    }
  };

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/config`);
      const data = await res.json();
      if (data.status === "success") {
        setConfig(data.config);
      }
    } catch (err) {
      console.error("Failed to fetch config:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const triggerManualSave = async () => {
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/config`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ settings: config }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setSaveStatus("Configuration securely encrypted & saved");
        setTimeout(() => setSaveStatus(null), 3000);
      }
    } catch (err) {
      console.error("Save failed:", err);
      setSaveStatus("Failed to save");
    } finally {
      setIsSaving(false);
    }
  };

  // Auto-Save Effect
  useEffect(() => {
    if (Object.keys(config).length === 0 || isLoading) return;
    
    const timer = setTimeout(() => {
      triggerManualSave();
    }, 1200);

    return () => clearTimeout(timer);
  }, [config, isLoading]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    await triggerManualSave();
  };


  const handleChange = (key: string, value: string) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleAccessSection = (index: number) => {
    if (activeSection !== null || isNavigating) return;
    setIsNavigating(true);
    setActiveSection(index);
    setTimeout(() => setIsNavigating(false), 300);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[var(--background)] flex selection:bg-[var(--tertiary)] selection:text-white max-w-[100vw] overflow-x-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col items-center justify-center">
          <div className="w-8 h-8 border-4 border-[var(--tertiary)]/30 border-t-[var(--tertiary)] rounded-full animate-spin mb-4" />
          <p className="text-[var(--tertiary)]/70 text-xs font-bold tracking-widest uppercase">DECRYPTING CONFIG...</p>
        </div>
      </div>
    );
  }

  const sections = [
    { id: "cloud", title: "Cloud Intelligence", icon: Key, description: "Manage LLM router keys and secure credentials.", chapter: 1 },
    { id: "infrastructure", title: "Core Infrastructure", icon: Server, description: "Calibrate Ollama endpoint and local persistence paths.", chapter: 2 },
    { id: "network", title: "Network & Ports", icon: Network, description: "Configure internal API gateway bindings.", chapter: 3 },
    { id: "economics", title: "Swarm Economics", icon: DollarSign, description: "Set daily budget telemetry and token limiters.", chapter: 4 },
  ];

  return (
    <div className="min-h-screen bg-[var(--background)] flex selection:bg-[var(--tertiary)] selection:text-white max-w-[100vw] overflow-x-hidden relative">
      <div className="grain-overlay" />
      <Sidebar />
      
      <main className="flex-1 p-0 relative flex flex-col transition-all duration-700 pb-20 lg:pb-0 min-w-0 overflow-x-hidden z-10">
        
        <header className="h-24 lg:h-32 border-b-2 border-[var(--border)] flex items-center justify-between px-6 lg:px-12 bg-[var(--background)]/60 z-20 sticky top-0 backdrop-blur-xl">
          <div className="flex items-center gap-4 lg:gap-10">
            <span className="ind-header text-[10px] lg:text-[12px] opacity-100 font-black">Control Hub</span>
            <div className="h-6 lg:h-10 w-[2px] bg-[var(--border)]" />
            <span className="font-serif italic text-lg lg:text-2xl text-[var(--primary)]">Calibration</span>
          </div>
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 px-3 py-1 border ${isOnline ? 'border-emerald-500/50 bg-emerald-500/5 text-emerald-500' : 'border-red-500/50 bg-red-500/5 text-red-500'} transition-all`}>
              <Activity className={`w-3 h-3 ${isOnline ? 'animate-pulse' : ''}`} />
              <span className="text-[9px] font-mono font-bold uppercase">{isOnline ? 'Mission Control: Online' : 'Mission Control: Offline'}</span>
            </div>
            <SettingsIcon className="w-5 h-5 text-[var(--tertiary)] hidden sm:block" />
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6 lg:p-12 xl:p-20 2xl:p-32 space-y-32 lg:space-y-48 relative z-10 custom-scrollbar pb-32">
          
          <header className="space-y-4 lg:space-y-8">
            <div className="flex items-center gap-4">
              <span className="ind-header text-[var(--tertiary)] opacity-100 uppercase text-[10px] font-bold tracking-widest">System Parameters</span>
              <div className="flex-1 h-[2px] bg-[var(--tertiary)] opacity-30" />
            </div>
            <h1 className="pub-title text-[clamp(3rem,14vw,14rem)] text-[var(--foreground)]">
              Control.
            </h1>
          </header>

          <ul className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-16 p-0 m-0">
            {sections.map((section, i) => (
              <CalibrationCard 
                key={section.id} 
                section={section} 
                onAccess={() => handleAccessSection(i)} 
                disabled={activeSection !== null || isNavigating}
              />
            ))}
          </ul>

          <section className="p-12 lg:p-20 border border-[var(--border)] bg-[var(--foreground)] text-[var(--background)] artisan-shadow space-y-8 rounded-md">
            <div className="flex items-center gap-4">
              <div className="w-2 h-2 bg-[var(--tertiary)]" />
              <span className="ind-header text-[var(--tertiary)] opacity-100 uppercase text-[10px] font-bold tracking-widest">Hardware Sign-off</span>
            </div>
            <p className="font-serif italic text-xl lg:text-3xl opacity-60">
              &ldquo;Authority is not granted; it is architected.&rdquo;
            </p>
            <div className="pt-8 border-t border-[var(--background)]/10 flex justify-between items-center text-[8px] font-mono tracking-widest opacity-40">
              <span>SYSTEM_VERSION: PORTABLE-KENBUN</span>
              <span>NODE_SECURE_STABLE</span>
            </div>
          </section>

        </div>

        <footer className="h-16 lg:h-24 border-t-2 border-[var(--border)] flex items-center justify-between px-8 lg:px-20 bg-[var(--background)]/60 text-[7px] lg:text-[9px] font-black uppercase tracking-[0.8em] opacity-30 sticky bottom-0 lg:static backdrop-blur-xl">
          <span>CONTROL_INTERFACE // SV.177</span>
          <span className="hidden sm:inline">© 2026</span>
        </footer>
      </main>

      {/* ACCESS CALIBRATION DRAWER / MODAL OVERLAY */}
      <AnimatePresence>
        {activeSection !== null && (
          <div 
            className="fixed inset-0 bg-[var(--background)]/80 backdrop-blur-md z-[9999] flex items-center justify-center p-4"
            onClick={() => setActiveSection(null)}
          >
            <motion.div 
              initial={{ scale: 0.95, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 20 }}
              className="border border-[var(--border)] bg-[var(--card)] max-w-xl w-full p-8 lg:p-12 shadow-2xl relative flex flex-col max-h-[85vh] rounded-md overflow-hidden artisan-shadow"
              onClick={(e) => e.stopPropagation()}
            >
              <button 
                onClick={() => setActiveSection(null)} 
                className="absolute top-6 right-6 text-[var(--foreground)]/45 hover:text-[var(--tertiary)] transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar">
                
                {/* CH.1 Cloud Intelligence */}
                {activeSection === 0 && (
                  <form onSubmit={handleSave} className="space-y-6 pt-4">
                    <div className="space-y-2">
                      <span className="text-[8px] font-mono text-[var(--tertiary)] border border-[var(--tertiary)]/30 px-2 py-0.5 font-bold uppercase rounded bg-[var(--tertiary)]/10">Cloud Integration Node</span>
                      <h3 className="text-xl font-serif font-black text-[var(--foreground)]">Cloud Intelligence Keys</h3>
                    </div>
                    
                    <div className="border border-[var(--border)] p-4 bg-[var(--background)]/40 rounded space-y-4">
                      <div className="flex justify-between items-center border-b border-[var(--border)] pb-3">
                        <span className="text-[10px] font-bold opacity-60 text-[var(--foreground)]">Sovereign Key Registry</span>
                      </div>
                      <div className="space-y-4">
                        {[
                          { key: "GEMINI_API_KEY", label: "Google Gemini API Key", placeholder: "AIzaSy..." },
                          { key: "OPENAI_API_KEY", label: "OpenAI API Key", placeholder: "sk-proj-..." },
                          { key: "ANTHROPIC_API_KEY", label: "Anthropic API Key", placeholder: "sk-ant-..." }
                        ].map((field) => (
                          <div key={field.key} className="space-y-2">
                            <label className="text-[10px] font-bold text-[var(--foreground)] uppercase tracking-wider">{field.label}</label>
                            <input
                              type="password"
                              value={config[field.key] || ""}
                              onChange={(e) => handleChange(field.key, e.target.value)}
                              placeholder={field.placeholder}
                              className="w-full bg-[var(--background)] border border-[var(--border)] px-3 py-2 text-[10px] focus:outline-none text-[var(--foreground)] rounded-sm font-mono focus:border-[var(--tertiary)] focus:ring-1 focus:ring-[var(--tertiary)]/20"
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
                      <div>
                        {saveStatus && <span className="text-emerald-500 text-[10px] font-bold">{saveStatus}</span>}
                        {isSaving && !saveStatus && <span className="text-[var(--tertiary)]/70 text-[10px] font-bold animate-pulse">Saving...</span>}
                        {!isSaving && !saveStatus && <span className="text-[var(--foreground)]/40 text-[10px] font-bold">Auto-save active</span>}
                      </div>
                      <button
                        type="button"
                        onClick={async () => {
                          await triggerManualSave();
                          setActiveSection(null);
                        }}
                        className="bg-[var(--tertiary)] hover:bg-[var(--tertiary)]/80 text-white text-[10px] font-bold uppercase tracking-wider px-4 py-2 rounded-sm cursor-pointer transition-all focus:outline-none focus:ring-1 focus:ring-[var(--tertiary)]"
                      >
                        Save & Close
                      </button>
                    </div>
                  </form>
                )}

                {/* CH.2 Core Infrastructure */}
                {activeSection === 1 && (
                  <form onSubmit={handleSave} className="space-y-6 pt-4">
                    <div className="space-y-2">
                      <span className="text-[8px] font-mono text-[var(--tertiary)] border border-[var(--tertiary)]/30 px-2 py-0.5 font-bold uppercase rounded bg-[var(--tertiary)]/10">Storage Calibration</span>
                      <h3 className="text-xl font-serif font-black text-[var(--foreground)]">Core Infrastructure</h3>
                    </div>

                    <div className="border border-[var(--border)] p-4 bg-[var(--background)]/40 rounded space-y-4">
                      <div className="space-y-4">
                        {[
                          { key: "PROJECT_ROOT", label: "Project Root Directory", placeholder: "/app" },
                          { key: "OLLAMA_URL", label: "Local Ollama Inference URL", placeholder: "http://ollama_server:11434/api/generate" },
                          { key: "LM_STUDIO_URL", label: "Local LM Studio URL", placeholder: "http://host.docker.internal:1234/v1" },
                          { key: "LM_STUDIO_MODEL", label: "LM Studio Model Name", placeholder: "local-model" },
                          { key: "PRIMARY_LLM_URL", label: "Primary LLM Router", placeholder: "http://ollama_server:11434/v1" }
                        ].map((field) => (
                          <div key={field.key} className="space-y-2">
                            <label className="text-[10px] font-bold text-[var(--foreground)] uppercase tracking-wider">{field.label}</label>
                            <input
                              type="text"
                              value={config[field.key] || ""}
                              onChange={(e) => handleChange(field.key, e.target.value)}
                              placeholder={field.placeholder}
                              className="w-full bg-[var(--background)] border border-[var(--border)] px-3 py-2 text-[10px] focus:outline-none text-[var(--foreground)] rounded-sm font-mono focus:border-[var(--tertiary)] focus:ring-1 focus:ring-[var(--tertiary)]/20"
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
                      <div>
                        {saveStatus && <span className="text-emerald-500 text-[10px] font-bold">{saveStatus}</span>}
                        {isSaving && !saveStatus && <span className="text-[var(--tertiary)]/70 text-[10px] font-bold animate-pulse">Saving...</span>}
                        {!isSaving && !saveStatus && <span className="text-[var(--foreground)]/40 text-[10px] font-bold">Auto-save active</span>}
                      </div>
                      <button
                        type="button"
                        onClick={async () => {
                          await triggerManualSave();
                          setActiveSection(null);
                        }}
                        className="bg-[var(--tertiary)] hover:bg-[var(--tertiary)]/80 text-white text-[10px] font-bold uppercase tracking-wider px-4 py-2 rounded-sm cursor-pointer transition-all focus:outline-none focus:ring-1 focus:ring-[var(--tertiary)]"
                      >
                        Save & Close
                      </button>
                    </div>
                  </form>
                )}

                {/* CH.3 Network Ports */}
                {activeSection === 2 && (
                  <form onSubmit={handleSave} className="space-y-6 pt-4">
                    <div className="space-y-2">
                      <span className="text-[8px] font-mono text-[var(--tertiary)] border border-[var(--tertiary)]/30 px-2 py-0.5 font-bold uppercase rounded bg-[var(--tertiary)]/10">API Gateway</span>
                      <h3 className="text-xl font-serif font-black text-[var(--foreground)]">Network & Ports</h3>
                    </div>

                    <div className="border border-[var(--border)] p-4 bg-[var(--background)]/40 rounded space-y-4">
                      <div className="space-y-4">
                        {[
                          { key: "API_PORT", label: "FastMCP API Port", placeholder: "8001" },
                          { key: "DASHBOARD_PORT", label: "Dashboard Port", placeholder: "3000" }
                        ].map((field) => (
                          <div key={field.key} className="space-y-2">
                            <label className="text-[10px] font-bold text-[var(--foreground)] uppercase tracking-wider">{field.label}</label>
                            <input
                              type="text"
                              value={config[field.key] || ""}
                              onChange={(e) => handleChange(field.key, e.target.value)}
                              placeholder={field.placeholder}
                              className="w-full bg-[var(--background)] border border-[var(--border)] px-3 py-2 text-[10px] focus:outline-none text-[var(--foreground)] rounded-sm font-mono focus:border-[var(--tertiary)] focus:ring-1 focus:ring-[var(--tertiary)]/20"
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
                      <div>
                        {saveStatus && <span className="text-emerald-500 text-[10px] font-bold">{saveStatus}</span>}
                        {isSaving && !saveStatus && <span className="text-[var(--tertiary)]/70 text-[10px] font-bold animate-pulse">Saving...</span>}
                        {!isSaving && !saveStatus && <span className="text-[var(--foreground)]/40 text-[10px] font-bold">Auto-save active</span>}
                      </div>
                      <button
                        type="button"
                        onClick={async () => {
                          await triggerManualSave();
                          setActiveSection(null);
                        }}
                        className="bg-[var(--tertiary)] hover:bg-[var(--tertiary)]/80 text-white text-[10px] font-bold uppercase tracking-wider px-4 py-2 rounded-sm cursor-pointer transition-all focus:outline-none focus:ring-1 focus:ring-[var(--tertiary)]"
                      >
                        Save & Close
                      </button>
                    </div>
                  </form>
                )}

                {/* CH.4 Swarm Economics */}
                {activeSection === 3 && (
                  <form onSubmit={handleSave} className="space-y-6 pt-4">
                    <div className="space-y-2">
                      <span className="text-[8px] font-mono text-[var(--tertiary)] border border-[var(--tertiary)]/30 px-2 py-0.5 font-bold uppercase rounded bg-[var(--tertiary)]/10">Telemetry Limiters</span>
                      <h3 className="text-xl font-serif font-black text-[var(--foreground)]">Swarm Economics</h3>
                    </div>

                    <div className="border border-[var(--border)] p-4 bg-[var(--background)]/40 rounded space-y-4">
                      <div className="space-y-4">
                        <div className="space-y-2">
                          <label className="text-[10px] font-bold text-[var(--foreground)] uppercase tracking-wider">Daily API Budget Limit ($)</label>
                          <input
                            type="number"
                            step="0.01"
                            value={config["DAILY_BUDGET"] || ""}
                            onChange={(e) => handleChange("DAILY_BUDGET", e.target.value)}
                            placeholder="50.00"
                            className="w-full bg-[var(--background)] border border-[var(--border)] px-3 py-2 text-[10px] focus:outline-none text-[var(--foreground)] rounded-sm font-mono focus:border-[var(--tertiary)] focus:ring-1 focus:ring-[var(--tertiary)]/20"
                          />
                          <p className="text-[9px] font-mono opacity-50 text-[var(--foreground)]">Controls the absolute daily ceiling for cloud-based inference tokens.</p>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
                      <div>
                        {saveStatus && <span className="text-emerald-500 text-[10px] font-bold">{saveStatus}</span>}
                        {isSaving && !saveStatus && <span className="text-[var(--tertiary)]/70 text-[10px] font-bold animate-pulse">Saving...</span>}
                        {!isSaving && !saveStatus && <span className="text-[var(--foreground)]/40 text-[10px] font-bold">Auto-save active</span>}
                      </div>
                      <button
                        type="button"
                        onClick={async () => {
                          await triggerManualSave();
                          setActiveSection(null);
                        }}
                        className="bg-[var(--tertiary)] hover:bg-[var(--tertiary)]/80 text-white text-[10px] font-bold uppercase tracking-wider px-4 py-2 rounded-sm cursor-pointer transition-all focus:outline-none focus:ring-1 focus:ring-[var(--tertiary)]"
                      >
                        Save & Close
                      </button>
                    </div>
                  </form>
                )}

              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
