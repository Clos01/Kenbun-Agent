---
kenbun:
  mode: prototype
  fidelity: high
  tech_stack: [html, css, svg]
  discovery_required: false
---

# Architecture Diagram Skill
Generate professional, dark-themed technical architecture diagrams as standalone HTML files with inline SVG graphics. No external tools, no API keys, no rendering libraries — just write the HTML file and open it in a browser.

## Spacing & Layout Logic
- **Standard Height:** 60px (Services); 80-120px (Large components)
- **Vertical Gap:** Minimum 40px between components
- **Background Grid:** Slate-950 (#020617) with a subtle 40px grid pattern
- **Legend Placement:** Crucial. Calculate the lowest Y-coordinate of all boundaries and place the legend at least 20px below it.

## Visual Language (Semantic Color Palette)
* **Frontend:** Fill: `rgba(8, 51, 68, 0.4)`, Stroke: `#22d3ee` (cyan-400)
* **Backend:** Fill: `rgba(6, 78, 59, 0.4)`, Stroke: `#34d399` (emerald-400)
* **Database:** Fill: `rgba(76, 29, 149, 0.4)`, Stroke: `#a78bfa` (violet-400)
* **AWS/Cloud:** Fill: `rgba(120, 53, 15, 0.3)`, Stroke: `#fbbf24` (amber-400)
* **Security:** Fill: `rgba(136, 19, 55, 0.4)`, Stroke: `#fb7185` (rose-400)
* **Message Bus:** Fill: `rgba(251, 146, 60, 0.3)`, Stroke: `#fb923c` (orange-400)
* **External:** Fill: `rgba(30, 41, 59, 0.5)`, Stroke: `#94a3b8` (slate-400)

## Document Structure
1. **Header:** Title with a pulsing dot indicator and subtitle.
2. **Main SVG:** The diagram contained within a rounded border card.
3. **Summary Cards:** A grid of three cards below the diagram for high-level details.
4. **Footer:** Minimal metadata.

## Output Location
Save diagrams to a user-specified path, or default to:
`./[project-name]-architecture.html`
To preview, run `open ./my-architecture.html` on macOS or `xdg-open ./my-architecture.html` on Linux.
