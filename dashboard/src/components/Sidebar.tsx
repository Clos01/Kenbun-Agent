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
  Terminal,
  Columns,
  Layers,
  Menu,
  X,
  ChevronDown,
  Mic
} from "lucide-react";
import { useTheme } from "@/context/ThemeContext";
import { useTenant } from "@/context/TenantContext";
import { motion, AnimatePresence } from "framer-motion";

export default function Sidebar() {
  const pathname = usePathname();
  const { theme, preset, setPreset, toggleTheme, mounted } = useTheme();
  const { tenantId, setTenantId, tenants } = useTenant();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const navItems = [
    { name: "Build Console", href: "/observatory", icon: Compass },
    { name: "Agents", href: "/fleet", icon: LayoutGrid },
    { name: "Board", href: "/board", icon: Columns },
    { name: "Services", href: "/apps", icon: Layers },
    { name: "Metrics", href: "/telemetry", icon: Activity },
    { name: "Audit", href: "/supervisor", icon: ShieldCheck },
    { name: "Code Search", href: "/hivemind", icon: Database },
    { name: "Chat", href: "/chat", icon: Terminal },
    { name: "Settings", href: "/settings", icon: Settings },
  ];

  // Selection of 4 primary pages to display directly on mobile bottom nav
  const mobilePrimaryItems = [
    { name: "Build Console", href: "/observatory", icon: Compass },
    { name: "Board", href: "/board", icon: Columns },
    { name: "Chat", href: "/chat", icon: Terminal },
    { name: "Metrics", href: "/telemetry", icon: Activity },
  ];

  return (
    <>
      <motion.aside 
        animate={{ width: isCollapsed ? 80 : 280 }}
        transition={{ type: "spring", stiffness: 320, damping: 30 }}
        className="hidden lg:flex h-screen border-r border-border/80 flex-col sticky left-0 top-0 z-40 bg-card/45 backdrop-blur-xl shrink-0 relative group text-primary"
      >
        {/* COLLAPSE TOGGLE (Centered Floating Circle, NOT Clipped) */}
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 w-6 h-6 rounded-full bg-card/90 backdrop-blur-md border border-border/80 hover:border-gold/50 text-primary flex items-center justify-center z-50 opacity-0 group-hover:opacity-100 transition-all hover:scale-110 hover:shadow-md cursor-pointer"
        >
          {isCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
        </button>

        {/* BRAND SPINE */}
        <div className={`h-32 border-b border-border/40 flex flex-col items-center justify-center transition-all duration-500 overflow-hidden ${isCollapsed ? 'space-y-1' : 'space-y-3'} shrink-0`}>
          <div className="relative group/logo">
            <div className="absolute inset-0 bg-gold/20 rounded-full blur-md opacity-0 group-hover/logo:opacity-100 transition-opacity duration-500" />
            <div className="relative w-9 h-9 border border-gold/40 rounded flex items-center justify-center bg-gold/5 shrink-0 group-hover/logo:border-gold transition-colors duration-300">
              <span className="text-gold font-serif font-black text-sm select-none">K</span>
            </div>
          </div>
          <AnimatePresence mode="wait">
            {!isCollapsed && (
              <motion.div 
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                transition={{ duration: 0.2 }}
                className="flex flex-col items-center select-none"
              >
                <span className="font-serif text-lg font-black italic tracking-tighter text-primary">Kenbun</span>
                <span className="ind-header tracking-[0.4em] opacity-35 text-[7px] uppercase font-bold text-primary">Sovereign Hive</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* NAVIGATION */}
        <nav className="flex-1 flex flex-col items-stretch pt-6 space-y-1.5 px-3 overflow-hidden">
          {navItems.map((item, idx) => {
            const isActive = pathname === item.href;
            return (
              <Link 
                key={item.name} 
                href={item.href}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                className={`flex items-center gap-4 px-4 py-2.5 rounded-lg transition-all group relative border ${
                  isActive 
                    ? "bg-gold/8 border-gold/15 text-gold font-bold" 
                    : "border-transparent text-primary/45 hover:text-primary"
                }`}
              >
                {/* Hover Pill Background */}
                {hoveredIndex === idx && !isActive && (
                  <motion.div
                    layoutId="hover-pill"
                    className="absolute inset-0 bg-primary/5 rounded-lg -z-10"
                    transition={{ type: "spring", stiffness: 350, damping: 25 }}
                  />
                )}
                
                <item.icon className={`w-4 h-4 transition-all duration-300 group-hover:scale-110 ${isActive ? "text-gold" : "text-primary/40 group-hover:text-primary"}`} />
                
                <AnimatePresence>
                  {!isCollapsed && (
                    <motion.span
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -8 }}
                      className="text-[10px] font-bold uppercase tracking-[0.25em]"
                    >
                      {item.name}
                    </motion.span>
                  )}
                </AnimatePresence>

                {isActive && !isCollapsed && (
                  <motion.div 
                    layoutId="active-indicator"
                    className="absolute right-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-gold shadow-[0_0_8px_rgba(var(--tertiary-rgb),0.6)]" 
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {/* SETTINGS UTILITY (Popover) */}
        <div className="p-4 border-t border-border/40 shrink-0 relative overflow-visible">
          <button 
            onClick={() => setIsSettingsOpen(!isSettingsOpen)}
            className={`w-full flex items-center ${isCollapsed ? 'justify-center' : 'justify-start px-4'} gap-4 py-2.5 rounded-lg transition-all group relative border cursor-pointer ${
              isSettingsOpen ? "bg-gold/8 border-gold/15 text-gold font-bold" : "border-transparent text-primary/45 hover:text-primary hover:bg-primary/5"
            }`}
          >
            <Settings className={`w-4 h-4 transition-all duration-300 group-hover:scale-110 shrink-0 ${isSettingsOpen ? "text-gold" : "text-primary/40 group-hover:text-primary"}`} />
            <AnimatePresence>
              {!isCollapsed && (
                <motion.span
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  className="text-[10px] font-bold uppercase tracking-[0.25em]"
                >
                  Preferences
                </motion.span>
              )}
            </AnimatePresence>
          </button>
          
          <AnimatePresence>
            {isSettingsOpen && (
              <>
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 z-40"
                  onClick={() => setIsSettingsOpen(false)}
                />
                <motion.div 
                  initial={{ opacity: 0, y: 10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.95 }}
                  className={`absolute bottom-full mb-2 w-64 bg-card/95 backdrop-blur-xl border border-border/80 rounded-xl shadow-2xl overflow-hidden z-50 flex flex-col ${isCollapsed ? 'left-full ml-4 bottom-0 mb-0' : 'left-4'}`}
                >
                  <div className="px-5 py-4 border-b border-border/40 flex flex-col gap-2">
                    <label className="text-[8px] font-bold uppercase tracking-[0.25em] opacity-40 select-none">Active Tenant</label>
                    <div className="relative">
                      <select
                        value={tenantId}
                        onChange={(e) => setTenantId(e.target.value)}
                        className="bg-card/45 border border-border/60 hover:border-gold/30 text-[10px] py-1.5 pl-2.5 pr-8 rounded text-primary focus:outline-none focus:ring-1 focus:ring-gold w-full cursor-pointer appearance-none transition-colors"
                      >
                        {tenants.map((t) => (
                          <option key={t.id} value={t.id}>{t.name}</option>
                        ))}
                      </select>
                      <ChevronDown className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-primary/40" />
                    </div>
                  </div>

                  <div className="px-5 py-4 flex flex-col gap-2">
                    <label className="text-[8px] font-bold uppercase tracking-[0.25em] opacity-40 select-none">Visual Theme</label>
                    <div className="flex items-center gap-2.5">
                      {mounted ? [
                        { id: "limestone", color: "#B8422E", bg: "#F7F5F2", name: "Limestone" },
                        { id: "forest", color: "#2E8B57", bg: "#F0F4F1", name: "Forest" },
                        { id: "cobalt", color: "#2F6FEB", bg: "#F0F4F8", name: "Cobalt" },
                        { id: "breeze", color: "#0EA5E9", bg: "#F8FAFC", name: "Breeze" },
                        { id: "obsidian", color: "#FF6B4A", bg: "#0F1011", name: "Obsidian" },
                        { id: "sunset", color: "#F97316", bg: "#170F11", name: "Sunset" },
                        { id: "midnight", color: "#818CF8", bg: "#09090B", name: "Midnight" },
                        { id: "cyber", color: "#00FF41", bg: "#000000", name: "Cyber" }
                      ].map((item) => (
                        <button
                          key={item.id}
                          onClick={() => setPreset(item.id as any)}
                          title={item.name}
                          className={`w-6 h-6 rounded-full flex items-center justify-center border transition-all cursor-pointer ${
                            preset === item.id 
                              ? "border-gold scale-110 shadow-sm" 
                              : "border-border hover:scale-105 opacity-60 hover:opacity-100"
                          }`}
                          style={{ backgroundColor: item.bg }}
                        >
                          <motion.div 
                            layoutId="theme-indicator"
                            className="w-2.5 h-2.5 rounded-full" 
                            style={{ backgroundColor: item.color }} 
                          />
                        </button>
                      )) : (
                        <div className="h-6 w-32 bg-white/5 rounded animate-pulse" />
                      )}
                    </div>
                  </div>
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>
      </motion.aside>

      {/* MOBILE DRAWER OVERLAY & MENU */}
      <AnimatePresence>
        {isMobileOpen && (
          <>
            {/* Backdrop */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/45 backdrop-blur-xs z-50 lg:hidden"
              onClick={() => setIsMobileOpen(false)}
            />
            {/* Drawer */}
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="fixed inset-y-0 left-0 w-64 border-r border-border/80 flex flex-col z-50 bg-card/95 backdrop-blur-xl shrink-0 overflow-hidden text-primary lg:hidden"
            >
              {/* BRAND SPINE with Close button */}
              <div className="h-24 border-b border-border/40 flex items-center justify-between px-6 shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 border border-gold/40 rounded flex items-center justify-center bg-gold/5">
                    <span className="text-gold font-serif font-black text-xs">K</span>
                  </div>
                  <div className="flex flex-col select-none">
                    <span className="font-serif text-sm font-black italic tracking-tighter text-primary">Kenbun</span>
                    <span className="ind-header tracking-[0.4em] opacity-35 text-[5px] uppercase font-bold text-primary">Sovereign Hive</span>
                  </div>
                </div>
                <button 
                  onClick={() => setIsMobileOpen(false)} 
                  className="p-1.5 rounded-full hover:bg-border/40 text-primary cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* NAVIGATION */}
              <nav className="flex-1 flex flex-col items-stretch pt-6 space-y-1 px-3 overflow-y-auto custom-scrollbar">
                {navItems.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link 
                      key={item.name} 
                      href={item.href}
                      onClick={() => setIsMobileOpen(false)}
                      className={`flex items-center gap-4 px-4 py-2.5 rounded-lg transition-all group relative border ${
                        isActive 
                          ? "bg-gold/8 border-gold/15 text-gold font-bold" 
                          : "border-transparent text-primary/55 hover:text-primary"
                      }`}
                    >
                      <item.icon className="w-4 h-4" />
                      <span className="text-[9.5px] font-bold uppercase tracking-[0.25em]">{item.name}</span>
                    </Link>
                  );
                })}
              </nav>

              {/* TENANT SELECTOR */}
              <div className="px-6 py-4 border-t border-border/40 flex flex-col gap-2 shrink-0">
                <label className="text-[8px] font-bold uppercase tracking-[0.25em] opacity-40 select-none">Active Tenant</label>
                <div className="relative">
                  <select
                    value={tenantId}
                    onChange={(e) => setTenantId(e.target.value)}
                    className="bg-card border border-border text-[10px] py-1.5 pl-2.5 pr-8 rounded text-primary focus:outline-none focus:ring-1 focus:ring-gold w-full cursor-pointer appearance-none"
                  >
                    {tenants.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-primary/45" />
                </div>
              </div>

              {/* THEME PICKER */}
              <div className="p-6 border-t border-border/40 flex flex-col gap-2 shrink-0">
                <label className="text-[8px] font-bold uppercase tracking-[0.25em] opacity-40 select-none">Visual Theme</label>
                <div className="flex flex-wrap items-center gap-2.5">
                  {mounted ? [
                    { id: "limestone", color: "#B8422E", bg: "#F7F5F2", name: "Limestone" },
                    { id: "forest", color: "#2E8B57", bg: "#F0F4F1", name: "Forest" },
                    { id: "cobalt", color: "#2F6FEB", bg: "#F0F4F8", name: "Cobalt" },
                    { id: "breeze", color: "#0EA5E9", bg: "#F8FAFC", name: "Breeze" },
                    { id: "obsidian", color: "#FF6B4A", bg: "#0F1011", name: "Obsidian" },
                    { id: "sunset", color: "#F97316", bg: "#170F11", name: "Sunset" },
                    { id: "midnight", color: "#818CF8", bg: "#09090B", name: "Midnight" },
                    { id: "cyber", color: "#00FF41", bg: "#000000", name: "Cyber" }
                  ].map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setPreset(item.id as any)}
                      title={item.name}
                      className={`w-6 h-6 rounded-full flex items-center justify-center border transition-all cursor-pointer ${
                        preset === item.id ? "border-gold scale-110" : "border-border opacity-60"
                      }`}
                      style={{ backgroundColor: item.bg }}
                    >
                      <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                    </button>
                  )) : (
                    <div className="h-6 w-32 bg-white/5 rounded animate-pulse" />
                  )}
                </div>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* MOBILE BOTTOM NAVIGATION BAR */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 h-16 bg-card/85 backdrop-blur-lg border-t border-border/80 z-40 flex items-stretch text-primary">
        {mobilePrimaryItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link 
              key={item.name} 
              href={item.href}
              className={`flex-1 flex flex-col items-center justify-center relative transition-all ${
                isActive ? "text-gold" : "text-primary opacity-45"
              }`}
            >
              <item.icon className={`w-3.5 h-3.5 transition-transform ${isActive ? "text-gold scale-110" : "text-primary/50"}`} />
              <span className={`text-[7px] font-bold uppercase tracking-widest mt-1.5 text-primary ${isActive ? "opacity-100 font-bold" : "opacity-45"}`}>
                {item.name}
              </span>
              {isActive && (
                <motion.div 
                  layoutId="mobile-active-indicator"
                  className="absolute bottom-1.5 left-1/2 -translate-x-1/2 w-4 h-[2px] bg-gold rounded-full" 
                />
              )}
            </Link>
          );
        })}
        {/* Menu (More) Trigger Button */}
        <button 
          onClick={() => setIsMobileOpen(true)}
          className={`flex-1 flex flex-col items-center justify-center relative transition-all cursor-pointer ${
            isMobileOpen ? "text-gold" : "text-primary opacity-45"
          }`}
        >
          <Menu className="w-3.5 h-3.5 text-primary/50" />
          <span className="text-[7px] font-bold uppercase tracking-widest mt-1.5 text-primary opacity-45">
            More
          </span>
        </button>
      </nav>
    </>
  );
}
