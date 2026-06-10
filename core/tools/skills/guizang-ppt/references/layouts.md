# Page Layout Library (Layouts)

This document contains 10 of the most commonly used page layout skeletons. Each is a complete, paste-able `<section class="slide ...">...</section>` code block; just replace the copy/images to use it.

---

## ⚠️ Must-read Before Generation (Pre-flight)

### A. Class names must come from template.html

All classes used in `layouts.md` (`h-hero` / `h-xl` / `h-sub` / `h-md` / `lead` / `meta-row` / `stat-card` / `stat-label` / `stat-nb` / `stat-unit` / `stat-note` / `pipeline-section` / `pipeline-label` / `pipeline` / `step` / `step-nb` / `step-title` / `step-desc` / `grid-2-7-5` / `grid-2-6-6` / `grid-2-8-4` / `grid-3-3` / `grid-6` / `grid-3` / `grid-4` / `frame` / `frame-img` / `img-cap` / `callout` / `callout-src` / `kicker`) are predefined in the `<style>` block of `assets/template.html`.

**Do not invent new class names**. If customization is necessary, write it inline with `style="..."`. If unsure whether a class exists before generation, grep `template.html` to confirm.

### B. Image Proportion Guidelines (Very Important)

**Always use standard proportions**, do not use bizarre proportions like the original image's `aspect-ratio: 2592/1798`:

| Scenario | Recommended Proportion | Syntax |
|------|---------|------|
| Left text right image main image | 16:10 or 4:3 | `aspect-ratio:16/10; max-height:54vh` |
| Image grid (multi-image comparison) | Unified | **Fixed `height:26vh`, do not use aspect-ratio** |
| Small left image + right text | 1:1 or 3:2 | `aspect-ratio:1/1; max-width:40vw` |
| Full-screen main visual | 16:9 | `aspect-ratio:16/9; max-height:64vh` |
| Image-text wrap small illustration | 3:2 | `aspect-ratio:3/2; max-width:30vw` |

Images must be wrapped in `<figure class="frame-img">`, and the `<img>` inside will automatically have `object-fit:cover + object-position:top center`, only cropping the bottom, not the top/left/right.

### C. Image Positioning Guidelines (Avoid images piling up at the bottom, being obscured by browser toolbars)

**Wrong practices** (already hit pitfalls, do not repeat):
- Using `align-self:end` in a non-grid container: `align-self` is completely invalid outside of flex/grid, and the image will drop to the end of the document flow and pile up at the bottom.
- Using `position:absolute + bottom:0` to "fix" the image to the bottom: it will be covered by `.foot` and `#nav` dots at the bottom.
- Only writing `height:N vh` without `max-height` for a single image: it will burst out of the viewport on low-res screens.

**Correct practices**:
- Image-text combinations **must use the `.frame.grid-2-7-5`** (or `.grid-2-6-6` / `.grid-2-8-4`) grid structure.
- Grid containers default to `align-items:start` (already set in the template), so images naturally stick to the top of the cell.
- If you need to "bottom-align the image with the left column callout": **Use flex column + `justify-content:space-between` on the left column** (let the callout stick to the bottom of the left column on its own), **and let the right column figure just keep `align-items:start`**, do not add `align-self:end`.
- All grid parent containers are recommended to add inline `style="padding-top:6vh"` to leave breathing room for the title area.

### D. Theme Colors and Theme Rhythm

- Choose one theme color from the 5 presets in `references/themes.md`, custom hex values are not allowed.
- The theme rhythm (which of light / dark / hero light / hero dark to use for each page) has hard rules in the "Theme Rhythm Planning" section below, must read before generation.
- Both of these must be decided before picking layouts to avoid rework.

---

## 0. Basic Structure (All slides are the same)

