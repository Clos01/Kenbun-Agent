# Design System: Planhat

## 0. Brand Context

_Skipped by the deterministic emitter  Brand Context requires world knowledge about the company, audience, and personality that no extraction can produce reliably._

For a complete, agent-written Brand Context section, paste `prompts/universal.md` (downloadable from the SPA result panel) into Claude Code / Claude.ai / ChatGPT / Cursor.

## 1. Visual Theme & Atmosphere

_Skipped by the deterministic emitter  Visual Theme requires aesthetic judgement ("could this describe 3 other sites?") that no extraction can produce reliably._

For a complete, agent-written Visual Theme section, paste `prompts/universal.md` into an AI agent.

## 2. Color Palette & Roles

Permanent palette (L1 infrastructure + L2 system): 7 tokens. 0 campaign-level tokens are listed separately below; 1 content-level tokens are excluded per the 4-layer stability classification.

### Brand Colors

- **Primary** (`#0000ee`): frequency 981. Used as (text 981). (layer: infrastructure)
- **Muted** (`#958d7e`): frequency 3. Used as (text 3). (CSS var: `--token-e30314d8-6043-47db-ba45-f5fb52251c2e`; layer: infrastructure)

### Structural Colors

- **Ink** (`#000000`): frequency 1835. Used as (text 1777, bg 46, border 2, shadow 6, gradient 2, icon 2). (layer: infrastructure)
- **Canvas** (`#ffffff`): frequency 357. Used as (text 260, bg 89, border 4, gradient 2, icon 2). (CSS var: `--token-6889a6d4-a9a4-45fd-a538-dcf976f7e3db`; layer: infrastructure)
- **Dark Surface** (`#121211`): frequency 13. Used as (text 13). (CSS var: `--token-db54caba-b31b-41fa-9f69-699e0eb81f2b`; layer: infrastructure)
- **Mid Neutral** (`#9e9d9b`): frequency 5. Used as (text 1, bg 3, icon 1). (CSS var: `--token-79144cdb-25c1-430c-aaff-2584be63d295`; layer: infrastructure)
- **Mid Neutral** (`#d4d4d4`): frequency 1. Used as (border 1). (layer: system)

### Color Boundary Rules

- Infrastructure (L1) and System (L2) colors form the permanent palette. Use them anywhere.
- Campaign (L3) tokens (launch-specific accents that change between campaigns) were not present in this extraction.
- Content (L4) colors appear inside product imagery and are NOT part of the design system. Excluded from this document.
- Permanent chromatic colors at frequency < 5 may be decorative. Verify intent before adopting them as system tokens.

## 3. Typography Rules

### Font Families

- `Geigy LL Duplex Var Variable Reg`
- `Inter`
- `Inter Variable`

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | OpenType | Frequency | Typical Tags |
|------|------|------|--------|-------------|----------------|----------|-----------|--------------|
| Display XXL | `Geigy LL Duplex Var Variable Reg` | `113px` | `400` | `113px` | `-6.78px` | — | 2 | p |
| Display XXL | `Geigy LL Duplex Var Variable Reg` | `72px` | `400` | `76px` | `-3.6px` | `"blwf", "cv03", "cv04", "cv09", "cv11"` | 1 | h2 |
| Display XXL | `Geigy LL Duplex Var Variable Reg` | `60px` | `400` | `66px` | `-1.8px` | `"blwf", "cv03", "cv04", "cv09", "cv11"` | 15 | h2, p |
| Display XL | `Geigy LL Duplex Var Variable Reg` | `48px` | `400` | `53px` | `-2.16px` | `"blwf", "cv03", "cv04", "cv09", "cv11"` | 10 | h2, p, span |
| Display MD | `Geigy LL Duplex Var Variable Reg` | `32px` | `400` | `38px` | `-1.12px` | `"blwf", "cv03", "cv04", "cv09", "cv11"` | 10 | h5, h2, p |
| Heading LG | `Geigy LL Duplex Var Variable Reg` | `24px` | `400` | `30px` | `-0.72px` | `"blwf", "cv03", "cv04", "cv09", "cv11"` | 26 | p, h6 |
| Heading MD | `Geigy LL Duplex Var Variable Reg` | `18px` | `400` | `25px` | `-0.36px` | `"blwf", "cv03", "cv04", "cv09", "cv11"` | 100 | h3, p, h4, span |
| Body MD | `Inter` | `16px` | `400` | `22px` | `-0.24px` | — | 4 | p |
| Body SM | `Inter` | `14px` | `400` | `21px` | `-0.28px` | — | 46 | p |
| Body SM | `Inter` | `14px` | `400` | `20px` | `normal` | — | 2 | p, span |
| Body SM | `Inter` | `14px` | `400` | `17px` | `normal` | — | 80 | p |
| Body SM | `Inter` | `14px` | `300` | `21px` | `0.28px` | — | 2 | p |
| Body SM | `Inter` | `14px` | `500` | `17px` | `-0.28px` | — | 4 | button |
| Button | `Inter` | `13px` | `600` | `21px` | `0.28px` | — | 2 | a |
| Overline | `Inter Variable` | `12px` | `400` | `18px` | `1.8px` | `"dlig"` | 36 | h1, p, h2 |
| Caption | `Inter` | `12px` | `400` | `18px` | `-0.12px` | — | 5 | p |
| Overline | `Inter` | `12px` | `500` | `12px` | `1.2px` | — | 1 | p |
| Overline | `Inter Variable` | `10px` | `400` | `15px` | `1px` | — | 93 | p, h2 |
| Micro | `Inter` | `10px` | `400` | `15px` | `normal` | — | 16 | p, a |
| Overline | `Inter` | `10px` | `500` | `12px` | `1px` | — | 1 | p |

