/**
 * Layered layout for the wireframe graph.
 *
 * The document that arrives from the generator carries NO coordinates — only
 * which node connects to which. Everything spatial is decided here, from sizes
 * the browser actually measured, which is the point: the previous generator
 * computed x/y in Python from a table of nominal component heights, and the two
 * disagreed often enough that content routinely escaped its frame and backend
 * cards were drawn on top of one another.
 *
 * The algorithm is the ordering half of Sugiyama, which is what the old code was
 * groping towards with "centre this endpoint under the button that calls it":
 *
 *   1. Nodes are assigned to a fixed layer by kind (screens, endpoints, data).
 *   2. Within a layer, nodes are ordered by the BARYCENTRE of their neighbours
 *      in the layer above — the average position of the things pointing at them.
 *      That is the principled version of "put it under its caller", and unlike
 *      the old version it degrades gracefully when a node has two callers, or
 *      none, instead of stacking everything at one x or falling off the canvas.
 *   3. Each layer is packed left-to-right at measured widths with a fixed gutter,
 *      then centred.
 *
 * Overlap is impossible by construction: a layer is a single row of boxes laid
 * end to end, and layers are stacked below one another by measured height. There
 * is no case left where two nodes can be assigned the same rectangle, which is
 * the failure the old emitter could not stop reproducing.
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

/** Layer index by node kind. Entities and integrations share the bottom layer:
 *  they are peers (both are things an endpoint talks to), and giving them their
 *  own rows produced two half-empty bands. */
export const LAYER_OF: Record<WNode["kind"], number> = {
  screen: 0,
  endpoint: 1,
  entity: 2,
  integration: 2,
};

export const BANDS = [
  { layer: 0, label: "FRONTEND · UI SCREENS" },
  { layer: 1, label: "BACKEND · API ENDPOINTS" },
  { layer: 2, label: "DATA & INTEGRATIONS" },
];

const H_GAP = 64; // gutter between siblings in a layer
const V_GAP = 150; // vertical breathing room between layers
const BAND_PAD = 32; // padding from a band's edge to the nodes inside it

export type Size = { width: number; height: number };
export type Pos = { x: number; y: number };

export type LayoutResult = {
  positions: Map<string, Pos>;
  bands: { layer: number; label: string; x: number; y: number; width: number; height: number }[];
};

/**
 * @param sizes MEASURED sizes, keyed by node id. A node missing from this map is
 *              skipped rather than guessed at — placing a box at an assumed size
 *              is exactly how the old engine produced overlaps.
 */
export function layeredLayout(
  nodes: WNode[],
  edges: WEdge[],
  sizes: Map<string, Size>,
): LayoutResult {
  const placeable = nodes.filter((n) => sizes.has(n.id));
  const layers = new Map<number, WNode[]>();
  for (const n of placeable) {
    const l = LAYER_OF[n.kind] ?? 0;
    if (!layers.has(l)) layers.set(l, []);
    layers.get(l)!.push(n);
  }

  // Inbound neighbours, used for the barycentre. Relation edges are excluded:
  // they run WITHIN the data layer, so letting them vote on ordering makes a
  // node try to sit under its sibling and fights the layer above.
  const inbound = new Map<string, string[]>();
  for (const e of edges) {
    if (e.kind === "relation") continue;
    if (!inbound.has(e.target)) inbound.set(e.target, []);
    inbound.get(e.target)!.push(e.source);
  }

  const positions = new Map<string, Pos>();
  const centreOf = new Map<string, number>(); // node id -> centre x, for the next layer
  const rows: { layer: number; nodes: WNode[]; y: number; height: number }[] = [];

  let cursorY = 0;
  const sortedLayers = [...layers.keys()].sort((a, b) => a - b);

  for (const layerIdx of sortedLayers) {
    const group = layers.get(layerIdx)!;

    // Ordering. A node whose parents are all in a layer we have already placed
    // gets their average centre; a node with no placed parent gets Infinity so it
    // lands at the END of the row — inside the band, in spec order. The old code
    // sent exactly these nodes to x = -70, outside the band entirely.
    const bary = new Map<string, number>();
    for (const n of group) {
      const parents = (inbound.get(n.id) || [])
        .map((p) => centreOf.get(p))
        .filter((v): v is number => typeof v === "number");
      bary.set(n.id, parents.length ? parents.reduce((a, b) => a + b, 0) / parents.length : Infinity);
    }
    group.sort((a, b) => {
      const d = bary.get(a.id)! - bary.get(b.id)!;
      if (Number.isFinite(d) && d !== 0) return d;
      if (bary.get(a.id) !== bary.get(b.id)) return bary.get(a.id)! - bary.get(b.id)!;
      // Stable tiebreak, so the same document always lays out identically.
      return (a.order ?? 0) - (b.order ?? 0) || a.id.localeCompare(b.id);
    });

    const rowW =
      group.reduce((sum, n) => sum + sizes.get(n.id)!.width, 0) + H_GAP * (group.length - 1);
    const rowH = Math.max(...group.map((n) => sizes.get(n.id)!.height));

    let x = -rowW / 2; // centred on 0; the whole scene is re-origined at the end
    for (const n of group) {
      const s = sizes.get(n.id)!;
      // Top-align within the row. Bottom-aligning tall and short cards in the same
      // row makes the row read as two rows.
      positions.set(n.id, { x, y: cursorY });
      centreOf.set(n.id, x + s.width / 2);
      x += s.width + H_GAP;
    }

    rows.push({ layer: layerIdx, nodes: group, y: cursorY, height: rowH });
    cursorY += rowH + V_GAP;
  }

  // Re-origin so the whole scene sits in positive space, and size the bands to
  // what was actually placed rather than to a guessed width.
  const allX = [...positions.entries()].map(([id, p]) => [p.x, p.x + sizes.get(id)!.width]);
  const minX = allX.length ? Math.min(...allX.map((a) => a[0])) : 0;
  const maxX = allX.length ? Math.max(...allX.map((a) => a[1])) : 0;
  const shiftX = -minX + BAND_PAD;
  const shiftY = BAND_PAD;
  for (const [id, p] of positions) positions.set(id, { x: p.x + shiftX, y: p.y + shiftY });

  const bandW = maxX - minX + BAND_PAD * 2;
  const bands = rows.map((r) => ({
    layer: r.layer,
    label: BANDS.find((b) => b.layer === r.layer)?.label ?? "",
    x: 0,
    y: r.y + shiftY - BAND_PAD,
    width: bandW,
    height: r.height + BAND_PAD * 2,
  }));

  return { positions, bands };
}

/** Edge styling by semantic kind, so the picture reads without a legend. */
export const EDGE_STYLE: Record<
  WEdge["kind"],
  { stroke: string; dashed: boolean; animated: boolean }
> = {
  flow: { stroke: "#1971c2", dashed: false, animated: true },
  writes: { stroke: "#e8590c", dashed: false, animated: false },
  reads: { stroke: "#868e96", dashed: true, animated: false },
  relation: { stroke: "#7048e8", dashed: true, animated: false },
  integration: { stroke: "#0ca678", dashed: false, animated: false },
};

export const METHOD_COLOR: Record<string, string> = {
  GET: "#2f9e44",
  POST: "#1971c2",
  PUT: "#f08c00",
  PATCH: "#f08c00",
  DELETE: "#e03131",
};
