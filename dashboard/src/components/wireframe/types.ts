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
 * Drafting-sheet palette, resolved from the active theme preset at paint time.
 *
 * Two earlier versions of this got it wrong in opposite directions, and both
 * mistakes are worth keeping written down.
 *
 * The FIRST was an independent sepia palette (#E4DFD4 backdrop, #1F1E1B ink,
 * #B0562A accent) held fixed so the wireframe would "stay on paper when the app
 * is dark". It was right about dark mode and wrong about the values: every one
 * of them was a NEAR-MISS of the token the rest of the dashboard used, and a
 * colour that is close to a token but not equal to it reads as a mistake rather
 * than a decision.
 *
 * The SECOND — correcting that — pinned the palette to Limestone's literal
 * values (#FFFFFF, #F7F5F2, #1A1C1E, ...). That fixed the near-misses and broke
 * something worse: ThemeContext ships eight presets, four of them dark
 * (obsidian, midnight, cyber, sunset), and it applies them by setting CSS custom
 * properties on documentElement at runtime. A hardcoded #1A1C1E ink is the LIGHT
 * foreground; under obsidian, --primary is #F7F5F2 and the whole sheet stayed
 * blinding white while everything around it went dark.
 *
 * So the values below are var() references, not literals. The theme provides
 * foreground (--primary), a muted text tone (--secondary), surfaces (--card,
 * --background) and an accent; everything else is derived with color-mix against
 * `transparent`, which composites over whatever surface is behind it and is
 * therefore correct in both directions rather than tuned for one. `well` mixes
 * toward --primary, so it recedes from --card whichever way the theme runs.
 *
 * This is safe for the Node-side audit: sheet.ts imports only the types above
 * and never PAPER, so nothing browser-only reaches scripts/audit_wireframe_sheet.
 *
 * Still deliberately tonal: colour never encodes meaning here. Endpoints are not
 * coloured by HTTP method and models are not coloured by layer — that made the
 * wiring louder than the screens people actually read a wireframe for. One
 * accent exists, it is the theme's accent, and it is used sparingly.
 *
 * NOTE: these must be applied via the `style` property. A CSS variable does not
 * resolve in an SVG presentation ATTRIBUTE (stroke="..."), only in style.
 */
export const PAPER = {
  sheet: "var(--card)",                                          // the page itself
  sheetEdge: "var(--background)",                                // the desk it lies on
  well: "color-mix(in srgb, var(--primary) 4%, var(--card))",    // recessed surface
  ink: "var(--primary)",                                         // foreground
  inkSoft: "var(--secondary)",
  inkMuted: "color-mix(in srgb, var(--secondary) 70%, transparent)",
  rule: "color-mix(in srgb, var(--secondary) 30%, transparent)",
  ruleStrong: "color-mix(in srgb, var(--secondary) 55%, transparent)",
  fill: "color-mix(in srgb, var(--secondary) 14%, transparent)", // filled controls
  accent: "var(--accent)",
} as const;
