"use client";

import React, { useRef } from "react";
import { useRouter } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { 
  ShieldCheck, 
  Activity, 
  Cpu, 
  ChevronRight, 
  Zap, 
  Terminal
} from "lucide-react";

export default function EntryTerminal() {
  const container = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useGSAP(() => {
    const tl = gsap.timeline();
    
    // Initial Entrance
    tl.from(".terminal-text", {
      opacity: 0,
      y: 20,
      duration: 0.8,
      stagger: 0.1,
      ease: "power3.out",
    })
    .from(".central-node", {
      scale: 0,
      opacity: 0,
      duration: 1.2,
      ease: "elastic.out(1, 0.5)",
    }, "-=0.4")
    .from(".action-btn", {
      y: 20,
      opacity: 0,
      duration: 0.8,
      ease: "back.out(1.7)",
    }, "-=0.6");

    // Continuous Pulse for the central node
    gsap.to(".node-pulse", {
      scale: 1.5,
      opacity: 0,
      duration: 2,
      repeat: -1,
      ease: "power2.out",
    });
  }, { scope: container });

  const handleLaunch = () => {
    gsap.to(container.current, {
      opacity: 0,
      scale: 1.1,
      duration: 0.5,
      ease: "power2.in",
      onComplete: () => router.push("/observatory")
    });
  };

  return (
    <main ref={container} className="min-h-screen bg-neutral flex flex-col items-center justify-center p-6 relative overflow-hidden font-sans">
      {/* Background Ambience */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,136,95,0.04)_0%,transparent_70%)]" />
      <div className="grain-overlay opacity-20" />

      {/* Central Node */}
      <div className="relative mb-12 central-node">
        <div className="node-pulse absolute inset-0 bg-tertiary/10 rounded-full scale-0" />
        <div className="w-32 h-32 rounded-sm border border-primary/5 flex items-center justify-center bg-card relative z-10 shadow-xl shadow-primary/5">
          <ShieldCheck className="w-12 h-12 text-tertiary" />
        </div>
      </div>

      {/* Content */}
      <div className="text-center space-y-6 relative z-10 max-w-xl">
        <div className="space-y-3">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tighter text-primary uppercase terminal-text leading-none italic">
            Kenbun <span className="text-tertiary">Intelligence</span>
          </h1>
          <p className="text-primary/40 font-bold text-xs md:text-sm tracking-[0.3em] uppercase flex items-center justify-center gap-2 terminal-text">
            <Activity className="w-4 h-4 text-tertiary/50" />
            System Node :: Heritage Active
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4 terminal-text">
          <div className="bg-card/60 backdrop-blur-sm border border-primary/5 p-5 text-left space-y-1 rounded-sm shadow-sm">
            <div className="flex items-center gap-2 text-[10px] text-primary/40 uppercase font-black tracking-widest">
              <Cpu className="w-3 h-3" /> Hardware
            </div>
            <div className="text-sm font-bold text-primary">Apple M1 Max</div>
          </div>
          <div className="bg-card/60 backdrop-blur-sm border border-primary/5 p-5 text-left space-y-1 rounded-sm shadow-sm">
            <div className="flex items-center gap-2 text-[10px] text-primary/40 uppercase font-black tracking-widest">
              <Zap className="w-3 h-3" /> Swarm Latency
            </div>
            <div className="text-sm font-bold text-primary">12.4ms (Bayesian)</div>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 w-full action-btn">
          <button 
            onClick={handleLaunch}
            className="flex-1 py-5 bg-primary hover:bg-primary/95 text-white font-black uppercase tracking-[0.3em] text-xs transition-all duration-300 rounded-sm shadow-lg shadow-primary/10 flex items-center justify-center gap-2 cursor-pointer"
            aria-label="Animate Swarm Launch and Enter"
          >
            Animate Launch
            <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
          
          <button 
            onClick={() => router.push("/observatory")}
            className="flex-1 py-5 bg-tertiary hover:bg-tertiary/95 text-white font-black uppercase tracking-[0.3em] text-xs transition-all duration-300 rounded-sm shadow-lg shadow-tertiary/10 flex items-center justify-center gap-2 cursor-pointer"
            aria-label="Direct access to Observatory dashboard"
          >
            Direct Access
            <Zap className="w-4 h-4 text-[#FAF9F6] animate-pulse" />
          </button>
        </div>

        <div className="pt-8 terminal-text">
          <div className="flex items-center justify-center gap-8 opacity-20 grayscale hover:opacity-100 hover:grayscale-0 transition-all duration-700">
            <Terminal className="w-5 h-5 text-primary" />
            <Activity className="w-5 h-5 text-primary" />
            <ShieldCheck className="w-5 h-5 text-primary" />
          </div>
        </div>
      </div>

      {/* Footer Branding */}
      <div className="fixed bottom-10 left-0 right-0 text-center opacity-30 pointer-events-none terminal-text">
        <span className="text-[9px] font-black uppercase tracking-[0.6em] text-primary">
          Architectural Minimalism :: Heritage v1.0
        </span>
      </div>
    </main>
  );
}
