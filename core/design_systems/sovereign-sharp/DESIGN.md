# Design System Inspired by Sovereign Sharp

> Category: Kenbun Intelligence
> High-fidelity industrial minimalism for sovereign intelligence interfaces. Sharp edges, champagne accents, and architectural typography.

## 1. Visual Theme & Atmosphere

An "Architectural Luxury" aesthetic designed for neurodivergent focus (ADHD) and professional sovereignty. It blends the precision of a scientific instrument with the refinement of a high-end publication.

- **Visual style:** sharp, minimal, high-contrast, editorial
- **Color stance:** warm industrial
- **Design intent:** Eliminate "soft" patterns and decision noise. Prioritize vertical flow and information density without visual clutter.

## 2. Color

- **Primary:** `#AF966F` — Champagne Gold. Used for high-status accents and primary signals.
- **Surface:** `#FAF9F6` — Bone White. The primary canvas for light mode.
- **Background:** `#FAF9F6` — Used for layout containers.
- **Text:** `#1A1A1A` — Onyx. High-legibility primary text.
- **Secondary:** `#7D8471` — Sage Green. Used for telemetry and stable signals.
- **Accent:** `#8E4B3D` — Burnt Clay. Used for entropy and alert states.
- **Neutral:** `#E8E6DF` — Warm Slate. Used for borders and dividers.

**Strict Rule**: NO BLUE or PURPLE tones are allowed in any component.

## 3. Typography

- **Scale:** Large editorial display headers with tight tracking.
- **Families:** 
  - Display: `Space Grotesk` (Bold, Tracking -0.06em)
  - Primary: `Inter` (Medium, Tracking -0.02em)
  - Mono: `Space Mono` (Bold, Tracking 0.2em)
- **Rules**: Headlines should be massive but clean. Metadata labels should be tiny (8pt) with high tracking (0.6em).

## 4. Spacing & Grid

- **Grid**: 4pt/8pt baseline grid.
- **Whitespace**: "Luxury Whitespace" — use generous padding to separate concerns rather than lines.
- **Alignment**: Strict vertical alignment. Single-column primary flows to reduce cognitive overhead.

## 5. Layout & Composition

- **The Monolith**: Every page should have one massive primary focal point.
- **Data Density**: Use grid-based visualization for metrics, but keep it within the vertical scroll context.
- **No Floating Elements**: Everything is anchored to the architectural grid.

## 6. Components

- **Edges**: 100% Sharp (Radius: 0px). No rounded corners allowed.
- **Shadows**: Hard Shadows only (`4px 4px 0px 0px`). No soft blurs.
- **Buttons**: Thin 1px borders, high-impact hover states (Champagne background).
- **Cards**: Use thin 1px `Neutral` borders. 

## 7. Motion & Interaction

- **Industrial Easing**: Purposeful, linear, or "snap" transitions. No "bouncy" or elastic animations.
- **Signals**: Use Champagne Gold for active reasoning signals and Sage Green for stable network pulses.

## 8. Voice & Brand

- **Tone**: Sovereign, authoritative, precise, and concise. 
- **Language**: Use technical/scientific terminology (Node, Entropy, Pulse, Governance).

## 9. Anti-patterns

- **No Rounded Corners**: Any radius > 0 is a design failure.
- **No Soft Shadows**: Avoid `box-shadow` with blur radii.
- **No Blue/Purple**: These colors are purged from the system.
- **No Cards**: Favor semantic sections with borders/whitespace over independent floating cards.
