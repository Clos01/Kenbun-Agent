"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Sidebar from "@/components/Sidebar";
import { 
  Layers, 
  ExternalLink, 
  Eye, 
  RefreshCw, 
  Plus, 
  Trash2, 
  X, 
  Check, 
  Code,
  Layout,
  FileText,
  Sliders,
  Terminal,
  Database
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { createPortal } from "react-dom";
import { CONFIG } from "@/lib/config";

// Interface for Web Apps
interface WebApp {
  id: string;
  name: string;
  description: string;
  defaultPort: number;
  /** Path appended to the URL for the iframe/launch link (display URL) */
  path?: string;
  /** Separate path used ONLY for the health-check ping. Falls back to `path` if omitted. */
  pingPath?: string;
  icon: React.ComponentType<{ className?: string }>;
  isCustom?: boolean;
  urlOverride?: string;
  hostType?: "host" | "tailscale";
}

// Security: Strict URL Sanitization to prevent XSS via javascript: or data: protocols
function sanitizeUrl(url: string): string {
  if (!url) return "about:blank";
  try {
    // Standardize URL protocol
    let targetUrl = url.trim();
    if (!/^https?:\/\//i.test(targetUrl)) {
      targetUrl = `http://${targetUrl}`;
    }
    const parsed = new URL(targetUrl);
    // Reject URLs with embedded credentials (http://user:pass@host)
    if (parsed.username || parsed.password) return "about:blank";
    // Return the parser's normalized form, not the raw input, so the validated
    // URL and the rendered URL can never diverge (parser-mismatch hardening).
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.href;
    }
  } catch {
    console.warn("Invalid URL blocked during sanitization:", url);
  }
  return "about:blank";
}

// Default Webapps definition matching ports and configurations (static — module scope
// keeps the reference stable so hooks don't re-run on every render)
const DEFAULT_APPS: WebApp[] = [
  {
    id: "gitea",
    name: "Gitea",
    description: "Sovereign Git repository mapping to the 'sovereign' remote.",
    defaultPort: 3005,
    hostType: "host",
    icon: Code
  },
  {
    id: "planka",
    name: "Planka",
    description: "Kanban Board for agile mission planning and task management.",
    defaultPort: 1337,
    hostType: "host",
    icon: Layout
  },
  {
    id: "dozzle",
    name: "Dozzle",
    description: "Real-time log viewer for monitoring active Docker containers.",
    defaultPort: 8888,
    hostType: "tailscale",
    icon: Terminal
  },
  {
    id: "honcho",
    name: "Honcho API",
    description: "Short-Term Memory Palace administration API and dreaming hub.",
    defaultPort: 8006,
    // Launch users to the Swagger docs — the root `/` returns FastAPI 404
    path: "/docs",
    // Health check hits the dedicated /health endpoint
    pingPath: "/health",
    hostType: "tailscale",
    icon: Database
  },
  {
    id: "ollama",
    name: "Ollama Server",
    description: "Local model generation server and models repository.",
    defaultPort: 11434,
    // Ping the model list endpoint; root also works but /api/tags is more meaningful
    pingPath: "/api/tags",
    hostType: "tailscale",
    icon: Sliders
  }
];