```html
<section class="slide [light|dark|hero light|hero dark]">
  <div class="chrome">
    <div>Context Tag · Subtag</div>
    <div>ACT · Page Number / Total Pages</div>
  </div>
  <!-- Main content -->
  <div class="foot">
    <div>Page Description · Page Description</div>
    <div>— · —</div>
  </div>
</section>
```

- It is recommended to add `light` or `dark` theme to non-hero pages; add `hero light` or `hero dark` to hero pages (participates in WebGL theme interpolation)
- `chrome` and `foot` are optional but recommended metadata in the four corners
- **Hero pages are used for chapter covers/openings/closings/transitions**, non-hero pages are for the main body

### ⚠️ chrome and kicker should not write the same sentence

This is the most common content repetition problem. The two are in completely different semantic dimensions:

| Position | Role | Nature of Content | Example |
|------|------|---------|------|
| `.chrome` Top Left | **Magazine header / Navigation metadata** | Stable "column name" or "chapter category", can be the same across multiple pages | "Act II · Workflow" / "Data · Result" / "lukew.com · 2026.04" |
| `.chrome` Top Right | **Page number + Act number** | Fixed format | "Act II · 15 / 25" |
| `.kicker` | **Unique guiding sentence for this page** | A "small prefix" for the big title, like a line of text above a magazine headline, should be different for every page | "BUT" / "One person, what was done." / "Phase 01 · Design Phase" |

**Bad example** (already hit pitfall): chrome writes "Design First", kicker also writes "Phase 01 · Design Phase" — repetitive meaning, readers immediately feel it's AI-generated.

**Correct practice**: chrome is a **column tag** (stable, reusable across pages), kicker is the **hook of this page** (short sentence, dramatic), the two complement each other and do not translate each other.

### ⚠️ Theme Rhythm Planning (Must-read · Must do before generation)

**Core mechanism**: Each `<section>` page must carry one of `light` / `dark` / `hero light` / `hero dark`. JS infers the theme based on the class to decide whether to add `light-bg` to the body, thereby switching which of the dark/light WebGL canvases is in front. No theme or custom name = fallback error.

#### Default themes by layout

| Layout | Default Theme | Reason |
|---|---|---|
| 1. Opening Cover | `hero dark` | Opening ritual sense, dark background strong impact |
| 2. Chapter Cover | `hero dark` and `hero light` **must alternate** | Breathing rhythm |
| 3. Big Numbers (Data) | `light` | Numbers need paper white background; occasionally insert `dark` for continuous acts |
| 4. Left Text Right Image | **`light` / `dark` alternate** | Mainstay of body rhythm |
| 5. Image Grid | `light` | Screenshots need a bright background |
| 6. Pipeline | `light` | Flowcharts need clarity |
| 7. Question Page | `hero dark` | Default for strong visual impact |
| 8. Big Quote | **`dark` preferred**, occasionally `light` | Ritual sense of quotes relies on dark backgrounds |
| 9. Comparison Page | `light` | Dual columns need clarity |
| 10. Image-Text Wrap | **`light` / `dark` alternate** | Rhythm |

#### Hard rules for rhythm (grep self-check after generation)

- ❌ **Prohibited** from having more than 3 consecutive pages with the same theme (including light stacking and dark stacking)
- ❌ **Prohibited** from having a deck > 8 pages without at least 1 `hero dark` + 1 `hero light`
- ❌ **Prohibited** for the entire deck to only have `light` body pages without any `dark` body pages — it will seem flat and breathless
- ✅ **Recommended** to insert 1 hero (cover/chapter cover/question/big quote) every 3-4 pages

#### 8-page rhythm template (can be applied directly)

| Page | Theme | Layout | Note |
|---|---|---|---|
| 1 | `hero dark` | Cover | Opening |
| 2 | `light` | Big Numbers | Throwing data |
| 3 | `dark` | Left Text Right Image | Comparison/Story |
| 4 | `light` | Pipeline | Flow |
| 5 | `hero light` | Chapter Cover | Breathing |
| 6 | `dark` | Left Text Right Image or Big Quote | |
| 7 | `hero dark` | Question Page | Suspense closing |
| 8 | `light` | Big Quote / Ending | Wrap up |

