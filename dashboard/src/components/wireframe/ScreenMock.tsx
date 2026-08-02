"use client";

/**
 * Renders one screen's component tree as real HTML, in ink on paper.
 *
 * Two things this file is doing, and they are separate.
 *
 * FIRST, flexbox. The previous engine drew each widget as an absolutely
 * positioned Excalidraw rectangle and hand-summed the heights in Python: a
 * table's height came from one expression, the frame meant to contain it from
 * another, and whenever the two drifted the content spilled out and collided
 * with the next screen. Text had the mirror problem — Excalidraw text does not
 * wrap or clip, so a label ran under its neighbour and the generator carried a
 * hand-built table of per-glyph advance widths to guess when to ellipsise.
 * Flexbox settles both, exactly, for every component type at once, and a new
 * component type cannot desynchronise anything because there is no second
 * height calculation to keep in sync.
 *
 * SECOND, the palette. Colours are fixed values from PAPER rather than the app's
 * theme tokens. A wireframe is a document, not a panel of the dashboard, and it
 * stays on paper when the app is dark. Colour is not used to encode meaning
 * anywhere here: the Excalidraw version coloured endpoints by HTTP method and
 * models by layer, which made the wiring louder than the screens people
 * actually read the wireframe for. One accent exists and is used sparingly.
 */

import React from "react";
import { PAPER, type WComponent } from "./types";

const CONTAINERS = new Set(["row", "column", "stack", "region", "group", "panel", "section"]);

const truncate: React.CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const rule = `0.5px solid ${PAPER.rule}`;

/** Diagonal hatching, the sketch convention for "a chart goes here". Defined
 *  once and referenced by id so a sheet with twenty charts carries one pattern. */
export function HatchDefs() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true">
      <defs>
        <pattern id="wf-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke={PAPER.ruleStrong} strokeWidth="1.1" />
        </pattern>
      </defs>
    </svg>
  );
}

