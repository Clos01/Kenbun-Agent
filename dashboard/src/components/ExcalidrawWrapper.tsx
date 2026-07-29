"use client";

import React, { useEffect, useState } from "react";
// @ts-ignore
import { Excalidraw } from "@excalidraw/excalidraw";

import { useTheme } from "@/context/ThemeContext";

function isDarkColor(hex: string): boolean {
  if (!hex || hex === "transparent" || hex === "none") return false;
  let h = hex.replace("#", "");
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  if (h.length !== 6) return false;
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  if (isNaN(r) || isNaN(g) || isNaN(b)) return false;
  return (r * 299 + g * 587 + b * 114) / 1000 < 140;
}

function isLightColor(hex: string): boolean {
  if (!hex || hex === "transparent" || hex === "none") return false;
  return !isDarkColor(hex);
}

export default function ExcalidrawWrapper() {
  const { theme } = useTheme();
  const [initialData, setInitialData] = useState<any>(null);

  useEffect(() => {
    // Sync localStorage cache so Excalidraw canvas background matches active theme
    try {
      const targetBg = theme === "dark" ? "#0F1011" : "#F7F5F2";
      const saved = localStorage.getItem("excalidraw-state");
      if (saved) {
        const parsed = JSON.parse(saved);
        parsed.viewBackgroundColor = targetBg;
        parsed.theme = theme;
        localStorage.setItem("excalidraw-state", JSON.stringify(parsed));
      }
    } catch (e) {}

    // Fetch the latest wireframe data from our API on mount
    fetch("/api/wireframe")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.elements) {
          const isDark = theme === "dark";

          // Dynamically adapt appState
          const appState = {
            ...(data.appState || {}),
            theme: theme,
            viewBackgroundColor: isDark ? "#0F1011" : "#F7F5F2",
          };

          // Dynamically adapt element colors (dark text on light bg vs white text on dark bg)
          const adaptedElements = data.elements.map((el: any) => {
            let strokeColor = el.strokeColor;
            let backgroundColor = el.backgroundColor;

            if (!isDark) {
              // Light mode: dark background fills become light white/slate, light strokes become dark ink
              if (isDarkColor(backgroundColor)) {
                backgroundColor = "#FFFFFF";
              }
              if (isLightColor(strokeColor) || strokeColor === "#ffffff" || strokeColor === "#FFFFFF") {
                strokeColor = "#1A1C1E";
              }
            } else {
              // Dark mode: light background fills become dark slate, dark strokes become white
              if (isLightColor(backgroundColor)) {
                backgroundColor = "#181A1C";
              }
              if (isDarkColor(strokeColor)) {
                strokeColor = "#FFFFFF";
              }
            }

            return {
              ...el,
              strokeColor,
              backgroundColor,
            };
          });

          setInitialData({
            elements: adaptedElements,
            appState: appState,
          });
        } else {
          setInitialData({ elements: [] });
        }
      })
      .catch((err) => {
        console.error("Failed to load wireframe data", err);
        setInitialData({ elements: [] });
      });
  }, [theme]);

  if (!initialData) {
    return <div className="w-full h-full flex items-center justify-center text-primary/60">Loading Excalidraw Canvas...</div>;
  }

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-3 right-4 z-50 flex items-center gap-2">
        <a
          href="/NeverMiss_AI_Dashboard_Wireframes.pdf"
          download="Project_Wireframes.pdf"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium shadow-md transition-all border border-emerald-400/30 cursor-pointer"
          title="Export Wireframe PDF"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Export Wireframe PDF
        </a>
      </div>
      <Excalidraw
        key={theme}
        initialData={initialData}
        theme={theme}
        name="NeverMiss AI Architecture"
        UIOptions={{
          canvasActions: {
            changeViewBackgroundColor: true,
            clearCanvas: true,
            loadScene: true,
            saveToActiveFile: true,
            toggleTheme: true,
            saveAsImage: true,
          },
        }}
      />
    </div>
  );
}
