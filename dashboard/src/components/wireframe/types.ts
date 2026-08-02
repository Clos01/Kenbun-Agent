/**
 * The wireframe document, as emitted by core/tools/craft/wireframe_graph.py.
 *
 * Deliberately carries no coordinates. Python decides WHAT connects to what;
 * everything spatial is the renderer's business. See the module docstring in
 * wireframe_graph.py for why that split exists.
 */

export type WComponent = {
  type: string;
  label?: string;
  children?: WComponent[];
  span?: number;
  width?: number;
  role?: string;
  variant?: "primary" | "secondary";
  handleId?: string;
  columns?: string[];
  rows?: number;
  value?: string;
};

export type WNode = {
  id: string;
  kind: "screen" | "endpoint" | "entity" | "integration";
  label: string;
  order?: number;
  body?: WComponent;
  method?: string;
  path?: string;
  desc?: string;
  payload?: string;
  fields?: string[];
  service?: string;
};

export type WEdge = {
  id: string;
  source: string;
  target: string;
  kind: "flow" | "reads" | "writes" | "relation" | "integration";
  label?: string;
  sourceHandle?: string;
};

export type WDoc = {
  type: string;
  version: number;
  title: string;
  detail: string;
  nodes: WNode[];
  edges: WEdge[];
  warnings?: unknown[];
};

/**
 * Fixed drafting-sheet palette.
 *
 * Deliberately NOT wired to the app's theme tokens. The wireframe reads as a
 * document you opened rather than a panel of the dashboard, so it stays on
 * paper in dark mode too. Theme-following was tried in the Excalidraw version
 * and produced a canvas that inverted independently of the app around it.
 */
export const PAPER = {
  sheet: "#F4F1EA",
  sheetEdge: "#E4DFD4",
  ink: "#1F1E1B",
  inkSoft: "#57544C",
  inkMuted: "#8C887E",
  rule: "#CBC6BA",
  ruleStrong: "#A9A497",
  fill: "#E9E5DB",
  accent: "#B0562A",
} as const;
