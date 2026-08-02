/**
 * Sheet audit — runs the REAL doc-to-sheet model outside the browser and asserts
 * that nothing in the document is silently dropped.
 *
 * This replaces the overlap audit, and the reason is worth stating. Overlap was
 * the right thing to test while the renderer positioned boxes itself: the
 * Excalidraw emitter drew two 320px endpoint cards 10px apart and put un-flowed
 * endpoints outside the band meant to contain them, and nothing anywhere looked
 * for it. The sheet renders in normal document flow, so two elements occupying
 * one rectangle is not expressible — testing for it would be testing the browser.
 *
 * The failure that IS possible here is omission. A screen with no body, a flow
 * whose button was never rendered, an endpoint attached to nothing: each would
 * quietly leave the page, and a wireframe missing a screen looks exactly like a
 * wireframe that was meant to have fewer screens. So the invariant is
 * conservation — every node and every edge is either placed on the sheet or
 * named in `unplaced`, and a non-empty `unplaced` fails the run.
 *
 * Usage:
 *   node --experimental-strip-types scripts/audit_wireframe_sheet.ts <doc.json ...>
 */

import { readFileSync } from "node:fs";
import { buildSheet } from "../dashboard/src/components/wireframe/sheet.ts";
import type { WComponent, WDoc } from "../dashboard/src/components/wireframe/types.ts";

const CONTAINERS = new Set(["row", "column", "stack", "region", "group", "panel", "section"]);

/** Leaves only. An EMPTY container is not a leaf — counting it as one made a
 *  screen stripped to a bare `{type:"column", children:[]}` score 1 and slip
 *  past the blank-section check. */
function countLeaves(c: WComponent | undefined): number {
  if (!c) return 0;
  const kids = c.children ?? [];
  if (kids.length > 0) return kids.reduce((n, k) => n + countLeaves(k), 0);
  return CONTAINERS.has(c.type) ? 0 : 1;
}

function audit(file: string): string[] {
  const doc = JSON.parse(readFileSync(file, "utf8")) as WDoc;
  const model = buildSheet(doc);
  const problems: string[] = [...model.unplaced];

  const nodes = doc.nodes ?? [];
  const edges = doc.edges ?? [];
  const kinds = (k: string) => nodes.filter((n) => n.kind === k).length;

  // 1. Conservation of nodes: every screen becomes a section, every model and
  //    integration reaches the footer.
  if (model.sections.length !== kinds("screen")) {
    problems.push(`${kinds("screen")} screens in the document, ${model.sections.length} sections on the sheet`);
  }
  if (model.models.length !== kinds("entity")) {
    problems.push(`${kinds("entity")} models in the document, ${model.models.length} in the footer`);
  }
  if (model.integrations.length !== kinds("integration")) {
    problems.push(`${kinds("integration")} integrations in the document, ${model.integrations.length} in the footer`);
  }

  // 2. Conservation of endpoints: each is either annotated against a control or
  //    listed as standalone. Neither is an error; vanishing is.
  const annotated = new Set<string>();
  for (const s of model.sections) {
    for (const list of s.annotations.values()) for (const a of list) annotated.add(`${a.method} ${a.path}`);
  }
  const accounted = annotated.size + model.standaloneEndpoints.length;
  if (accounted !== kinds("endpoint")) {
    problems.push(`${kinds("endpoint")} endpoints in the document, ${accounted} accounted for on the sheet`);
  }

  // 3. Conservation of flow edges: every one becomes a visible annotation.
  const flowCount = edges.filter((e) => e.kind === "flow").length;
  let noteCount = 0;
  for (const s of model.sections) for (const list of s.annotations.values()) noteCount += list.length;
  if (noteCount !== flowCount) {
    problems.push(`${flowCount} flow edges in the document, ${noteCount} annotations on the sheet`);
  }

  // 4. No section may be blank. An empty frame is indistinguishable from a
  //    rendering failure.
  for (const s of model.sections) {
    if (countLeaves(s.screen.body) === 0) problems.push(`section ${s.index} (${s.title}) renders no components`);
    if (!s.caption.trim()) problems.push(`section ${s.index} (${s.title}) has an empty caption`);
  }

  return problems;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("usage: node --experimental-strip-types scripts/audit_wireframe_sheet.ts <doc.json ...>");
  process.exit(2);
}

let failed = 0;
for (const f of files) {
  const problems = audit(f);
  const doc = JSON.parse(readFileSync(f, "utf8")) as WDoc;
  const label = `${f} — ${doc.nodes?.length ?? 0} nodes, ${doc.edges?.length ?? 0} edges`;
  if (problems.length) {
    failed++;
    console.log(`FAIL  ${label}`);
    problems.slice(0, 10).forEach((p) => console.log(`        ${p}`));
  } else {
    console.log(`PASS  ${label}`);
  }
}
process.exit(failed ? 1 : 0);