**Draw this table first to align, then start writing slides**. Skipping planning and pasting skeletons directly = all light.

---

## Layout 1: Opening Cover (Hero Cover)

```html
<section class="slide hero dark">
  <div class="chrome">
    <div>A Talk · 2026.04.22</div>
    <div>Vol.01</div>
  </div>
  <div class="frame" style="display:grid; gap:4vh; align-content:center; min-height:80vh">
    <div class="kicker">Private Session · Li Jigang</div>
    <h1 class="h-hero">One-Person Company</h1>
    <h2 class="h-sub">Organizations Folded by AI</h2>
    <p class="lead" style="max-width:60vw">
      An AI creator — made 110,000 lines of code in 64 days, continuously published on 9 platforms, and the rhythm of life was hardly changed.
    </p>
    <div class="meta-row">
      <span>歸藏 Guizang</span><span>·</span><span>Independent Creator / CodePilot Author</span>
    </div>
  </div>
  <div class="foot">
    <div>A sharing about AI · Organizations · Individuals</div>
    <div>— 2026 —</div>
  </div>
</section>
```

**Key points**:
- Use `hero dark` to let the WebGL background show through in most areas
- `h-hero` is the largest font size (10vw), used here as the main visual for the title
- Use `min-height:80vh + align-content:center` to center the content vertically as a whole
- No need to write page numbers in `.chrome`, the cover page stands alone

---

## Layout 2: Chapter Cover (Act Divider)

```html
<section class="slide hero light">
  <div class="chrome">
    <div>Act I · Hard Data</div>
    <div>Act I · 01 / 25</div>
  </div>
  <div class="frame" style="display:grid; gap:6vh; align-content:center; min-height:80vh">
    <div class="kicker">Act I</div>
    <h1 class="h-hero" style="font-size:8.5vw">Hard Data</h1>
    <p class="lead" style="max-width:55vw">
      Look at the numbers first, then talk about methods.
    </p>
  </div>
  <div class="foot">
    <div>Act I Intro</div>
    <div>— · —</div>
  </div>
</section>
```

**Key points**:
- Minimalist, only requires kicker + big title + one line of intro
- The covers of the two acts can alternate `hero light` / `hero dark` to create rhythm
- The `h-hero` font size can be adjusted from 10vw to 8.5vw to adapt to length

---

## Layout 3: Data Poster (Big Numbers Grid)

```html
<section class="slide light">
  <div class="chrome">
    <div>Past 64 Days · Dev Chapter</div>
    <div>Act I / Dev · 02 / 25</div>
  </div>
  <div class="frame" style="padding-top:6vh">
    <div class="kicker">One person, what was done.</div>
    <h2 class="h-xl">Past 64 Days</h2>
    <p class="lead" style="margin-bottom:5vh">From 0 to open-source CodePilot.</p>

    <div class="grid-6" style="margin-top:6vh">
      <div class="stat-card">
        <div class="stat-label">Duration</div>
        <div class="stat-nb">64 <span class="stat-unit">Days</span></div>
        <div class="stat-note">From 0 to now</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Lines of Code</div>
        <div class="stat-nb">110K+</div>
        <div class="stat-note">Written line by line to 110K+</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">GitHub Stars</div>
        <div class="stat-nb">5,166</div>
        <div class="stat-note">One open-source repo</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Downloads</div>
        <div class="stat-nb">41K+</div>
        <div class="stat-note">Installed on tens of thousands of computers</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">AI Providers</div>
        <div class="stat-nb">19</div>
        <div class="stat-note">Cross-platform integration</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Commits</div>
        <div class="stat-nb">608+</div>
        <div class="stat-note">No collaborators</div>
      </div>
    </div>
  </div>
  <div class="foot">
    <div>Project · CodePilot　|　github.com/codepilot</div>
    <div>Act I · Dev Numbers</div>
  </div>
</section>
```

