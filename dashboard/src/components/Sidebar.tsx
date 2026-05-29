"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Compass, 
  LayoutGrid, 
  Settings, 
  Activity,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  Database,
  ShieldCheck,
  Terminal
} from "lucide-react";
import { useTheme } from "@/context/ThemeContext";
import { motion, AnimatePresence } from "framer-motion";

export default function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme, mounted } = useTheme();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const navItems = [
    { name: "Bridge", href: "/observatory", icon: Compass, idx: "I" },
    { name: "Fleet", href: "/fleet", icon: LayoutGrid, idx: "II" },
    { name: "Intel", href: "/telemetry", icon: Activity, idx: "III" },
    { name: "Supervisor", href: "/supervisor", icon: ShieldCheck, idx: "IV" },
    { name: "Hivemind", href: "/hivemind", icon: Database, idx: "V" },
    { name: "Chat", href: "/chat", icon: Terminal, idx: "VI" },
    { name: "Controls", href: "/settings", icon: Settings, idx: "VII" },
  ];

  return (
    <>
      {/* DESKTOP SIDEBAR */}
      <motion.aside 
        animate={{ width: isCollapsed ? 80 : 280 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        className={`hidden lg:flex h-screen border-r border-border flex-col sticky left-0 top-0 z-40 bg-card/85 backdrop-blur-xl shrink-0 overflow-hidden relative group text-primary`}
      >
        {/* COLLAPSE TOGGLE */}
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 w-6 h-12 bg-border text-primary flex items-center justify-center z-50 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>

        {/* BRAND SPINE - Cleaned up branding */}
        <div className={`h-32 border-b border-border-muted flex flex-col items-center justify-center transition-all duration-500 overflow-hidden ${isCollapsed ? 'space-y-1' : 'space-y-3'} shrink-0`}>
          <div className="w-8 h-8 border border-gold flex items-center justify-center bg-gold/10 shrink-0">
            <span className="text-gold font-black text-xs">K</span>
          </div>
          <AnimatePresence mode="wait">
            {!isCollapsed && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="flex flex-col items-center"
              >
                <span className="font-serif text-lg font-black italic tracking-tighter text-primary">Kenbun</span>
                <span className="ind-header tracking-[0.4em] opacity-30 text-[7px] text-primary">Sovereign Hive</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* NAVIGATION - Minimalist Flow */}
        <nav className="flex-1 flex flex-col items-stretch pt-8 space-y-2 px-4">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link 
                key={item.name} 
                href={item.href}
                className={`flex items-center gap-4 px-4 py-3 transition-all group relative border border-transparent ${
                  isActive 
                    ? "bg-gold/10 border-gold/20 text-gold" 
                    : "text-primary opacity-40 hover:opacity-100"
                }`}
              >
                <item.icon className={`w-4 h-4 transition-transform group-hover:scale-110 ${isActive ? "text-gold" : "text-primary opacity-40 group-hover:opacity-100"}`} />
                <AnimatePresence>
                  {!isCollapsed && (
                    <motion.div
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -10 }}
                      className="flex flex-col"
                    >
                      <span className={`text-[10px] font-bold uppercase tracking-[0.2em]`}>
                        {item.name}
                      </span>
                    </motion.div>
                  )}
                </AnimatePresence>
                {isActive && (
                  <motion.div 
                    layoutId="active-indicator"
                    className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-4 bg-gold" 
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {/* FOOTER UTILITY - Simplified */}
        <div className={`p-8 border-t border-border-muted transition-all duration-500 shrink-0`}>
          <button 
            onClick={toggleTheme}
            className="w-full flex items-center gap-4 text-primary hover:text-gold transition-all group opacity-40 hover:opacity-100"
          >
            <div className="w-8 h-8 border border-border flex items-center justify-center group-hover:border-gold transition-colors shrink-0 text-primary">
              {!mounted || theme === "dark" ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            </div>
            {!isCollapsed && <span className="ind-header text-[8px] tracking-[0.4em] text-primary">{!mounted || theme === "dark" ? "Dawn" : "Dusk"}</span>}
          </button>
        </div>
      </motion.aside>

      {/* MOBILE BOTTOM NAVIGATION */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 h-20 bg-card/90 backdrop-blur-lg border-t-2 border-border z-40 flex items-stretch text-primary">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link 
              key={item.name} 
              href={item.href}
              className={`flex-1 flex flex-col items-center justify-center relative transition-all ${
                isActive ? "text-gold" : "text-primary opacity-40"
              }`}
            >
              <item.icon className={`w-4 h-4 transition-transform ${isActive ? "text-gold scale-110" : "text-primary opacity-40"}`} />
              <span className={`text-[8px] font-bold uppercase tracking-widest mt-2 text-primary ${isActive ? "opacity-100" : "opacity-20"}`}>
                {item.name}
              </span>
              {isActive && (
                <motion.div 
                  layoutId="mobile-active-indicator"
                  className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-[2px] bg-gold" 
                />
              )}
            </Link>
          );
        })}
        <button 
          onClick={toggleTheme}
          className="w-16 border-l border-border-muted flex items-center justify-center text-primary"
        >
          {!mounted || theme === "dark" ? <Sun className="w-4 h-4 opacity-40" /> : <Moon className="w-4 h-4 opacity-40" />}
        </button>
      </nav>
    </>
  );
}
