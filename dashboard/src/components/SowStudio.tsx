"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { 
  FileText, 
  Save, 
  Copy, 
  Printer, 
  Plus, 
  Trash2, 
  Check, 
  AlertCircle, 
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Calendar, 
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  User, 
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Briefcase,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Layers,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Sparkles,
  CheckCircle2,
  Circle,
  ArrowDownToLine,
  ChevronDown,
  ChevronRight,
  Edit3,
  Eye,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Clock,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Target as TargetIcon,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ShieldCheck,
  CheckSquare,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Filter,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ListFilter,
  Zap
} from "lucide-react";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";

export interface SOWProject {
  id: string;
  name: string;
  boardId?: string;
}

export interface BoardList {
  id: string;
  name: string;
}

export interface BoardCard {
  id: string;
  listId: string;
  name: string;
  description: string;
  isClosed?: boolean;
}

const DEFAULT_PROJECTS: SOWProject[] = [
  { id: "1821314860437210840", name: "NeverMiss.ai", boardId: "1821314980880844507" },
  { id: "1814746128873162572", name: "CRG Backoffice", boardId: "1814746129032546126" },
  { id: "1803497645411402763", name: "Kenbun Workspace", boardId: "1803497714239931407" },
  { id: "1816489008423765798", name: "Claude Corps Fellowship", boardId: "1816489052271019820" },
  { id: "1829876127221417883", name: "Webull Trading", boardId: "1829876156405385119" }
];

export type PricingModel = "internal_operational" | "turnkey_fixed" | "milestone_based" | "time_and_materials";

export interface DeliverableEpic {
  id: number | string;
  title: string;
  details: string;
  category?: string;
  status?: "pending" | "in_progress" | "completed";
  completed?: boolean;
}

export interface Target {
  label: string;
  value: string;
}

export interface SOWMeta {
  client: string;
  consultant: string;
  date: string;
  target_date: string;
  overview: string;
  pricing_model: PricingModel;
  // Fixed / Turnkey fields
  total_budget: string;
  material_cost: string;
  labor_cost: string;
  // Time & Materials fields
  hourly_rate: string;
  weekly_hours: string;
  total_hours: string;
  // Metrics & Prerequisites
  targets: Target[];
  prereqs: string[];
}

const EMPTY_META: SOWMeta = {
  client: "",
  consultant: "Carlos Rivas (CRG Flooring LLC)",
  date: new Date().toISOString().split("T")[0],
  target_date: "",
  overview: "",
  pricing_model: "internal_operational",
  total_budget: "",
  material_cost: "",
  labor_cost: "",
  hourly_rate: "",
  weekly_hours: "",
  total_hours: "",
  targets: [],
  prereqs: [],
};

interface SowStudioProps {
  projectId?: string;
  projectName?: string;
  availableProjects?: SOWProject[];
  boardLists?: BoardList[];
  boardCards?: BoardCard[];
}

