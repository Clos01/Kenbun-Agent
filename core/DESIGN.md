# Kenbun Design Manifesto (DESIGN.md)

This document is the **Design Law** of the Kenbun Intelligence Ecosystem. All agents generating UI or visual assets MUST adhere to these semantic rules. Failure to comply is a System 2 violation.

## 1. The Core Aesthetic: "Filmic Monolith"
- **Atmosphere**: Dark, cinematic, and high-contrast. 
- **Lighting**: Subtle orange and blue gradients (`#EA580C` / `#2563EB`) as atmospheric glows, never as flat backgrounds.
- **Surface**: Glassmorphism (Background blur: `12px` to `24px`). Use `border: 1px solid rgba(255, 255, 255, 0.05)` to define shapes.

## 2. Typography
- **Primary**: *Inter* or *Roboto* for interface density.
- **Display**: *Outfit* or *Playfair Display* for "Editorial" moments (headers, pitch decks).
- **Rules**:
    - Tight tracking for headlines (`tracking-tighter`).
    - Wide tracking for labels (`tracking-widest`).
    - Hierarchy must be obvious: Headers are 3XL+, subheads are medium, body is small.
- **API Integration**: For standard Google Fonts API integration, optimization protocols (like subsetting and `font-display`), and beta text effects, refer to [docs/Google_Fonts_API.md](../docs/Google_Fonts_API.md).

## 3. Color Palette (OKLch)
We prioritize OKLch for perceptual uniformity.
- **Base**: `oklch(15% 0.01 250)` (Deep Obsidian)
- **Accent (Orange)**: `oklch(65% 0.22 45)` (Kenbun Pulse)
- **Accent (Blue)**: `oklch(55% 0.18 260)` (Cognitive Flow)
- **Border**: `rgba(255, 255, 255, 0.05)`

## 4. Spacing & Grid
- **The "Linear" Rule**: Everything is on an 8px grid.
- **Density**: Use "Dense Data" for dashboards (archives) and "Breathable Air" for creative work (Atelier).
- **Rounding**: `1.5rem` (24px) for main containers, `0.75rem` (12px) for internal cards.

## 5. Motion & Interaction
- **Springs only**: No linear animations. Use `framer-motion` spring configs for all transitions.
- **Hover**: Subtle scale-up (`1.02x`) and border-glow intensity increase.
- **Micro-interactions**: Every click must trigger a visual "synaptic pulse."

## 🛑 Anti-Patterns (The "AI-Slop" Blacklist)
- **NO** Purple/Blue gradients (Generic SaaS).
- **NO** Rounded cards with thick left-border accents.
- **NO** Generic emoji icons in navigation. Use Lucide or Radix.
- **NO** Inter as a display face for brand moments.
- **NO** "MVP-style" flat white backgrounds.
