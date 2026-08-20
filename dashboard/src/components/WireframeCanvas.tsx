"use client";

/**
 * The board's Wireframe tab: a drafting sheet.
 *
 * History matters for why this is a scrolling document and not a canvas.
 *
 * It was an <iframe> around self-hosted Excalidraw rendering a scene whose every
 * coordinate had been computed in Python — which drew backend cards on top of
 * one another and placed un-flowed endpoints outside the band meant to contain
 * them. Replacing that with a React Flow node graph fixed the overlaps, but kept
 * the shape of the problem: a wireframe presented as a web of colour-coded nodes
 * and connector arrows, where the screens compete with the wiring.
 *
 * A wireframe is read for the screens. So the backend is demoted to annotation —
 * an endpoint is named in mono under the button that calls it — and once there
 * are no arrows, there is no graph, and once there is no graph a pan-and-zoom
 * canvas is the wrong container. This is a sheet you scroll.
 *
 * Two properties fall out of that, both of which had to be engineered before:
 * nothing can overlap, because normal document flow does not permit it; and
 * nothing can escape its frame, because flexbox does not permit that either.
 */

import React, { useEffect, useMemo, useState } from "react";
import { Download, FileWarning, Minus, Plus } from "lucide-react";

import { ComponentTree, HatchDefs } from "./wireframe/ScreenMock";
import { buildSheet, type SheetModel } from "./wireframe/sheet";
import { PAPER, type WDoc } from "./wireframe/types";

const mono = "var(--font-geist-mono, ui-monospace, SFMono-Regular, Menlo, monospace)";

function Marker({ n }: { n: number }) {
  return (
    <div style={{ fontFamily: mono, fontSize: 11, color: PAPER.inkMuted, minWidth: 20, paddingTop: 2 }}>
      {String(n).padStart(2, "0")}
    </div>
  );
}

function EndpointNote({ method, path }: { method: string; path: string }) {
  return (
    <div style={{ fontFamily: mono, fontSize: 10, color: PAPER.inkMuted, whiteSpace: "nowrap" }}>
      &rarr; {method} {path}
    </div>
  );
}

