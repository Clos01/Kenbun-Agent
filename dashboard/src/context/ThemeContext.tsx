"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type ThemePreset = "limestone" | "obsidian" | "forest" | "cobalt" | "midnight" | "cyber" | "sunset" | "breeze";

export const THEME_PRESETS = {
  limestone: {
    name: "Limestone",
    primary: "#1A1C1E",
    secondary: "#6C7278",
    tertiary: "#B8422E",
    neutral: "#F7F5F2",
    card: "#FFFFFF",
    border: "rgba(26, 28, 30, 0.08)",
    borderMuted: "rgba(26, 28, 30, 0.04)",
    sand: "rgba(184, 66, 46, 0.04)"
  },
  obsidian: {
    name: "Obsidian",
    primary: "#F7F5F2",
    secondary: "#9EA4AC",
    tertiary: "#FF6B4A",
    neutral: "#0F1011",
    card: "#181A1C",
    border: "rgba(247, 245, 242, 0.08)",
    borderMuted: "rgba(247, 245, 242, 0.04)",
    sand: "rgba(255, 107, 74, 0.04)"
  },
  forest: {
    name: "Forest",
    primary: "#1B2A1E",
    secondary: "#788A7D",
    tertiary: "#2E8B57",
    neutral: "#F0F4F1",
    card: "#FFFFFF",
    border: "rgba(27, 42, 30, 0.08)",
    borderMuted: "rgba(27, 42, 30, 0.04)",
    sand: "rgba(46, 139, 87, 0.04)"
  },
  cobalt: {
    name: "Cobalt",
    primary: "#1A2332",
    secondary: "#6C7D93",
    tertiary: "#2F6FEB",
    neutral: "#F0F4F8",
    card: "#FFFFFF",
    border: "rgba(26, 35, 50, 0.08)",
    borderMuted: "rgba(26, 35, 50, 0.04)",
    sand: "rgba(47, 111, 235, 0.04)"
  },
  breeze: {
    name: "Breeze",
    primary: "#1E293B",
    secondary: "#64748B",
    tertiary: "#0EA5E9",
    neutral: "#F8FAFC",
    card: "#FFFFFF",
    border: "rgba(30, 41, 59, 0.08)",
    borderMuted: "rgba(30, 41, 59, 0.04)",
    sand: "rgba(14, 165, 233, 0.04)"
  },
  midnight: {
    name: "Midnight",
    primary: "#F8FAFC",
    secondary: "#94A3B8",
    tertiary: "#818CF8",
    neutral: "#09090B",
    card: "#121216",
    border: "rgba(248, 250, 252, 0.08)",
    borderMuted: "rgba(248, 250, 252, 0.04)",
    sand: "rgba(129, 140, 248, 0.04)"
  },
  cyber: {
    name: "Cyber",
    primary: "#00FF41",
    secondary: "#008F11",
    tertiary: "#00FF41",
    neutral: "#000000",
    card: "#050505",
    border: "rgba(0, 255, 65, 0.15)",
    borderMuted: "rgba(0, 255, 65, 0.05)",
    sand: "rgba(0, 255, 65, 0.04)"
  },
  sunset: {
    name: "Sunset",
    primary: "#FDE047",
    secondary: "#FDBA74",
    tertiary: "#F97316",
    neutral: "#170F11",
    card: "#211518",
    border: "rgba(253, 224, 71, 0.1)",
    borderMuted: "rgba(253, 224, 71, 0.04)",
    sand: "rgba(249, 115, 22, 0.04)"
  }
};

interface ThemeContextType {
  theme: "light" | "dark";
  preset: ThemePreset;
  setPreset: (preset: ThemePreset) => void;
  toggleTheme: () => void;
  mounted: boolean;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preset, setPresetState] = useState<ThemePreset>(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("kenbun_theme_preset") as ThemePreset;
      if (stored && THEME_PRESETS[stored]) {
        return stored;
      }
      const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      return isDark ? "obsidian" : "limestone";
    }
    return "obsidian";
  });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!preset) return;
    try {
      localStorage.setItem("kenbun_theme_preset", preset);
    } catch {}

    const root = document.documentElement;
    const p = THEME_PRESETS[preset];
    if (p) {
      root.style.setProperty("--primary", p.primary);
      root.style.setProperty("--secondary", p.secondary);
      root.style.setProperty("--tertiary", p.tertiary);
      root.style.setProperty("--accent", p.tertiary);
      root.style.setProperty("--neutral", p.neutral);
      root.style.setProperty("--background", p.neutral);
      root.style.setProperty("--foreground", p.primary);
      root.style.setProperty("--card", p.card);
      root.style.setProperty("--border", p.border);
      root.style.setProperty("--border-muted", p.borderMuted);
      root.style.setProperty("--sand", p.sand);
      root.style.setProperty("--gold", p.tertiary);

      const isObsidian = preset === "obsidian";
      root.classList.toggle("light", !isObsidian);
    }
  }, [preset]);

  const setPreset = (newPreset: ThemePreset) => {
    if (THEME_PRESETS[newPreset]) {
      setPresetState(newPreset);
    }
  };

  const toggleTheme = () => {
    setPresetState((prev) => (prev === "obsidian" ? "limestone" : "obsidian"));
  };

  const theme = preset === "obsidian" ? "dark" : "light";

  return (
    <ThemeContext.Provider value={{ theme, preset, setPreset, toggleTheme, mounted }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