## 4. Component Stylings

_Partial template: extracted variant styles are documented below, but the "Use:" lines and state-change rationale are subjective and best filled in by an AI agent. See `prompts/universal.md` for the agent-written version._

### Link

#### Default

- **Count:** 193
- **Style:**
  - `backgroundColor`: `rgba(0, 0, 0, 0)`
  - `color`: `rgb(0, 0, 0)`
  - `fontSize`: `12px`
  - `fontWeight`: `400`
  - `borderRadius`: `4px`
  - `padding`: `84px 48px 96px 48px`
- **Transition:** `all`

### Footer

#### Default

- **Count:** 32
- **Style:**
  - `backgroundColor`: `rgb(255, 255, 255)`
  - `color`: `rgb(0, 0, 0)`
  - `fontSize`: `12px`
  - `fontWeight`: `400`
  - `borderRadius`: `0px`
  - `padding`: `64px 0px 64px 0px`
- **Transition:** `all`

### Button

#### Ghost

- **Count:** 26
- **Style:**
  - `backgroundColor`: `rgba(0, 0, 0, 0)`
  - `color`: `rgb(0, 0, 0)`
  - `fontSize`: `12px`
  - `fontWeight`: `400`
  - `borderRadius`: `4px`
  - `padding`: `10px 16px 10px 18px`
- **Transition:** `all`

#### Ghost

- **Count:** 2
- **Style:**
  - `backgroundColor`: `rgba(0, 0, 0, 0)`
  - `color`: `rgb(0, 0, 238)`
  - `fontSize`: `12px`
  - `fontWeight`: `400`
  - `borderRadius`: `0px`
  - `padding`: `0px 0px 48px 0px`
- **Transition:** `all`

#### Outline

- **Count:** 2
- **Style:**
  - `backgroundColor`: `rgba(0, 0, 0, 0)`
  - `color`: `rgb(255, 255, 255)`
  - `fontSize`: `14px`
  - `fontWeight`: `500`
  - `borderRadius`: `19px`
  - `padding`: `9px 14px 9px 14px`
  - `borderWidth`: `1px`
  - `borderColor`: `rgb(255, 255, 255)`
  - `borderStyle`: `solid`
- **Transition:** `all`

#### Secondary

- **Count:** 2
- **Style:**
  - `backgroundColor`: `rgb(255, 255, 255)`
  - `color`: `rgb(0, 0, 0)`
  - `fontSize`: `14px`
  - `fontWeight`: `500`
  - `borderRadius`: `19px`
  - `padding`: `9px 14px 9px 14px`
  - `boxShadow`: `rgba(0, 0, 0, 0.12) 0px 0px 10px 0px`
  - `borderWidth`: `1px`
  - `borderColor`: `rgb(255, 255, 255)`
  - `borderStyle`: `solid`
- **Transition:** `all`

### Badge

#### Neutral

- **Count:** 8
- **Style:**
  - `backgroundColor`: `rgb(0, 0, 0)`
  - `color`: `rgb(0, 0, 0)`
  - `fontSize`: `12px`
  - `fontWeight`: `400`
  - `borderRadius`: `999px`
  - `padding`: `0px 0px 0px 0px`
- **On hover:** 1 property change(s).
- **On active:** 1 property change(s).
- **Transition:** `all`

### Input

#### Default

