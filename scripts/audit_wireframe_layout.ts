/**
 * Layout audit — runs the REAL layout code outside the browser and asserts the
 * property the old engine could not hold: no two nodes ever occupy the same
 * rectangle, and every node sits inside the band that labels its layer.
 *
 * This exists because the previous audits checked the wrong thing. They measured
 * text overflow and frame escape — real problems, but not the one that made the
 * board unreadable. Nothing anywhere checked card-against-card overlap, so a
 * generator that routinely drew two 320px endpoint cards 10px apart, and put
 * un-flowed endpoints at x = -70 (outside the band entirely), passed every check
 * it had.
 *
 * Sizes are FUZZED rather than fixed. Real sizes come from the browser and vary
 * with content; a single hand-picked set would only prove the algorithm works for
 * that set, which is exactly the assumption the old engine died on.
 *
 * Usage:
 *   node --experimental-strip-types scripts/audit_wireframe_layout.ts [doc.json ...]
 */

import { readFileSync } from "node:fs";
import {
  layeredLayout,
  LAYER_OF,
  type Size,
  type WDoc,
  type WNode,
} from "../dashboard/src/components/wireframe/layout.ts";

// Deterministic PRNG: a failing seed has to be reproducible to be worth anything.
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

/** Plausible measured sizes per node kind, with the variance real content has. */
function fuzzSizes(nodes: WNode[], seed: number): Map<string, Size> {
  const r = rng(seed);
  const m = new Map<string, Size>();
  for (const n of nodes) {
    switch (n.kind) {
      case "screen":
        m.set(n.id, { width: [340, 560, 720][Math.floor(r() * 3)], height: 160 + r() * 700 });
        break;
      case "endpoint":
        m.set(n.id, { width: 320, height: 56 + (r() < 0.3 ? r() * 200 : 0) });
        break;
      case "entity":
        m.set(n.id, { width: 260, height: 60 + r() * 220 });
        break;
      default:
        m.set(n.id, { width: 240, height: 78 });
    }
  }
  return m;
}

type Rect = { id: string; x: number; y: number; w: number; h: number };

function overlaps(a: Rect, b: Rect): number {
  const ix = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const iy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return ix > 0.5 && iy > 0.5 ? ix * iy : 0;
}

function auditOnce(doc: WDoc, seed: number) {
  const sizes = fuzzSizes(doc.nodes, seed);
  const { positions, bands } = layeredLayout(doc.nodes, doc.edges, sizes);
  const problems: string[] = [];

  const rects: Rect[] = doc.nodes
    .filter((n) => positions.has(n.id))
    .map((n) => ({
      id: n.id,
      x: positions.get(n.id)!.x,
      y: positions.get(n.id)!.y,
      w: sizes.get(n.id)!.width,
      h: sizes.get(n.id)!.height,
    }));

  if (rects.length !== doc.nodes.length) {
    problems.push(`${doc.nodes.length - rects.length} node(s) were not placed at all`);
  }

  // 1. No two nodes may share a rectangle. This is THE check.
  for (let i = 0; i < rects.length; i++) {
    for (let j = i + 1; j < rects.length; j++) {
      const area = overlaps(rects[i], rects[j]);
      if (area > 0) problems.push(`OVERLAP ${rects[i].id} × ${rects[j].id} (${Math.round(area)}px²)`);
    }
  }

  // 2. Every node must sit inside the band for its layer. The old engine put
  //    un-flowed endpoints 120px outside the band that was supposed to hold them.
  const bandByLayer = new Map(bands.map((b) => [b.layer, b]));
  for (const n of doc.nodes) {
    const p = positions.get(n.id);
    if (!p) continue;
    const band = bandByLayer.get(LAYER_OF[n.kind]);
    if (!band) {
      problems.push(`${n.id} is in layer ${LAYER_OF[n.kind]} but no band was emitted for it`);
      continue;
    }
    const s = sizes.get(n.id)!;
    if (
      p.x < band.x - 0.5 ||
      p.y < band.y - 0.5 ||
      p.x + s.width > band.x + band.width + 0.5 ||
      p.y + s.height > band.y + band.height + 0.5
    ) {
      problems.push(
        `OUT OF BAND ${n.id} at (${Math.round(p.x)},${Math.round(p.y)}) ` +
          `${Math.round(s.width)}×${Math.round(s.height)} vs band ` +
          `(${Math.round(band.x)},${Math.round(band.y)}) ${Math.round(band.width)}×${Math.round(band.height)}`,
      );
    }
  }

  // 3. Bands must not overlap each other.
  for (let i = 0; i < bands.length; i++) {
    for (let j = i + 1; j < bands.length; j++) {
      const a = bands[i];
      const b = bands[j];
      if (overlaps({ id: "a", x: a.x, y: a.y, w: a.width, h: a.height },
                   { id: "b", x: b.x, y: b.y, w: b.width, h: b.height }) > 0) {
        problems.push(`BAND OVERLAP layer ${a.layer} × layer ${b.layer}`);
      }
    }
  }

  // 4. Nothing may be placed in negative space; the canvas origin is the corner.
  for (const r of rects) {
    if (r.x < 0 || r.y < 0) problems.push(`NEGATIVE ORIGIN ${r.id} at (${Math.round(r.x)},${Math.round(r.y)})`);
  }

  return problems;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("usage: node --experimental-strip-types scripts/audit_wireframe_layout.ts <doc.json ...>");
  process.exit(2);
}

let failed = 0;
const SEEDS = 200;
for (const f of files) {
  const doc = JSON.parse(readFileSync(f, "utf8")) as WDoc;
  const found: string[] = [];
  for (let seed = 1; seed <= SEEDS; seed++) {
    const p = auditOnce(doc, seed);
    if (p.length) found.push(`  seed ${seed}: ${p[0]}${p.length > 1 ? ` (+${p.length - 1} more)` : ""}`);
  }
  const label = `${f} — ${doc.nodes?.length ?? 0} nodes, ${doc.edges?.length ?? 0} edges, ${SEEDS} size fuzzes`;
  if (found.length) {
    failed++;
    console.log(`FAIL  ${label}`);
    found.slice(0, 10).forEach((l) => console.log(l));
    if (found.length > 10) console.log(`  … +${found.length - 10} more failing seeds`);
  } else {
    console.log(`PASS  ${label}`);
  }
}
process.exit(failed ? 1 : 0);
