"use client";

import React, { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldCheck,
  ShieldAlert,
  Network,
  Zap,
  GitCommit,
  Clock,
  RefreshCw,
  Server,
  Cpu,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { tenantFetch } from "@/lib/tenantFetch";

/* ------------------------------------------------------------------ types */

type Provider = {
  name: string;
  healthy: boolean;
  primary: boolean;
  fail_count: number;
  cooldown_remaining_s: number;
};

type FailoverEvent = {
  ts: string;
  kind: "failover" | "exhausted" | "recovered" | string;
  capability: string;
  provider: string | null;
  detail: string;
  providers_order?: string[];
};

type Phase = {
  id: string;
  title: string;
  status: "done" | "in_progress" | "todo" | string;
  commit: string;
  blurb: string;
};

type PrimerItem = { term: string; line: string };

type ResiliencePayload = {
  capability: { name?: string; where?: string; was?: string; now?: string };
  providers: Provider[];
  provider_error: string | null;
  healthy_count: number;
  total_count: number;
  spof: boolean;
  events: FailoverEvent[];
  phases: Phase[];
  primer: PrimerItem[];
};

/* ------------------------------------------------------------------ helpers */

const PROVIDER_META: Record<string, { label: string; sub: string; Icon: React.ComponentType<{ className?: string }> }> = {
  gemini: { label: "Gemini", sub: "Google · high-reasoning", Icon: Sparkles },
  deepseek: { label: "DeepSeek", sub: "DeepSeek-V3 · cloud", Icon: Server },
  local: { label: "Local Gateway", sub: "llm_router · your box", Icon: Cpu },
};

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const s = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

/* Narrative fallback so the showcase still reads if the API is briefly down.
   The live board (providers / events) genuinely needs the backend. */
const FALLBACK_PHASES: Phase[] = [
  { id: "DSH-01", title: "An undo button for the tool registry", status: "done", commit: "8297614", blurb: "Adding a tool to the running swarm used to be permanent. Now every registration hands back a disposer that removes exactly what it added — no restart, no leftovers." },
  { id: "DSH-02", title: "Shell / files / web became swappable", status: "done", commit: "26fa15d", blurb: "Split each capability into what it promises, who provides it, and who uses it. A sandboxed provider can stand in without touching callers." },
  { id: "DSH-03", title: "One honest record of what the model saw", status: "done", commit: "59f5449", blurb: "The session event log is the single source of truth for model context. A guard raises if anything reaches the model unlogged." },
  { id: "DSH-04", title: "One way to hand work to a sub-agent", status: "done", commit: "00e8cfa", blurb: "One interface, pluggable drivers. When one reports 'unavailable', the seam walks to the next — where the 429 quota failure first got a real fallback." },
  { id: "DSH-05", title: "Mount a new tool while the swarm runs", status: "done", commit: "ca6858f", blurb: "Hand the swarm a fresh tool, smoke-test it, keep it only if it passes — otherwise auto-reverted. Self-modification without a restart." },
  { id: "DSH-06", title: "No single point of failure, anywhere", status: "in_progress", commit: "6cd3785", blurb: "Every seam gets 2+ providers and a resolver that demotes a failing one instead of stopping. First seam wired: the swarm Queen's task decomposition." },
];
const FALLBACK_PRIMER: PrimerItem[] = [
  { term: "Static composition", line: "Decided once, at build time. Changing it means editing code and restarting — and a restart wipes every bit of in-memory state." },
  { term: "Dynamic composition", line: "Swapped while running, and undoable. Add a piece, test it, roll it back if a guard fails — the swarm never stops." },
  { term: "The trap", line: "Depending on one API key / one router / one model is static composition in disguise. A resolver with real fallbacks makes it dynamic." },
];

const STATUS_STYLE: Record<string, string> = {
  done: "bg-emerald-500/10 text-emerald-600 border-emerald-500/25",
  in_progress: "bg-tertiary/10 text-tertiary border-tertiary/30",
  todo: "bg-primary/5 text-secondary border-primary/10",
};
const STATUS_LABEL: Record<string, string> = {
  done: "Shipped",
  in_progress: "In progress",
  todo: "Planned",
};

/* ------------------------------------------------------------------ subcomponents */

function SectionLabel({ icon: Icon, children, hint }: { icon: React.ComponentType<{ className?: string }>; children: React.ReactNode; hint?: string }) {
  return (
    <div className="flex items-baseline gap-3 flex-wrap">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-tertiary" />
        <span className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">{children}</span>
      </div>
      {hint && <span className="text-[10px] font-bold opacity-30 uppercase tracking-widest italic">{hint}</span>}
    </div>
  );
}

function ProviderCard({ p, isNextHop }: { p: Provider; isNextHop: boolean }) {
  const meta = PROVIDER_META[p.name] ?? { label: p.name, sub: "provider", Icon: Network };
  const { Icon } = meta;
  return (
    <motion.div
      layout
      className={`relative flex-1 min-w-[190px] p-5 border rounded-md bg-card/70 backdrop-blur-xl transition-colors ${
        p.healthy ? "border-primary/5" : "border-amber-500/30 bg-amber-500/[0.03]"
      } ${isNextHop ? "ring-1 ring-tertiary/40" : ""}`}
    >
      {p.primary && (
        <span className="absolute -top-2 left-4 px-2 py-0.5 bg-primary text-neutral text-[7.5px] font-black uppercase tracking-[0.2em] rounded-sm">
          First choice
        </span>
      )}
      {isNextHop && !p.primary && (
        <span className="absolute -top-2 left-4 px-2 py-0.5 bg-tertiary text-neutral text-[7.5px] font-black uppercase tracking-[0.2em] rounded-sm">
          Serving now
        </span>
      )}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <Icon className="w-4 h-4 text-primary/70" />
          <div className="flex flex-col">
            <span className="text-xs font-black uppercase tracking-wider text-primary">{meta.label}</span>
            <span className="text-[9px] font-bold text-secondary opacity-70 tracking-wide">{meta.sub}</span>
          </div>
        </div>
        <span className="relative flex h-2.5 w-2.5 mt-1 shrink-0">
          {p.healthy && (
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 motion-reduce:hidden" />
          )}
          <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${p.healthy ? "bg-emerald-500" : "bg-amber-500"}`} />
        </span>
      </div>

      <div className="mt-4 pt-3 border-t border-primary/5 flex items-center justify-between text-[9px] font-mono font-bold uppercase tracking-widest">
        {p.healthy ? (
          <span className="text-emerald-600">Healthy</span>
        ) : (
          <span className="flex items-center gap-1.5 text-amber-600">
            <Clock className="w-3 h-3" />
            cooling down · ~{Math.ceil(p.cooldown_remaining_s)}s
          </span>
        )}
        <span className="text-secondary opacity-50">
          {p.fail_count} fail{p.fail_count === 1 ? "" : "s"}
        </span>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ main */

export default function DSHResiliencePanel({ apiBase }: { apiBase: string }) {
  const [data, setData] = useState<ResiliencePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        const res = await tenantFetch(`${apiBase}/api/v1/resilience`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = (await res.json()) as ResiliencePayload;
        if (!alive) return;
        setData(json);
        setError(null);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "unreachable");
      } finally {
        if (alive) setLoading(false);
      }
    };

    load();
    const t = setInterval(load, 12000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [apiBase]);

  const nextHop = useMemo(() => data?.providers.find((p) => p.healthy)?.name ?? null, [data]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-24 opacity-40">
        <RefreshCw className="w-4 h-4 animate-spin mr-3" />
        <span className="text-[10px] font-black uppercase tracking-[0.3em]">Reading resolver health…</span>
      </div>
    );
  }

  const providers = data?.providers ?? [];
  const events = data?.events ?? [];
  const phases = data?.phases?.length ? data.phases : FALLBACK_PHASES;
  const primer = data?.primer?.length ? data.primer : FALLBACK_PRIMER;
  const allHealthy = (data?.healthy_count ?? 0) === (data?.total_count ?? 0) && (data?.total_count ?? 0) > 0;

  return (
    <div className="space-y-12 animate-fade-in text-left pb-4">
      {/* ---------- hero ---------- */}
      <div className="p-6 lg:p-8 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-md">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              {data?.spof ? <ShieldAlert className="w-4 h-4 text-amber-500" /> : <ShieldCheck className="w-4 h-4 text-emerald-500" />}
              <span className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">No single point of failure</span>
            </div>
            <h2 className="font-heading text-2xl lg:text-3xl leading-tight text-primary">
              If one brain goes down, the swarm keeps thinking.
            </h2>
            <p className="text-[12px] leading-relaxed text-secondary opacity-80">
              The <strong>{data?.capability?.name ?? "Queen decomposition"}</strong> used to be{" "}
              <span className="line-through opacity-60">{data?.capability?.was ?? "one call to Gemini"}</span>. Now it&apos;s{" "}
              <strong className="text-tertiary">{data?.capability?.now ?? "gemini → deepseek → local, health-aware"}</strong>. A provider
              that fails gets <em>demoted</em> for a cooldown — not switched off — and quietly comes back when it recovers.
            </p>
          </div>
          <div className="shrink-0 flex lg:flex-col items-center gap-3 lg:min-w-[140px]">
            <div
              className={`px-4 py-3 rounded-md border text-center w-full ${
                allHealthy ? "border-emerald-500/25 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
              }`}
            >
              <div className="text-2xl font-black tracking-tighter text-primary">
                {data?.healthy_count ?? "—"}
                <span className="opacity-30"> / {data?.total_count ?? "—"}</span>
              </div>
              <div className="text-[8px] font-black uppercase tracking-[0.25em] text-secondary opacity-70 mt-0.5">providers up</div>
            </div>
          </div>
        </div>
        {error && (
          <p className="mt-4 text-[10px] font-mono font-bold uppercase tracking-widest text-amber-600">
            live data unreachable ({error}) — showing last known
          </p>
        )}
      </div>

      {/* ---------- provider rail ---------- */}
      <section className="space-y-5">
        <SectionLabel icon={Network} hint="tried in this order · gemini first">
          The fallback chain
        </SectionLabel>
        <div className="relative flex flex-col md:flex-row items-stretch gap-3 md:gap-2">
          {providers.map((p, i) => (
            <React.Fragment key={p.name}>
              <ProviderCard p={p} isNextHop={p.name === nextHop} />
              {i < providers.length - 1 && (
                <div className="flex md:flex-col items-center justify-center px-1 text-primary/20">
                  <ArrowRight className="w-4 h-4 rotate-90 md:rotate-0" />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
        <p className="text-[10px] leading-relaxed text-secondary opacity-60 italic">
          {nextHop
            ? nextHop === providers[0]?.name
              ? `Right now the request goes straight to ${PROVIDER_META[nextHop]?.label ?? nextHop}.`
              : `${PROVIDER_META[providers[0]?.name]?.label ?? providers[0]?.name} is cooling down — ${PROVIDER_META[nextHop]?.label ?? nextHop} is covering.`
            : "Every provider is cooling down — the resolver will still try the least-recently-failed one rather than give up."}
        </p>
      </section>

      {/* ---------- failover feed ---------- */}
      <section className="space-y-5">
        <SectionLabel icon={Zap} hint="what actually happened, across every process">
          Failover activity
        </SectionLabel>
        <div className="border border-primary/5 bg-card/60 backdrop-blur-xl rounded-md divide-y divide-primary/5 overflow-hidden">
          <AnimatePresence initial={false}>
            {events.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center gap-3 px-5 py-6 text-[11px] font-bold text-secondary"
              >
                <span className="relative flex h-2 w-2">
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
                No failovers on record. Gemini&apos;s been holding — nothing has had to reroute.
              </motion.div>
            ) : (
              events.map((ev, i) => (
                <motion.div
                  key={`${ev.ts}-${i}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-start gap-4 px-5 py-3.5"
                >
                  <span
                    className={`mt-0.5 shrink-0 w-1.5 h-1.5 rounded-full ${
                      ev.kind === "exhausted" ? "bg-red-500" : "bg-amber-500"
                    }`}
                  />
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <p className="text-[11px] font-bold text-primary leading-snug">
                      {ev.kind === "exhausted" ? (
                        <>Every provider was down — decomposition could not run.</>
                      ) : (
                        <>
                          {ev.detail || "primary unavailable"} →{" "}
                          <span className="text-tertiary">
                            {PROVIDER_META[ev.provider ?? ""]?.label ?? ev.provider} picked it up
                          </span>
                        </>
                      )}
                    </p>
                    {ev.providers_order && (
                      <p className="text-[8.5px] font-mono uppercase tracking-widest text-secondary opacity-40">
                        chain: {ev.providers_order.join(" › ")}
                      </p>
                    )}
                  </div>
                  <span className="shrink-0 text-[9px] font-mono font-bold uppercase tracking-widest text-secondary opacity-50">
                    {timeAgo(ev.ts)}
                  </span>
                </motion.div>
              ))
            )}
          </AnimatePresence>
        </div>
      </section>

      {/* ---------- DSH journey ---------- */}
      <section className="space-y-5">
        <SectionLabel icon={Sparkles} hint="the road to no-SPOF · 6 phases">
          What we&apos;ve been building
        </SectionLabel>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {phases.map((ph) => (
            <div
              key={ph.id}
              className="p-5 border border-primary/5 bg-card/60 backdrop-blur-xl rounded-md flex flex-col gap-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[9px] font-mono font-black uppercase tracking-[0.25em] text-secondary opacity-50">{ph.id}</span>
                <span
                  className={`px-2 py-0.5 text-[7.5px] font-black uppercase tracking-[0.2em] rounded-sm border ${
                    STATUS_STYLE[ph.status] ?? STATUS_STYLE.todo
                  }`}
                >
                  {STATUS_LABEL[ph.status] ?? ph.status}
                </span>
              </div>
              <h3 className="text-[13px] font-black tracking-tight text-primary leading-snug">{ph.title}</h3>
              <p className="text-[10.5px] leading-relaxed text-secondary opacity-80 flex-1">{ph.blurb}</p>
              {ph.commit && (
                <span className="flex items-center gap-1.5 text-[8.5px] font-mono font-bold uppercase tracking-widest text-secondary opacity-40">
                  <GitCommit className="w-3 h-3" />
                  {ph.commit}
                </span>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ---------- primer ---------- */}
      {primer.length > 0 && (
        <section className="space-y-5">
          <SectionLabel icon={ShieldCheck} hint="why this matters · 20 seconds">
            The idea, plainly
          </SectionLabel>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {primer.map((it) => (
              <div key={it.term} className="p-5 border border-primary/5 bg-sand rounded-md space-y-2">
                <span className="text-[10px] font-black uppercase tracking-[0.25em] text-tertiary">{it.term}</span>
                <p className="text-[10.5px] leading-relaxed text-secondary opacity-85">{it.line}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