- **Count:** 8
- **Style:**
  - `backgroundColor`: `rgba(255, 255, 255, 0)`
  - `color`: `rgb(0, 0, 0)`
  - `fontSize`: `14px`
  - `fontWeight`: `400`
  - `borderRadius`: `0px`
  - `padding`: `12px 0px 12px 0px`
- **Transition:** `all`

### Card

#### Default

- **Count:** 2
- **Style:**
  - `backgroundColor`: `rgba(0, 0, 0, 0.4)`
  - `color`: `rgb(255, 255, 255)`
  - `fontSize`: `12px`
  - `fontWeight`: `400`
  - `borderRadius`: `20px`
  - `padding`: `28px 28px 28px 28px`
  - `boxShadow`: `rgba(0, 0, 0, 0.12) 0px 4px 8px 0px, rgba(0, 0, 0, 0.12) 0px 8px 32px 0px`
- **Transition:** `all`

#### Filled

- **Count:** 1
- **Style:**
  - `backgroundColor`: `rgb(255, 255, 255)`
  - `color`: `rgb(0, 0, 0)`
  - `fontSize`: `12px`
  - `fontWeight`: `400`
  - `borderRadius`: `2px`
  - `padding`: `64px 64px 48px 64px`
- **Transition:** `all`

### Navigation

#### Default

- **Count:** 2
- **Style:**
  - `backgroundColor`: `rgba(0, 0, 0, 0)`
  - `color`: `rgb(0, 0, 0)`
  - `fontSize`: `12px`
  - `fontWeight`: `400`
  - `borderRadius`: `0px`
  - `padding`: `0px 0px 0px 0px`
- **Transition:** `all`

## 5. Layout Principles

### Spacing System

- **Base unit:** `4px`
- **Scale:** `4px`, `8px`, `12px`, `16px`, `20px`, `24px`, `28px`, `32px`, `36px`, `40px`, `48px`, `64px`, `72px`, `80px`, `84px`, `96px`, `120px`
- **Section spacing:** `48px`, `64px`, `72px`, `80px`, `91px`, `96px`, `120px`, `180px`
- **Max content width:** `1260px`

### Grid & Container

- **Common column counts:** 2, 3, 4, 6
- **Content alignment:** mixed
- **Max content width:** `1260px`

### Border Radius Scale

| Value | Frequency | Typical Elements |
|-------|-----------|------------------|
| `4px` | 161 | button, div, img, a |
| `8px` | 102 | a, div, img |
| `6px` | 12 | div, img |
| `100px` | 10 | div |
| `999px` | 9 | div |
| `19px` | 4 | button |
| `4px 0px 0px 4px` | 3 | div, a |
| `50%` | 2 | div |
| `20px` | 2 | div |
| `0px 4px 4px 0px` | 1 | a |
| `4px 0px 0px` | 1 | a |
| `0px 4px 0px 0px` | 1 | a |
| `0px 0px 4px 4px` | 1 | a |
| `12px` | 1 | div |
| `2px` | 1 | form |

## 6. Depth & Elevation

### Shadow Scale

| Type | Value | Frequency | Typical Elements |
|------|-------|-----------|------------------|
| elevation | `rgba(0, 0, 0, 0.12) 0px 0px 10px 0px` | 2 | button |
| complex-stack | `rgba(0, 0, 0, 0.12) 0px 4px 8px 0px, rgba(0, 0, 0, 0.12) 0px 8px 32px 0px` | 2 | div |

## 6.5. Motion System

### Duration Scale

| Label | Value | Frequency |
|-------|-------|-----------|
| small | `150ms` | 1 |
| medium | `300ms` | 13 |
| large | `500ms` | 8 |
| xl | `2000ms` | 2 |

### Easing

- **Primary:** `ease`
- **Other observed:**
  - `ease` (frequency 37)
  - `cubic-bezier(.44` (frequency 6)
  - `ease-out` (frequency 4)

### Keyframe Animations

| Name | Type | Duration | Properties |
|------|------|----------|------------|
| `ch2-bar-bottom-in-2` | entrance | `2s` | opacity, transform |
| `__framer-loading-spin` | generic | `800ms` | transform |
| `ch2-settings-in` | generic | `0s` | top, -webkit-transform, transform |
| `ch2-bar-top-in` | generic | `0s` | -webkit-transform, transform |
| `ch2-bar-bottom-in` | generic | `0s` | -webkit-transform, transform |
| `ch2-bubble-left-in` | entrance | `0s` | opacity |
| `ch2-default-top-in` | attention | `0s` | -webkit-transform, transform |
| `ch2-default-center-in` | attention | `0s` | top, -webkit-transform, transform |

