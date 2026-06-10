---
name: magazine-web-ppt
description: Generates an "Editorial Magazine × E-Ink" style horizontal swipe web presentation (single HTML file), featuring WebGL fluid backgrounds, serif headings + sans-serif body text, chapter covers, data billboards, image grids, and more. Use this skill when the user needs to create a presentation/pitch/slideshow with an editorial or magazine aesthetic, or mentions "horizontal swipe deck", "editorial magazine", "e-ink presentation", or "web PPT".
triggers:
  - "ppt"
  - "deck"
  - "slides"
  - "presentation"
  - "magazine"
  - "horizontal swipe"
  - "horizontal swipe deck"
  - "editorial magazine"
  - "e-ink presentation"
  - "web presentation"
  - "pitch deck"
od:
  mode: deck
  scenario: marketing
  featured: 9
  default_for: deck
  upstream: "https://github.com/op7418/guizang-ppt-skill"
  preview:
    type: html
    entry: index.html
  design_system:
    requires: false
  example_prompt: "Help me make a magazine-style PPT — about 'Company of One', 25-minute sharing session, target audience is designers + founders. First recommend a direction (Monocle / WIRED / Kinfolk / Domus / Lab) for me to choose from."
---

# Magazine Web Ppt

## What this Skill does

Generates a **single-file HTML** horizontal swipe presentation with the following visual tone:

- **Editorial Magazine + E-Ink** hybrid style
- **WebGL fluid / contour / dispersion backgrounds** (visible on hero pages)
- **Serif headings (Noto Serif + Playfair Display) + Sans-serif body (Noto Sans + Inter) + Monospace metadata (IBM Plex Mono)**
- **Lucide linear icons** (no emojis)
- **Horizontal swipe navigation** (keyboard ← →, mouse wheel, touch swipe, bottom dots, ESC index)
- **Smooth theme interpolation**: Colors and shaders transition smoothly when swiping to hero pages

The aesthetic of this skill is not "corporate PPT" nor "consumer internet UI" — it looks like *Monocle* magazine applied with code.

## When to use

**Suitable Scenarios**:
- Offline sharing / Internal industry talks / Private sessions
- AI new product releases / demo days
- Speeches with a strong personal style
- Web-based slides that need to be "done once, without presentation software"

**Unsuitable Scenarios**:
- Large blocks of table data, stacked charts (use regular PPT software)
- Training courseware (not enough information density)
- Needs multi-person collaborative editing (this is static HTML)

## Workflow

### Step 0 · Choose Direction (Direction · Mandatory first step)

**Before asking the 6 clarification questions, have the user pick one of the 5 magazine directions**. Each direction bundles "theme color / recommended layout / chrome style / recommended slide count", answering half the clarification questions automatically.

Open `references/styles.md`, **copy the whole block** to show the user the 1-line summary of the 5 directions, and let them choose:

```
1. Monocle Editorial · International Magazine Style ✦ Default
2. WIRED Tech · Data + Engineering
3. Kinfolk Slow · Slow Living / Humanities
4. Domus Architectural · Architecture / Spatial Sense
5. Lab / Reference · Academic + Craft Manual
```

If the user says "I don't know, you recommend" — **default to Monocle Editorial**, as it has the lowest failure rate. If the user mentions "AI / benchmark / tech release" — recommend WIRED; "reading / private sharing" — Kinfolk; "design / architecture / portfolio" — Domus; "research / methodology" — Lab.

After picking a direction, create or update `Project_Record.md` in the project directory. The first line should state the direction + theme color + audience + duration (see template at the end of `styles.md`). **Do not change directions midway** — changing midway = everything before is wasted.

### Step 1 · Clarify Requirements (**Must do before starting**)

**If the user has already provided a full outline + images**, you can skip directly to Step 2.

**If the user only gives a topic or vague idea**, align these 6 questions one by one before starting. Do not start writing slides based on guesses — fixing a wrong structure later is very costly:

#### 6-Question Clarification Checklist

> Question 5 is already answered in Step 0 when choosing a direction (direction → theme color). In the 5 questions below, you can skip question 5.

