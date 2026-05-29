// 🏛️ Spatial Projection Constants
export const MAP_OFFSET = 50;
export const MAP_MULTIPLIER = 30;

// Coordinate Projection Helper
export const getProjectedCoords = (x: number, y: number) => ({
  x: (x - MAP_OFFSET) * MAP_MULTIPLIER,
  y: (y - MAP_OFFSET) * MAP_MULTIPLIER
});

// 🎨 Swarm Theme Color Palettes (Static allocations to eliminate GC overhead in draw loop)
export const ROOM_COLORS_DARK: Record<string, string> = {
  "Central_Logic": "#F43F5E", // Vibrant Rose
  "Vault": "#2DD4BF",         // Cyan
  "Observatory": "#3B82F6",   // Royal Blue
  "Simulations": "#A78BFA",   // Violet
  "Archives": "#FBBF24"       // Amber Gold
};

export const ROOM_COLORS_LIGHT: Record<string, string> = {
  "Central_Logic": "#B8422E", // Boston Clay
  "Vault": "#0D9488",         // Muted Forest Teal
  "Observatory": "#2563EB",   // Cobalt Blue
  "Simulations": "#4F46E5",   // Indigo
  "Archives": "#B45309"       // Amber Bronze
};

export const ROOM_COLORS_MAP_DARK: Record<string, string> = {
  "Central_Logic": "bg-rose-500/10 border-rose-500/40 text-rose-400",
  "Vault": "bg-teal-500/10 border-teal-500/40 text-teal-400",
  "Observatory": "bg-blue-500/10 border-blue-500/40 text-blue-400",
  "Simulations": "bg-purple-500/10 border-purple-500/40 text-purple-400",
  "Archives": "bg-amber-500/10 border-amber-500/40 text-amber-400"
};

export const ROOM_COLORS_MAP_LIGHT: Record<string, string> = {
  "Central_Logic": "bg-[#B8422E]/10 border-[#B8422E]/30 text-[#B8422E]",
  "Vault": "bg-teal-600/10 border-teal-600/30 text-teal-700",
  "Observatory": "bg-blue-600/10 border-blue-600/30 text-blue-700",
  "Simulations": "bg-indigo-600/10 border-indigo-600/30 text-indigo-700",
  "Archives": "bg-amber-700/10 border-amber-700/30 text-amber-800"
};
