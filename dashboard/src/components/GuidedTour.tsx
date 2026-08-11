"use client";

import React, { useState, useEffect, useCallback, useLayoutEffect } from "react";
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

  useEffect(() => setMounted(true), []);

  // Register this page's tour so global UI (e.g. the guide modal) can tell a tour exists here
  useEffect(() => {
    const w = window as any;
    (w.__kenbunTours = w.__kenbunTours || new Set()).add(module);
    return () => { try { w.__kenbunTours?.delete(module); } catch (_) {} };
  }, [module]);

  useEffect(() => {
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
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
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
  let calloutTop: number, calloutLeft: number, placeBelow = true;
  if (spot) {
    placeBelow = spot.top + spot.height + 200 < vh;
    calloutTop = placeBelow ? spot.top + spot.height + 14 : Math.max(16, spot.top - 200);
    calloutLeft = Math.min(Math.max(16, spot.left), vw - calloutW - 16);
  } else {
    calloutTop = vh / 2 - 100;
    calloutLeft = vw / 2 - calloutW / 2;
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
              className="absolute rounded-2xl"
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
            initial={{ opacity: 0, y: placeBelow ? -8 : 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="absolute rounded-2xl border border-black/10 shadow-2xl p-5 space-y-3"
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
