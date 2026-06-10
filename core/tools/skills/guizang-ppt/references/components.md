# Component Reference · Components

This is the component manual for the `magazine-web-ppt` skill. `template.html` has already defined all the styles, here we only describe "what this component looks like and how to use it".

## Table of Contents

- [Basic Slide Wrapper](#basic-slide-wrapper)
- [Fonts Typography](#fonts-typography)
- [Chrome & Foot](#chrome--foot)
- [Callout Quote Box](#callout-quote-box)
- [Stat Number Matrix](#stat-number-matrix)
- [Platform Card](#platform-card)
- [Rowline Table Row](#rowline-table-row)
- [Pillar Card](#pillar-card)
- [Tag & Kicker](#tag--kicker)
- [Figure Image Box](#figure-image-box)
- [Icons](#icons)
- [Ghost Giant Background Text](#ghost-giant-background-text)
- [Highlight Marker](#highlight-marker)

---

## Basic Slide Wrapper

Every page is a `<section class="slide ...">`. It must contain the `data-theme` attribute (`light` or `dark`), and JS will switch the background based on this attribute when turning pages.

```html
<section class="slide light" data-theme="light">   <!-- Light page -->
<section class="slide dark" data-theme="dark">     <!-- Dark page -->
<section class="slide light hero" data-theme="light">  <!-- Hero page: Light + thin mask to reveal WebGL -->
<section class="slide dark hero" data-theme="dark">    <!-- Hero page: Dark + thin mask -->
```

**Usage of light vs dark: Alternate usage**, switch themes every 2-3 pages, avoid more than 3 consecutive pages of the same color. When turning pages, the WebGL background will automatically smoothly transition between the two shaders.

**Usage of the hero class**: Only add it to visually dominant pages (covers, quote pages, chapter transitions, endings). After adding `hero`, the mask opacity drops to 12-16%, and the WebGL background will be largely revealed, so don't put too much text on hero pages.

---

## Fonts Typography

Font division of labor is the most important rule of this template; mixing them is strictly prohibited.

| Class | Usage | Font |
|---|---|---|
| `.display` | Extra-large English (Hero page) | Playfair Display 700, 11vw |
| `.display-zh` | Extra-large Chinese title | Noto Serif SC 700, 7.8vw |
| `.h1-zh` | Main page title | Noto Serif SC 700, 4.6vw |
| `.h2-zh` | Subtitle | Noto Serif SC 600, 3.2vw |
| `.h3-zh` | Pipeline step title | Noto Serif SC 500, 1.9vw |
| `.lead` | Lead paragraph (larger than body) | Noto Serif SC 400, 1.9vw |
| `.body-zh` | **Body/Description (Sans-serif)** | Noto Sans SC 400, 1.22vw |
| `.body-serif` | Body (Serif) | Noto Serif SC 400, 1.3vw |
| `.kicker` | Section prompt (above title) | IBM Plex Mono, 12px uppercase |
| `.meta` | Meta info tag | IBM Plex Mono, 0.88vw uppercase |
| `.big-num` | Giant numbers | Playfair Display 800, 10vw |
| `.mid-num` | Medium numbers | Playfair Display 700, 5.5vw |

**Core rules**:
- **Serif** (`serif-zh` / `serif-en`): Titles, key quotes, numbers — used for "visual accent"
- **Sans-serif** (`sans-zh`): Body descriptions, large blocks of reading content — used for "information density"
- **Monospace** (`mono`): English tags for kicker, meta, foot — used for "decorative rhythm"

**Emphasis techniques**:
- `<em class="en">English Word</em>` — Renders the English word in Playfair Display italic (looks very nice)
- `<em style="opacity:.65">Phrase</em>` — Fades out the latter half of the title to create rhythm

---

## Chrome & Foot

The meta info bars at the top and bottom of each page. Almost every page should have them.

```html
<div class="chrome">
  <div class="left">
    <span>Act I · Hard Data</span>
    <span class="sep"></span>
    <span>Act I</span>
  </div>
  <div class="right"><span>02 / 27</span></div>
</div>

<!-- ... Page Body ... -->

<div class="foot">
  <div class="title">Project · CodePilot　|　github.com/codepilot</div>
  <div>Act I · Dev Numbers</div>
</div>
```

**Rules**:
- `chrome.right` always holds the page number `NN / TOTAL` (TOTAL is the total number of pages)
- `foot.title` is a Chinese description, `foot.right` is an English act marker
- chrome and foot together form the "header and footer" with a magazine feel

---

## Callout Quote Box

Display key quotes / key viewpoints / quotes from others.

```html
<div class="callout" style="max-width:80vw">
  <div class="q-big">"This thing three years ago,<br>would require a team of ten for a year."</div>
  <span class="cite">— A judgment from an observer</span>
</div>
```

Variants:
- Without cite: Just remove `<span class="cite">`
- With an English quote: `<em class="en">"Thin Harness, Fat Skills."</em>`
- Used on a hero page: Add `style="position:relative;z-index:2"` to the outer layer (to avoid being covered by the background mask)

---

## Stat Number Matrix

Display data metrics, often paired with `.grid-6` / `.grid-4`.

```html
<div class="grid-6">
  <div class="stat">
    <span class="m">Duration</span>
    <span class="n">64<em style="font-size:.4em;opacity:.5;font-style:normal"> Days</em></span>
    <span class="l">From 0 to now</span>
  </div>
  <!-- ... More stats ... -->
</div>
```

Three-part structure: `.m` small monospace tag → `.n` giant number → `.l` description. The unit after the number uses `<em>` to scale down to 0.4em, opacity 0.5.

**Common layout containers**:
- `.grid-6` — 3×2 grid (most common, 6 stats)
- `.grid-4` — 2×2 grid (4 stats)
- `.grid-3` — 3 equal columns in a single row (3 stats / pillars)

---

## Platform Card

Display social platforms / channels + follower count.

```html
<div class="plat">
  <div class="sub">Weibo</div>
  <div class="name">Weibo</div>
  <div class="nb">289K</div>
</div>
```

Optional fourth line (supplementary info):
```html
<div class="body-zh" style="font-size:max(11px,.8vw);opacity:.5;margin-top:.6vh">
  Includes Little Green Book sync
</div>
```

**"Also On" variant** (supplementary platforms):
```html
<div class="plat" style="border-top-style:dashed;opacity:.72">
  <div class="sub">Also On</div>
  <div class="body-zh" style="font-weight:600;margin-top:.8vh">
    Bilibili　·　Zhihu
  </div>
</div>
```

---

## Rowline Table Row

List-style content, one item per row.

```html
<div class="rowline">
  <div class="k">KENBUN.md</div>
  <div class="v">How you should work — Behavioral rules + Work preferences + Prohibited matters</div>
  <div class="m">EMPLOYEE · HANDBOOK</div>
</div>
```

Three-column structure: `.k` serif keyword · `.v` body description · `.m` monospace tag (right-aligned). The first and last rowlines automatically get top and bottom borders.

**Variant: 2 columns**: `style="grid-template-columns:1fr 3fr"` to remove the `.m` column.

---

## Pillar Card

Three-pillar structure, often used for "parallel concept" type pages.

```html
<div class="grid-3">
  <div class="pillar">
    <div class="ic">01</div>
    <div class="t">Three-layer<br>Doc System</div>
    <div class="d">KENBUN.md<br>+ Project KB<br>+ Guardrail file</div>
  </div>
  <!-- ... More pillars ... -->
</div>
```

**Pillar with icon (used for emphasis pages)**:
```html
<div class="pillar" style="padding:4vh 2vw;border:1px solid currentColor;border-color:rgba(10,10,11,.2)">
  <div class="ic"><i data-lucide="compass" class="ico-lg"></i></div>
  <div class="t">Judgment</div>
  <div class="d">Authority in decisions and direction.<br>Trade-offs, taste, sense of direction.</div>
</div>
```

`.ic` can be a number (`01 / 02 / 03` or `A. / B. / C.`), or a Lucide icon.

---

## Tag & Kicker

**Kicker** is the small prompt text above the title (monospace, all caps, small font):
```html
<div class="kicker">Past 64 Days · Dev Chapter</div>
<div class="h1-zh">One person, what was done.</div>
```

**Tag** is an independent tag capsule (with border):
```html
<div style="display:flex;gap:1.6vw;flex-wrap:wrap">
  <div class="tag">Wake up at 10 AM</div>
  <div class="tag">Gym on Tue / Thu afternoon</div>
  <div class="tag">Still watch shows · Play games at night</div>
</div>
```

---

## Figure Image Box

**This is the component in this template most prone to pitfalls; strictly follow these rules**.

### Basic Structure

```html
<figure class="tile">
  <div class="frame-img" style="height:26vh">
    <img src="images/xxx.png" alt="Description">
  </div>
  <figcaption class="frame-cap">
    <span class="pf">Twitter</span>
    <span class="nb">137K</span>
  </figcaption>
</figure>
```

### Key Constraints (Lessons learned in blood, do not violate)

1. **Must use `height:Nvh` to fix the height**, do not use `aspect-ratio`.
   - Reason: Using aspect-ratio in a grid will burst the parent container, causing images to stack up.
   - Recommended sizes: `height:18vh` (compact bar) / `22vh` (standard grid) / `26vh` (prominent display) / `28vh` (large image).

2. **`object-position:top center` (already set in CSS)**, only the bottom is allowed to be cropped.
   - Strictly no cropping of the left, right, and top — this is the core identity information area of the image.

3. **When there are multiple images in a grid, use inline grid instead of `grid-3`**:
   ```html
   <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1vh 1.2vw">
     <figure class="tile">...</figure>
     <figure class="tile">...</figure>
     <figure class="tile">...</figure>
   </div>
   ```

4. **Aligning images with other parts of the layout**: Add `align-self:end` to the figure individually to make the image stick to the bottom.

### Frame Caption Variants

```html
<!-- Standard: Left figure name, right number -->
<figcaption class="frame-cap">
  <span class="pf">Twitter</span>
  <span class="nb">137K</span>
</figcaption>

<!-- With numbering -->
<figcaption class="frame-cap">
  <span class="idx">01</span>
  <span class="pf">AI Polish</span>
  <span>Polish</span>
</figcaption>
```

### Image Placeholder (Placeholders during the design phase)

When the image is not yet in place, use a dashed box as a placeholder:
```html
<div class="img-slot r-4x3">  <!-- r-4x3 / r-16x9(default) / r-3x2 / r-1x1 -->
  <span class="plus">+</span>
  <span class="label">GitHub Screenshot Position</span>
</div>
```

---

## Icons

**Using emojis is strictly prohibited**. Use Lucide via CDN (already included in template.html).

```html
<i data-lucide="compass" class="ico-lg"></i>     <!-- Large icon (for pillars) -->
<i data-lucide="target" class="ico-md"></i>      <!-- Medium icon (for list items) -->
<i data-lucide="check-circle" class="ico-sm"></i>  <!-- Small icon (for inline) -->
```

**Common Lucide Icon Names** (grouped by meaning):

- Judgment: `compass`, `target`, `crosshair`, `search-check`
- Relationship: `share-2`, `users`, `network`, `link`, `handshake`
- Brand: `crown`, `gem`, `award`, `star`, `badge-check`
- Process: `workflow`, `route`, `arrow-right-left`, `repeat`
- Data: `grid-2x2`, `bar-chart-3`, `trending-up`, `activity`
- Aesthetic: `palette`, `brush`, `eye`, `sparkles`
- Correct/Incorrect: `check-circle`, `x-circle`, `check`, `x`
- Direction: `arrow-right`, `arrow-up-right`, `corner-down-right`

**Inline combination of icon and text**:
```html
<div class="h3-zh" style="display:flex;align-items:center;gap:.8em">
  <i data-lucide="target" class="ico-md"></i>
  Judgment — What is worth writing
</div>
```

---

## Ghost Giant Background Text

Used as "decorative background text", extremely low opacity, creating a magazine feel.

```html
<div class="ghost" style="right:-6vw;top:-8vh">BUT</div>
<div class="ghost" style="left:-8vw;bottom:-18vh;font-style:italic">Harness</div>
```

- Font size 34vw, opacity 0.06
- Common positioning: `right:-6vw;top:-8vh` (overflowing top right) / `left:-8vw;bottom:-18vh` (overflowing bottom left)
- Content: English words or numbers (Chapter numbers 01/02/03, keywords BUT/NOW/HERE)

**Note**: In pages using ghost, other content must have `position:relative;z-index:2` to avoid being pressed underneath.

---

## Highlight Marker

"Highlighter" effect for inline phrases:

```html
<span class="hi">Not</span>
<span class="hi">a one-time burst</span>
```

Generates a semi-transparent highlight bar at the bottom of the text. Dark themes use bright bars, light themes use dark bars (handled in CSS).

**Suitable scenario**: Only use for 1-3 key words, do not use it over large areas.
