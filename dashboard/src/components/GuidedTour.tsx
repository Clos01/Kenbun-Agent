"use client";

import React, { useState, useEffect, useCallback, useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, ArrowLeft, ArrowRight, Sparkles } from "lucide-react";

export interface TourStep {
  selector: string;
  title: string;
  body: string;
}

/**
 * GuidedTour — game-style spotlight walkthrough.
 * Dims the page, cuts a spotlight hole around the target element, wraps it in a
 * pulsing ring, and tethers a callout with Back / Next / progress dots.
 * Launch by dispatching: window.dispatchEvent(new CustomEvent("kenbun:start-tour", { detail: { module } }))
 * A page mounts <GuidedTour module="hivemind" steps={[...]} /> and it activates when the module matches.
 */
export default function GuidedTour({ module, steps }: { module: string; steps: TourStep[] }) {
  const [active, setActive] = useState(false);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<{ top: number; left: number; width: number; height: number } | null>(null);
  const [mounted, setMounted] = useState(false);
  // Measured height of the callout. Placement needs it before it can decide
  // which gap the callout fits in; the seed is only used for the first frame.
  const calloutRef = useRef<HTMLDivElement | null>(null);
  const [calloutH, setCalloutH] = useState(280);

      // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);

  // Register this page's tour so global UI (e.g. the guide modal) can tell a tour exists here
  useEffect(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const w = window as any;
    (w.__kenbunTours = w.__kenbunTours || new Set()).add(module);
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
    return () => { try { w.__kenbunTours?.delete(module); } catch (_) {} };
  }, [module]);

  useEffect(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const onStart = (e: any) => {
      if (!e?.detail || e.detail.module === module) {
        setI(0);
        setActive(true);
      }
    };
    window.addEventListener("kenbun:start-tour", onStart as EventListener);
    return () => window.removeEventListener("kenbun:start-tour", onStart as EventListener);
  }, [module]);

  const measure = useCallback(() => {
    const step = steps[i];
    if (!step) return;
    const el = document.querySelector(step.selector) as HTMLElement | null;
    if (!el) { setRect(null); return; }
    const r = el.getBoundingClientRect();
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
  }, [i, steps]);

  // scroll target into view when the step changes
  useLayoutEffect(() => {
    if (!active) return;
    const step = steps[i];
    const el = step && (document.querySelector(step.selector) as HTMLElement | null);
    if (el) {
      // Top-align under the sticky subsystem bar rather than centring.
      // Centring splits the leftover space above and below the target, so a
      // mid-height panel ends up with two gaps that are each too small for the
      // callout; top-aligning pools it all below.
      // Instant, not smooth: this page re-renders on a 5s poll and smooth
      // scrolling is silently cancelled here (measured — scrollY never moved),
      // which left every step measuring a target still far below the fold.
      const STICKY_HEADER = 96;
      const top = window.scrollY + el.getBoundingClientRect().top - STICKY_HEADER;
      window.scrollTo({ top: Math.max(0, top) });
    }
      // eslint-disable-next-line react-hooks/set-state-in-effect
    measure();
  }, [active, i, steps, measure]);

  // keep the ring glued to the target through scroll / resize / layout shifts
  useEffect(() => {
    if (!active) return;
    const onMove = () => measure();
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, true);
    const t = setInterval(measure, 300);
    return () => {
      window.removeEventListener("resize", onMove);
      window.removeEventListener("scroll", onMove, true);
      clearInterval(t);
    };
  }, [active, measure]);

  // Measure the rendered callout so placement uses its real height. Runs after
  // every render (the ring re-measures on a 300ms tick, so this settles with
  // it); guarded on a changed value to avoid a render loop.
  useLayoutEffect(() => {
    const h = calloutRef.current?.offsetHeight;
    if (h && Math.abs(h - calloutH) > 1) setCalloutH(h);
  }, [calloutH]);

  const close = useCallback(() => setActive(false), []);
  const next = useCallback(() => setI((p) => (p < steps.length - 1 ? p + 1 : (setActive(false), p))), [steps.length]);
  const prev = useCallback(() => setI((p) => (p > 0 ? p - 1 : p)), []);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, close, next, prev]);

  if (!mounted || !active || !steps.length) return null;

  const pad = 8;
  const spot = rect
    ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }
    : null;

  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const calloutW = 340;

  // Place the callout in a gap beside the spotlight rather than on top of it.
  // The previous logic only ever tried below-then-above against a hardcoded
  // 200px height guess, so a target taller than roughly half the viewport —
  // which most cards on this page are — landed the callout squarely over the
  // component it was describing.
  const M = 16;   // keep clear of the viewport edge
  const GAP = 14; // breathing room between spotlight and callout
  let calloutTop: number, calloutLeft: number, placeBelow = true;
  if (spot) {
    const clampH = (x: number) => Math.min(Math.max(M, x), Math.max(M, vw - calloutW - M));
    const clampV = (y: number) => Math.min(Math.max(M, y), Math.max(M, vh - calloutH - M));

    // Calculate intersection area between a candidate position and the spotlight
    const getOverlapArea = (l: number, t: number) => {
      const xOverlap = Math.max(0, Math.min(l + calloutW, spot.left + spot.width) - Math.max(l, spot.left));
      const yOverlap = Math.max(0, Math.min(t + calloutH, spot.top + spot.height) - Math.max(t, spot.top));
      return xOverlap * yOverlap;
    };

    // Generate candidate positions, all clamped to stay fully on screen
    const candidates = [
      // 1. Right of spotlight
      { pos: [clampH(spot.left + spot.width + GAP), clampV(spot.top)], weight: 0.0 },
      // 2. Left of spotlight
      { pos: [clampH(spot.left - GAP - calloutW), clampV(spot.top)], weight: 0.1 },
      // 3. Below spotlight
      { pos: [clampH(spot.left), clampV(spot.top + spot.height + GAP)], weight: 0.2 },
      // 4. Above spotlight
      { pos: [clampH(spot.left), clampV(spot.top - GAP - calloutH)], weight: 0.3 },
    ].map((c) => {
      const [l, t] = c.pos;
      const overlap = getOverlapArea(l, t);
      // Score prioritizes zero/minimal overlap, with slight weights to break ties
      const score = overlap + c.weight;
      return { pos: c.pos, score };
    });

    // Find the candidate that minimizes the overlap area
    candidates.sort((a, b) => a.score - b.score);
    const best = candidates[0];

    // Minimum *area* is the wrong objective once nothing fits cleanly: on a
    // narrow viewport the smallest-area option is usually "above", which covers
    // the panel's heading and headline figure — the parts the step is naming.
    // When no candidate is clean, pin to the bottom edge instead: same callout,
    // but it covers the panel's tail rather than its title.
    const chosen =
      best.score < 1
        ? best.pos
        : [clampH(spot.left), Math.max(M, vh - calloutH - M)];

    [calloutLeft, calloutTop] = chosen;
    placeBelow = calloutTop > spot.top;
  } else {
    calloutTop = Math.max(M, vh / 2 - calloutH / 2);
    calloutLeft = Math.max(M, vw / 2 - calloutW / 2);
  }

  const step = steps[i];

  return createPortal(
    <AnimatePresence>
      {active && (
        <motion.div
          key="kenbun-guided-tour"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[9999]"
        >
          {/* Dimmed backdrop with spotlight cutout */}
          <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: "none" }}>
            <defs>
              <mask id="kenbun-tour-mask">
                <rect x="0" y="0" width="100%" height="100%" fill="white" />
                {spot && (
                  <rect x={spot.left} y={spot.top} width={spot.width} height={spot.height} rx="14" fill="black" />
                )}
              </mask>
            </defs>
            <rect x="0" y="0" width="100%" height="100%" fill="rgba(12,10,9,0.74)" mask="url(#kenbun-tour-mask)" />
          </svg>

          {/* Block clicks to the underlying UI while touring (does not close) */}
          <div className="absolute inset-0" style={{ pointerEvents: "auto" }} />

          {/* Pulsing highlight ring */}
          {spot && (
            <motion.div
              className="absolute rounded-md"
              style={{
                top: spot.top,
                left: spot.left,
                width: spot.width,
                height: spot.height,
                pointerEvents: "none",
                border: "2px solid var(--tertiary, #B8422E)",
              }}
              animate={{
                boxShadow: [
                  "0 0 0 3px rgba(184,66,46,0.35)",
                  "0 0 0 12px rgba(184,66,46,0.0)",
                  "0 0 0 3px rgba(184,66,46,0.35)",
                ],
              }}
              transition={{ duration: 1.7, repeat: Infinity, ease: "easeInOut" }}
            />
          )}

          {/* Tethered callout */}
          <motion.div
            key={i}
            ref={calloutRef}
            initial={{ opacity: 0, y: placeBelow ? -8 : 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="absolute rounded-md border border-black/10 shadow-2xl p-5 space-y-3"
            style={{ top: calloutTop, left: calloutLeft, width: calloutW, background: "var(--card, #ffffff)", pointerEvents: "auto" }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-tertiary">
                <Sparkles className="w-3.5 h-3.5" />
                <span className="text-[9px] font-black uppercase tracking-[0.3em]">Guided Tour</span>
              </div>
              <button onClick={close} className="text-primary/40 hover:text-primary transition-colors cursor-pointer" aria-label="Exit tour">
                <X className="w-4 h-4" />
              </button>
            </div>

            <h4 className="font-serif font-black text-base uppercase tracking-tight text-primary leading-tight">{step.title}</h4>
            <p className="text-xs leading-relaxed text-secondary">{step.body}</p>

            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center gap-1.5">
                {steps.map((_, idx) => (
                  <span
                    key={idx}
                    className={`h-1.5 rounded-full transition-all duration-300 ${idx === i ? "w-5 bg-tertiary" : "w-1.5 bg-primary/20"}`}
                  />
                ))}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={prev}
                  disabled={i === 0}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest flex items-center gap-1 transition-all ${i === 0 ? "opacity-30 cursor-not-allowed" : "hover:bg-primary/5 text-primary cursor-pointer"}`}
                >
                  <ArrowLeft className="w-3 h-3" />
                  Back
                </button>
                <button
                  onClick={next}
                  className="px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest bg-tertiary text-white flex items-center gap-1 hover:opacity-90 active:scale-95 transition-all cursor-pointer"
                >
                  {i === steps.length - 1 ? "Done" : "Next"}
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            </div>

            <div className="text-[9px] font-mono text-primary/30 uppercase tracking-widest text-right">
              {i + 1} / {steps.length} &middot; Esc to exit
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}
