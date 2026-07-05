"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  mounted: boolean;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTimeout(() => {
      setMounted(true);
    }, 0);
    
    // 1. Permanently remove legacy localStorage entries to break any persistent light-mode locks asynchronously
    const cleanupTimer = setTimeout(() => {
      try {
        localStorage.removeItem("theme");
        localStorage.removeItem("ag_theme");
      } catch {}
    }, 0);

    // 2. Synchronize React state with the class applied by the blocking head script
    setTimeout(() => {
      try {
        const hasLightClass = document.documentElement.classList.contains("light");
        setTheme(hasLightClass ? "light" : "dark");
      } catch {}
    }, 0);

    // 3. Add transition-colors class dynamically after load to avoid transition jitter (respects prefers-reduced-motion)
    const transitionTimer = setTimeout(() => {
      try {
        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (!prefersReducedMotion) {
          document.body.classList.add("transition-colors", "duration-300");
        }
      } catch {}
    }, 100);

    // 4. Listen to OS system preference changes dynamically
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleSystemChange = (e: MediaQueryListEvent) => {
      try {
        if (!localStorage.getItem("ag_theme_v2")) {
          const newTheme = e.matches ? "dark" : "light";
          setTheme(newTheme);
          document.documentElement.classList.toggle("light", !e.matches);
        }
      } catch {
        // Fallback for private browsing
        const newTheme = e.matches ? "dark" : "light";
        setTheme(newTheme);
        document.documentElement.classList.toggle("light", !e.matches);
      }
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleSystemChange);
    } else {
      mediaQuery.addListener(handleSystemChange);
    }

    // 5. Cross-tab synchronization for versioned theme key
    const handleStorageSync = (e: StorageEvent) => {
      if (e.key === "ag_theme_v2") {
        const newTheme = e.newValue as Theme || "dark";
        setTheme(newTheme);
        document.documentElement.classList.toggle("light", newTheme === "light");
      }
    };
    window.addEventListener("storage", handleStorageSync);

    return () => {
      clearTimeout(cleanupTimer);
      clearTimeout(transitionTimer);
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleSystemChange);
      } else {
        mediaQuery.removeListener(handleSystemChange);
      }
      window.removeEventListener("storage", handleStorageSync);
    };
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === "dark" ? "light" : "dark";
    setTheme(newTheme);
    try {
      localStorage.setItem("ag_theme_v2", newTheme);
    } catch {}
    document.documentElement.classList.toggle("light", newTheme === "light");
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, mounted }}>
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
