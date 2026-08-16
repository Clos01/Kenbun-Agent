"use client";

/**
 * DocsView — project documentation, backed by /api/v1/docs.
 *
 * Docs are keyed by (project_id, slug), the same per-project convention the SOW
 * and wireframe features use. They are NOT kanban cards: a document is never
 * "done", it is only kept accurate, so it does not belong in a workflow column.
 *
 * Lives in its own component rather than inside board/page.tsx, which is already
 * ~2,200 lines.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, Plus, Search, Save, Trash2, X, Download, History, FileText } from "lucide-react";
import { CONFIG } from "@/lib/config";
import { tenantFetch } from "@/lib/tenantFetch";
import { formatMarkdown } from "@/lib/markdown";

const LABEL = "text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-secondary";

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
  const [revisions, setRevisions] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const api = `${CONFIG.API_BASE}/api/v1/docs`;

  const loadList = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await tenantFetch(`${api}/list?project_id=${encodeURIComponent(projectId)}`, {
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
    setActive(null);
    setEditing(false);
    setHits(null);
    setQuery("");
    loadList();
  }, [projectId, loadList]);

  const openDoc = useCallback(
    async (slug: string) => {
      setEditing(false);
      setError(null);
      try {
        const res = await tenantFetch(
          `${api}/${encodeURIComponent(slug)}?project_id=${encodeURIComponent(projectId)}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error(`load failed (${res.status})`);
        setActive(await res.json());
        const rev = await tenantFetch(
          `${api}/revisions?project_id=${encodeURIComponent(projectId)}&slug=${encodeURIComponent(slug)}`,
          { cache: "no-store" }
        );
        setRevisions(rev.ok ? ((await rev.json()).revisions ?? []).length : null);
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
      setHits(null);
      return;
    }
    searchTimer.current = setTimeout(async () => {
      try {
        const res = await tenantFetch(
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

  const startNew = () => {
    setActive(null);
    setRevisions(null);
    setDraft({ title: "", body: "", category: "general", slug: "" });
    setEditing(true);
  };

  const startEdit = () => {
    if (!active) return;
    setDraft({
      title: active.title,
      body: active.body ?? "",
      category: active.category ?? "general",
      slug: active.slug,
    });
    setEditing(true);
  };

  const save = async () => {
    if (!draft.title.trim()) {
      setError("A title is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await tenantFetch(api, {
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

  const remove = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const res = await tenantFetch(
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

  /* Handover path: a client developer receives a git repo, not access to
     Kenbun. Docs have to be able to leave the system as plain markdown. */
  const exportAll = async () => {
    try {
      const res = await tenantFetch(`${api}/export?project_id=${encodeURIComponent(projectId)}`, {
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
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
      {/* ---- index ---- */}
      <aside className="lg:w-64 xl:w-72 shrink-0 space-y-4">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-secondary absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search docs"
              className="w-full bg-card/50 border border-primary/10 rounded-sm pl-8 pr-2 py-2 text-xs text-primary placeholder:text-secondary focus:outline-none focus:border-primary/40"
            />
          </div>
          <button
            onClick={startNew}
            title="New document"
            className="p-2 rounded-sm border border-primary/10 bg-card/50 text-secondary hover:text-primary hover:bg-card cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={exportAll}
            title="Export all docs as markdown"
            className="p-2 rounded-sm border border-primary/10 bg-card/50 text-secondary hover:text-primary hover:bg-card cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
        </div>

        {hits !== null ? (
          <div className="space-y-1">
            <div className={LABEL}>
              {hits.length} result{hits.length === 1 ? "" : "s"}
            </div>
            {hits.map((h) => (
              <button
                key={h.slug}
                onClick={() => {
                  setQuery("");
                  openDoc(h.slug);
                }}
                className="w-full text-left px-3 py-2.5 rounded-sm border border-primary/5 bg-card/40 hover:bg-card/80 cursor-pointer"
              >
                <div className="text-xs text-primary font-semibold">{h.title}</div>
                <div
                  className="text-[10px] text-secondary mt-1 leading-snug [&_b]:text-tertiary"
                  dangerouslySetInnerHTML={{ __html: h.snippet }}
                />
              </button>
            ))}
            {hits.length === 0 && (
              <p className="text-[10px] font-mono text-secondary">No matches.</p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {grouped.map(([cat, items]) => (
              <div key={cat}>
                <div className={`${LABEL} mb-2`}>{cat}</div>
                <div className="space-y-1">
                  {items.map((d) => (
                    <button
                      key={d.slug}
                      onClick={() => openDoc(d.slug)}
                      className={`w-full text-left px-3 py-2 rounded-sm border text-xs leading-snug cursor-pointer transition-colors ${
                        active?.slug === d.slug
                          ? "bg-primary/10 border-primary/40 text-primary"
                          : "bg-card/40 border-primary/5 text-secondary hover:text-primary hover:bg-card/80"
                      }`}
                    >
                      {d.title}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {docs.length === 0 && (
              <div className="text-center py-10">
                <FileText className="w-6 h-6 text-secondary mx-auto mb-3" />
                <p className="text-[10px] font-mono text-secondary leading-relaxed">
                  No documents for this project yet.
                  <br />
                  Use + to write the first one.
                </p>
              </div>
            )}
          </div>
        )}
      </aside>

      {/* ---- reader / editor ---- */}
      <article className="flex-1 min-w-0">
        {error && (
          <div className="mb-4 flex items-center justify-between gap-3 border border-red-500/30 bg-red-500/10 text-red-400 text-xs px-3 py-2 rounded-sm">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="cursor-pointer" aria-label="Dismiss">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {editing ? (
          <div className="bg-card/30 border border-primary/10 rounded-sm p-6 space-y-4">
            <input
              value={draft.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              placeholder="Document title"
              className="w-full bg-transparent border-b border-primary/10 pb-2 text-lg font-bold text-primary placeholder:text-secondary focus:outline-none focus:border-primary/40"
            />
            <div className="flex items-center gap-3">
              <span className={LABEL}>Category</span>
              <select
                value={draft.category}
                onChange={(e) => setDraft({ ...draft, category: e.target.value })}
                className="bg-card border border-primary/10 rounded-sm px-2 py-1 text-xs text-primary focus:outline-none cursor-pointer"
              >
                {(categories.length ? categories : ["general"]).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              value={draft.body}
              onChange={(e) => setDraft({ ...draft, body: e.target.value })}
              placeholder="Markdown supported."
              spellCheck={false}
              className="w-full h-[46vh] min-h-[300px] bg-black/30 border border-primary/10 rounded-sm p-4 font-mono text-xs text-primary leading-relaxed focus:outline-none focus:border-primary/40 resize-y"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={save}
                disabled={busy}
                className="flex items-center gap-2 px-4 py-2 rounded-sm bg-primary text-neutral text-[10px] font-bold uppercase tracking-widest disabled:opacity-40 cursor-pointer"
              >
                <Save className="w-3.5 h-3.5" />
                {busy ? "Saving" : "Save"}
              </button>
              <button
                onClick={() => setEditing(false)}
                className="px-4 py-2 rounded-sm border border-primary/10 text-secondary hover:text-primary text-[10px] font-bold uppercase tracking-widest cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : active ? (
          <div className="bg-card/30 border border-primary/10 rounded-sm p-6 lg:p-10">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="min-w-0">
                <h2 className="text-lg font-bold text-primary break-words">{active.title}</h2>
                <div className={`${LABEL} mt-1`}>
                  {active.category}
                  {revisions !== null && revisions > 0 && (
                    <span className="ml-3 inline-flex items-center gap-1">
                      <History className="w-3 h-3" />
                      {revisions} revision{revisions === 1 ? "" : "s"}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={startEdit}
                  className="px-3 py-1.5 rounded-sm border border-primary/10 text-secondary hover:text-primary text-[10px] font-bold uppercase tracking-widest cursor-pointer"
                >
                  Edit
                </button>
                <button
                  onClick={remove}
                  disabled={busy}
                  title="Delete document"
                  className="p-2 rounded-sm border border-primary/10 text-secondary hover:text-red-400 disabled:opacity-40 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            <div className="markdown-content text-sm text-primary leading-relaxed break-words w-full max-w-5xl mt-6">
              {formatMarkdown(active.body || "_This document is empty._")}
            </div>
          </div>
        ) : (
          <div className="text-center py-24">
            <BookOpen className="w-8 h-8 text-secondary mx-auto mb-4" />
            <div className={LABEL}>{projectName || "Documentation"}</div>
            <p className="text-xs text-secondary mt-3 w-full max-w-md mx-auto leading-relaxed">
              Select a document, or create one with +. Documents are scoped to this
              project, keep full revision history, and can be exported as markdown
              for handover.
            </p>
          </div>
        )}
      </article>
    </div>
  );
}
