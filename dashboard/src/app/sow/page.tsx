"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";

// ── Planka projects (project_id → primary board) ──────────────────────────────
// Each project has its OWN SOW row, keyed by project_id in the `sows` table.
const PROJECTS: { id: string; name: string; boardId: string }[] = [
  { id: "1821314860437210840", name: "NeverMiss.ai", boardId: "1821314980880844507" },
  { id: "1803497645411402763", name: "Kenbun (Default Workspace)", boardId: "1803497714239931407" },
  { id: "1814746128873162572", name: "CRG Backoffice", boardId: "1814746129032546126" },
  { id: "1816489008423765798", name: "Claude Corps Fellowship", boardId: "1816489052271019820" },
];

interface Epic { id: number; title: string; details: string; }
interface Target { label: string; value: string; }

const EMPTY_META = {
  client: "", consultant: "Carlos Rivas", hourly_rate: "", weekly_hours: "",
  total_hours: "", date: "", overview: "",
  targets: [] as Target[], prereqs: [] as string[],
};

export default function SOWPage() {
  const API_BASE = CONFIG.API_BASE;

  const [projectId, setProjectId] = useState(PROJECTS[0].id);
  const [title, setTitle] = useState("");
  const [meta, setMeta] = useState({ ...EMPTY_META });
  const [epics, setEpics] = useState<Epic[]>([]);
  const [content, setContent] = useState("");

  // Resolve project ID from query parameter on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const pid = params.get("project_id");
      if (pid && PROJECTS.some(p => p.id === pid)) {
        setProjectId(pid);
      }
    }
  }, []);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const project = PROJECTS.find((p) => p.id === projectId) || PROJECTS[0];

  // ── Load the selected project's SOW ────────────────────────────────────────
  const loadSOW = useCallback(async (pid: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/sow?project_id=${encodeURIComponent(pid)}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`Load failed (${res.status})`);
      const data = await res.json();
      const m = data.meta || {};
      setTitle(data.title || "");
      setContent(data.content || "");
      setEpics(Array.isArray(data.epics) ? data.epics : []);
      setMeta({
        client: m.client ?? "",
        consultant: m.consultant ?? "Carlos Rivas",
        hourly_rate: m.hourly_rate ?? "",
        weekly_hours: m.weekly_hours ?? "",
        total_hours: m.total_hours ?? "",
        date: m.date ?? "",
        overview: m.overview ?? "",
        targets: Array.isArray(m.targets) ? m.targets : [],
        prereqs: Array.isArray(m.prereqs) ? m.prereqs : [],
      });
      setSavedAt(data.updated_at || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load SOW");
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  useEffect(() => { loadSOW(projectId); }, [projectId, loadSOW]);

  // ── Save the current SOW ───────────────────────────────────────────────────
  const saveSOW = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await tenantFetch(`${API_BASE}/api/v1/sow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: project.id,
          project_name: project.name,
          board_id: project.boardId,
          title, content, epics, meta,
        }),
      });
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
      const data = await res.json();
      setSavedAt(data?.sow?.updated_at || new Date().toISOString());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save SOW");
    } finally {
      setSaving(false);
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const setMetaField = (k: keyof typeof meta, v: any) => setMeta((prev) => ({ ...prev, [k]: v }));

  const calculateTotalValue = () => {
    const rate = parseFloat(meta.hourly_rate) || 0;
    const hours = parseFloat(meta.total_hours) || 0;
    return (rate * hours).toLocaleString("en-US", { style: "currency", currency: "USD" });
  };

  // ── epics + prereqs + targets editors ──────────────────────────────────────
  const addEpic = () => setEpics((e) => [...e, { id: Date.now(), title: "New Epic", details: "" }]);
  const removeEpic = (id: number) => setEpics((e) => e.filter((x) => x.id !== id));
  const addPrereq = () => setMetaField("prereqs", [...meta.prereqs, ""]);
  const removePrereq = (i: number) => setMetaField("prereqs", meta.prereqs.filter((_, idx) => idx !== i));
  const addTarget = () => setMetaField("targets", [...meta.targets, { label: "", value: "" }]);
  const removeTarget = (i: number) => setMetaField("targets", meta.targets.filter((_, idx) => idx !== i));

  const handlePrint = () => window.print();

  const handleCopyMarkdown = () => {
    const mdText = `# STATEMENT OF WORK (SOW)
## ${title || project.name}

**Date:** ${meta.date}
**Client:** ${meta.client}
**Consultant / Architect:** ${meta.consultant}
**Project:** ${project.name}

---

### 1. PROJECT OVERVIEW & GOALS
${meta.overview}

${meta.targets.length ? "**Key Targets:**\n" + meta.targets.map((t) => `- ${t.label}: ${t.value}`).join("\n") : ""}

---

### 2. SCOPE OF WORK (DELIVERABLES)
${epics.map((e) => `#### ${e.title}\n* ${e.details}`).join("\n\n")}

---

### 3. TIMELINE, RATE & BILLING TERMS
- Hourly Rate: $${meta.hourly_rate} / hr
- Work Pacing: ~${meta.weekly_hours} hours per week
- Total Estimated Effort: ~${meta.total_hours} Hours (${calculateTotalValue()} Total Project Value)
- Invoicing: Weekly billing based on logged hours worked.

---

### 4. PREREQUISITES (CLIENT ACCESS REQUIREMENTS)
${meta.prereqs.map((p, i) => `${i + 1}. ${p}`).join("\n")}

---

### 5. SIGNATURES
Consultant: ${meta.consultant} | Date: ${meta.date}
Client: ${meta.client} | Date: _______________
`;
    navigator.clipboard.writeText(mdText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const inputCls = "w-full bg-white border border-[#E7E5E4] rounded px-3 py-1.5 text-sm font-semibold text-[#1A1C1E] focus:outline-none focus:border-[#B8422E] print:border-none print:p-0 print:bg-transparent";

  return (
    <div className="min-h-screen bg-[#FAF8F5] text-[#1A1C1E] p-4 sm:p-8 font-sans">
      {/* Top Action Header (hidden in print) */}
      <div className="print:hidden max-w-4xl mx-auto mb-8 bg-white p-4 rounded-xl border border-[#E7E5E4] shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Link href="/board" className="text-xs text-[#B8422E] hover:underline font-mono">
              &larr; Back to Kanban Board
            </Link>
            <span className="text-xs text-[#78716C]">&bull;</span>
            <span className="text-xs font-semibold text-[#1A1C1E] uppercase tracking-wider">
              SOW Studio &mdash; per project
            </span>
          </div>
          <div className="flex items-center gap-3 mt-2">
            <label className="text-xs font-bold uppercase tracking-wider text-[#78716C]">Project</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="bg-[#FAF8F5] border border-[#E7E5E4] rounded px-3 py-1.5 text-sm font-bold text-[#1A1C1E] focus:outline-none focus:border-[#B8422E] cursor-pointer"
            >
              {PROJECTS.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            {loading && <span className="text-xs text-[#78716C] animate-pulse">Loading…</span>}
            {!loading && savedAt && <span className="text-xs text-[#78716C]">Saved {new Date(savedAt).toLocaleString()}</span>}
            {error && <span className="text-xs text-[#B8422E] font-semibold">{error}</span>}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={saveSOW} disabled={saving || loading}
            className="px-5 py-2 bg-[#166534] text-white hover:bg-[#14532d] disabled:opacity-50 rounded-lg text-sm font-semibold transition-all shadow-md flex items-center gap-2 cursor-pointer">
            {saving ? "Saving…" : "💾 Save SOW"}
          </button>
          <button onClick={handleCopyMarkdown}
            className="px-4 py-2 bg-[#FAF8F5] text-[#1A1C1E] border border-[#E7E5E4] hover:bg-[#F5F2EC] rounded-lg text-sm font-semibold transition-all shadow-sm flex items-center gap-2 cursor-pointer">
            {copied ? "✓ Copied!" : "📋 Copy Markdown"}
          </button>
          <button onClick={handlePrint}
            className="px-5 py-2 bg-[#B8422E] text-white hover:bg-[#A03724] rounded-lg text-sm font-semibold transition-all shadow-md flex items-center gap-2 cursor-pointer">
            📄 Print PDF
          </button>
        </div>
      </div>

      {/* Printable Document */}
      <div className="max-w-4xl mx-auto bg-white p-8 sm:p-12 rounded-xl border border-[#E7E5E4] shadow-lg print:border-none print:shadow-none print:p-0 print:m-0">
        {/* Document Header */}
        <div className="border-b-2 border-[#1A1C1E] pb-6 mb-8">
          <div className="text-xs uppercase tracking-widest text-[#B8422E] font-bold mb-1">STATEMENT OF WORK (SOW)</div>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="SOW title…"
            className="w-full text-2xl sm:text-3xl font-extrabold text-[#1A1C1E] tracking-tight bg-transparent focus:outline-none print:border-none" />
          <div className="text-sm text-[#78716C] mt-2 font-medium">Project: {project.name}</div>
        </div>

        {/* Metadata */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 bg-[#FAF8F5] p-5 rounded-lg border border-[#E7E5E4] mb-8 print:bg-transparent print:p-0 print:border-none">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[#78716C] mb-1">Client Name &amp; Company</label>
            <input value={meta.client} onChange={(e) => setMetaField("client", e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[#78716C] mb-1">Consultant / Lead Architect</label>
            <input value={meta.consultant} onChange={(e) => setMetaField("consultant", e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[#78716C] mb-1">Date</label>
            <input value={meta.date} onChange={(e) => setMetaField("date", e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[#78716C] mb-1">Total Contract Value</label>
            <div className="text-lg font-extrabold text-[#B8422E] mt-0.5">
              {calculateTotalValue()} <span className="text-xs text-[#78716C] font-normal">(${meta.hourly_rate || 0}/hr &times; {meta.total_hours || 0} hrs)</span>
            </div>
          </div>
        </div>

        {/* Section 1: Overview + targets */}
        <section className="mb-8">
          <h2 className="text-lg font-bold text-[#1A1C1E] border-b border-[#E7E5E4] pb-2 mb-3">1. Project Overview &amp; Business Targets</h2>
          <textarea value={meta.overview} onChange={(e) => setMetaField("overview", e.target.value)} rows={3}
            placeholder="Objective of this engagement…"
            className="w-full bg-white border border-[#E7E5E4] rounded p-2 text-sm text-[#44403C] leading-relaxed focus:outline-none focus:border-[#B8422E] mb-4 print:border-none print:p-0" />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {meta.targets.map((t, i) => (
              <div key={i} className="bg-[#FAF8F5] p-3 rounded-lg border border-[#E7E5E4] print:border print:p-2 relative group">
                <input value={t.label} onChange={(e) => setMetaField("targets", meta.targets.map((x, idx) => idx === i ? { ...x, label: e.target.value } : x))}
                  placeholder="Target" className="w-full text-xs text-[#78716C] font-medium bg-transparent focus:outline-none" />
                <input value={t.value} onChange={(e) => setMetaField("targets", meta.targets.map((x, idx) => idx === i ? { ...x, value: e.target.value } : x))}
                  placeholder="Value" className="w-full text-base font-bold text-[#166534] mt-0.5 bg-transparent focus:outline-none" />
                <button onClick={() => removeTarget(i)} className="print:hidden absolute top-1 right-2 text-[#B8422E] opacity-0 group-hover:opacity-100 text-xs">✕</button>
              </div>
            ))}
            <button onClick={addTarget} className="print:hidden border border-dashed border-[#E7E5E4] rounded-lg text-xs text-[#78716C] hover:border-[#B8422E] hover:text-[#B8422E] py-3">+ Add target</button>
          </div>
        </section>

        {/* Section 2: Epics */}
        <section className="mb-8">
          <div className="flex items-center justify-between border-b border-[#E7E5E4] pb-2 mb-4">
            <h2 className="text-lg font-bold text-[#1A1C1E]">2. Scope of Work (Deliverables &amp; Epics)</h2>
            <button onClick={addEpic} className="print:hidden text-xs text-[#B8422E] font-semibold hover:underline">+ Add epic</button>
          </div>
          <div className="space-y-4">
            {epics.map((epic) => (
              <div key={epic.id} className="p-4 bg-[#FAF8F5] rounded-lg border border-[#E7E5E4] print:bg-transparent print:p-2 print:border-b relative group">
                <input type="text" value={epic.title}
                  onChange={(e) => setEpics(epics.map((it) => it.id === epic.id ? { ...it, title: e.target.value } : it))}
                  className="w-full bg-transparent font-bold text-sm text-[#1A1C1E] focus:outline-none mb-1 print:border-none" />
                <textarea value={epic.details} rows={2}
                  onChange={(e) => setEpics(epics.map((it) => it.id === epic.id ? { ...it, details: e.target.value } : it))}
                  className="w-full bg-white border border-[#E7E5E4] rounded p-2 text-xs text-[#44403C] leading-relaxed focus:outline-none focus:border-[#B8422E] print:border-none print:p-0 print:bg-transparent" />
                <button onClick={() => removeEpic(epic.id)} className="print:hidden absolute top-2 right-2 text-[#B8422E] opacity-0 group-hover:opacity-100 text-xs">✕ remove</button>
              </div>
            ))}
            {!epics.length && !loading && <p className="text-xs text-[#78716C] italic">No epics yet — add one above.</p>}
          </div>
        </section>

        {/* Section 3: Billing */}
        <section className="mb-8">
          <h2 className="text-lg font-bold text-[#1A1C1E] border-b border-[#E7E5E4] pb-2 mb-3">3. Rate, Timeline &amp; Billing Terms</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs text-[#78716C] font-semibold">Hourly Rate</label>
              <div className="flex items-center gap-1 mt-1">
                <span className="text-sm font-bold">$</span>
                <input value={meta.hourly_rate} onChange={(e) => setMetaField("hourly_rate", e.target.value)}
                  className="w-16 bg-white border border-[#E7E5E4] rounded px-2 py-1 text-sm font-bold focus:outline-none print:border-none print:p-0" />
                <span className="text-xs text-[#78716C]">/ hr</span>
              </div>
            </div>
            <div>
              <label className="block text-xs text-[#78716C] font-semibold">Pacing</label>
              <div className="flex items-center gap-1 mt-1">
                <input value={meta.weekly_hours} onChange={(e) => setMetaField("weekly_hours", e.target.value)}
                  className="w-12 bg-white border border-[#E7E5E4] rounded px-2 py-1 text-sm font-bold focus:outline-none print:border-none print:p-0" />
                <span className="text-xs text-[#78716C]">hrs / wk</span>
              </div>
            </div>
            <div>
              <label className="block text-xs text-[#78716C] font-semibold">Est. Scope</label>
              <div className="flex items-center gap-1 mt-1">
                <input value={meta.total_hours} onChange={(e) => setMetaField("total_hours", e.target.value)}
                  className="w-12 bg-white border border-[#E7E5E4] rounded px-2 py-1 text-sm font-bold focus:outline-none print:border-none print:p-0" />
                <span className="text-xs text-[#78716C]">Hours</span>
              </div>
            </div>
            <div>
              <label className="block text-xs text-[#78716C] font-semibold">Total Value</label>
              <div className="text-sm font-bold text-[#166534] mt-1">{calculateTotalValue()}</div>
            </div>
          </div>
          <p className="text-xs text-[#78716C] mt-3">* Invoicing occurs weekly based on logged engineering hours worked.</p>
        </section>

        {/* Section 4: Prerequisites */}
        <section className="mb-8">
          <div className="flex items-center justify-between border-b border-[#E7E5E4] pb-2 mb-3">
            <h2 className="text-lg font-bold text-[#1A1C1E]">4. Client Access Prerequisites</h2>
            <button onClick={addPrereq} className="print:hidden text-xs text-[#B8422E] font-semibold hover:underline">+ Add prerequisite</button>
          </div>
          <ul className="space-y-2">
            {meta.prereqs.map((prereq, idx) => (
              <li key={idx} className="flex items-center gap-2 text-xs text-[#44403C] group">
                <span className="w-5 h-5 rounded-full bg-[#B8422E]/10 text-[#B8422E] font-bold text-[10px] flex items-center justify-center shrink-0">{idx + 1}</span>
                <input value={prereq}
                  onChange={(e) => setMetaField("prereqs", meta.prereqs.map((p, i) => i === idx ? e.target.value : p))}
                  className="w-full bg-transparent border-b border-transparent hover:border-[#E7E5E4] focus:border-[#B8422E] focus:outline-none py-1 print:border-none" />
                <button onClick={() => removePrereq(idx)} className="print:hidden text-[#B8422E] opacity-0 group-hover:opacity-100 text-xs shrink-0">✕</button>
              </li>
            ))}
            {!meta.prereqs.length && !loading && <p className="text-xs text-[#78716C] italic">No prerequisites yet.</p>}
          </ul>
        </section>

        {/* Section 5: Signatures */}
        <section className="mt-12 pt-6 border-t-2 border-[#1A1C1E]">
          <h2 className="text-sm font-bold uppercase tracking-wider text-[#78716C] mb-6">5. Authorization &amp; Signatures</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
            <div>
              <div className="border-b border-[#1A1C1E] pb-8 mb-2"></div>
              <div className="text-xs font-bold text-[#1A1C1E]">Consultant Signature: {meta.consultant}</div>
              <div className="text-xs text-[#78716C]">Date: {meta.date}</div>
            </div>
            <div>
              <div className="border-b border-[#1A1C1E] pb-8 mb-2"></div>
              <div className="text-xs font-bold text-[#1A1C1E]">Client Signature: {meta.client}</div>
              <div className="text-xs text-[#78716C]">Date: ________________________</div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