**Key points**:
- 3×2 or 4×2 grid is the most stable (see `.grid-6`)
- Fixed structure for each `stat-card`: label (small English text) → nb (big number) → note (annotation)
- Numbers should be 2-3 characters (too long will overflow), use K / M abbreviations
- Leave a top buffer of > 5vh so the title area grabs the eye first

---

## Layout 4: Left Text Right Image (Quote + Image)

```html
<section class="slide light">
  <div class="chrome">
    <div>Identity Contrast · The Twist</div>
    <div>03 / 25</div>
  </div>
  <div class="frame grid-2-7-5" style="padding-top:6vh">
    <!-- Left column: title + body + callout, flex column makes callout stick to the bottom -->
    <div style="display:flex; flex-direction:column; justify-content:space-between; gap:3vh">
      <div>
        <div class="kicker">BUT</div>
        <h2 class="h-xl" style="white-space:nowrap; font-size:7.2vw">
          I'm not a programmer.
        </h2>
        <p class="lead" style="margin-top:3vh">
          Haven't written a single line of code since college graduation. The past ten years have been UI design and AI effects.
        </p>
      </div>
      <div class="callout">
        "This thing three years ago,<br>
        would require a team of ten for a year."
        <div class="callout-src">— A judgment from an observer</div>
      </div>
    </div>
    <!-- Right column: Image uses standard 16/10 proportion + max-height, do not use align-self:end -->
    <figure class="frame-img" style="aspect-ratio:16/10; max-height:56vh">
      <img src="images/codepilot.png" alt="CodePilot Product Screenshot">
      <figcaption class="img-cap">CodePilot · Product Screenshot</figcaption>
    </figure>
  </div>
  <div class="foot">
    <div>Page 03 · I am not a programmer</div>
    <div>— · —</div>
  </div>
</section>
```

**Key points**:
- Use `grid-2-7-5` (left 7 parts, right 5 parts), `align-items:start` is preset in the template
- **Left column** uses flex column + `justify-content:space-between`: title sticks to the top, callout naturally sticks to the bottom
- **Right column image** **DO NOT add `align-self:end`**. It will make the image slide to the bottom of the cell and be obscured by the browser toolbar on low-res screens.
- Images must use **standard proportion 16/10 or 4/3 + `max-height:56vh`**, do not use bizarre proportions from the original image (like `2592/1798`)

---

## Layout 5: Image Grid (Multi-image comparison)

```html
<section class="slide light">
  <div class="chrome">
    <div>Platform Fan Evidence</div>
    <div>Act I / Ops · 05 / 27</div>
  </div>
  <div class="frame" style="padding-top:5vh">
    <div class="kicker">Proof · Fan Evidence</div>
    <h2 class="h-xl">10 Platforms · 6 Screenshots</h2>
 
    <div class="grid-3-3" style="margin-top:4vh">
      <figure class="frame-img" style="height:26vh">
        <img src="images/weibo.png" alt="Weibo 289K">
        <figcaption class="img-cap">Weibo · 289K</figcaption>
      </figure>
      <figure class="frame-img" style="height:26vh">
        <img src="images/twitter.png" alt="Twitter 137K">
        <figcaption class="img-cap">Twitter · 137K</figcaption>
      </figure>
      <figure class="frame-img" style="height:26vh">
        <img src="images/wechat.png" alt="WeChat 96K">
        <figcaption class="img-cap">WeChat · 96K</figcaption>
      </figure>
      <figure class="frame-img" style="height:26vh">
        <img src="images/jike.png" alt="Jike 26K">
        <figcaption class="img-cap">Jike · 26K</figcaption>
      </figure>
      <figure class="frame-img" style="height:26vh">
        <img src="images/xhs.png" alt="Xiaohongshu 19K">
        <figcaption class="img-cap">Xiaohongshu · 19K</figcaption>
      </figure>
      <figure class="frame-img" style="height:26vh">
        <img src="images/douyin.png" alt="Douyin 10K">
        <figcaption class="img-cap">Douyin · 10K</figcaption>
      </figure>
    </div>
  </div>
  <div class="foot">
    <div>Screenshot time · 2026.04</div>
    <div>Page 05 · Fan Evidence</div>
  </div>
</section>
```