function Sheet({ model, doc }: { model: SheetModel; doc: WDoc }) {
  const [zoom, setZoom] = useState(1);

  const download = () => {
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(doc.title || "wireframe").replace(/[^a-z0-9]+/gi, "_")}.wireframe.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const btn: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 5,
    padding: "4px 9px",
    borderRadius: 3,
    border: `0.5px solid ${PAPER.ruleStrong}`,
    background: PAPER.sheet,
    color: PAPER.inkSoft,
    fontSize: 10,
    fontFamily: mono,
    cursor: "pointer",
  };

  return (
    <div style={{ position: "relative", height: "100%", width: "100%", overflow: "auto", background: PAPER.sheetEdge }}>
      <HatchDefs />

      <div style={{ position: "sticky", top: 0, zIndex: 5, display: "flex", justifyContent: "flex-end", gap: 6, padding: "10px 14px 0" }}>
        <button onClick={() => setZoom((z) => Math.max(0.6, +(z - 0.1).toFixed(2)))} style={btn} aria-label="Zoom out">
          <Minus style={{ width: 11, height: 11 }} />
        </button>
        <button onClick={() => setZoom(1)} style={btn}>{Math.round(zoom * 100)}%</button>
        <button onClick={() => setZoom((z) => Math.min(1.6, +(z + 0.1).toFixed(2)))} style={btn} aria-label="Zoom in">
          <Plus style={{ width: 11, height: 11 }} />
        </button>
        <button onClick={download} style={btn}>
          <Download style={{ width: 11, height: 11 }} /> JSON
        </button>
      </div>

      <div style={{ padding: "14px 24px 48px", display: "flex", justifyContent: "center" }}>
        <div
          style={{
            width: 860,
            transform: `scale(${zoom})`,
            transformOrigin: "top center",
            background: PAPER.sheet,
            border: `0.5px solid ${PAPER.rule}`,
            borderRadius: 4,
            // --card on --background is a quiet pairing in every preset, so the
            // page needs a little help reading as a page. Plain black at low
            // alpha rather than a themed colour: under a dark preset --primary is
            // the LIGHT foreground, and a shadow mixed from it would glow instead
            // of shading. This lifts the sheet in the light presets and fades to
            // nothing in the dark ones, where the card/background step and the
            // themed border already do the separating.
            boxShadow: "0 1px 2px rgba(0, 0, 0, 0.05), 0 8px 24px rgba(0, 0, 0, 0.07)",
            padding: "30px 36px 34px",
          }}
        >
          <div style={{ fontSize: 19, color: PAPER.ink, marginBottom: 4 }}>{model.title}</div>
          <div style={{ fontFamily: mono, fontSize: 10, color: PAPER.inkMuted, letterSpacing: "0.07em" }}>
            {model.counts.screens} screens · {model.counts.endpoints} endpoints · {model.counts.models} models
            {model.counts.integrations > 0 ? ` · ${model.counts.integrations} integrations` : ""}
          </div>

          <div style={{ height: 1, background: PAPER.rule, margin: "18px 0 22px" }} />

          {model.sections.map((s) => (
            <div key={s.id} style={{ display: "flex", gap: 14, marginBottom: 30 }}>
              <Marker n={s.index} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: PAPER.ink }}>{s.title}</div>
                <div style={{ fontSize: 11, color: PAPER.inkMuted, marginBottom: 10 }}>{s.caption}</div>
                <div style={{ border: `0.5px solid ${PAPER.ruleStrong}`, borderRadius: 4, padding: "14px 16px", background: PAPER.well }}>
                  {s.screen.body ? (
                    <ComponentTree
                      c={s.screen.body}
                      annotate={(h) => {
                        const notes = s.annotations.get(h);
                        if (!notes?.length) return null;
                        return (
                          <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                            {notes.map((n, i) => (
                              <EndpointNote key={i} method={n.method} path={n.path} />
                            ))}
                          </div>
                        );
                      }}
                    />
                  ) : null}
                </div>
              </div>
            </div>
          ))}

          <div style={{ height: 1, background: PAPER.rule, margin: "4px 0 14px" }} />

          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontFamily: mono, fontSize: 10, color: PAPER.inkMuted, lineHeight: 1.6 }}>
            {model.models.length > 0 && (
              <div>
                <span style={{ letterSpacing: "0.07em" }}>Data&nbsp;&nbsp;</span>
                {model.models.map((m, i) => (
                  <span key={m.label}>
                    {i > 0 && " · "}
                    <span style={{ color: PAPER.inkSoft }} title={m.fields.join(", ")}>
                      {m.label}
                    </span>
                    <span>({m.fields.length})</span>
                  </span>
                ))}
              </div>
            )}
            {model.integrations.length > 0 && (
              <div>
                <span style={{ letterSpacing: "0.07em" }}>External&nbsp;&nbsp;</span>
                {model.integrations.map((g, i) => (
                  <span key={g.label}>
                    {i > 0 && " · "}
                    <span style={{ color: PAPER.inkSoft }}>{g.label}</span>
                    {g.service ? ` (${g.service})` : ""}
                  </span>
                ))}
              </div>
            )}
            {model.standaloneEndpoints.length > 0 && (
              <div>
                {/* Endpoints no button calls are legitimate — a list GET that
                    populates a table triggers no click. They are listed rather
                    than dropped, and rather than floating unattached as they did
                    on the old canvas. */}
                <span style={{ letterSpacing: "0.07em" }}>Also&nbsp;&nbsp;</span>
                {model.standaloneEndpoints.map((e, i) => (
                  <span key={`${e.method}${e.path}`}>
                    {i > 0 && " · "}
                    <span style={{ color: PAPER.inkSoft }}>
                      {e.method} {e.path}
                    </span>
                  </span>
                ))}
              </div>
            )}
          </div>

          {model.unplaced.length > 0 && (
            <div style={{ marginTop: 14, paddingTop: 10, borderTop: `0.5px solid ${PAPER.rule}`, fontFamily: mono, fontSize: 10, color: PAPER.accent, lineHeight: 1.6 }}>
              {model.unplaced.map((u, i) => (
                <div key={i}>! {u}</div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Notice({ title, body }: { title: string; body: string }) {
  return (
    <div style={{ display: "flex", height: "100%", width: "100%", alignItems: "center", justifyContent: "center", padding: 32 }}>
      <div className="w-full max-w-lg rounded-lg border border-border bg-card/60 p-5 text-center">
        <FileWarning className="mx-auto mb-3 h-5 w-5 text-secondary" />
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-primary">{title}</div>
        <p className="mt-2 text-xs leading-relaxed text-secondary">{body}</p>
      </div>
    </div>
  );
}

type State = { status: "loading" | "ok" | "empty" | "legacy" | "error"; doc?: WDoc; msg?: string };

function Loader({ projectId }: { projectId: string }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetch(`/api/wireframe?project_id=${encodeURIComponent(projectId)}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        // Wireframes saved before the move off Excalidraw are a different format
        // entirely, and cannot be converted — that file is finished pixels with
        // the semantic structure already discarded. Say so plainly rather than
        // rendering an empty sheet, which looks identical to "generation failed".
        if (data?.type === "excalidraw") {
          setState({
            status: "legacy",
            msg:
              "This project's wireframe was saved in the old Excalidraw format. " +
              "Re-run generate_wireframe for this project to rebuild it on the new sheet.",
          });
          return;
        }
        if (data?.type !== "kenbun-wireframe" || !Array.isArray(data?.nodes) || data.nodes.length === 0) {
          setState({ status: "empty", msg: "No wireframe for this project yet. Run generate_wireframe to create one." });
          return;
        }
        setState({ status: "ok", doc: data as WDoc });
      })
      .catch((e) => {
        if (!cancelled) setState({ status: "error", msg: String(e) });
      });

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const model = useMemo(() => (state.doc ? buildSheet(state.doc) : null), [state.doc]);

  switch (state.status) {
    case "loading":
      return <div className="flex h-full items-center justify-center text-xs text-secondary">Loading wireframe…</div>;
    case "ok":
      return <Sheet model={model!} doc={state.doc!} />;
    case "legacy":
      return <Notice title="Old format" body={state.msg!} />;
    case "error":
      return <Notice title="Could not load" body={state.msg!} />;
    default:
      return <Notice title="Nothing here yet" body={state.msg!} />;
  }
}

export default function WireframeCanvas({ projectId }: { projectId?: string }) {
  if (!projectId) {
    return <Notice title="No project selected" body="Select a project to view its wireframe." />;
  }
  // Keyed on the project so switching boards REMOUNTS rather than leaving the
  // previous app's design on screen — the guarantee the old iframe key gave.
  // It also resets the loader's state without an effect having to do it.
  return <Loader key={projectId} projectId={projectId} />;
}