export default function SowStudio({ 
  projectId: initialProjectId, 
  projectName, 
  availableProjects = DEFAULT_PROJECTS,
  boardLists,
  boardCards
}: SowStudioProps) {
  const API_BASE = CONFIG.API_BASE;
  const [selectedProjectId, setSelectedProjectId] = useState(initialProjectId || availableProjects[0]?.id || "");
  const [title, setTitle] = useState("");
  const [meta, setMeta] = useState<SOWMeta>({ ...EMPTY_META });
  const [epics, setEpics] = useState<DeliverableEpic[]>([]);
  const [content, setContent] = useState("");

  const [isEditMode, setIsEditMode] = useState(false);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "completed">("all");
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    if (initialProjectId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedProjectId(initialProjectId);
    }
  }, [initialProjectId]);

  const activeProject = availableProjects.find((p) => p.id === selectedProjectId) || {
    id: selectedProjectId,
    name: projectName || "Active Project",
    boardId: ""
  };

  const showToast = (msg: string): void => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const loadSOW = useCallback(async (pid: string): Promise<void> => {
    if (!pid) return;
    setLoading(true);
    setError(null);
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/sow?project_id=${encodeURIComponent(pid)}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(8000),
      });
      if (!res.ok) throw new Error("Failed to load SOW details from server.");
      const data = await res.json();
      const m = data.meta || {};
      
      setTitle(data.title || `Statement of Work: ${activeProject.name}`);
      setContent(data.content || "");
      
      // Normalize epics
      const rawEpics = Array.isArray(data.epics) ? data.epics : [];
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const normalizedEpics: DeliverableEpic[] = rawEpics.map((e: any, idx: number) => {
        const isDone = Boolean(e.completed || e.status === "completed");
        return {
          id: e.id || `epic-${Date.now()}-${idx}`,
          title: e.title ? String(e.title).trim() : "Deliverable",
          details: e.details ? String(e.details).trim() : "",
          category: e.category ? String(e.category).trim() : "General Scope",
          status: isDone ? "completed" : (e.status || "pending"),
          completed: isDone,
        };
      });
      setEpics(normalizedEpics);

      // Auto-expand all categories by default
      const initialExpanded: Record<string, boolean> = {};
      normalizedEpics.forEach((e) => {
        const cat = e.category || "General Scope";
        initialExpanded[cat] = true;
      });
      setExpandedCategories(initialExpanded);

      // Determine initial pricing model
      let inferredModel: PricingModel = m.pricing_model || "internal_operational";
      if (!m.pricing_model) {
        if (m.material_cost || m.material_sku || m.material_subtotal) {
          inferredModel = "turnkey_fixed";
        } else if (m.hourly_rate && m.total_hours && parseFloat(m.hourly_rate) > 0) {
          inferredModel = "time_and_materials";
        } else {
          inferredModel = "internal_operational";
        }
      }

      setMeta({
        client: m.client ?? "",
        consultant: m.consultant ?? "Carlos Rivas (CRG Flooring LLC)",
        date: m.date ?? new Date().toISOString().split("T")[0],
        target_date: m.target_date ?? "",
        overview: m.overview ?? "",
        pricing_model: inferredModel,
        total_budget: m.total_budget ?? (m.material_subtotal ? String(m.material_subtotal) : ""),
        material_cost: m.material_cost ?? (m.material_subtotal ? String(m.material_subtotal) : ""),
        labor_cost: m.labor_cost ?? "",
        hourly_rate: m.hourly_rate ?? "",
        weekly_hours: m.weekly_hours ?? "",
        total_hours: m.total_hours ?? "",
        targets: Array.isArray(m.targets) ? m.targets : [],
        prereqs: Array.isArray(m.prereqs) ? m.prereqs : [],
      });
      setSavedAt(data.updated_at || null);
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (e) {
      setError("Unable to load SOW data. Please check your network connection.");
    } finally {
      setLoading(false);
    }
  }, [API_BASE, activeProject.name]);

  useEffect(() => {
      // eslint-disable-next-line react-hooks/set-state-in-effect
    loadSOW(selectedProjectId);
  }, [selectedProjectId, loadSOW]);

  const saveSOW = async (): Promise<void> => {
    setSaving(true);
    setError(null);
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/sow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(8000),
        body: JSON.stringify({
          project_id: activeProject.id,
          project_name: activeProject.name,
          board_id: activeProject.boardId,
          title,
          content,
          epics,
          meta,
        }),
      });
      if (!res.ok) throw new Error("Failed to save SOW.");
      const data = await res.json();
      setSavedAt(data?.sow?.updated_at || new Date().toISOString());
      showToast("Statement of Work saved successfully.");
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (e) {
      setError("Unable to save SOW data. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const setMetaField = <K extends keyof SOWMeta>(k: K, v: SOWMeta[K]): void => {
    setMeta((prev) => ({ ...prev, [k]: v }));
  };

  const completedEpicsCount = useMemo(() => {
    return epics.filter((e) => e.completed || e.status === "completed").length;
  }, [epics]);

  const progressPercent = epics.length > 0 ? Math.round((completedEpicsCount / epics.length) * 100) : 0;

  const toggleEpicCompletion = (id: number | string): void => {
    setEpics((prev) =>
      prev.map((e) => {
        if (e.id === id) {
          const nextCompleted = !e.completed;
          return {
            ...e,
            completed: nextCompleted,
            status: nextCompleted ? "completed" : "pending",
          };
        }
        return e;
      })
    );
  };

  const toggleCategoryExpand = (cat: string): void => {
    setExpandedCategories((prev) => ({
      ...prev,
      [cat]: !prev[cat],
    }));
  };

  const importFromBoardCards = (): void => {
    if (!boardCards || boardCards.length === 0) {
      showToast("No active cards detected on this board.");
      return;
    }
    const listMap = new Map((boardLists || []).map((l) => [l.id, l.name]));
    const imported: DeliverableEpic[] = boardCards.map((card, idx) => {
      const listName = listMap.get(card.listId) || "To Do";
      const isDone = Boolean(card.isClosed || listName.toLowerCase().includes("done") || listName.toLowerCase().includes("completed"));
      const isInProgress = Boolean(listName.toLowerCase().includes("progress") || listName.toLowerCase().includes("doing"));
      
      const safeId = card.id 
        ? `card-${card.id}` 
        : (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" 
            ? crypto.randomUUID() 
            : `epic-${Date.now()}-${idx}-${Math.random().toString(36).slice(2, 7)}`);

      return {
        id: safeId,
        title: card.name ? String(card.name).trim() : "Deliverable",
        details: card.description ? String(card.description).trim() : `Deliverable tracked under Kanban list: ${listName}`,
        category: listName,
        status: isDone ? "completed" : isInProgress ? "in_progress" : "pending",
        completed: isDone,
      };
    });

    setEpics(imported);

    const newExpanded: Record<string, boolean> = {};
    imported.forEach((e) => {
      newExpanded[e.category || "General Scope"] = true;
    });
    setExpandedCategories(newExpanded);
    showToast(`Successfully synchronized ${imported.length} deliverables from board.`);
  };

  const addEpic = (defaultCategory?: string): void => {
    const newId = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" 
      ? crypto.randomUUID() 
      : `epic-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const cat = defaultCategory || "Scope of Work";
    setEpics((e) => [
      ...e,
      {
        id: newId,
        title: "New Scope Deliverable",
        details: "Describe implementation requirements, technical architecture, and verification criteria.",
        category: cat,
        status: "pending",
        completed: false,
      },
    ]);
    setExpandedCategories((prev) => ({ ...prev, [cat]: true }));
  };

  const removeEpic = (id: number | string): void => setEpics((e) => e.filter((x) => x.id !== id));
  const addPrereq = (): void => setMetaField("prereqs", [...meta.prereqs, ""]);
  const removePrereq = (i: number): void => setMetaField("prereqs", meta.prereqs.filter((_, idx) => idx !== i));
  const addTarget = (): void => setMetaField("targets", [...meta.targets, { label: "", value: "" }]);
  const removeTarget = (i: number): void => setMetaField("targets", meta.targets.filter((_, idx) => idx !== i));

  const handlePrint = (): void => window.print();

  const handleCopyMarkdown = (): void => {
    let commercialSection = "";
    if (meta.pricing_model === "internal_operational") {
      commercialSection = `### 3. PROJECT TIMELINE & OPERATIONAL SCOPE
- Execution Mode: Internal Operational Engine
- Scope Completion: ${completedEpicsCount} of ${epics.length} Deliverables Completed (${progressPercent}%)
- Target Delivery Date: ${meta.target_date || "Continuous Release"}`;
    } else if (meta.pricing_model === "turnkey_fixed") {
      const total = parseFloat(meta.total_budget) || ((parseFloat(meta.material_cost) || 0) + (parseFloat(meta.labor_cost) || 0));
      commercialSection = `### 3. TURNKEY BUDGET & COMMERCIAL TERMS
- Total Project Value: $${total.toLocaleString("en-US", { minimumFractionDigits: 2 })}
- Material / Direct Cost: $${parseFloat(meta.material_cost || "0").toLocaleString("en-US", { minimumFractionDigits: 2 })}
- Labor & Installation Scope: $${parseFloat(meta.labor_cost || "0").toLocaleString("en-US", { minimumFractionDigits: 2 })}
- Target Delivery Date: ${meta.target_date || "TBD"}`;
    } else if (meta.pricing_model === "milestone_based") {
      commercialSection = `### 3. MILESTONE PAYMENT SCHEDULE
- Total Fixed Budget: $${parseFloat(meta.total_budget || "0").toLocaleString("en-US", { minimumFractionDigits: 2 })}
- Payout Structure: Milestone-based sign-off upon acceptance of deliverable epics.
- Target Delivery Date: ${meta.target_date || "TBD"}`;
    } else {
      const rate = parseFloat(meta.hourly_rate) || 0;
      const hours = parseFloat(meta.total_hours) || 0;
      const total = rate * hours;
      commercialSection = `### 3. TIMELINE, RATE & BILLING TERMS
- Hourly Rate: $${meta.hourly_rate} / hr
- Work Pacing: ~${meta.weekly_hours} hours/wk
- Estimated Total Effort: ~${meta.total_hours} Hours ($${total.toLocaleString("en-US", { minimumFractionDigits: 2 })} Total Value)
- Invoicing: Weekly billing based on logged effort.`;
    }

    const mdText = `# STATEMENT OF WORK (SOW)
## ${title || activeProject.name}

**Date:** ${meta.date}
**Project / Board:** ${activeProject.name}
**Client / Stakeholder:** ${meta.client || "Internal Operations"}
**Lead Architect / Consultant:** ${meta.consultant}

---

### 1. PROJECT OBJECTIVE & SCOPE OVERVIEW
${meta.overview || "No overview provided."}

${meta.targets.length ? "**Key Performance Targets & SLAs:**\n" + meta.targets.map((t) => `- ${t.label}: ${t.value}`).join("\n") : ""}

---

### 2. SCOPE OF WORK & DELIVERABLES CHECKLIST (${completedEpicsCount}/${epics.length} Completed)
${epics.map((e, idx) => `${idx + 1}. [${e.completed ? "x" : " "}] **${e.title}**${e.category ? ` *(${e.category})*` : ""}\n   ${e.details}`).join("\n\n")}

---

${commercialSection}

---

### 4. PREREQUISITES & DEPENDENCIES
${meta.prereqs.length ? meta.prereqs.map((p, i) => `${i + 1}. ${p}`).join("\n") : "None specified."}

---

### 5. SIGNATURES & SCOPE ACCEPTANCE
Lead Architect / Project Owner: ${meta.consultant} | Date: ${meta.date}
Client / Stakeholder: ${meta.client || "CRG Operations"} | Date: _______________
`;
    navigator.clipboard.writeText(mdText);
    setCopied(true);
    showToast("Statement of Work copied to clipboard as Markdown.");
    setTimeout(() => setCopied(false), 2500);
  };

  // Group epics by category/stream
  const groupedEpics = useMemo(() => {
    const groups: Record<string, DeliverableEpic[]> = {};
    
    // Filter first
    const filtered = epics.filter((e) => {
      if (statusFilter === "completed") return e.completed || e.status === "completed";
      if (statusFilter === "active") return !e.completed && e.status !== "completed";
      return true;
    });

    filtered.forEach((e) => {
      const cat = e.category || "General Scope";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(e);
    });

    return groups;
  }, [epics, statusFilter]);

  const categoryKeys = Object.keys(groupedEpics);

  const handleDispatchToKanban = async (): Promise<void> => {
    if (!selectedProjectId) return;
    setDispatching(true);
    setError(null);
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/sow/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: selectedProjectId,
          board_id: activeProject.boardId || undefined,
          target_list_name: "Backlog"
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Dispatch failed");
      showToast(data.message || `Dispatched ${data.dispatched_count} cards to Kanban.`);
      await loadSOW(selectedProjectId);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      setError(err.message || "Failed to dispatch SOW to Kanban.");
    } finally {
      setDispatching(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6 text-foreground pb-20">
      {/* TOAST NOTIFICATION */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-primary text-neutral px-4 py-2.5 rounded-md shadow-xl border border-primary/20 flex items-center gap-2 text-xs font-mono animate-in fade-in slide-in-from-bottom-2 duration-200">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* TOP CONTROL BAR */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 sm:p-4 border border-border/40 bg-card/40 backdrop-blur-md rounded-md artisan-shadow print:hidden">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 border border-tertiary/30 bg-tertiary/10 rounded-md flex items-center justify-center text-tertiary shrink-0">
            <FileText className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-tertiary">SOW Specification</span>
              {savedAt && (
                <span className="text-[9px] font-mono opacity-40">
                  · {new Date(savedAt).toLocaleTimeString()}
                </span>
              )}
            </div>
            <div className="text-xs font-serif font-bold text-primary truncate max-w-xs sm:max-w-md">
              {activeProject.name}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          {boardCards && boardCards.length > 0 && (
            <button
              onClick={importFromBoardCards}
              title="Sync deliverables from active Kanban board cards"
              className="px-2.5 py-1.5 bg-tertiary/10 border border-tertiary/30 hover:bg-tertiary/20 text-tertiary text-[10px] font-mono font-bold rounded-md transition-all active:scale-95 flex items-center gap-1.5 cursor-pointer"
            >
              <ArrowDownToLine className="w-3.5 h-3.5" />
              Sync Cards ({boardCards.length})
            </button>
          )}

          <button
            onClick={handleDispatchToKanban}
            disabled={dispatching || !activeProject.boardId}
            title="Dispatch unfinished SOW deliverables into Planka Kanban cards"
            className="px-2.5 py-1.5 bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 text-emerald-600 text-[10px] font-mono font-bold rounded-md transition-all active:scale-95 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <Zap className="w-3.5 h-3.5" />
            {dispatching ? "Dispatching..." : "Dispatch to Kanban"}
          </button>

          <button
            onClick={() => setIsEditMode(!isEditMode)}
            className={`px-2.5 py-1.5 border text-[10px] font-mono font-bold rounded-md transition-all active:scale-95 flex items-center gap-1.5 cursor-pointer ${
              isEditMode 
                ? "bg-tertiary text-neutral border-tertiary" 
                : "border-border/60 text-secondary hover:text-primary hover:bg-card"
            }`}
          >
            {isEditMode ? <Eye className="w-3.5 h-3.5" /> : <Edit3 className="w-3.5 h-3.5" />}
            {isEditMode ? "Document View" : "Edit Scope"}
          </button>

          <button
            onClick={handleCopyMarkdown}
            className="px-2.5 py-1.5 border border-border/60 hover:border-tertiary/50 text-[10px] font-mono rounded-md transition-all active:scale-95 flex items-center gap-1.5 cursor-pointer text-secondary hover:text-primary hover:bg-card"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5 opacity-60" />}
            Copy MD
          </button>

          <button
            onClick={handlePrint}
            className="px-2.5 py-1.5 border border-border/60 hover:border-tertiary/50 text-[10px] font-mono rounded-md transition-all active:scale-95 flex items-center gap-1.5 cursor-pointer text-secondary hover:text-primary hover:bg-card"
          >
            <Printer className="w-3.5 h-3.5 opacity-60" />
            PDF
          </button>

          <button
            onClick={saveSOW}
            disabled={saving}
            className="px-3.5 py-1.5 bg-primary hover:bg-primary/90 text-neutral font-bold text-[10px] font-mono rounded-md transition-all active:scale-95 flex items-center gap-1.5 disabled:opacity-50 cursor-pointer shadow-xs"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 border border-red-500/30 bg-red-500/10 rounded-md flex items-center gap-3 text-red-500 text-xs font-mono">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SOW SPECIFICATION DOCUMENT CANVAS (Clean Editorial Style)                 */}
      {/* ========================================================================= */}
      <div 
        id="sow-printable-doc"
        className="p-6 sm:p-10 md:p-12 border border-border/60 bg-card/60 rounded-md shadow-sm space-y-10 print:p-0 print:border-none print:bg-white print:text-slate-900 print:shadow-none"
      >
        {/* DOCUMENT HEADER */}
        <header className="border-b border-border/60 pb-6 space-y-3 print:border-slate-300">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold uppercase tracking-[0.25em] text-tertiary print:text-amber-900">
              Statement of Work · Scope Specification
            </span>
            <span className="text-[10px] font-mono text-secondary/60 print:text-slate-500 uppercase tracking-widest">
              Confidential · Commercial Scope
            </span>
          </div>

          {isEditMode ? (
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Statement of Work Title"
              className="w-full bg-transparent border-b border-tertiary/40 pb-1 text-2xl sm:text-3xl font-serif font-bold text-primary focus:outline-none placeholder:opacity-20"
            />
          ) : (
            <h1 className="text-2xl sm:text-3xl font-serif font-bold text-primary tracking-tight leading-snug">
              {title || `Statement of Work: ${activeProject.name}`}
            </h1>
          )}

          {/* Metadata Summary Pill Bar */}
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <span className="px-2.5 py-1 bg-neutral/80 border border-border rounded-sm text-[10px] font-mono text-secondary">
              <strong className="text-primary font-semibold">Scope:</strong> {activeProject.name}
            </span>
            <span className="px-2.5 py-1 bg-neutral/80 border border-border rounded-sm text-[10px] font-mono text-secondary">
              <strong className="text-primary font-semibold">Owner:</strong> {meta.consultant || "Carlos Rivas"}
            </span>
            <span className="px-2.5 py-1 bg-neutral/80 border border-border rounded-sm text-[10px] font-mono text-secondary">
              <strong className="text-primary font-semibold">Date:</strong> {meta.date}
            </span>
            <span className="px-2.5 py-1 bg-tertiary/10 border border-tertiary/30 rounded-sm text-[10px] font-mono text-tertiary font-bold">
              {completedEpicsCount}/{epics.length} Deliverables Done ({progressPercent}%)
            </span>
          </div>
        </header>

        {/* PROGRESS BANNER */}
        <div className="p-4 rounded-md border border-border/60 bg-neutral/40 space-y-2 print:border-slate-200 print:bg-slate-50">
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="font-bold uppercase tracking-wider text-secondary flex items-center gap-2">
              <CheckSquare className="w-3.5 h-3.5 text-tertiary" />
              Delivery Progress
            </span>
            <span className="text-primary font-bold">{completedEpicsCount} of {epics.length} Completed ({progressPercent}%)</span>
          </div>
          <div className="w-full h-2 bg-neutral rounded-full overflow-hidden border border-border/40">
            <div 
              className="h-full bg-tertiary transition-all duration-300 rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* SECTION 1: OBJECTIVES & SCOPE OVERVIEW */}
        <section className="space-y-4">
          <div className="flex items-center gap-3">
            <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary print:text-amber-900">
              1. Executive Objective & Strategic Scope
            </h2>
            <div className="flex-1 h-[1px] bg-border/60 print:bg-slate-300" />
          </div>

          {isEditMode ? (
            <textarea
              rows={3}
              value={meta.overview}
              onChange={(e) => setMetaField("overview", e.target.value)}
              placeholder="Describe primary business objectives, scope background, and strategic goals for this engagement..."
              className="w-full bg-neutral/60 border border-border rounded-md p-4 text-xs font-mono text-primary focus:outline-none focus:border-tertiary leading-relaxed"
            />
          ) : (
            <div className="text-xs sm:text-sm text-secondary font-sans leading-relaxed whitespace-pre-wrap bg-neutral/20 p-4 rounded-md border border-border/40">
              {meta.overview || "This Statement of Work defines the technical architecture, execution deliverables, and operational milestones required to complete and deploy the project specifications."}
            </div>
          )}

          {/* Performance Targets / SLAs */}
          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase text-secondary/70 font-bold">
                Target Metrics & SLAs:
              </span>
              {isEditMode && (
                <button
                  type="button"
                  onClick={addTarget}
                  className="text-[10px] font-mono text-tertiary hover:underline flex items-center gap-1 cursor-pointer"
                >
                  <Plus className="w-3 h-3" /> Add SLA
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {meta.targets.map((t, idx) => (
                <div key={idx} className="p-3 border border-border/60 bg-neutral/30 rounded-md flex items-center justify-between gap-2 print:bg-slate-50 print:border-slate-200">
                  {isEditMode ? (
                    <>
                      <input
                        type="text"
                        value={t.label}
                        onChange={(e) => {
                          const updated = [...meta.targets];
                          updated[idx].label = e.target.value;
                          setMetaField("targets", updated);
                        }}
                        placeholder="Metric label"
                        className="w-1/2 bg-transparent text-xs font-mono text-secondary focus:outline-none"
                      />
                      <span className="opacity-30">:</span>
                      <input
                        type="text"
                        value={t.value}
                        onChange={(e) => {
                          const updated = [...meta.targets];
                          updated[idx].value = e.target.value;
                          setMetaField("targets", updated);
                        }}
                        placeholder="Target value"
                        className="w-1/2 bg-transparent text-xs font-mono font-bold text-tertiary focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => removeTarget(idx)}
                        className="p-1 text-red-500 hover:opacity-100 opacity-60 cursor-pointer"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="text-xs font-mono text-secondary">{t.label || "Target SLA"}</span>
                      <span className="text-xs font-mono font-bold text-tertiary print:text-slate-900">{t.value || "—"}</span>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* SECTION 2: SCOPE OF WORK & DELIVERABLES CHECKLIST */}
        <section className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary print:text-amber-900">
                2. Scope of Work (Deliverables Matrix)
              </h2>
              <div className="w-12 h-[1px] bg-border/60 print:bg-slate-300" />
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1 bg-neutral/60 p-0.5 rounded-md border border-border/40 print:hidden">
              <button
                type="button"
                onClick={() => setStatusFilter("all")}
                className={`px-2.5 py-1 text-[9px] font-mono uppercase font-bold rounded-sm cursor-pointer transition-colors ${
                  statusFilter === "all" ? "bg-primary text-neutral shadow-xs" : "text-secondary hover:text-primary"
                }`}
              >
                All ({epics.length})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("active")}
                className={`px-2.5 py-1 text-[9px] font-mono uppercase font-bold rounded-sm cursor-pointer transition-colors ${
                  statusFilter === "active" ? "bg-primary text-neutral shadow-xs" : "text-secondary hover:text-primary"
                }`}
              >
                Active ({epics.length - completedEpicsCount})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("completed")}
                className={`px-2.5 py-1 text-[9px] font-mono uppercase font-bold rounded-sm cursor-pointer transition-colors ${
                  statusFilter === "completed" ? "bg-primary text-neutral shadow-xs" : "text-secondary hover:text-primary"
                }`}
              >
                Done ({completedEpicsCount})
              </button>
            </div>
          </div>

          {/* Grouped Category Streams */}
          {categoryKeys.length === 0 ? (
            <div className="text-center p-8 border border-dashed border-border rounded-md text-xs font-mono text-secondary/60">
              No deliverables recorded. Click &quot;Sync Cards&quot; or &quot;Edit Scope&quot; to populate.
            </div>
          ) : (
            <div className="space-y-6">
              {categoryKeys.map((category) => {
                const categoryEpics = groupedEpics[category] || [];
                const catDone = categoryEpics.filter((e) => e.completed || e.status === "completed").length;
                const isExpanded = expandedCategories[category] !== false;

                return (
                  <div 
                    key={category} 
                    className="border border-border/60 bg-neutral/20 rounded-md overflow-hidden print:border-slate-200 print:bg-white"
                  >
                    {/* Category Header */}
                    <button
                      type="button"
                      onClick={() => toggleCategoryExpand(category)}
                      className="w-full px-4 py-3 bg-neutral/60 hover:bg-neutral/80 border-b border-border/40 flex items-center justify-between text-left cursor-pointer transition-colors print:bg-slate-100"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-tertiary shrink-0 print:hidden" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-secondary shrink-0 print:hidden" />
                        )}
                        <span className="font-mono text-xs font-bold uppercase tracking-wider text-primary truncate">
                          {category}
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-card border border-border text-secondary shrink-0">
                          {catDone}/{categoryEpics.length} Completed
                        </span>
                      </div>

                      {isEditMode && (
                        <div 
                          onClick={(e) => e.stopPropagation()} 
                          className="flex items-center gap-2"
                        >
                          <button
                            type="button"
                            onClick={() => addEpic(category)}
                            className="px-2 py-0.5 text-[9px] font-mono text-tertiary hover:underline flex items-center gap-1 cursor-pointer"
                          >
                            <Plus className="w-3 h-3" /> Add Item
                          </button>
                        </div>
                      )}
                    </button>

                    {/* Category Items List */}
                    {isExpanded && (
                      <div className="divide-y divide-border/40">
                        {categoryEpics.map((epic) => (
                          <div 
                            key={epic.id} 
                            className={`p-3.5 sm:p-4 transition-colors ${
                              epic.completed ? "bg-emerald-500/[0.02]" : "hover:bg-card/40"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              {/* Checkbox and Title */}
                              <div className="flex items-start gap-3 flex-1 min-w-0">
                                <button
                                  type="button"
                                  onClick={() => toggleEpicCompletion(epic.id)}
                                  className="mt-0.5 text-secondary hover:text-tertiary transition-colors cursor-pointer shrink-0 print:hidden"
                                  title={epic.completed ? "Mark pending" : "Mark completed"}
                                >
                                  {epic.completed ? (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                  ) : (
                                    <Circle className="w-4 h-4 text-secondary/40" />
                                  )}
                                </button>

                                <span className="hidden print:inline-block text-xs font-mono font-bold text-slate-800 shrink-0">
                                  [{epic.completed ? "✓" : " "}]
                                </span>

                                <div className="space-y-1 flex-1 min-w-0">
                                  {isEditMode ? (
                                    <input
                                      type="text"
                                      value={epic.title}
                                      onChange={(e) => {
                                        const updated = epics.map((item) =>
                                          item.id === epic.id ? { ...item, title: e.target.value } : item
                                        );
                                        setEpics(updated);
                                      }}
                                      placeholder="Deliverable title"
                                      className="w-full bg-transparent border-b border-border text-xs sm:text-sm font-semibold text-primary focus:outline-none focus:border-tertiary"
                                    />
                                  ) : (
                                    <div className={`text-xs sm:text-sm font-serif font-bold ${
                                      epic.completed ? "text-secondary line-through opacity-70" : "text-primary"
                                    }`}>
                                      {epic.title}
                                    </div>
                                  )}

                                  {/* Details / Description */}
                                  {isEditMode ? (
                                    <textarea
                                      rows={2}
                                      value={epic.details}
                                      onChange={(e) => {
                                        const updated = epics.map((item) =>
                                          item.id === epic.id ? { ...item, details: e.target.value } : item
                                        );
                                        setEpics(updated);
                                      }}
                                      placeholder="Implementation details and acceptance criteria..."
                                      className="w-full bg-neutral/60 border border-border rounded-md p-2 text-xs font-mono text-secondary focus:outline-none focus:border-tertiary mt-1"
                                    />
                                  ) : epic.details ? (
                                    <p className="text-[11px] sm:text-xs font-mono text-secondary/80 leading-relaxed whitespace-pre-wrap pt-0.5">
                                      {epic.details}
                                    </p>
                                  ) : null}
                                </div>
                              </div>

                              {/* Status Badge & Delete in Edit Mode */}
                              <div className="flex items-center gap-2 shrink-0">
                                <span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded-sm font-bold ${
                                  epic.completed 
                                    ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20" 
                                    : epic.status === "in_progress"
                                    ? "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                                    : "bg-neutral text-secondary border border-border"
                                }`}>
                                  {epic.completed ? "Done" : (epic.status === "in_progress" ? "In Progress" : "Pending")}
                                </span>

                                {isEditMode && (
                                  <button
                                    type="button"
                                    onClick={() => removeEpic(epic.id)}
                                    className="p-1 text-red-500 hover:opacity-100 opacity-60 cursor-pointer"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {isEditMode && (
            <button
              type="button"
              onClick={() => addEpic("New Stream")}
              className="w-full py-2.5 border border-dashed border-tertiary/40 rounded-md text-center text-xs font-mono font-bold text-tertiary hover:bg-tertiary/5 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <Plus className="w-4 h-4" /> Add Deliverable Stream
            </button>
          )}
        </section>

        {/* SECTION 3: PROJECT TIMELINE & COMMERCIAL TERMS */}
        <section className="space-y-4 pt-2">
          <div className="flex items-center gap-3">
            <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary print:text-amber-900">
              3. Execution Timeline & Commercial Model
            </h2>
            <div className="flex-1 h-[1px] bg-border/60 print:bg-slate-300" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-md border border-border/60 bg-neutral/30 space-y-1">
              <span className="text-[9px] font-mono uppercase text-secondary/70 font-bold block">Execution Model</span>
              <div className="text-xs font-mono font-bold text-primary">
                {meta.pricing_model === "internal_operational" ? "Internal Operational Engine" : meta.pricing_model}
              </div>
            </div>

            <div className="p-4 rounded-md border border-border/60 bg-neutral/30 space-y-1">
              <span className="text-[9px] font-mono uppercase text-secondary/70 font-bold block">Target Delivery</span>
              {isEditMode ? (
                <input
                  type="date"
                  value={meta.target_date}
                  onChange={(e) => setMetaField("target_date", e.target.value)}
                  className="bg-transparent border-b border-border text-xs font-mono text-primary focus:outline-none focus:border-tertiary w-full"
                />
              ) : (
                <div className="text-xs font-mono text-secondary">
                  {meta.target_date || "Continuous Deployment"}
                </div>
              )}
            </div>

            <div className="p-4 rounded-md border border-border/60 bg-neutral/30 space-y-1">
              <span className="text-[9px] font-mono uppercase text-secondary/70 font-bold block">Deliverable Tally</span>
              <div className="text-xs font-mono font-bold text-tertiary">
                {completedEpicsCount} of {epics.length} Verified
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 4: PREREQUISITES & ACCESS */}
        <section className="space-y-3 pt-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary print:text-amber-900">
                4. Prerequisites & Dependencies
              </h2>
              <div className="w-12 h-[1px] bg-border/60 print:bg-slate-300" />
            </div>
            {isEditMode && (
              <button
                type="button"
                onClick={addPrereq}
                className="text-[10px] font-mono text-tertiary hover:underline flex items-center gap-1 cursor-pointer"
              >
                <Plus className="w-3 h-3" /> Add Requirement
              </button>
            )}
          </div>

          <div className="space-y-2">
            {meta.prereqs.length === 0 ? (
              <div className="text-xs font-mono text-secondary/60">No external dependencies required.</div>
            ) : (
              meta.prereqs.map((p, idx) => (
                <div key={idx} className="flex items-center gap-2 p-2.5 bg-neutral/30 rounded-md border border-border/40">
                  <span className="text-xs font-mono font-bold text-tertiary">{idx + 1}.</span>
                  {isEditMode ? (
                    <>
                      <input
                        type="text"
                        value={p}
                        onChange={(e) => {
                          const updated = [...meta.prereqs];
                          updated[idx] = e.target.value;
                          setMetaField("prereqs", updated);
                        }}
                        placeholder="Requirement or access token description"
                        className="flex-1 bg-transparent text-xs font-mono text-primary focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => removePrereq(idx)}
                        className="p-1 text-red-500 hover:opacity-100 opacity-60 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  ) : (
                    <span className="text-xs font-mono text-secondary">{p}</span>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        {/* SECTION 5: SIGNATURES & SCOPE ACCEPTANCE */}
        <section className="space-y-4 pt-4 border-t border-border/60 print:border-slate-300">
          <div className="flex items-center gap-3">
            <h2 className="text-xs font-mono font-bold uppercase tracking-[0.2em] text-tertiary print:text-amber-900">
              5. Signatures & Scope Acceptance
            </h2>
            <div className="flex-1 h-[1px] bg-border/60 print:bg-slate-300" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 pt-2">
            <div className="space-y-1.5 p-4 rounded-md bg-neutral/20 border border-border/40">
              <div className="text-[9px] font-mono uppercase text-secondary/70 font-bold">Lead Architect / Project Owner</div>
              <div className="font-serif italic font-bold text-sm text-primary">
                {meta.consultant || "Carlos Rivas (CRG Flooring LLC)"}
              </div>
              <div className="text-[9px] font-mono text-secondary/60">Date: {meta.date}</div>
            </div>

            <div className="space-y-1.5 p-4 rounded-md bg-neutral/20 border border-border/40">
              <div className="text-[9px] font-mono uppercase text-secondary/70 font-bold">Client / Stakeholder Authorization</div>
              <div className="font-serif italic font-bold text-sm text-primary">
                {meta.client || "CRG Backoffice Operations"}
              </div>
              <div className="text-[9px] font-mono text-secondary/60">Status: Verified & Accepted</div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