**Key points**:
- Crucial: each `frame-img` must have a hardcoded `height:NNvh` (do not use `aspect-ratio`), otherwise the grid will burst
- Images will automatically `object-fit:cover + object-position:top`, only cropping the bottom
- Carried by `.grid-3-3` (3×2) or `.grid-3` (3×1)

---

## Layout 6: Two-column Pipeline

```html
<section class="slide light">
  <div class="chrome">
    <div>My Workflow · Workflow</div>
    <div>Act II · 15 / 27</div>
  </div>
  <div class="frame">
    <div class="kicker">Pipeline</div>
    <h2 class="h-xl">Two Pipelines</h2>
 
    <!-- First group: Text side -->
    <div class="pipeline-section">
      <div class="pipeline-label">Text Side · Text Pipeline</div>
      <div class="pipeline">
        <div class="step">
          <div class="step-nb">01</div>
          <div class="step-title">Draft</div>
          <div class="step-desc">AI helps me draft</div>
        </div>
        <div class="step">
          <div class="step-nb">02</div>
          <div class="step-title">Polish</div>
          <div class="step-desc">AI polishes to remove AI flavor</div>
        </div>
        <div class="step">
          <div class="step-nb">03</div>
          <div class="step-title">Morph</div>
          <div class="step-desc">AI morphs for Twitter / XHS</div>
        </div>
        <div class="step">
          <div class="step-nb">04</div>
          <div class="step-title">Illustrate</div>
          <div class="step-desc">AI generates infographics</div>
        </div>
        <div class="step">
          <div class="step-nb">05</div>
          <div class="step-title">Distribute</div>
          <div class="step-desc">One-click distribute to 9 platforms</div>
        </div>
      </div>
    </div>
 
    <!-- Second group: Video side -->
    <div class="pipeline-section">
      <div class="pipeline-label">Visual · Video Side · Video Pipeline</div>
      <div class="pipeline">
        <div class="step">
          <div class="step-nb">06</div>
          <div class="step-title">Cut</div>
          <div class="step-desc">AI helps me edit</div>
        </div>
        <div class="step">
          <div class="step-nb">07</div>
          <div class="step-title">Wrap</div>
          <div class="step-desc">AI helps me package</div>
        </div>
        <div class="step">
          <div class="step-nb">08</div>
          <div class="step-title">Cover</div>
          <div class="step-desc">AI generates cover</div>
        </div>
      </div>
    </div>
  </div>
  <div class="foot">
    <div>Page 15 · My Content Factory</div>
    <div>Workflow</div>
  </div>
</section>
```

**Key points**:
- Use `.pipeline-section` to group + `.pipeline-label` as the group title
- 3.6vh spacing between the two groups + a thin top separator line (preset in CSS)
- Each step is a fixed nb → title → desc structure
- Number of steps is unlimited, but preferably ≤5 per row, otherwise wrap to the second pipeline

---

## Layout 7: Suspense Closing / Question Page (Hero Question)

```html
<section class="slide hero dark">
  <div class="chrome">
    <div>Question Left for You</div>
    <div>24 / 27</div>
  </div>
  <div class="frame" style="display:grid; gap:8vh; align-content:center; min-height:80vh">
    <div class="kicker">The Question</div>
    <h1 class="h-hero" style="font-size:7vw; line-height:1.15">
      In your company,<br>
      which roles shouldn't<br>
      be done by humans?
    </h1>
    <p class="lead" style="max-width:50vw">
      This is not a technical question, it's an architectural question.
    </p>
  </div>
  <div class="foot">
    <div>Page 24 · The Question</div>
    <div>— · —</div>
  </div>
</section>
```