### Reduced Motion

- **Supported:** not detected

## 7. Content & Voice

_Skipped by the deterministic emitter  Content & Voice requires reading microcopy and inferring brand voice, which no extraction can do reliably._

For a complete, agent-written Content & Voice section, paste `prompts/universal.md` into an AI agent.

## 8. Do's and Don'ts

_Skipped by the deterministic emitter  Do's and Don'ts are brand-specific judgement calls._

For a complete, agent-written Do's and Don'ts section, paste `prompts/universal.md` into an AI agent.

## 9. Accessibility Contract

### WCAG Target

- **Default:** WCAG 2.2 AA (4.5:1 normal text, 3:1 large text)

### Contrast Pairs

| Foreground | Background | Ratio | AA | AAA | Usage |
|------------|------------|-------|----|-----|-------|
| `rgb(0, 0, 0)` | `rgb(255, 255, 255)` | 21.00:1 | ✓ | ✓ | 7 |
| `rgb(0, 0, 0)` | `rgb(0, 0, 0)` | 1.00:1 | ✗ | ✗ | 7 |
| `rgb(255, 255, 255)` | `rgba(0, 0, 0, 0.4)` | 21.00:1 | ✓ | ✓ | 2 |
| `rgb(0, 0, 0)` | `rgba(255, 255, 255, 0.05)` | 21.00:1 | ✓ | ✓ | 1 |

### Touch / Click Target

- **Minimum observed:** `13×12px`


## 10. Responsive Behavior

### Breakpoints

| Type | Value | Rules |
|------|-------|-------|
| max-width | `809.98px` | 76 |
| min-width | `810px` | 113 |
| min-width | `0` | 63 |
| max-width | `600px` | 70 |
| max-width | `800px` | 78 |
| other | `(max-height:600px)` | 10 |
| min-width | `801px` | 18 |
| max-width | `450px` | 10 |
| other | `(max-height:700px)` | 4 |
| max-width | `1000px` | 16 |
| max-width | `650px` | 36 |
| min-width | `651px` | 10 |
| min-width | `1000px` | 4 |
| min-width | `650px` | 6 |
| max-width | `599px` | 6 |
| min-width | `600px` | 12 |

## 11. State Matrix

| Component / Variant | default | hover | focus-visible | active | disabled |
|---------------------|---------|-------|---------------|--------|----------|
| Link · Default | ✓ |  |  |  |  |
| Footer · Default | ✓ |  |  |  |  |
| Button · Ghost | ✓ |  |  |  |  |
| Button · Ghost | ✓ |  |  |  |  |
| Button · Outline | ✓ |  |  |  |  |
| Button · Secondary | ✓ |  |  |  |  |
| Badge · Neutral | ✓ | ✓ |  | ✓ |  |
| Input · Default | ✓ |  |  |  |  |
| Card · Default | ✓ |  |  |  |  |
| Card · Filled | ✓ |  |  |  |  |
| Navigation · Default | ✓ |  |  |  |  |

## 12. Iconography

- **Library:** custom / unknown
- **Total icons observed:** 193
- **Color mode:** fixed
- **Sizes observed:** `0px`, `10px`, `16px`

## 13. Agent Prompt Guide

Quick reference for an AI coding agent generating UI from this design system.

### Quick Color Reference

- **Ink**: `#000000`
- **Primary**: `#0000ee`
- **Canvas**: `#ffffff`
- **Muted**: `#958d7e`
- **Accent**: `#22c55e`

### Self-Containment Checklist

When asking an AI to produce a component using this system, the prompt MUST inline:

- [ ] Font family, size, weight, line-height, letter-spacing
- [ ] All colors as 6-digit lowercase hex
- [ ] Padding, border-radius, shadow values
- [ ] OpenType features when the system uses them
- [ ] Hover, focus-visible, active values where the variant has them
- [ ] Transition value

### Where to go for the full premium guide

For agent-written prose covering Sections 0, 1, 4 (rationale), 7, 8, and the iteration guide, paste `prompts/universal.md` into Claude Code / Claude.ai / ChatGPT / Cursor / Codex / Windsurf / Lovable / Replit Agent.


<!-- Generated: 2026-05-26 | Source: https://www.planhat.com/ | Pages: 2 | Framework: Bootstrap | Format: v2 -->
<!-- This is not the official design system. Colors, fonts, and spacing may not be 100% accurate. -->
<!-- Sections 0, 1, 7, 8 are skipped in the deterministic emitter  they require -->
<!-- brand judgement. Paste prompts/universal.md into an AI agent for full coverage. -->