| # | Question | Why ask this |
|---|----------|--------------|
| 1 | **Who is the audience? Sharing scenario?** (Internal / Commercial / Demo Day / Private) | Determines tone and depth |
| 2 | **Sharing duration?** | 15 mins ≈ 10 slides, 30 mins ≈ 20 slides, 45 mins ≈ 25-30 slides (see `styles.md` for recommendations) |
| 3 | **Any raw materials?** (Docs / Data / Old PPT / Article links) | Build on existing materials if any, otherwise help structure |
| 4 | **Any images? Where are they?** | See "Image Conventions" below |
| 5 | ~~**Which theme color do you want?**~~ | ✓ Already decided by Step 0 direction |
| 6 | **Any hard constraints?** (Must include XX data / Cannot show YY) | Avoid rework |

#### Outline Assistance (If user has no outline)

Use the "Narrative Arc" template to build the skeleton, then fill in content:

```
Hook             → 1 page   : Drop a contrast / question / hard data to grab attention
Context          → 1-2 pages: Explain background / who you are / why this matters
Core             → 3-5 pages: Core content, use Layout 4/5/6/9/10
Shift            → 1 page   : Break expectations / propose new viewpoint
Takeaway         → 1-2 pages: Golden quote / suspense question / action advice
```

Narrative arc + Page count plan + Theme rhythm chart (see `layouts.md`), **align these three tables** before entering Step 2.

Save the outline as `Project_Record.md` or `Outline-v1.md` for future iteration.

#### Image Conventions (Inform the user)

Before starting, clarify to the user:

- **Folder location**: Under `Project/XXX/ppt/images/` (same level as `index.html`)
- **Naming convention**: `{slide_number}-{semantics}.{ext}`, e.g., `01-cover.jpg` / `03-figma.jpg`
  - Zero-padding slide numbers makes sorting easier
  - Use short, specific English semantics matching content
- **Specification suggestions**:
  - Width ≥ 1600px for single images (prevents blur on large screens)
  - JPG for photos/screenshots, PNG for transparent UI/charts
  - Total size under 10MB (affects swipe performance)
- **How to replace**: **Overwriting with the same filename** is safest (no HTML edits needed); if filename changes, globally search `images/old_name` and replace with the new name.
- **What if there are no images**: Align with user, you can use placeholder color blocks to build structure first, add images later; but inform them that layouts like 4/5/10 (image-text mix) cannot be visually verified without images.

### Step 2 · Copy Template

Copy `assets/template.html` to the target location (usually `Project/XXX/ppt/index.html`), and create an `images/` folder next to it.

```bash
mkdir -p "Project/XXX/ppt/images"
cp "<SKILL_ROOT>/assets/template.html" "Project/XXX/ppt/index.html"
```

`template.html` is a **fully runnable** file — CSS, WebGL shaders, swipe JS, fonts/icons CDN are all pre-configured. The `<main id="deck">` only contains 3 sample slides (cover, chapter intro, blank).

#### 2.1 · Mandatory Placeholders (**Easy to miss**)

Immediately replace the following placeholders after copying, otherwise the browser tab will look embarrassing:

| Location | Original | Change to |
|----------|----------|-----------|
| `<title>` | `[REQUIRED] Replace with PPT Title · Deck Title` | Actual deck title (e.g., `A New Way to Work · Luke`) |

First thing after copying template.html: grep for "[REQUIRED]" to ensure all are replaced.

#### 2.2 · Select Theme Color (5 Presets · No Customization)

This skill **only allows selecting from 5 carefully curated presets**, custom hex values are not accepted — wrong color combinations ruin the visual instantly. Protecting aesthetics is more important than offering freedom.

| # | Theme | Suitable for |
|---|-------|--------------|
| 1 | 🖋 Ink Classic | Universal / Commercial / Default when unsure |
| 2 | 🌊 Indigo Porcelain | Tech / Research / Data / Tech Release |
| 3 | 🌿 Forest Ink | Nature / Sustainability / Culture / Non-fiction |
| 4 | 🍂 Kraft Paper | Nostalgia / Humanities / Literature / Indie Mag |
| 5 | 🌙 Dune | Art / Design / Creative / Gallery |