**Key points**:
- The more white space on a Hero page, the better; only ask one question
- Adjust `h-hero` font size based on length (7vw for 3 lines, 10vw for 1 line)
- Manually break lines with `<br>`, ensuring the break point is at a semantic boundary
- A line of `lead` can be added at the end for emphasis

---

## Layout 8: Big Quote Page (Big Quote · Serif Gold Sentence)

```html
<section class="slide light">
  <div class="chrome">
    <div>The Takeaway · Core Quote</div>
    <div>18 / 25</div>
  </div>
  <div class="frame" style="display:grid; gap:5vh; align-content:center; min-height:80vh">
    <div class="kicker">Quote</div>
    <blockquote style="font-family:var(--serif-zh); font-weight:700; font-size:5.8vw; line-height:1.2; letter-spacing:-.01em; max-width:72vw">
      "Without the handoff,<br>everyone builds."
    </blockquote>
    <p class="lead" style="max-width:55vw; opacity:.65">
      Without the handoff, everyone builds.<br>
      And that makes all the difference.
    </p>
    <div class="meta-row">
      <span>— Luke Wroblewski</span><span>·</span><span>2026.04.16</span>
    </div>
  </div>
  <div class="foot">
    <div>Page 18 · Quote</div>
    <div>— · —</div>
  </div>
</section>
```

**Key points**:
- Leave the whole page blank, only put one large quote + source
- Scale `<blockquote>` independently with inline styles (5-6vw), do not use `h-hero` (that is for main page titles)
- Follow with the original English text (lead · opacity:.65) to create hierarchy
- Pair with `meta-row` to write source · date

---

## Layout 9: Side-by-side Comparison (A vs B · Old vs New)

```html
<section class="slide light">
  <div class="chrome">
    <div>Old vs New · The Shift</div>
    <div>12 / 25</div>
  </div>
  <div class="frame" style="padding-top:5vh">
    <div class="kicker">Before / After · Paradigm Shift</div>
    <h2 class="h-xl" style="margin-bottom:4vh">From Handoff to Co-creation</h2>
 
    <div class="grid-2-6-6" style="gap:5vw 4vh">
      <!-- Left column: Old -->
      <div style="padding:3vh 2vw; border-left:3px solid currentColor; opacity:.55">
        <div class="kicker" style="opacity:.9">Before · Old Model</div>
        <h3 class="h-md" style="margin-top:2vh">Design → Dev → Handoff</h3>
        <ul style="margin-top:3vh; padding-left:1.2em; display:flex; flex-direction:column; gap:1.4vh; font-family:var(--sans-zh); font-size:max(14px,1.1vw); line-height:1.55">
          <li>Designers make drafts in Figma</li>
          <li>Developers look at files and translate pixels</li>
          <li>Repeated PR communication to align</li>
          <li>Non-technical staff cannot touch code</li>
        </ul>
      </div>
      <!-- Right column: New -->
      <div style="padding:3vh 2vw; border-left:3px solid currentColor">
        <div class="kicker" style="opacity:.9">After · New Model</div>
        <h3 class="h-md" style="margin-top:2vh">Same Tool · Parallel · Co-creation</h3>
        <ul style="margin-top:3vh; padding-left:1.2em; display:flex; flex-direction:column; gap:1.4vh; font-family:var(--sans-zh); font-size:max(14px,1.1vw); line-height:1.55">
          <li>Three roles work on Intent at the same time</li>
          <li>agents.md as shared context</li>
          <li>Agents handle alignment / conflicts / animations</li>
          <li>Anyone can safely contribute code</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="foot">
    <div>Page 12 · Paradigm Shift</div>
    <div>Before / After</div>
  </div>
</section>
```

