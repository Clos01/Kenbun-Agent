"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Sigma } from "lucide-react";

/**
 * How every agent/tool weight is derived.
 *
 * Mirrors the two real code paths:
 *   write   — core/tools/utils/bayesian.py          (tune_swarm)
 *   display — core/tools/strategy/strategy_manager.py (_recency_factor / _decayed_weights)
 *
 * The numbers rendered on this page come from the DISPLAY path, which
 * recomputes weights from raw event counts with recency decay rather than
 * reading the stored alpha/beta columns. If that Python changes, change this.
 */

interface ToolLike {
  tool_id: string;
  alpha: number;
  beta: number;
  success_rate: number;
  success_count?: number;
  failure_count?: number;
}

const HALF_LIFE_H = 24;

const STEPS = [
  {
    n: "1",
    title: "Prior — where every tool starts",
    math: "Beta(α₀ = 1, β₀ = 1)",
    body:
      "A uniform prior: one imagined success, one imagined failure. A brand-new tool sits at exactly 50%, " +
      "neither trusted nor distrusted. This is what stops a tool that succeeded once from outranking a tool " +
      "with a hundred runs behind it.",
    src: "bayesian.py · tune_swarm()",
  },
  {
    n: "2",
    title: "Recording an outcome",
    math: "success → success_count += 1\nfailure → failure_count += 1",
    body:
      "Exactly one counter increments per run; they are mutually exclusive. Weights are keyed by " +
      "(tool_id, category), so a tool can be strong at security work and weak at UI work. Lookup tries the " +
      "category row and falls back to global, and a new category row is seeded by copying the tool's current " +
      "global values — so a tool carries its general reputation into a new domain instead of restarting cold.",
    src: "bayesian.py · tune_swarm() — raw counts are the ground truth",
  },
  {
    n: "3",
    title: "Recency decay — evidence expires",
    math: "λ = 0.5 ^ (age_hours / H)     H = 24h",
    body:
      "Every observation is discounted by how old it is, on a 24-hour half-life (override with " +
      "BAYES_DECAY_HALFLIFE_HOURS). Evidence from yesterday counts half as much as evidence from an hour ago; " +
      "from three days ago, about a tenth. λ is forced to 1.0 when the timestamp is missing, future, or " +
      "unparseable, so fresh or unknown data is never penalised. This is the mechanism that stops stale rows — " +
      "including one-off seed data — from dominating the store forever.",
    src: "strategy_manager.py · _recency_factor()",
  },
  {
    n: "4",
    title: "The weights this page actually shows",
    math: "α = 1 + success_count · λ\nβ = 1 + failure_count · λ",
    body:
      "Note what this does NOT do: it ignores the stored alpha/beta columns entirely and rebuilds them from " +
      "raw counts each time. The stored columns exist, but their prior base drifted across code paths over " +
      "time, so the display path treats the event counts as the only trustworthy source.",
    src: "strategy_manager.py · _decayed_weights()",
  },
  {
    n: "5",
    title: "Confidence — the number on each tile",
    math: "P(success) = α / (α + β)",
    body:
      "The posterior mean of the Beta distribution, and the percentage rendered on every tool tile above. " +
      "Falls back to 0.5 when α + β = 0 or the row is missing, rather than erroring. Because of decay, a tool " +
      "nobody has called in a week drifts back toward 50% — not because it got worse, but because the evidence " +
      "that it was good has expired.",
    src: "bayesian.py · get_confidence() · strategy_manager.py · get_tool_confidence()",
  },
];