**Operation**:
1. Recommend one based on content, or ask the user.
2. Open `references/themes.md`, find the `:root` block for the chosen theme.
3. **Completely replace** the commented lines in the `:root{` block at the top of your copied `assets/template.html` (`--ink` / `--ink-rgb` / `--paper` / `--paper-rgb` / `--paper-tint` / `--ink-tint`).
4. All other CSS uses `var(--...)`, no other changes needed.

**Hard Rules**:
- One deck uses only one theme, do not change midway.
- Do not accept arbitrary hex values from the user — politely refuse and offer the 5 presets.
- Do not mix and match (e.g., ink from Ink Classic, paper from Dune) — it will clash horribly.

### Step 3 · Fill Content

#### 3.0 · Pre-flight: Class names must be defined in template.html (**Most Important**)

**This is the source of all generation issues**. The skeletons in `layouts.md` use many class names (`h-hero` / `h-xl` / `stat-card` / `pipeline` / `grid-2-7-5` etc.). If they are not defined in the `<style>` of `assets/template.html`, the browser falls back to default styles — large headings become sans-serif, data cards squash together, pipelines blur into one line, images stack at the bottom.

**Before writing any slide code:**

1. **Read `assets/template.html`** (at least down to the end of the `<style>` block).
2. **Check against the Pre-flight list in `layouts.md`**, ensuring every class you plan to use exists in the `<style>`.
3. If a class is missing: **add it to the `<style>` in template.html**, do not write inline styles on every slide.
4. **template.html is the ONLY source of truth for class names** — do not invent new class names. If you need customization, use inline `style="..."`.

Commonly missed classes (must verify existence):
`h-hero`, `h-xl`, `h-sub`, `h-md`, `lead`, `kicker`, `meta-row`, `stat-card`, `stat-label`, `stat-nb`, `stat-unit`, `stat-note`, `pipeline-section`, `pipeline-label`, `pipeline`, `step`, `step-nb`, `step-title`, `step-desc`, `grid-2-7-5`, `grid-2-6-6`, `grid-2-8-4`, `grid-3-3`, `grid-6`, `grid-3`, `grid-4`, `frame`, `frame-img`, `img-cap`, `callout`, `callout-src`, `chrome`, `foot`.

#### 3.0.5 · Plan Theme Rhythm (**Equally as important as class pre-flight**)

**Before picking layouts**, you must list the theme class for every page (`hero dark` / `hero light` / `light` / `dark`) and align it in the document or draft. See "Theme Rhythm Planning" at the top of `references/layouts.md`.

**Mandatory Rules**:

- Every section must have one of `light` / `dark` / `hero light` / `hero dark`, do not just write `hero`.
- More than 3 consecutive pages of the same theme = visual fatigue, not allowed.
- Decks over 8 pages must have ≥1 `hero dark` + ≥1 `hero light`.
- The entire deck cannot only have `light` body pages, must use `dark` pages for breathing room.
- Insert 1 hero page (cover/intro/question/big quote) every 3-4 pages.

**Post-generation self-check**: `grep 'class="slide' index.html` to list all themes, manually confirm rhythm before delivering.

#### 3.1 · Pick Layouts

**Do not write slides from scratch**. Open `references/layouts.md`, it contains 10 ready-made layout skeletons, each is a fully pasteable `<section>` code block:

| Layout | Purpose |
|---|---|
| 1. Opening Cover | Page 1 |
| 2. Chapter Intro | Start of each act |
| 3. Data Billboard | Hard numbers |
| 4. Left Text Right Image | Contrast / Story |
| 5. Image Grid | Comparison / Evidence |
| 6. Two-column Pipeline | Workflow |
| 7. Suspense / Question | Act end / Closing |
| 8. Big Quote | Serif quote / takeaway |
| 9. Before / After | Old vs New model |
| 10. Mixed Media | Dense text + image |

Pick the corresponding layout, paste it, change the text and image paths. **Must complete 3.0 Pre-flight first**.

#### 3.2 · Image Ratio Standards

Always use **standard ratios**, never use weird original ratios (like `2592/1798`):

| Scenario | Recommended Ratio |
|----------|-------------------|
| Left Text Right Image (Main) | 16:10 or 4:3 + `max-height:56vh` |
| Image Grid (Comparison) | **Fixed `height:26vh`**, no aspect-ratio |
| Left small + Right text | 1:1 or 3:2 |
| Full screen hero visual | 16:9 + `max-height:64vh` |
| Mixed media small illustration | 3:2 or 3:4 |

