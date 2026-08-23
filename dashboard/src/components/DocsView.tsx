"use client";

/**
 * DocsView — project documentation, backed by /api/v1/docs.
 *
 * Docs are keyed by (project_id, slug), the same per-project convention the SOW
 * and wireframe features use. They are NOT kanban cards: a document is never
 * "done", it is only kept accurate, so it does not belong in a workflow column.
 *
 * Designed with a premium, theme-aware visual language, split-screen editor preview,
 * category contextual icons, and a visual historical revisions panel with rollback.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { 
  BookOpen, Plus, Search, Save, Trash2, X, Download, History, FileText,
       
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  Folder, FolderOpen, Cpu, Play, CheckSquare, Link, ChevronRight, Eye, Edit3,
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
  ArrowLeft, Clock, RefreshCw, Check
} from "lucide-react";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";
import { formatMarkdown } from "@/lib/markdown";

const LABEL = "text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-secondary";
const INPUT_CLASS = "w-full bg-card/40 border border-border rounded pl-8 pr-2.5 py-2 text-xs text-primary placeholder:text-secondary focus:outline-none focus:border-tertiary/40 focus:ring-1 focus:ring-tertiary/20 transition-all";

interface DocMeta {
  id: number;
  slug: string;
  title: string;
  category: string;
  size: number;
  updated_at: string;
}

interface DocFull extends DocMeta {
  body: string;
  exists?: boolean;
}

interface Revision {
  id: number;
  title: string;
  body: string;
  author: string;
  created_at: string;
  size: number;
}

interface Hit {
  slug: string;
  title: string;
  category: string;
  snippet: string;
}

export default function DocsView({
  projectId,
  projectName,
}: {
  projectId: string;
  projectName?: string;
}) {
  const [docs, setDocs] = useState<DocMeta[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [active, setActive] = useState<DocFull | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ title: "", body: "", category: "general", slug: "" });
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [showRevisions, setShowRevisions] = useState(false);
  const [selectedRevision, setSelectedRevision] = useState<Revision | null>(null);
  const [editorTab, setEditorTab] = useState<"write" | "preview">("write");
  const [exportSuccess, setExportSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const api = `${CONFIG.API_BASE}/api/v1/docs`;

  const getCategoryIcon = (category: string): React.ReactNode => {
    switch (category.toLowerCase()) {
      case "architecture":
        return <Cpu className="w-3.5 h-3.5 text-secondary" />;
      case "runbook":
        return <Play className="w-3.5 h-3.5 text-emerald-500/70" />;
      case "decision":
        return <CheckSquare className="w-3.5 h-3.5 text-tertiary/80" />;
      case "record":
        return <BookOpen className="w-3.5 h-3.5 text-secondary" />;
      case "reference":
        return <Link className="w-3.5 h-3.5 text-secondary" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-secondary" />;
    }
  };

  const fetchWithTimeout = async (
    url: string,
    init: RequestInit = {},
    timeoutMs: number = 8000
  ): Promise<Response> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await tenantFetch(url, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  };

  const loadList = useCallback(async (): Promise<void> => {
    if (!projectId) return;
    try {
      const res = await fetchWithTimeout(`${api}/list?project_id=${encodeURIComponent(projectId)}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`list failed (${res.status})`);
      const data = await res.json();
      setDocs(data.docs ?? []);
      setCategories(data.categories ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load docs");
    }
  }, [api, projectId]);

  useEffect(() => {
      // eslint-disable-next-line react-hooks/set-state-in-effect
    setActive(null);
    setEditing(false);
    setHits(null);
    setQuery("");
    setShowRevisions(false);
    setSelectedRevision(null);
    loadList();
  }, [projectId, loadList]);

  const openDoc = useCallback(
    async (slug: string): Promise<void> => {
      setEditing(false);
      setError(null);
      setShowRevisions(false);
      setSelectedRevision(null);
      try {
        const res = await fetchWithTimeout(
          `${api}/${encodeURIComponent(slug)}?project_id=${encodeURIComponent(projectId)}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error(`load failed (${res.status})`);
        setActive(await res.json());

        const rev = await fetchWithTimeout(
          `${api}/revisions?project_id=${encodeURIComponent(projectId)}&slug=${encodeURIComponent(slug)}`,
          { cache: "no-store" }
        );
        setRevisions(rev.ok ? ((await rev.json()).revisions ?? []) : []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to open doc");
      }
    },
    [api, projectId]
  );

  // Debounced so typing doesn't fire a query per keystroke.
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (!query.trim()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setHits(null);
      return;
    }
    searchTimer.current = setTimeout(async () => {
      try {
        const res = await fetchWithTimeout(
          `${api}/search?project_id=${encodeURIComponent(projectId)}&q=${encodeURIComponent(query)}`,
          { cache: "no-store" }
        );
        setHits(res.ok ? ((await res.json()).results ?? []) : []);
      } catch {
        setHits([]);
      }
    }, 250);
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, [query, api, projectId]);

  const startNew = (): void => {
    setActive(null);
    setRevisions([]);
    setShowRevisions(false);
    setSelectedRevision(null);
    setDraft({ title: "", body: "", category: "general", slug: "" });
    setEditorTab("write");
    setEditing(true);
  };

  const startEdit = (): void => {
    if (!active) return;
    setDraft({
      title: active.title,
      body: active.body ?? "",
      category: active.category ?? "general",
      slug: active.slug,
    });
    setEditorTab("write");
    setEditing(true);
  };

  const save = async (): Promise<void> => {
    if (!draft.title.trim()) {
      setError("A title is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetchWithTimeout(api, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          slug: draft.slug || undefined,
          title: draft.title,
          body: draft.body,
          category: draft.category,
        }),
      });
      if (!res.ok) throw new Error(`save failed (${res.status})`);
      const { doc } = await res.json();
      setEditing(false);
      await loadList();
      await openDoc(doc.slug);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (): Promise<void> => {
    if (!active) return;
    setBusy(true);
    try {
      const res = await fetchWithTimeout(
        `${api}/${encodeURIComponent(active.slug)}?project_id=${encodeURIComponent(projectId)}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error(`delete failed (${res.status})`);
      setActive(null);
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    } finally {
      setBusy(false);
    }
  };

  const restoreRevision = async (rev: Revision): Promise<void> => {
    if (!active) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetchWithTimeout(api, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          slug: active.slug,
          title: rev.title || active.title,
          body: rev.body,
          category: active.category,
        }),
      });
      if (!res.ok) throw new Error(`restore failed (${res.status})`);
      const { doc } = await res.json();
      setShowRevisions(false);
      setSelectedRevision(null);
      await loadList();
      await openDoc(doc.slug);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to restore revision");
    } finally {
      setBusy(false);
    }
  };

  const exportAll = async (): Promise<void> => {
    setBusy(true);
    setExportSuccess(false);
    try {
      const res = await fetchWithTimeout(`${api}/export?project_id=${encodeURIComponent(projectId)}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`export failed (${res.status})`);
      const data = await res.json();
      const bundle = (data.files ?? [])
        .map((f: { path: string; content: string }) => `<!-- file: ${f.path} -->\n\n${f.content}`)
        .join("\n\n---\n\n");
      const blob = new Blob([bundle], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(projectName || projectId).replace(/\W+/g, "-").toLowerCase()}-docs.md`;
      a.click();
      URL.revokeObjectURL(url);
      setExportSuccess(true);
      setTimeout(() => setExportSuccess(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(false);
    }
  };

  const insertMarkdown = (syntax: string): void => {
    const textarea = document.getElementById("docs-editor-textarea") as HTMLTextAreaElement;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = draft.body;
    const before = text.substring(0, start);
    const after = text.substring(end, text.length);
    const selected = text.substring(start, end);

    let replacement = "";
    switch (syntax) {
      case "bold": replacement = `**${selected || "bold text"}**`; break;
      case "italic": replacement = `*${selected || "italic text"}*`; break;
      case "h1": replacement = `# ${selected || "Heading 1"}`; break;
      case "h2": replacement = `## ${selected || "Heading 2"}`; break;
      case "h3": replacement = `### ${selected || "Heading 3"}`; break;
      case "code": replacement = `\`${selected || "code"}\``; break;
      case "codeblock": replacement = `\`\`\`\n${selected || "code block"}\n\`\`\``; break;
      case "list": replacement = `\n- ${selected || "item"}`; break;
      case "quote": replacement = `\n> ${selected || "quote"}`; break;
      default: replacement = selected;
    }

    setDraft({ ...draft, body: before + replacement + after });
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + replacement.length, start + replacement.length);
    }, 0);
  };

  const grouped = useMemo(() => {
    const m = new Map<string, DocMeta[]>();
    docs.forEach((d) => {
      const k = d.category || "general";
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(d);
    });
    return [...m.entries()];
  }, [docs]);

  if (!projectId) {
    return (
      <div className="w-full text-center py-20 px-6">
        <BookOpen className="w-8 h-8 text-secondary mx-auto mb-4" />
        <div className={LABEL}>No Project Selected</div>
      </div>
    );
  }

  return (
    <div className="w-full min-w-0 flex flex-col lg:flex-row gap-8 px-6 lg:px-10 py-6">
      {/* ---- Index Sidebar ---- */}
      <aside className="lg:w-64 xl:w-72 shrink-0 space-y-5">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-secondary absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search docs"
              className={INPUT_CLASS}
            />
          </div>
          <button
            onClick={startNew}
            title="New document"
            className="p-2 rounded-sm border border-border bg-card/40 text-secondary hover:text-primary hover:bg-card cursor-pointer transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={exportAll}
            title="Export all docs as markdown"
            className={`p-2 rounded-sm border cursor-pointer transition-colors relative ${
              exportSuccess 
                ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-500" 
                : "border-border bg-card/40 text-secondary hover:text-primary hover:bg-card"
            }`}
          >
            {exportSuccess ? <Check className="w-3.5 h-3.5 animate-pulse" /> : <Download className="w-3.5 h-3.5" />}
          </button>
        </div>

        {hits !== null ? (
          <div className="space-y-2">
            <div className={LABEL}>
              {hits.length} result{hits.length === 1 ? "" : "s"}
            </div>
            <div className="space-y-1.5">
              {hits.map((h) => (
                <button
                  key={h.slug}
                  onClick={() => {
                    setQuery("");
                    openDoc(h.slug);
                  }}
                  className="w-full text-left px-3 py-2.5 rounded border border-border bg-card/40 hover:bg-card hover:border-border/80 cursor-pointer transition-all duration-200"
                >
                  <div className="flex items-center gap-1.5">
                    {getCategoryIcon(h.category)}
                    <span className="text-xs text-primary font-semibold truncate">{h.title}</span>
                  </div>
                  <div
                    className="text-[10px] text-secondary mt-1.5 leading-snug [&_b]:text-tertiary"
                    dangerouslySetInnerHTML={{ __html: h.snippet }}
                  />
                </button>
              ))}
              {hits.length === 0 && (
                <p className="text-[10px] font-mono text-secondary px-1">No matches.</p>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {grouped.map(([cat, items]) => (
              <div key={cat} className="space-y-2">
                <div className="flex items-center gap-2 border-b border-border/20 pb-1">
                  <FolderOpen className="w-3 h-3 text-secondary/70" />
                  <span className={LABEL}>{cat}</span>
                  <span className="text-[8px] font-mono text-secondary/60 bg-border/20 px-1.5 py-0.2 rounded-full ml-auto">
                    {items.length}
                  </span>
                </div>
                <div className="space-y-1 pl-1">
                  {items.map((d) => (
                    <button
                      key={d.slug}
                      onClick={() => openDoc(d.slug)}
                      className={`w-full text-left px-3 py-2 rounded text-xs leading-snug cursor-pointer transition-all flex items-center gap-2 border ${
                        active?.slug === d.slug
                          ? "bg-primary/10 border-primary/20 text-primary font-medium"
                          : "bg-card/25 border-transparent text-secondary hover:text-primary hover:bg-card/60"
                      }`}
                    >
                      {getCategoryIcon(d.category)}
                      <span className="truncate flex-1">{d.title}</span>
                      <ChevronRight className={`w-3 h-3 transition-transform ${active?.slug === d.slug ? "translate-x-0.5 opacity-100" : "opacity-0 group-hover:opacity-40"}`} />
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {docs.length === 0 && (
              <div className="text-center py-12 border border-dashed border-border/30 rounded bg-card/10">
                <FileText className="w-5 h-5 text-secondary/60 mx-auto mb-2" />
                <p className="text-[10px] font-mono text-secondary leading-relaxed">
                  No docs found.
                  <br />
                  Click + to create one.
                </p>
              </div>
            )}
          </div>
        )}
      </aside>

      {/* ---- Reader / Editor Panel ---- */}
      <article className="flex-1 min-w-0 flex flex-col lg:flex-row gap-6 items-start">
        <div className="flex-1 w-full min-w-0">
          {error && (
            <div className="mb-4 flex items-center justify-between gap-3 border border-red-500/20 bg-red-500/5 text-red-400 text-xs px-3.5 py-2.5 rounded">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="cursor-pointer hover:opacity-80" aria-label="Dismiss">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {editing ? (
            <div className="bg-card/45 backdrop-blur-xs border border-border rounded p-6 space-y-5 artisan-shadow">
              <div className="flex items-center justify-between border-b border-border/35 pb-4">
                <div className="flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-tertiary" />
                  <span className="font-mono text-xs uppercase tracking-widest text-primary font-bold">
                    {draft.slug ? "Edit Document" : "Create Document"}
                  </span>
                </div>
                <div className="flex bg-neutral border border-border rounded p-0.5 text-xs font-mono">
                  <button
                    onClick={() => setEditorTab("write")}
                    className={`px-3 py-1 rounded-sm cursor-pointer transition-colors ${editorTab === "write" ? "bg-card text-primary font-semibold shadow-xs" : "text-secondary hover:text-primary"}`}
                  >
                    Write
                  </button>
                  <button
                    onClick={() => setEditorTab("preview")}
                    className={`px-3 py-1 rounded-sm cursor-pointer transition-colors ${editorTab === "preview" ? "bg-card text-primary font-semibold shadow-xs" : "text-secondary hover:text-primary"}`}
                  >
                    Preview
                  </button>
                </div>
              </div>

              {editorTab === "write" ? (
                <div className="space-y-4">
                  <input
                    value={draft.title}
                    onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                    placeholder="Document title"
                    className="w-full bg-transparent border-b border-border pb-2 text-lg font-heading font-semibold text-primary placeholder:text-secondary/50 focus:outline-none focus:border-tertiary transition-colors"
                  />
                  
                  <div className="flex items-center gap-4 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className={LABEL}>Category:</span>
                      <select
                        value={draft.category}
                        onChange={(e) => setDraft({ ...draft, category: e.target.value })}
                        className="bg-card border border-border rounded px-2.5 py-1 text-xs text-primary focus:outline-none cursor-pointer focus:border-tertiary/40"
                      >
                        {(categories.length ? categories : ["general", "architecture", "runbook", "decision", "record", "reference"]).map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="flex items-center gap-1 border-l border-border pl-4 text-[10px] font-mono text-secondary flex-wrap">
                      <span className="mr-1">Insert:</span>
                      <button type="button" onClick={() => insertMarkdown("bold")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer"><b>B</b></button>
                      <button type="button" onClick={() => insertMarkdown("italic")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer"><i>I</i></button>
                      <button type="button" onClick={() => insertMarkdown("h1")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer font-bold">H1</button>
                      <button type="button" onClick={() => insertMarkdown("h2")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer font-bold">H2</button>
                      <button type="button" onClick={() => insertMarkdown("h3")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer font-bold">H3</button>
                      <button type="button" onClick={() => insertMarkdown("code")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer font-mono">code</button>
                      <button type="button" onClick={() => insertMarkdown("codeblock")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer font-mono">block</button>
                      <button type="button" onClick={() => insertMarkdown("list")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer">- list</button>
                      <button type="button" onClick={() => insertMarkdown("quote")} className="px-1.5 py-0.5 hover:bg-card rounded cursor-pointer">&gt; quote</button>
                    </div>
                  </div>

                  <textarea
                    id="docs-editor-textarea"
                    value={draft.body}
                    onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                    placeholder="Markdown body supports # h1, ## h2, - lists, `code`, and block quotes."
                    spellCheck={false}
                    className="w-full h-[48vh] min-h-[320px] bg-neutral border border-border rounded p-4 font-mono text-xs text-primary leading-relaxed focus:outline-none focus:border-tertiary/40 resize-y"
                  />
                </div>
              ) : (
                <div className="border border-border/20 rounded p-6 bg-card/25 min-h-[48vh] overflow-y-auto max-h-[60vh] custom-scrollbar text-left">
                  <div className="font-heading font-bold text-2xl text-primary border-b border-border/30 pb-2 mb-4">
                    {draft.title || "Untitled Document"}
                  </div>
                  <div className="markdown-content text-sm text-primary leading-relaxed break-words">
                    {formatMarkdown(draft.body || "*No preview content compiled. Start writing to view.*")}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2 border-t border-border/35 pt-4">
                <button
                  onClick={save}
                  disabled={busy}
                  className="flex items-center gap-2 px-4 py-2 rounded-sm bg-primary text-neutral text-[10px] font-bold uppercase tracking-widest disabled:opacity-40 cursor-pointer hover:bg-primary/95 transition-colors"
                >
                  <Save className="w-3.5 h-3.5" />
                  {busy ? "Saving" : "Save"}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="px-4 py-2 rounded-sm border border-border text-secondary hover:text-primary hover:bg-card text-[10px] font-bold uppercase tracking-widest cursor-pointer transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : active ? (
            <div className="bg-card/45 backdrop-blur-xs border border-border rounded p-6 lg:p-10 artisan-shadow space-y-6">
              <div className="flex items-start justify-between gap-4 flex-wrap border-b border-border/30 pb-4">
                <div className="min-w-0">
                  <h2 className="text-xl lg:text-2xl font-heading font-bold text-primary break-words leading-tight">{active.title}</h2>
                  <div className="flex items-center gap-3 mt-2 flex-wrap">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-tertiary/10 border border-tertiary/15 text-tertiary text-[9px] font-mono font-bold uppercase tracking-wider">
                      {active.category}
                    </span>
                    <span className="text-[9px] font-mono text-secondary">
                      {active.size ? `${(active.size / 1024).toFixed(2)} KB` : "0 KB"}
                    </span>
                    {revisions.length > 0 && (
                      <button
                        onClick={() => setShowRevisions(!showRevisions)}
                        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9px] font-mono border transition-colors cursor-pointer ${
                          showRevisions 
                            ? "bg-tertiary/10 border-tertiary/20 text-tertiary" 
                            : "bg-border/20 border-transparent text-secondary hover:bg-border/40 hover:text-primary"
                        }`}
                      >
                        <Clock className="w-2.5 h-2.5" />
                        {revisions.length} revision{revisions.length === 1 ? "" : "s"}
                      </button>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={startEdit}
                    className="px-3.5 py-1.5 rounded-sm border border-border text-secondary hover:text-primary hover:bg-card text-[10px] font-bold uppercase tracking-widest cursor-pointer transition-colors flex items-center gap-1.5"
                  >
                    <Edit3 className="w-3 h-3" />
                    Edit
                  </button>
                  <button
                    onClick={remove}
                    disabled={busy}
                    title="Delete document"
                    className="p-2 rounded-sm border border-border text-secondary hover:text-red-500 hover:bg-red-500/5 hover:border-red-500/20 disabled:opacity-40 cursor-pointer transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {selectedRevision ? (
                <div className="border border-tertiary/20 rounded bg-tertiary/[0.02] p-6 text-left relative overflow-hidden">
                  <div className="absolute top-0 right-0 bg-tertiary/10 border-b border-l border-tertiary/20 px-3 py-1 text-[8px] font-mono text-tertiary uppercase tracking-widest font-semibold">
                    Previewing History
                  </div>
                  <div className="flex items-center gap-4 mb-4 pb-3 border-b border-border/30">
                    <button 
                      onClick={() => setSelectedRevision(null)}
                      className="flex items-center gap-1.5 text-xs text-secondary hover:text-primary cursor-pointer transition-colors"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      Back to active
                    </button>
                    <div className="text-[10px] font-mono text-secondary">
                      Saved {new Date(selectedRevision.created_at).toLocaleString()} {selectedRevision.author && `by ${selectedRevision.author}`}
                    </div>
                  </div>
                  <h3 className="text-xl font-heading font-semibold text-primary mb-3">
                    {selectedRevision.title || active.title}
                  </h3>
                  <div className="markdown-content text-sm text-primary leading-relaxed break-words">
                    {formatMarkdown(selectedRevision.body || "_This historical version is empty._")}
                  </div>
                  <div className="mt-6 pt-4 border-t border-border/30 flex justify-end">
                    <button
                      onClick={() => restoreRevision(selectedRevision)}
                      disabled={busy}
                      className="px-3.5 py-1.5 rounded-sm bg-tertiary text-neutral hover:bg-tertiary/90 text-[10px] font-bold uppercase tracking-widest cursor-pointer transition-colors flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <History className="w-3.5 h-3.5" />
                      Restore this version
                    </button>
                  </div>
                </div>
              ) : (
                <div className="markdown-content text-sm text-primary leading-relaxed break-words text-left">
                  {formatMarkdown(active.body || "_This document is empty. Click Edit to add content._")}
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-24 bg-card/25 border border-dashed border-border/30 rounded artisan-shadow">
              <BookOpen className="w-8 h-8 text-secondary/60 mx-auto mb-4" />
              <div className={LABEL}>{projectName || "Documentation"}</div>
              <p className="text-xs text-secondary mt-3 w-full max-w-lg mx-auto leading-relaxed px-6">
                Select a document from the left folder, or create a new one using the <b>+</b> button. 
                Documents are saved scoped per-project, keep a detailed historical revisions audit log, 
                and can be exported as structured markdown files for system handovers.
              </p>
            </div>
          )}
        </div>

        {/* ---- Collapsible Revisions Sidebar panel ---- */}
        {showRevisions && active && (
          <div className="w-full lg:w-72 shrink-0 bg-card/45 backdrop-blur-xs border border-border rounded p-5 artisan-shadow space-y-4 text-left self-stretch">
            <div className="flex items-center justify-between border-b border-border/30 pb-3">
              <div className="flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-secondary" />
                <span className="font-mono text-xs uppercase tracking-widest text-primary font-bold">Revisions</span>
              </div>
              <button 
                onClick={() => { setShowRevisions(false); setSelectedRevision(null); }}
                className="p-1 text-secondary hover:text-primary rounded hover:bg-primary/5 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 max-h-[55vh] overflow-y-auto pr-1 custom-scrollbar">
              {revisions.map((r, index) => (
                <button
                  key={r.id}
                  onClick={() => setSelectedRevision(r)}
                  className={`w-full text-left p-3 rounded border transition-all cursor-pointer block ${
                    selectedRevision?.id === r.id
                      ? "bg-tertiary/10 border-tertiary/30 text-primary"
                      : "bg-card/20 border-border/40 text-secondary hover:text-primary hover:border-border"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono font-bold text-primary">
                      v{revisions.length - index}
                    </span>
                    <span className="text-[8px] font-mono text-secondary">
                      {r.size ? `${(r.size / 1024).toFixed(2)} KB` : "0 KB"}
                    </span>
                  </div>
                  <div className="text-[10px] text-secondary mt-1 truncate">
                    {r.title || active.title}
                  </div>
                  <div className="text-[9px] font-mono text-secondary/70 mt-1.5 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5 shrink-0" />
                    <span>{new Date(r.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}</span>
                  </div>
                  {r.author && (
                    <div className="text-[8px] font-mono text-secondary/60 mt-1">
                      Edited by {r.author}
                    </div>
                  )}
                </button>
              ))}
              {revisions.length === 0 && (
                <p className="text-[10px] font-mono text-secondary text-center py-4">No revisions logged yet.</p>
              )}
            </div>
          </div>
        )}
      </article>
    </div>
  );
}
