"use client";

/**
 * The board's Wireframe tab.
 *
 * Replaces the previous `<iframe src="/custom_excalidraw.html">`. Beyond the
 * layout problems that motivated the change, the iframe had two defects it could
 * not fix from inside: it followed the OS colour scheme (`prefers-color-scheme`)
 * rather than the app's own theme, so the canvas could sit in dark mode inside a
 * light dashboard; and it opened at whatever viewport the saved scene happened to
 * carry, which on a wide diagram meant landing on empty space. Rendering in-tree
 * fixes the first by construction and the second with a fit-to-content pass once
 * the real node sizes are known.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AlertTriangle, Download, Maximize2 } from "lucide-react";

import { NODE_TYPES } from "./wireframe/nodes";
import { EDGE_STYLE, LAYER_OF, layeredLayout, type WDoc, type WEdge, type WNode } from "./wireframe/layout";

const LEGEND: { kind: WEdge["kind"]; label: string }[] = [
  { kind: "flow", label: "UI action → endpoint" },
  { kind: "writes", label: "writes data" },
  { kind: "reads", label: "reads data" },
  { kind: "relation", label: "model relation" },
  { kind: "integration", label: "external service" },
];

function toFlowNodes(doc: WDoc): Node[] {
  return doc.nodes.map((n: WNode) => ({
    id: n.id,
    type: n.kind,
    position: { x: 0, y: 0 },
    data: { ...n },
    draggable: true,
    // Sorted so a node is never rendered behind the band that labels its layer.
    zIndex: 10 + (LAYER_OF[n.kind] ?? 0),
  }));
}

function toFlowEdges(doc: WDoc): Edge[] {
  return doc.edges.map((e: WEdge) => {
    const s = EDGE_STYLE[e.kind] ?? EDGE_STYLE.reads;
    // A relation runs sideways within the data layer; anchoring it to the same
    // top/bottom handles the vertical edges use makes it loop around the card.
    const sideways = e.kind === "relation";
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? (sideways ? "rel-out" : undefined),
      targetHandle: sideways ? "rel-in" : undefined,
      type: "smoothstep",
      animated: s.animated,
      label: e.kind === "flow" ? e.label : undefined,
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 3,
      labelStyle: { fontSize: 9, fill: s.stroke },
      labelBgStyle: { fill: "var(--card, #fff)", fillOpacity: 0.9 },
      style: {
        stroke: s.stroke,
        strokeWidth: 1.5,
        strokeDasharray: s.dashed ? "4 3" : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: s.stroke, width: 14, height: 14 },
    };
  });
}

function Canvas({ doc }: { doc: WDoc }) {
  const [nodes, setNodes] = useState<Node[]>(() => toFlowNodes(doc));
  const [edges] = useState<Edge[]>(() => toFlowEdges(doc));
  const [laidOut, setLaidOut] = useState(false);
  const initialized = useNodesInitialized();
  const { getNodes, fitView } = useReactFlow();
  const done = useRef(false);

  useEffect(() => {
    if (!initialized || done.current) return;
    done.current = true;

    // Lay out from MEASURED sizes only. A node React Flow has not measured yet is
    // left out rather than guessed at — an assumed size is precisely how the old
    // engine produced boxes drawn on top of one another.
    const sizes = new Map(
      getNodes()
        .filter((n) => n.type !== "band" && n.measured?.width && n.measured?.height)
        .map((n) => [n.id, { width: n.measured!.width!, height: n.measured!.height! }]),
    );

    const { positions, bands } = layeredLayout(doc.nodes, doc.edges, sizes);

    const bandNodes: Node[] = bands.map((b) => ({
      id: `band-${b.layer}`,
      type: "band",
      position: { x: b.x, y: b.y },
      data: { label: b.label, width: b.width, height: b.height },
      draggable: false,
      selectable: false,
      zIndex: 0,
    }));

    setNodes([
      ...bandNodes,
      ...toFlowNodes(doc).map((n) => ({ ...n, position: positions.get(n.id) ?? { x: 0, y: 0 } })),
    ]);
    setLaidOut(true);
    // fitView needs the new positions committed first.
    requestAnimationFrame(() => fitView({ padding: 0.12, duration: 400 }));
  }, [initialized, doc, getNodes, fitView]);

  const download = useCallback(() => {
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${doc.title.replace(/[^a-z0-9]+/gi, "_") || "wireframe"}.wireframe.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [doc]);

  return (
    <div className="relative h-full w-full" style={{ opacity: laidOut ? 1 : 0, transition: "opacity 200ms" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodesChange={(changes) =>
          // Position changes only: the diagram is generated, so a node can be
          // nudged for readability but not added, removed or rewired by hand.
          setNodes((ns) =>
            ns.map((n) => {
              const c = changes.find((ch) => "id" in ch && ch.id === n.id && ch.type === "position");
              return c && "position" in c && c.position ? { ...n, position: c.position } : n;
            }),
          )
        }
        proOptions={{ hideAttribution: true }}
        minZoom={0.05}
        maxZoom={2}
        nodesConnectable={false}
        elementsSelectable
        fitView
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />
        <Controls showInteractive={false} className="!bottom-4 !left-4" />
        <MiniMap pannable zoomable className="!bottom-4 !right-4 !h-24 !w-40" />
      </ReactFlow>

      <div className="pointer-events-none absolute left-0 right-0 top-0 flex items-start justify-between gap-3 p-3">
        <div className="pointer-events-auto rounded-lg border border-border bg-card/90 px-3 py-2 backdrop-blur">
          <div className="truncate text-[11px] font-bold uppercase tracking-[0.15em] text-primary">
            {doc.title}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
            {LEGEND.map((l) => (
              <span key={l.kind} className="flex items-center gap-1.5 text-[9px] text-secondary">
                <span
                  className="inline-block h-0 w-4 border-t-2"
                  style={{
                    borderColor: EDGE_STYLE[l.kind].stroke,
                    borderTopStyle: EDGE_STYLE[l.kind].dashed ? "dashed" : "solid",
                  }}
                />
                {l.label}
              </span>
            ))}
          </div>
        </div>

        <div className="pointer-events-auto flex items-center gap-2">
          <button
            onClick={() => fitView({ padding: 0.12, duration: 400 })}
            className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-card/90 px-2.5 py-1.5 text-[10px] font-semibold text-primary backdrop-blur transition-colors hover:bg-card"
            title="Fit to content"
          >
            <Maximize2 className="h-3 w-3" /> Fit
          </button>
          <button
            onClick={download}
            className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-card/90 px-2.5 py-1.5 text-[10px] font-semibold text-primary backdrop-blur transition-colors hover:bg-card"
            title="Download the wireframe document"
          >
            <Download className="h-3 w-3" /> JSON
          </button>
        </div>
      </div>
    </div>
  );
}

function Notice({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <div className="max-w-md rounded-lg border border-border bg-card/60 p-5 text-center">
        <AlertTriangle className="mx-auto mb-3 h-5 w-5 text-secondary" />
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-primary">{title}</div>
        <p className="mt-2 text-xs leading-relaxed text-secondary">{body}</p>
      </div>
    </div>
  );
}

function Loader({ projectId }: { projectId: string }) {
  const [state, setState] = useState<{ status: "loading" | "ok" | "empty" | "legacy" | "error"; doc?: WDoc; msg?: string }>(
    { status: "loading" },
  );

  useEffect(() => {
    let cancelled = false;

    fetch(`/api/wireframe?project_id=${encodeURIComponent(projectId)}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        // Wireframes saved before the move off Excalidraw are a different format
        // entirely. Say so plainly instead of rendering an empty canvas, which
        // looks identical to "generation failed".
        if (data?.type === "excalidraw") {
          setState({
            status: "legacy",
            msg:
              "This project's wireframe was saved in the old Excalidraw format. " +
              "Re-run generate_wireframe for this project to rebuild it on the new canvas.",
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

  const body = useMemo(() => {
    switch (state.status) {
      case "loading":
        return <div className="flex h-full items-center justify-center text-xs text-secondary">Loading wireframe…</div>;
      case "ok":
        return (
          <ReactFlowProvider>
            <Canvas doc={state.doc!} />
          </ReactFlowProvider>
        );
      case "legacy":
        return <Notice title="Old format" body={state.msg!} />;
      case "error":
        return <Notice title="Could not load" body={state.msg!} />;
      default:
        return <Notice title="Nothing here yet" body={state.msg!} />;
    }
  }, [state]);

  return <div className="h-full w-full">{body}</div>;
}

export default function WireframeCanvas({ projectId }: { projectId?: string }) {
  if (!projectId) {
    return <Notice title="No project selected" body="Select a project to view its wireframe." />;
  }
  // Keyed on the project so switching boards REMOUNTS rather than leaving the
  // previous app's design on screen — the same guarantee the old iframe key gave.
  // It also resets the loader's state without an effect having to do it.
  return <Loader key={projectId} projectId={projectId} />;
}