**Images should never use `align-self:end`** — they will slide to the bottom of the cell and be covered by browser UI. Use grid container + `align-items:start` (pre-set in template) so images stick to the top; if the left column needs to stick to bottom, use flex column + `justify-content:space-between`.

Component details (fonts, colors, grids, icons, callouts, stat-cards) are in `references/components.md`.

### Step 4 · Self-Check against Checklist

After generating, you must open `references/checklist.md` and check item by item. It summarizes **all pitfalls encountered during real-world iteration**, P0 level issues (emojis, broken images, wrapped headings, font roles) must all pass.

Key items to note:

1. **Large headings MUST be serif** — if they show as sans-serif, 99% of the time Step 3.0 Pre-flight was skipped, and the `h-hero` class is missing in template.html.
2. **Use `height:Nvh` in image grids, never `aspect-ratio`** (it will break out).
3. **Images cannot stack at the bottom** — don't use `align-self:end`, use grid + `align-items:start`.
4. **Images must use standard ratios** (16:10 / 4:3 / 3:2 / 1:1 / 16:9).
5. **No Emojis, use Lucide icons only.**
6. **Headings use serif, body uses sans-serif, metadata uses monospace.**

### Step 5 · Local Preview

Open `index.html` directly in the browser. On macOS:

```bash
open "Project/XXX/ppt/index.html"
```

No local server required. Images use relative paths `images/xxx.png`.

### Step 6 · Iterate

Modify based on user feedback — the CSS in the template is highly parameterized, 90% of adjustments are inline styles (`font-size:Xvw` / `height:Yvh` / `gap:Zvh`).

---

## Resource File Guide

```
magazine-web-ppt/
├── SKILL.md              ← You are reading this
├── assets/
│   ├── template.html     ← Full runnable template (seed file)
│   └── example-slides.html ← 9-page sample deck (for previews)
└── references/
    ├── styles.md         ← 5 magazine directions (Monocle/WIRED/Kinfolk/Domus/Lab)
    ├── components.md     ← Component manual (fonts, colors, grids, icons, callout, stat, pipeline...)
    ├── layouts.md        ← 10 layout skeletons (pasteable)
    ├── themes.md         ← 5 theme presets (no customization allowed)
    └── checklist.md      ← Quality checklist (P0/P1/P2/P3 levels)
```

**Loading Order Suggestion**:
1. Finish reading `SKILL.md` (this file) for an overview.
2. **When choosing direction in Step 0, read `styles.md`** — it has theme colors + recommended layouts ready.
3. After clarifying requirements in Step 1, read `themes.md` if color details are needed.
4. **Before starting, read `<style>` in `assets/template.html`** — this is the sole source of class names. Missing classes break layouts.
5. Read `layouts.md` to pick layouts (check Pre-flight and Rhythm at the top).
6. Read `components.md` for specific component details during adjustments.
7. After generating, read `checklist.md` for self-checking.

## Core Design Principles (Philosophy)

> These principles were refined over 5 iterations of the "Company of One" presentation. Violating any of them ruins the visual feel.

1. **Restraint over flashiness** — WebGL backgrounds only show on hero pages, almost invisible on regular pages.
2. **Structure over decoration** — No shadows, no floating cards, no padding boxes. All information relies on **large font sizes + font contrast + grid whitespace**.
3. **Content hierarchy defined by size and font** — Largest serif = Main title, Medium serif = Subtitle, Large sans = Lead, Small sans = Body, Monospace = Metadata.
4. **Images are first-class citizens** — Only crop the bottom of images, keep top and sides intact; use `height:Nvh` for grids, not `aspect-ratio`.
5. **Rhythm relies on hero pages** — Alternating hero and non-hero prevents eye fatigue.
6. **Consistent terminology** — Keep wording precise and professional.

## Reference Works

The visual tone of this skill was inspired by:
- "Company of One: Organizations folded by AI" talk (2026-04-22, 27 pages)
- Typography of *Monocle* magazine
- Demo from YC's Garry Tan's blog "Thin Harness, Fat Skills"

Use them as style anchors.