export default function AppsPortal() {
  const [ipAddress, setIpAddress] = useState<string>("localhost");
  // tailscaleHost is empty during SSR so server + first client render match.
  // After mount it is set to window.location.hostname (e.g. 127.0.0.1).
  const [tailscaleHost, setTailscaleHost] = useState<string>("");
  const [customApps, setCustomApps] = useState<Array<{ id: string; name: string; description: string; url: string }>>([]);
  const [statuses, setStatuses] = useState<Record<string, "checking" | "online" | "offline">>({});
  const [activeIframeUrl, setActiveIframeUrl] = useState<string | null>(null);
  const [activeIframeName, setActiveIframeName] = useState<string>("");
  const [isAddingCustom, setIsAddingCustom] = useState(false);
  const [newAppName, setNewAppName] = useState("");
  const [newAppDesc, setNewAppDesc] = useState("");
  const [newAppUrl, setNewAppUrl] = useState("");
  const [iframeKey, setIframeKey] = useState(0);

  // Load configuration from API to resolve host IP
  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${CONFIG.API_BASE}/api/v1/config`, { cache: "no-store" });
      if (!res.ok) throw new Error("API failed");
      const data = await res.json();
      if (data.status === "success" && data.config) {
        const resolvedIp = data.config.PC_IP_ADDRESS || data.config.SWARM_PC_IP || "localhost";
        setIpAddress(resolvedIp);
      }
    } catch (err) {
      console.warn("Failed to retrieve PC IP Address, using localhost as fallback:", err);
    }
  }, []);

  // Load custom apps from local storage with security schema validation
  const loadCustomApps = useCallback(() => {
    try {
      const stored = localStorage.getItem("kenbun_custom_webapps");
      if (stored) {
        const rawList = JSON.parse(stored);
        if (Array.isArray(rawList)) {
          // Schema validation & sanitization on load
          const validApps = rawList
            .filter(item => item && typeof item === "object" && typeof item.id === "string" && typeof item.name === "string" && typeof item.url === "string")
            .map(item => ({
              id: String(item.id).replace(/[^\w-]/g, ""), // Sanitize ID to letters/numbers/dashes
              name: String(item.name).slice(0, 50),       // Max length limit
              description: String(item.description || "").slice(0, 200),
              url: sanitizeUrl(item.url)
            }))
            .filter(item => item.id && item.url !== "about:blank"); // Remove invalid urls & empty IDs (dup React keys)
          
          setCustomApps(validApps);
          return;
        }
      }
    } catch (e) {
      console.error("Failed to parse custom webapps:", e);
    }
    setCustomApps([]);
  }, []);

  // Capture browser hostname after mount (safe: never runs on the server).
  useEffect(() => {
    setTailscaleHost(window.location.hostname);
  }, []);

  // Initial load — deferred to a macrotask so no setState runs synchronously
  // inside the effect body (avoids cascading-render lint / hydration churn).
  useEffect(() => {
    const t = setTimeout(() => {
      fetchConfig();
      loadCustomApps();
    }, 0);
    return () => clearTimeout(t);
  }, [fetchConfig, loadCustomApps]);

  // Construct URLs dynamically based on current configurations and browser context.
  // Uses tailscaleHost (empty on server, set after mount) so SSR and first client
  // render produce identical markup — eliminating the hydration mismatch.
  const getAppUrl = useCallback((app: WebApp): string => {
    if (app.urlOverride) return sanitizeUrl(app.urlOverride);

    // tailscale containers: use browser hostname once mounted; fall back to ipAddress
    // host-bound services: always use the machine IP from config
    const host =
      app.hostType === "tailscale" && tailscaleHost
        ? tailscaleHost
        : ipAddress;

    const url = `http://${host}:${app.defaultPort}${app.path || ""}`;
    return sanitizeUrl(url);
  }, [ipAddress, tailscaleHost]);

  // Build the URL used ONLY for the health-check ping.
  // Uses `pingPath` if defined, otherwise falls back to the display path.
  const getPingUrl = useCallback((app: WebApp): string => {
    if (app.urlOverride) return sanitizeUrl(app.urlOverride);
    const host =
      app.hostType === "tailscale" && tailscaleHost
        ? tailscaleHost
        : ipAddress;
    const pingPath = app.pingPath ?? app.path ?? "";
    return sanitizeUrl(`http://${host}:${app.defaultPort}${pingPath}`);
  }, [ipAddress, tailscaleHost]);

  // Merge default apps with custom ones (derived state — no effect needed)
  const apps = useMemo<WebApp[]>(() => [
    ...DEFAULT_APPS,
    ...customApps.map(c => ({
      id: c.id,
      name: c.name,
      description: c.description,
      defaultPort: 80,
      urlOverride: c.url,
      icon: FileText,
      isCustom: true
    }))
  ], [customApps]);

  // Pinger: delegates health check to the Next.js server-side /api/ping route
  // to avoid browser CORS/mixed-content blocks on cross-origin HEAD requests.
  const checkServiceStatus = useCallback(async (appId: string, url: string) => {
    if (url === "about:blank") {
      setStatuses(prev => ({ ...prev, [appId]: "offline" }));
      return;
    }
    setStatuses(prev => ({ ...prev, [appId]: "checking" }));

    try {
      const res = await fetch(
        `/api/ping?url=${encodeURIComponent(url)}`,
        { cache: "no-store" }
      );
      if (!res.ok) throw new Error("ping-proxy error");
      const data = await res.json();
      setStatuses(prev => ({ ...prev, [appId]: data.online ? "online" : "offline" }));
    } catch {
      setStatuses(prev => ({ ...prev, [appId]: "offline" }));
    }
  }, []);

  // Trigger status pings on apps load and every 30s thereafter.
  // Pings use getPingUrl (which may differ from the display URL for APIs like Honcho).
  useEffect(() => {
    if (apps.length === 0) return;
    const pingAll = () => {
      apps.forEach(app => checkServiceStatus(app.id, getPingUrl(app)));
    };
    pingAll();
    const interval = setInterval(pingAll, 30_000);
    return () => clearInterval(interval);
  }, [apps, getPingUrl, checkServiceStatus]);

  // Handle adding custom app
  const handleAddCustomApp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAppName.trim() || !newAppUrl.trim()) return;

    const sanitizedUrl = sanitizeUrl(newAppUrl);
    if (sanitizedUrl === "about:blank") {
      alert("Invalid application URL provided. Only http and https protocols are supported.");
      return;
    }

    const newApp = {
      id: `custom_${Date.now()}`,
      name: newAppName.trim().slice(0, 50),
      description: newAppDesc.trim().slice(0, 200) || "User registered network application.",
      url: sanitizedUrl
    };

    const updated = [...customApps, newApp];
    setCustomApps(updated);
    localStorage.setItem("kenbun_custom_webapps", JSON.stringify(updated));

    setNewAppName("");
    setNewAppDesc("");
    setNewAppUrl("");
    setIsAddingCustom(false);
  };

  // Handle deleting custom app
  const handleDeleteCustomApp = (id: string) => {
    const updated = customApps.filter(c => c.id !== id);
    setCustomApps(updated);
    localStorage.setItem("kenbun_custom_webapps", JSON.stringify(updated));
    setStatuses(prev => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
  };

  return (
    <div className="min-h-screen bg-neutral text-primary flex selection:bg-tertiary selection:text-white max-w-[100vw] overflow-x-hidden relative font-sans">
      <div className="grain-overlay opacity-20" />
      
      {/* Background Ambience */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-20%] left-[-10%] w-[60vw] h-[60vw] bg-tertiary/[0.02] rounded-full blur-[160px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50vw] h-[50vw] bg-accent/[0.01] rounded-full blur-[140px]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] opacity-30" />
      </div>

      <Sidebar />

      <main className="flex-1 p-6 lg:p-10 relative flex flex-col z-10 pb-24 lg:pb-10 min-w-0">
        {/* HEADER */}
        <header className="h-20 flex items-center justify-between border-b border-primary/5 mb-8 shrink-0 bg-transparent">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 border border-tertiary flex items-center justify-center bg-tertiary/10 rounded-sm">
              <Layers className="w-4 h-4 text-tertiary" />
            </div>
            <div className="h-6 w-[1px] bg-primary/10" />
            <div className="flex flex-col">
              <span className="text-[9px] font-mono text-secondary uppercase tracking-[0.2em] leading-none mb-1">
                Sovereign Stack
              </span>
              <span className="font-serif italic text-lg lg:text-xl font-bold text-primary tracking-tight">
                Web Applications
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 font-mono text-[10px] text-secondary">
            <span>Swarm Machine: </span>
            <span className="px-2 py-0.5 border border-primary/10 rounded bg-card/65 font-bold text-primary">
              {ipAddress}
            </span>
            <button 
              onClick={() => apps.forEach(app => checkServiceStatus(app.id, getAppUrl(app)))}
              className="p-1.5 border border-border hover:border-tertiary bg-card rounded transition-all hover:text-tertiary flex items-center justify-center cursor-pointer"
              title="Refresh Health Checks"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </header>

        {/* APPS BENTO GRID */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 flex-1 items-start">
          {apps.map((app) => {
            const appUrl = getAppUrl(app);
            const cleanUrl = appUrl.split("?")[0];
            const status = statuses[app.id] || "checking";
            const Icon = app.icon;

            return (
              <motion.div
                key={app.id}
                layout
                className="bg-card/45 backdrop-blur-md border border-primary/5 rounded-md p-6 artisan-shadow hover:bg-sand/30 hover:border-tertiary/20 transition-all flex flex-col justify-between group relative overflow-hidden min-h-[220px]"
              >
                <div className="absolute top-6 right-6 flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${
                    status === "online" ? "bg-tertiary animate-pulse shadow-[0_0_8px_var(--tertiary)]" :
                    status === "offline" ? "bg-accent/70" : "bg-secondary/40"
                  }`} />
                  <span className="text-[8px] font-mono font-bold tracking-wider uppercase text-secondary">
                    {status}
                  </span>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 border border-primary/5 rounded bg-card flex items-center justify-center group-hover:border-tertiary/20 group-hover:bg-tertiary/5 transition-all text-primary group-hover:text-tertiary">
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-serif font-black text-base text-primary">
                          {app.name}
                        </h3>
                        {app.isCustom && (
                          <span className="px-1.5 py-0.5 border border-primary/10 rounded text-[7px] font-mono tracking-widest text-secondary uppercase bg-card">
                            Custom
                          </span>
                        )}
                      </div>
                      <span className="text-[9px] font-mono text-secondary tracking-tight block max-w-[200px] truncate" title={cleanUrl}>
                        {cleanUrl}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-secondary leading-relaxed font-sans line-clamp-2">
                    {app.description}
                  </p>
                </div>

                <div className="flex gap-3 pt-6 border-t border-primary/5 mt-4">
                  <button
                    onClick={() => {
                      setActiveIframeUrl(appUrl);
                      setActiveIframeName(app.name);
                    }}
                    className="flex-1 py-2 border border-primary/10 hover:border-tertiary/40 bg-card hover:bg-tertiary/5 text-primary hover:text-tertiary text-[10px] font-bold uppercase tracking-wider rounded transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    View
                  </button>
                  <a
                    href={appUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 py-2 border border-primary/10 hover:border-accent/40 bg-card hover:bg-accent/5 text-primary hover:text-accent text-[10px] font-bold uppercase tracking-wider rounded transition-all flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Launch
                  </a>
                  {app.isCustom && (
                    <button
                      onClick={() => handleDeleteCustomApp(app.id)}
                      className="p-2 border border-primary/5 hover:border-accent/30 text-secondary hover:text-accent bg-card hover:bg-accent/5 rounded transition-all cursor-pointer flex items-center justify-center"
                      title="Remove App"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </motion.div>
            );
          })}

          {/* ADD CUSTOM APP CARD */}
          {!isAddingCustom ? (
            <button
              onClick={() => setIsAddingCustom(true)}
              className="border border-dashed border-primary/10 hover:border-tertiary/40 bg-transparent rounded-md p-6 transition-all flex flex-col items-center justify-center group min-h-[220px] cursor-pointer hover:bg-sand/10"
            >
              <div className="w-12 h-12 rounded-full border border-dashed border-primary/15 group-hover:border-tertiary/30 flex items-center justify-center group-hover:bg-tertiary/5 transition-all text-secondary group-hover:text-tertiary mb-3">
                <Plus className="w-5 h-5" />
              </div>
              <span className="font-serif italic font-bold text-sm text-secondary group-hover:text-primary">
                Add Custom Webapp
              </span>
              <span className="text-[9px] font-mono text-secondary/50 uppercase tracking-widest mt-1">
                Local storage register
              </span>
            </button>
          ) : (
            <motion.div
              layout
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-card border border-tertiary/20 rounded-md p-6 artisan-shadow flex flex-col justify-between min-h-[220px]"
            >
              <form onSubmit={handleAddCustomApp} className="space-y-3.5 flex-1 flex flex-col justify-between">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-tertiary uppercase tracking-widest font-bold">
                      New Custom App
                    </span>
                    <button 
                      type="button" 
                      onClick={() => setIsAddingCustom(false)} 
                      className="text-secondary hover:text-accent transition-colors cursor-pointer"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="space-y-2">
                    <input
                      type="text"
                      placeholder="App Name (e.g. Jenkins)"
                      value={newAppName}
                      onChange={(e) => setNewAppName(e.target.value)}
                      required
                      maxLength={50}
                      className="w-full px-3 py-1.5 text-xs border border-primary/10 rounded focus:border-tertiary/50 bg-neutral/30 focus:outline-none text-primary"
                    />
                    <input
                      type="text"
                      placeholder="App Description"
                      value={newAppDesc}
                      onChange={(e) => setNewAppDesc(e.target.value)}
                      maxLength={200}
                      className="w-full px-3 py-1.5 text-xs border border-primary/10 rounded focus:border-tertiary/50 bg-neutral/30 focus:outline-none text-primary"
                    />
                    <input
                      type="text"
                      placeholder="http://192.168.1.100:9090"
                      value={newAppUrl}
                      onChange={(e) => setNewAppUrl(e.target.value)}
                      required
                      className="w-full px-3 py-1.5 text-xs border border-primary/10 rounded focus:border-tertiary/50 bg-neutral/30 focus:outline-none font-mono text-primary"
                    />
                  </div>
                </div>

                <div className="flex gap-3 pt-3">
                  <button
                    type="button"
                    onClick={() => setIsAddingCustom(false)}
                    className="flex-1 py-1.5 border border-primary/5 bg-neutral/50 text-secondary text-[10px] font-bold uppercase tracking-wider rounded transition-all cursor-pointer hover:bg-neutral"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-1.5 border border-tertiary/20 bg-tertiary text-white text-[10px] font-bold uppercase tracking-wider rounded transition-all cursor-pointer hover:bg-tertiary/90 flex items-center justify-center gap-1"
                  >
                    <Check className="w-3.5 h-3.5" />
                    Save App
                  </button>
                </div>
              </form>
            </motion.div>
          )}
        </div>


      </main>

      {/* EMBEDDED IFRAME SHELL DRAWER - Rendered via Portal to escape all stacking contexts */}
      {typeof document !== "undefined" && createPortal(
        <AnimatePresence>
          {activeIframeUrl && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-neutral/65 backdrop-blur-md z-[9999] flex flex-col p-4 lg:p-8"
            >
              <div className="bg-card border border-primary/10 rounded-lg flex-1 flex flex-col shadow-2xl relative overflow-hidden">
                {/* Iframe Header */}
                <div className="h-14 border-b border-primary/5 px-6 flex items-center justify-between bg-card/90 shrink-0">
                  <div className="flex items-center gap-3">
                    <div className="w-2.5 h-2.5 rounded-full bg-tertiary animate-pulse" />
                    <span className="font-serif italic font-bold text-sm text-primary">
                      {activeIframeName}
                    </span>
                    <span className="text-[10px] font-mono text-secondary hidden sm:inline px-2 py-0.5 border border-primary/5 rounded bg-neutral/40">
                      {activeIframeUrl.split("?")[0]}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setIframeKey(k => k + 1)}
                      className="p-1.5 border border-border hover:border-tertiary bg-card rounded transition-all text-secondary hover:text-tertiary cursor-pointer"
                      title="Reload Iframe"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                    <a
                      href={activeIframeUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 border border-border hover:border-accent bg-card rounded transition-all text-secondary hover:text-accent cursor-pointer"
                      title="Open in New Tab"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                    <div className="w-[1px] h-5 bg-primary/10 mx-1" />
                    <button
                      onClick={() => {
                        setActiveIframeUrl(null);
                        setActiveIframeName("");
                      }}
                      className="p-1.5 border border-border hover:border-accent hover:bg-accent/5 bg-card rounded transition-all text-secondary hover:text-accent cursor-pointer"
                      title="Close Portal"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Iframe Viewport. Sandbox note: allow-same-origin + allow-scripts
                    together is equivalent to NO sandbox for the framed document —
                    required because Gitea/Planka need cookies + JS to function.
                    Actual isolation relies on the cross-origin boundary (apps run
                    on different ports/origins than this dashboard). */}
                <div className="flex-1 bg-neutral/20 relative">
                  <iframe
                    key={iframeKey}
                    src={activeIframeUrl}
                    className="w-full h-full border-none bg-white"
                    title={activeIframeName}
                    referrerPolicy="no-referrer"
                    sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
                  />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}