export default function WeightFormula({ tools }: { tools: ToolLike[] }) {
  const [open, setOpen] = useState(true);

  // Worked example uses the most-observed real tool so the numbers on screen
  // are the ones actually in the store rather than invented.
  const sample =
    tools && tools.length
      ? [...tools].sort((a, b) => b.alpha + b.beta - (a.alpha + a.beta))[0]
      : null;

  // Recover the decay factor the backend applied: alpha = 1 + s*lambda.
  const s = sample?.success_count;
  const lambda =
    sample && typeof s === "number" && s > 0
      ? (sample.alpha - 1) / s
      : null;
  const ageH =
    lambda && lambda > 0 && lambda <= 1
      ? (Math.log(1 / lambda) / Math.log(2)) * HALF_LIFE_H
      : null;

  return (
    <section className="border-2 border-[var(--border-muted)] bg-[var(--background)]/40 artisan-shadow rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="w-full flex items-center gap-4 p-5 text-left hover:bg-[var(--sand)]/50 transition-colors cursor-pointer"
      >
        <Sigma className="w-4 h-4 text-[var(--gold)] shrink-0" />
        <div className="flex-1 min-w-0">
          <h3 className="ind-header text-[var(--gold)] opacity-100 font-serif italic text-lg">
            How these weights are made
          </h3>
          <p className="text-[10px] sm:text-xs font-mono opacity-40 mt-0.5">
            Beta-Bernoulli conjugate model · recency-decayed · one distribution per tool per category
          </p>
        </div>
        <motion.div animate={{ rotate: open ? 180 : 0 }} className="shrink-0">
          <ChevronDown className="w-4 h-4 opacity-40" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-6 space-y-5 border-t border-[var(--border-muted)] pt-5">
              {STEPS.map((st) => (
                <div key={st.n} className="flex gap-4">
                  <span className="text-[10px] font-mono font-bold text-[var(--gold)] border border-[var(--gold)]/30 rounded w-6 h-6 flex items-center justify-center shrink-0 mt-0.5">
                    {st.n}
                  </span>
                  <div className="min-w-0 flex-1 space-y-2">
                    <h4 className="text-sm font-bold uppercase tracking-wide text-[var(--foreground)]">
                      {st.title}
                    </h4>
                    <pre className="text-[13px] font-mono font-semibold text-[var(--gold)] bg-[var(--foreground)]/[0.04] border border-[var(--border-muted)] rounded-lg p-3 whitespace-pre-wrap overflow-x-auto">
                      {st.math}
                    </pre>
                    <p className="text-xs leading-relaxed opacity-70">{st.body}</p>
                    <p className="text-[10px] font-mono opacity-30 break-all">{st.src}</p>
                  </div>
                </div>
              ))}

              {/* ---- Selection ---- */}
              <div className="flex gap-4">
                <span className="text-[10px] font-mono font-bold text-[var(--gold)] border border-[var(--gold)]/30 rounded w-6 h-6 flex items-center justify-center shrink-0 mt-0.5">
                  6
                </span>
                <div className="min-w-0 flex-1 space-y-2">
                  <h4 className="text-sm font-bold uppercase tracking-wide text-[var(--foreground)]">
                    Choosing a tool — two different selectors
                  </h4>
                  <p className="text-xs leading-relaxed opacity-70">
                    These weights feed two selectors, and they do not behave the same way:
                  </p>
                  <div className="grid sm:grid-cols-2 gap-3">
                    <div className="border border-[var(--border-muted)] rounded-lg p-3 space-y-1.5">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--gold)]">
                        Thompson sampling
                      </div>
                      <pre className="text-[12px] font-mono font-semibold whitespace-pre-wrap">
                        {"θ̂ᵢ ~ Beta(αᵢ, βᵢ)\npick argmax θ̂ᵢ"}
                      </pre>
                      <p className="text-[11px] leading-relaxed opacity-60">
                        Draws a random sample from each candidate&apos;s distribution, so an uncertain
                        tool sometimes wins and gets explored. The spread narrows as evidence accumulates.
                      </p>
                      <p className="text-[10px] font-mono opacity-30">
                        strategy_manager.py · sample_strategy()
                      </p>
                    </div>
                    <div className="border border-[var(--border-muted)] rounded-lg p-3 space-y-1.5">
                      <div className="text-[10px] font-bold uppercase tracking-widest opacity-50">
                        Greedy
                      </div>
                      <pre className="text-[12px] font-mono font-semibold whitespace-pre-wrap">
                        {"pick argmax α / (α + β)"}
                      </pre>
                      <p className="text-[11px] leading-relaxed opacity-60">
                        Always takes the current best mean, with no exploration. A tool that failed early
                        can stay buried even if it would succeed now — decay is what eventually frees it.
                      </p>
                      <p className="text-[10px] font-mono opacity-30">
                        bayesian.py · get_best_tool()
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* ---- Worked example on live data ---- */}
              {sample && (
                <div className="border-t border-[var(--border-muted)] pt-5">
                  <div className="text-[10px] font-bold uppercase tracking-widest opacity-40 mb-3">
                    Worked example — live values from this store
                  </div>
                  <div className="bg-[var(--foreground)]/[0.04] border border-[var(--border-muted)] rounded-lg p-4 space-y-2 font-mono text-[13px] overflow-x-auto">
                    <div className="font-bold text-[var(--gold)] break-all">{sample.tool_id}</div>
                    {typeof sample.success_count === "number" &&
                    typeof sample.failure_count === "number" ? (
                      <div className="opacity-70">
                        raw counts: {sample.success_count} success · {sample.failure_count} failure
                      </div>
                    ) : null}
                    {lambda !== null && lambda > 0 && lambda <= 1 && (
                      <div className="opacity-70">
                        λ = {lambda.toFixed(4)}
                        {ageH !== null && (
                          <span className="opacity-60">
                            {"  ⇒  evidence ≈ "}
                            {ageH.toFixed(1)}h old
                          </span>
                        )}
                      </div>
                    )}
                    <div className="opacity-70">
                      α = {sample.alpha} &nbsp; β = {sample.beta}
                    </div>
                    <div className="opacity-70">
                      P(success) = {sample.alpha} / ({sample.alpha} + {sample.beta}) ={" "}
                      <span className="text-[var(--gold)] font-bold">
                        {(sample.alpha / (sample.alpha + sample.beta) || 0).toFixed(4)}
                      </span>
                    </div>
                  </div>
                  <p className="text-[11px] leading-relaxed opacity-50 mt-3">
                    If this tool is never called again, λ keeps shrinking and both α and β slide back toward 1 —
                    so its confidence returns to 50%. Standing still is not neutral here; it is forgetting.
                  </p>
                </div>
              )}

              {!sample && (
                <div className="border-t border-[var(--border-muted)] pt-5">
                  <div className="text-[10px] font-bold uppercase tracking-widest opacity-40 mb-2">
                    Worked example
                  </div>
                  <p className="text-xs leading-relaxed opacity-60">
                    Unavailable — no tool has recorded a run yet, so there are no measured
                    weights to work through. Nothing is estimated here on a tool&apos;s behalf.
                  </p>
                </div>
              )}

              <p className="text-[10px] font-mono opacity-30 pt-1">
                Stored in Postgres · bayesian_weights (tool_id, category, alpha, beta, success_count,
                failure_count, last_updated) · SQLite `intelligence` table is the fallback path.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
