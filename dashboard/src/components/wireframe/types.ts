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
 * Drafting-sheet palette, derived from the Heritage tokens.
 *
 * This used to be an independent sepia palette, justified on the grounds that a
 * wireframe "stays on paper when the app is dark". The dashboard has no dark
 * mode — `:root` and `.light` in globals.css are identical — so that argument
 * was defending against a case that cannot arise, and what it actually produced
 * was a set of NEAR-MISSES: #E4DFD4 backdrop against the app's #F7F5F2, #1F1E1B
 * ink against #1A1C1E, #B0562A accent against Boston Clay #B8422E. A colour that
 * is close to a token but not equal to it reads as a mistake, where either an
 * exact match or a frank contrast would have read as a decision.
 *
 * The hue was the louder half of the problem. Heritage is COOL slate text on
 * WARM paper; the old palette was warm-on-warm throughout, so its greys drifted
 * yellow against every other panel in the dashboard. The neutrals below are
 * tints of --secondary (#6C7278) so they sit in the same slate family, over a
 * --card sheet on the app's own --neutral background.
 *
 * Still deliberately tonal: colour never encodes meaning here. Endpoints are not
 * coloured by HTTP method and models are not coloured by layer — that made the
 * wiring louder than the screens people actually read a wireframe for. One
 * accent exists, it is the Heritage accent, and it is used sparingly.
 *
 * Keep these in sync with globals.css. They are literals rather than var()
 * lookups because sheet.ts must stay browser-free for the Node-side audit.
 */
export const PAPER = {
  sheet: "#FFFFFF",       // --card: the page itself
  sheetEdge: "#F7F5F2",   // --background: the desk the page lies on
  well: "#F7F5F2",        // recessed surface inside the page (screen frames)
  ink: "#1A1C1E",         // --primary
  inkSoft: "#6C7278",     // --secondary
  inkMuted: "#A7AAAE",    // --secondary @ 60%
  rule: "#DADCDD",        // --secondary @ 25%
  ruleStrong: "#BDC0C2",  // --secondary @ 45%
  fill: "#EDEEEF",        // --secondary @ 12%, for filled controls
  accent: "#B8422E",      // --tertiary, Boston Clay
} as const;
