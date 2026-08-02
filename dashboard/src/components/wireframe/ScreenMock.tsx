"use client";

/**
 * Renders one screen's component tree as real HTML.
 *
 * This file is the reason the wireframe stopped looking broken. The previous
 * engine drew each widget as an absolutely-positioned Excalidraw rectangle and
 * hand-summed the heights in Python: a table's height came from one expression,
 * the frame that was supposed to contain it from another, and whenever the two
 * drifted the content spilled out of its frame and collided with the next screen.
 * Text had the same problem in the other axis — Excalidraw text does not wrap or
 * clip, so a label simply ran under its neighbour and the generator had to carry
 * a hand-built table of per-glyph advance widths to guess when to ellipsise.
 *
 * Flexbox already solves both, exactly and for every component type at once. A
 * child cannot escape its parent, `truncate` clips a label at whatever width it
 * really has, and adding a new component type cannot desynchronise anything
 * because there is no second height calculation to keep in sync.
 */

import React from "react";
import { Handle, Position } from "@xyflow/react";
import type { WComponent } from "./layout";

const CONTAINERS = new Set(["row", "column", "stack", "region", "group", "panel", "section"]);

function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`truncate ${className ?? ""}`}>{children}</div>;
}

function Leaf({ c }: { c: WComponent }) {
  const label = c.label ?? "";

  switch (c.type) {
    case "header":
      return <Label className="text-[15px] font-semibold text-primary">{label}</Label>;

    case "subheader":
      return <Label className="text-[12px] text-secondary">{label}</Label>;

    case "text":
      return <div className="text-[11px] leading-snug text-secondary line-clamp-3">{label}</div>;

    case "link":
      return <Label className="text-[11px] text-tertiary underline underline-offset-2">{label}</Label>;

    case "input":
    case "textarea":
      return (
        <div className="flex flex-col gap-1">
          {label && <Label className="text-[9px] uppercase tracking-wider text-secondary/70">{label}</Label>}
          <div
            className={`rounded border border-border bg-neutral/60 ${
              c.type === "textarea" ? "h-12" : "h-6"
            }`}
          />
        </div>
      );

    case "button": {
      const primary = (c.variant ?? "primary") === "primary";
      return (
        <div className="relative inline-flex">
          <div
            className={`relative rounded px-3 py-1.5 text-[11px] font-semibold truncate max-w-full ${
              primary
                ? "bg-tertiary text-white"
                : "border border-border bg-card text-primary"
            }`}
          >
            {label}
          </div>
          {/* The flow arrow leaves from the button itself, not the screen's
              outline. When every arrow started at the same point the diagram
              read as a bundle of yarn and you could not tell which control
              called which endpoint. */}
          {c.handleId && (
            <Handle
              type="source"
              position={Position.Bottom}
              id={c.handleId}
              className="!h-1.5 !w-1.5 !border-0 !bg-tertiary"
            />
          )}
        </div>
      );
    }

    case "nav":
      return (
        <div className="rounded border border-dashed border-border px-2 py-1.5">
          <Label className="text-[10px] text-primary">{label || "Navigation"}</Label>
        </div>
      );

    case "badge":
      return (
        <span className="inline-block max-w-full truncate rounded-full border border-tertiary/40 bg-tertiary/10 px-2 py-0.5 text-[9px] font-semibold text-tertiary">
          {label}
        </span>
      );

    case "divider":
      return <div className="h-px w-full bg-border" />;

    case "checkbox":
    case "radio":
      return (
        <div className="flex items-center gap-2">
          <span
            className={`h-3 w-3 shrink-0 border border-secondary/60 ${
              c.type === "radio" ? "rounded-full" : "rounded-[2px]"
            }`}
          />
          <Label className="text-[11px] text-primary">{label}</Label>
        </div>
      );

    case "image":
      return (
        <div className="flex h-16 items-center justify-center rounded border border-dashed border-border bg-neutral/40 text-[9px] uppercase tracking-wider text-secondary/60">
          {label || "image"}
        </div>
      );

    case "avatar":
    case "card":
      return (
        <div className="min-w-0 rounded border border-border bg-card/60 px-2.5 py-2">
          <Label className="text-[9px] uppercase tracking-wider text-secondary/70">{label || "Card"}</Label>
          {c.value ? (
            <div className="mt-1 truncate text-[13px] font-semibold text-primary">{c.value}</div>
          ) : (
            <div className="mt-1.5 h-px w-2/3 bg-border" />
          )}
        </div>
      );

    case "list":
    case "table": {
      const cols = c.columns ?? [];
      const rows = Math.max(1, Math.min(c.rows ?? 4, 8));
      return (
        <div className="overflow-hidden rounded border border-border">
          <div className="border-b border-border bg-neutral/60 px-2 py-1">
            <Label className="text-[10px] font-semibold text-primary">
              {label || (c.type === "table" ? "Table" : "List")}
            </Label>
          </div>
          {cols.length > 0 ? (
            <table className="w-full table-fixed border-collapse">
              <thead>
                <tr>
                  {cols.map((col, i) => (
                    <th
                      key={i}
                      className="truncate border-b border-border px-2 py-1 text-left text-[9px] font-medium uppercase tracking-wide text-secondary/80"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: rows }).map((_, r) => (
                  <tr key={r}>
                    {cols.map((_, ci) => (
                      <td key={ci} className="px-2 py-[3px]">
                        <div className="h-1 w-full rounded-full bg-border" />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="flex flex-col gap-1.5 px-2 py-2">
              {Array.from({ length: rows }).map((_, r) => (
                <div key={r} className="h-1 rounded-full bg-border" style={{ width: `${90 - r * 7}%` }} />
              ))}
            </div>
          )}
        </div>
      );
    }

    default:
      // An unrecognised type renders as its label rather than disappearing. A
      // silently dropped component is a wrong wireframe you cannot see is wrong.
      return <Label className="text-[11px] text-secondary">{label || c.type}</Label>;
  }
}

export function ComponentTree({ c, depth = 0 }: { c: WComponent; depth?: number }) {
  const children = c.children ?? [];

  if (CONTAINERS.has(c.type) && children.length > 0) {
    const horizontal = c.type === "row";
    const isSidebar = ["sidebar", "nav", "rail"].includes(c.role ?? "");

    const inner = (
      <div className={`flex min-w-0 ${horizontal ? "flex-row items-start gap-3" : "flex-col gap-2"}`}>
        {children.map((child, i) => (
          <div
            key={i}
            className="min-w-0"
            style={
              horizontal
                ? // flexBasis 0 + grow makes span/width behave as the RELATIVE
                  // weight the spec promises, regardless of content size. Without
                  // basis:0 a long table would quietly win the whole row.
                  { flexGrow: child.span ?? child.width ?? 1, flexBasis: 0 }
                : undefined
            }
          >
            <ComponentTree c={child} depth={depth + 1} />
          </div>
        ))}
      </div>
    );

    if (isSidebar) {
      return <div className="rounded border border-border bg-neutral/50 p-2">{inner}</div>;
    }
    if (["section", "panel", "region"].includes(c.type) && c.label) {
      return (
        <div className="flex flex-col gap-1.5">
          <Label className="text-[9px] uppercase tracking-[0.15em] text-secondary/60">{c.label}</Label>
          {inner}
        </div>
      );
    }
    return inner;
  }

  return <Leaf c={c} />;
}

/** How wide to render a screen: a sidebar+main layout genuinely needs more room
 *  than a single stack, and cramming it into one fixed width is what forced every
 *  label in a split screen to ellipsise. */
export function screenWidth(body?: WComponent): number {
  const top = body?.children ?? [];
  if (body?.type === "row") {
    if (top.length >= 3) return 720;
    if (top.length === 2) return 560;
  }
  return 340;
}
