/**
 * Graph document -> drafting-sheet model.
 *
 * Pure, browser-free and deterministic, so the audit can run it in Node without
 * rendering anything (see scripts/audit_wireframe_sheet.ts).
 *
 * The sheet does not draw the backend as a graph. Endpoints appear as a short
 * mono annotation under the button that calls them, data models and external
 * services as a footer. That is a deliberate demotion: the connector arrows in
 * the Excalidraw version all originated from the same point, crossed the whole
 * canvas, and made the screens — the part anyone actually reads a wireframe for
 * — compete for attention with the wiring. Naming the endpoint at the control
 * that calls it says the same thing in less space and cannot tangle.
 *
 * What this file must never do is drop something silently. Every node and every
 * edge is either placed or reported in `unplaced`, and the audit fails on a
 * non-empty `unplaced` — a component that vanishes from the sheet is a wrong
 * wireframe you cannot see is wrong.
 */

import type { WDoc, WEdge, WNode } from "./types";

export type Annotation = { handleId: string; label: string; method: string; path: string };

export type Section = {
  id: string;
  index: number;
  title: string;
  caption: string;
  screen: WNode;
  /** endpoint annotations keyed by the button handle that triggers them */
  annotations: Map<string, Annotation[]>;
};

export type SheetModel = {
  title: string;
  detail: string;
  sections: Section[];
  models: { label: string; fields: string[] }[];
  integrations: { label: string; service: string }[];
  /** endpoints no button calls — listed once at the foot, not dropped */
  standaloneEndpoints: { method: string; path: string; desc: string }[];
  counts: { screens: number; endpoints: number; models: number; integrations: number };
  unplaced: string[];
};

/** A one-line description of a screen's composition, in the register of the
 *  captions on a real wireframe sheet ("rail plus table, one primary action"). */
export function describe(screen: WNode): string {
  const body = screen.body;
  const top = body?.children ?? [];
  const parts: string[] = [];

  const roles = top.map((c) => c.role ?? "").filter(Boolean);
  if (body?.type === "row" && top.length >= 2) {
    if (roles.some((r) => ["sidebar", "nav", "rail"].includes(r))) {
      parts.push(top.length >= 3 ? "rail plus two panes" : "rail plus main pane");
    } else {
      parts.push(`${top.length} panes side by side`);
    }
  }

  const flat: string[] = [];
  const walk = (c: { type: string; children?: unknown[] }) => {
    flat.push(c.type);
    for (const k of (c.children as { type: string; children?: unknown[] }[]) ?? []) walk(k);
  };
  if (body) walk(body);

  if (flat.includes("table") || flat.includes("list")) parts.push("tabular data");
  const fields = flat.filter((t) => t === "input" || t === "textarea").length;
  if (fields >= 2) parts.push(`${fields} form fields`);
  const buttons = flat.filter((t) => t === "button").length;
  parts.push(buttons === 0 ? "no primary action" : buttons === 1 ? "one primary action" : `${buttons} actions`);

  return parts.join(", ");
}

export function buildSheet(doc: WDoc): SheetModel {
  const nodes = (doc.nodes ?? []).filter(Boolean);
  const edges = (doc.edges ?? []).filter(Boolean);
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const screens = nodes.filter((n) => n.kind === "screen").sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  const endpoints = nodes.filter((n) => n.kind === "endpoint");
  const entities = nodes.filter((n) => n.kind === "entity");
  const integrations = nodes.filter((n) => n.kind === "integration");

  const unplaced: string[] = [];

  const sections: Section[] = screens.map((screen, i) => ({
    id: screen.id,
    index: i + 1,
    title: screen.label,
    caption: describe(screen),
    screen,
    annotations: new Map<string, Annotation[]>(),
  }));
  const sectionById = new Map(sections.map((s) => [s.id, s]));

  const calledEndpoints = new Set<string>();
  for (const e of edges as WEdge[]) {
    if (e.kind !== "flow") continue;
    const section = sectionById.get(e.source);
    const ep = byId.get(e.target);
    if (!section || !ep || !e.sourceHandle) {
      unplaced.push(`flow edge ${e.id} (${e.source} -> ${e.target}) could not be placed on a screen`);
      continue;
    }
    calledEndpoints.add(ep.id);
    const list = section.annotations.get(e.sourceHandle) ?? [];
    list.push({
      handleId: e.sourceHandle,
      label: e.label ?? "",
      method: ep.method ?? "GET",
      path: ep.path ?? "/",
    });
    section.annotations.set(e.sourceHandle, list);
  }

  // Annotations reference a handle; if no component renders that handle the note
  // would never appear. Catch it here rather than losing it on the page.
  const rendered = new Set<string>();
  const collect = (c: { handleId?: string; children?: unknown[] }) => {
    if (c.handleId) rendered.add(c.handleId);
    for (const k of (c.children as { handleId?: string; children?: unknown[] }[]) ?? []) collect(k);
  };
  for (const s of sections) if (s.screen.body) collect(s.screen.body);
  for (const s of sections) {
    for (const h of s.annotations.keys()) {
      if (!rendered.has(h)) unplaced.push(`annotation for handle ${h} has no component to attach to`);
    }
  }

  return {
    title: doc.title ?? "Wireframe",
    detail: doc.detail ?? "overview",
    sections,
    models: entities.map((e) => ({ label: e.label, fields: e.fields ?? [] })),
    integrations: integrations.map((i) => ({ label: i.label, service: i.service ?? "" })),
    standaloneEndpoints: endpoints
      .filter((e) => !calledEndpoints.has(e.id))
      .map((e) => ({ method: e.method ?? "GET", path: e.path ?? "/", desc: e.desc ?? "" })),
    counts: {
      screens: screens.length,
      endpoints: endpoints.length,
      models: entities.length,
      integrations: integrations.length,
    },
    unplaced,
  };
}