function Leaf({ c }: { c: WComponent }) {
  const label = c.label ?? "";

  switch (c.type) {
    case "header":
      return <div style={{ ...truncate, fontSize: 15, color: PAPER.ink }}>{label}</div>;

    case "subheader":
      return <div style={{ ...truncate, fontSize: 12, color: PAPER.inkSoft }}>{label}</div>;

    case "text":
      return (
        <div style={{ fontSize: 11, lineHeight: 1.5, color: PAPER.inkSoft, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {label}
        </div>
      );

    case "link":
      return (
        <div style={{ ...truncate, fontSize: 11, color: PAPER.inkSoft, textDecoration: "underline", textUnderlineOffset: 2 }}>
          {label}
        </div>
      );

    case "input":
    case "textarea":
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {label && <div style={{ ...truncate, fontSize: 10, color: PAPER.inkMuted }}>{label}</div>}
          <div style={{ height: c.type === "textarea" ? 46 : 22, border: rule, borderRadius: 3, background: "#FBF9F5" }} />
        </div>
      );

    case "button": {
      const primary = (c.variant ?? "primary") === "primary";
      return (
        <div
          style={{
            ...truncate,
            display: "inline-block",
            maxWidth: "100%",
            fontSize: 11,
            padding: "5px 14px",
            borderRadius: 3,
            border: primary ? `1px solid ${PAPER.ink}` : rule,
            color: PAPER.ink,
            background: primary ? PAPER.fill : "transparent",
          }}
        >
          {label}
        </div>
      );
    }

    case "nav":
      return (
        <div style={{ ...truncate, fontSize: 11, color: PAPER.inkSoft, padding: "4px 8px", borderRadius: 3 }}>
          {label || "Navigation"}
        </div>
      );

    case "badge":
      return (
        <span style={{ ...truncate, display: "inline-block", maxWidth: "100%", fontSize: 10, padding: "2px 8px", borderRadius: 9, border: `0.5px solid ${PAPER.ruleStrong}`, color: PAPER.inkSoft }}>
          {label}
        </span>
      );

    case "divider":
      return <div style={{ height: 1, background: PAPER.rule }} />;

    case "checkbox":
    case "radio":
      return (
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ width: 11, height: 11, flexShrink: 0, border: `0.5px solid ${PAPER.ruleStrong}`, borderRadius: c.type === "radio" ? "50%" : 2 }} />
          <div style={{ ...truncate, fontSize: 11, color: PAPER.ink }}>{label}</div>
        </div>
      );

    case "image":
      return (
        <svg viewBox="0 0 100 46" preserveAspectRatio="none" style={{ width: "100%", height: 62, display: "block" }} role="img" aria-label={label || "image placeholder"}>
          <rect x="0.5" y="0.5" width="99" height="45" fill="url(#wf-hatch)" stroke={PAPER.rule} strokeWidth="0.5" />
        </svg>
      );

    case "avatar":
    case "card":
      return (
        <div style={{ minWidth: 0, border: rule, borderRadius: 3, padding: "7px 9px" }}>
          <div style={{ ...truncate, fontSize: 10, color: PAPER.inkMuted }}>{label || "Card"}</div>
          {c.value ? (
            <div style={{ ...truncate, marginTop: 2, fontSize: 15, color: PAPER.ink }}>{c.value}</div>
          ) : (
            <div style={{ marginTop: 6, height: 2, width: "60%", background: PAPER.rule }} />
          )}
        </div>
      );

    case "list":
    case "table": {
      const cols = c.columns ?? [];
      const rows = Math.max(1, Math.min(c.rows ?? 4, 8));
      return (
        <div style={{ border: rule, borderRadius: 3, overflow: "hidden" }}>
          <div style={{ ...truncate, borderBottom: rule, padding: "4px 9px", fontSize: 10, color: PAPER.inkMuted }}>
            {label || (c.type === "table" ? "Table" : "List")}
          </div>
          {cols.length > 0 ? (
            <table style={{ width: "100%", tableLayout: "fixed", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {cols.map((col, i) => (
                    <th key={i} style={{ ...truncate, textAlign: "left", padding: "4px 9px", borderBottom: rule, fontSize: 10, fontWeight: 400, color: PAPER.inkMuted }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: rows }).map((_, r) => (
                  <tr key={r}>
                    {cols.map((_, ci) => (
                      <td key={ci} style={{ padding: "5px 9px" }}>
                        <div style={{ height: 2, background: ci === 0 ? PAPER.ruleStrong : PAPER.rule }} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: "7px 9px" }}>
              {Array.from({ length: rows }).map((_, r) => (
                <div key={r} style={{ height: 2, background: PAPER.rule, width: `${92 - r * 8}%` }} />
              ))}
            </div>
          )}
        </div>
      );
    }

    default:
      // An unrecognised type renders as its label rather than disappearing. A
      // silently dropped component is a wrong wireframe you cannot see is wrong.
      return <div style={{ ...truncate, fontSize: 11, color: PAPER.inkSoft }}>{label || c.type}</div>;
  }
}

export function ComponentTree({
  c,
  annotate,
}: {
  c: WComponent;
  /** renders the endpoint note that belongs under a given control */
  annotate?: (handleId: string) => React.ReactNode;
}) {
  const children = c.children ?? [];

  if (CONTAINERS.has(c.type) && children.length > 0) {
    const horizontal = c.type === "row";
    const isSidebar = ["sidebar", "nav", "rail"].includes(c.role ?? "");

    const inner = (
      <div
        style={{
          display: "flex",
          minWidth: 0,
          flexDirection: horizontal ? "row" : "column",
          alignItems: horizontal ? "flex-start" : undefined,
          gap: horizontal ? 12 : 9,
        }}
      >
        {children.map((child, i) => (
          <div
            key={i}
            style={
              horizontal
                ? // basis 0 + grow makes span/width behave as the RELATIVE weight
                  // the spec promises. Without basis 0 a long table quietly wins
                  // the whole row regardless of the weights.
                  { minWidth: 0, flexGrow: child.span ?? child.width ?? 1, flexBasis: 0 }
                : { minWidth: 0 }
            }
          >
            <ComponentTree c={child} annotate={annotate} />
          </div>
        ))}
      </div>
    );

    if (isSidebar) {
      return <div style={{ borderRight: rule, paddingRight: 12, minWidth: 0 }}>{inner}</div>;
    }
    if (["section", "panel", "region"].includes(c.type) && c.label) {
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
          <div style={{ ...truncate, fontSize: 10, color: PAPER.inkMuted, letterSpacing: "0.06em" }}>{c.label}</div>
          {inner}
        </div>
      );
    }
    return inner;
  }

  const note = c.handleId && annotate ? annotate(c.handleId) : null;
  if (note) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
        <Leaf c={c} />
        {note}
      </div>
    );
  }
  return <Leaf c={c} />;
}