**Key points**:
- Use `.grid-2-6-6` (1:1) split in half
- Left column `opacity:.55` for visual weakening of "Old", right column full brightness for highlighting "New"
- Both columns use `border-left:3px solid` + `padding-left` to create a quote block feel
- Structure of each column is unified: `kicker` → `h-md` → `<ul>` points, consistent rhythm

---

## Layout 10: Image-Text Wrap (Lead Image + Side Text)

```html
<section class="slide light">
  <div class="chrome">
    <div>Design First</div>
    <div>08 / 16</div>
  </div>
  <div class="frame grid-2-8-4" style="padding-top:6vh">
    <!-- Left column: Large body of text + Quote -->
    <div>
      <div class="kicker">Phase 01 · Design Phase</div>
      <h2 class="h-xl" style="margin-top:1vh; margin-bottom:3vh">Design First · 2 Weeks</h2>
 
      <p class="lead" style="margin-bottom:3vh">
        Completed visual exploration and design systems in Figma, grids / typography / color variables / reusable components, desktop and mobile drafts over several rounds of feedback iterations.
      </p>
 
      <p style="font-family:var(--sans-zh); font-size:max(14px,1.15vw); line-height:1.75; opacity:.78; margin-bottom:2.4vh">
        Within two weeks, the visual style, rough structure, and directional content are completely stabilized. This is a solid traditional design process—nothing new here yet.
      </p>
 
      <div class="callout" style="margin-top:3vh">
        "This phase was pretty standard.<br>Just a solid Web design process."
        <div class="callout-src">— Luke Wroblewski</div>
      </div>
    </div>
    <!-- Right column: Auxiliary image · Portrait or Square -->
    <figure class="frame-img" style="aspect-ratio:3/4; max-height:60vh">
      <img src="images/figma.png" alt="Figma design system">
      <figcaption class="img-cap">Figma · Design System</figcaption>
    </figure>
  </div>
  <div class="foot">
    <div>Page 08 · Design First</div>
    <div>Approx. 2 Weeks</div>
  </div>
</section>
```

**Key points**:
- `.grid-2-8-4` (8:4) makes the main text dominant, image as auxiliary
- Left column contains multiple information hierarchies: kicker → large title → lead → body paragraph → callout (quote)
- Right column image uses **portrait 3:4** or square 1:1, avoiding competing for attention with the left column text
- This layout is suitable for scenarios with **a large amount of page information** (unlike Layout 4 which only has one quote)

---

## Appendix: Common Grid Templates

| Class Name | Ratio | Usage |
|---|---|---|
| `.grid-2-6-6` | 6:6 (1:1) | Split in half |
| `.grid-2-7-5` | 7:5 | Text primary + auxiliary image |
| `.grid-2-8-4` | 8:4 (2:1) | Large text + small image/data |
| `.grid-3` | 1:1:1 | 3 parallel items (cases/screenshots) |
| `.grid-3-3` | 3×2 | 6 image matrix |
| `.grid-6` | 3×2 | 6 data cards |

All grids reserve `gap: 3vw 4vh` (horizontal 3vw, vertical 4vh), which can be overridden individually.

---

## Page Rhythm Suggestions

For a 25-30 page presentation, the following rhythm is recommended:

1. **Hero Cover** (Page 1)
2. **Act Divider** (Opening of Act 1, hero light or hero dark)
3. **Big Numbers** (Throw hard data for impact)
4. **Quote + Image** (Talk about identity contrast/hook)
5. **Image Grid** (Evidence support)
6. **Hero Question** (End of act, leave suspense)
7. ... Act 2, Act 3 same rhythm ...
8. **Hero Close** (Last page, question or thanks)

Hero pages and non-hero pages should alternate at a **2-3 : 1 ratio**. Do not have more than 3 consecutive non-hero pages, and do not have more than 2 consecutive hero pages.
