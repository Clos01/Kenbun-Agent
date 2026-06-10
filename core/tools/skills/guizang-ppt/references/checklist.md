# Quality Checklist (Checklist)

This checklist comes from the real iteration process of the "One-Person Company" presentation PPT. Each item is summarized after stepping into a pitfall, sorted by importance.

Read through it before generating the PPT; after generating, self-check item by item.

---

## 🔴 P0 · Mistakes you absolutely cannot make

### 0. Class name validation must pass before generation (Most Important)

**Phenomenon**: You directly pasted the skeleton from `layouts.md` into a new HTML file, but all styles were lost—large titles turned into sans-serif, data posters had fonts as small as body text, multiple pipeline pages blurred into a mess, and images piled up at the bottom of the browser.

**Root cause**: If there are no definitions for these classes in the `<style>` of `template.html`, the browser falls back to default styles.

**Action**:
- **Before generating the PPT, you must `Read` `assets/template.html`** to confirm that the classes used in `layouts.md` are defined.
- Most commonly missed classes: `h-hero / h-xl / h-sub / h-md / lead / meta-row / stat-card / stat-label / stat-nb / stat-unit / stat-note / pipeline-section / pipeline-label / pipeline / step / step-nb / step-title / step-desc / grid-2-7-5 / grid-2-6-6 / grid-2-8-4 / grid-3-3 / frame / img-cap / callout-src`
- If a class is indeed missing, **add it to the `<style>` in template.html**, do not write inline overrides on every page.
- After generation, open the browser. If you see "large titles are sans-serif" or "pipeline steps squeezed into one line", it is almost 100% this issue.

### 1. Do not use emojis as icons

**Phenomenon**: Using emojis (🎯 💡 ✅) in a Chinese-style magazine will instantly ruin the tone.

**Action**: Use the Lucide icon library, referenced via CDN:

```html
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
...
<i data-lucide="target" class="ico-md"></i>
...
<script>lucide.createIcons();</script>
```

Common icon names: `target / palette / search-check / compass / share-2 / crown / check-circle / x-circle / plus / arrow-right / grid-2x2 / network`

### 2. Images are only allowed to be cropped at the bottom, never crop left/right and top

**Phenomenon**: Using `aspect-ratio` to stretch images causes grids to pile up or crop key image information (like the title bar at the top of a screenshot) when the parent container is insufficient.

**Action**: The image container uses **fixed height + overflow hidden**, and the image uses `object-fit:cover + object-position:top`:

```html
<figure class="frame-img" style="height:26vh">
  <img src="screenshot.png">
</figure>
```

In CSS, `.frame-img img` is pre-set with `object-position:top`, only cropping the bottom.

**Never use this syntax** (it will burst the container in a grid):

```html
<!-- Bad Example -->
<figure class="frame-img" style="aspect-ratio: 16/9">...</figure>
```

**Exception**: A single main visual (not in a grid) can use `aspect-ratio + max-height`, because the parent container will hold it.

### 2b. Light page with dark WebGL = Ashy gray (Theme switch failed)

**Phenomenon**: All light page backgrounds look covered in gray, even hero light is gray.

**Root cause**: JS switches the opacity of the two canvases based on the slide's theme. If the whole deck starts with hero dark, and there is no mechanism to switch the bg to light, the body never gets the `light-bg` class, and `canvas#bg-dark` is always on top.

**Action**:
- The `go()` function in the template has been changed to infer the theme (`light` / `dark`) from the `classList`, so **the slide must explicitly have the `light` or `dark` class**. Do not forget it, and absolutely do not use other custom theme names.
- Hero pages use `hero light` / `hero dark`, body pages use `light` / `dark`. Writing only `hero` without a theme color is broken.
- A deck must have at least one **non-hero light page**, ensuring the body has a chance to add `light-bg`.

### 2b-2. The entire deck is all light, no rhythm

**Phenomenon**: Except for the cover `hero dark`, all other pages are written as `light` by default—visually flat, no breathing room, a sea of white.

**Root cause**: The skeleton in `layouts.md` defaults to writing `light`. If you just paste the skeleton without adjusting the theme, it will be entirely bright.

**Action**:
- **Before generation, draw a "Theme Rhythm Chart"**: Clearly write down which of `hero dark` / `hero light` / `light` / `dark` each page is using, align them before writing the code.
- **Hard rules**: > 3 consecutive pages with the same theme = not allowed; > 8 pages must have ≥1 `hero dark` + ≥1 `hero light`; it cannot be all `light` body pages—there must be `dark` body pages.
- **Choose themes based on layout** (see "Theme Rhythm Planning" at the beginning of layouts.md):
  - Left text right image (Layout 4), Big quote (Layout 8), Image-text wrap (Layout 10) → **`light` / `dark` alternate**
  - Big numbers, Image grid, Pipeline, Before/After → `light` (screenshots/numbers/processes need a bright background)
  - Cover, Question page → `hero dark`
  - Chapter cover → `hero dark` and `hero light` alternate
- **Self-check after generation**: `grep 'class="slide' index.html`, visually confirm that the rhythm alternates.

### 2c. chrome and kicker should not write the same sentence

**Phenomenon**: The `.chrome` at the top left says "Design First", and the `.kicker` on the same page says "Phase 01 · Design Phase" — synonymous translation, strong AI flavor.

**Action**:
- **chrome = Magazine header / navigation tag**: Can be the same across multiple pages (e.g., "Act II · Workflow", "Data · Result", "lukew.com · 2026.04")
- **kicker = A unique guiding sentence for this page**: Short, with a hook, a "small prefix" for the big title (e.g., "BUT", "One person, what was done.", "The Question")
- One describes the column, the other describes the page—never translate each other.

### 3. Large title font size must not exceed screen width / word count

**Phenomenon**: Chinese large titles are set too large (e.g., 13vw), resulting in only 1 word fitting per line, forcing very ugly line breaks.

**Action**:
- `h-hero` (largest): 10vw, **and title length ≤ 5 words**
- `h-xl` (second largest): 6vw-7vw
- Use `<br>` to manually break long titles, do not rely on automatic word wrapping
- Add `white-space:nowrap` if necessary

**Example**: `我不是程序员。` (6 words) using `h-xl` 7.2vw + nowrap, formats beautifully on one line.

### 4. Font division of labor: Titles Serif, Body Sans-serif

**Action**:
- Large titles, key quotes, big numbers → **Serif fonts** (Noto Serif SC + Playfair Display + Source Serif)
- Body text, descriptions, pipeline step names → **Sans-serif fonts** (Noto Sans SC + Inter)
- Metadata, code, tags → **Monospace fonts** (IBM Plex Mono + JetBrains Mono)

All fonts are imported using Google Fonts CDN, pre-configured in the template.

### 4b. Images should not use `align-self:end` to stick to the bottom

**Phenomenon**: In the left text right image layout, to make the image on the right column align with the bottom of the callout on the left column, `align-self:end` was added to `<figure>`. Result:
- If the parent container is not a grid (e.g., the class name is undefined), `align-self` completely fails, and the image drops to the bottom of the document flow, obscured by the browser's bottom bar.
- Even if it is a grid, the image will stick to the bottom of the cell, and on low-res screens, it will still be obscured by `.foot` and the `#nav` dots.

**Action**:
- Image-text combinations **must use `.frame.grid-2-7-5`** (or `.grid-2-6-6`/`.grid-2-8-4`)
- The right column `<figure class="frame-img">` uses **standard aspect ratios 16/10 or 4/3 + max-height:56vh**, naturally sticking to the top.
- To make the left column callout look "bottom-aligned", add flex column + `justify-content:space-between` to the **left column**, do not touch the right column.

### 4c. Do not use bizarre proportions from the original image

**Phenomenon**: A proportion like `aspect-ratio: 2592/1798` copied from the original image stretches out weird empty spaces or overflows on different screens.

**Action**: Regardless of the original image's proportion, the placeholder always uses a standard proportion **16/10 / 4/3 / 3/2 / 1/1 / 16/9**. The image is automatically handled with `object-fit:cover + object-position:top`, not cropping the top; cropping a little at the bottom is harmless.

### 5. Do not add thick borders / shadows to images

**Phenomenon**: Adding a strong shadow or a black border for a "premium feel" instantly turns it into a corporate business PPT.

**Action**: At most 1-4px slight rounded corners + **an extremely faint noise background** (already in the template). Do not add `box-shadow`, do not add `border` (unless it's an extremely faint 1px gray).

---

## 🟡 P1 · Layout Rhythm

### 6. Hero pages and non-hero pages should alternate

**Recommended rhythm** (25-30 pages):
```
Hero Cover → Act Divider (hero) → 3-4 pages non-hero → Act Divider (hero)
→ 4-5 pages non-hero → Hero Question → ... → Hero Close
```

Consecutive hero pages > 2 will cause fatigue; consecutive non-hero pages > 4 will kill the rhythm.

### 7. Big number pages and dense pages should alternate

Big numbers (big numbers / hero question) and dense pages (pipeline / image grid) should appear alternately, so the audience's eyes do not get tired.

### 8. English/Chinese usage for the same concept should be unified

**Phenomenon**: Sometimes writing "Skills", sometimes writing "技能", sometimes writing "薄承载厚技能", inconsistent throughout.

**Action**:
- Terminology preferably uses **English words** (Skills / Harness / Pipeline / Workflow), these are familiar terms in the circle.
- **Do not translate forcefully**, forceful translation is stiff.
- Keep the same word written in 1 way throughout the whole deck.

### 9. Page numbers in the bottom chrome should be consistent

Use the format `XX / Total Pages` (e.g., `05 / 27`). **Do not add dynamic page numbers in the top right corner** (it will duplicate with `.chrome`).

---

## 🟢 P2 · Visual Polish

### 10. Mask opacity for WebGL backgrounds

**dark hero**: mask 12-15% (WebGL clearly shows through)
**light hero**: mask 16-20% (WebGL faintly visible, doesn't compete with text)
**normal light/dark pages**: mask 92-95% (almost opaque)

If a page has very little text (hero question), the mask can be thinner; if the body is dense, the mask must be thicker to ensure readability.

### 11. Light hero shader should not have a strong center point

**Phenomenon**: Spiral Vortex, radial ripples are too conspicuous under the light theme, looking like a Windows 98 screensaver.

**Action**: Light hero uses a center-less flow driven by FBM domain warping, base color remains silver/paper (`#F0F0F0` / `#FBF8F3`), subtle rainbow tint (< 0.05).

### 12. Dark hero allows more visual impact

Dark hero can use Holographic Dispersion (titanium gold dispersion) and other shaders with center structures, because a black background can accommodate more visual info.

### 13. Alignment for Left Text Right Image

- Left column text group `justify-content:space-between`: title sticks to the top, quote box sticks to the bottom
- Right column image `align-self:end`: aligns with the bottom element of the left column
- Grid overall `align-items:start` (not `center` / `end`)

### 14. Slight rounded corners for images

All `.frame-img` and `.frame-img img` have `border-radius:4px`, visually "soft" but not weak. **Do not exceed 8px**, otherwise it looks like a consumer app UI.

---

## 🔵 P3 · Operational Details

### 15. Use relative paths for image paths

Put images under the `images/` folder, use relative paths like `images/xxx.png` in HTML, do not use absolute paths.

### 16. Page numbers are hardcoded in `.chrome`

JS will dynamically calculate total pages and expand the bottom page indicator dots, but `XX / N` inside `.chrome` is hardcoded. When adding/deleting pages, N must be updated manually.

### 17. Page navigation should be preserved

The template supports by default: ← → / mouse wheel / touch swipe / bottom dots / Home·End. Do not delete the navigation logic in JS.

### 18. Do not hardcode `height:100vh`, use `min-height:80vh`

`100vh` will fit the content exactly to the screen, but browser toolbars/tab bars will eat up some height, causing content to overflow. Using `min-height:80vh + align-content:center` is safer.

---

## 🧪 Final Self-Check Checklist

After generating the PPT, compare item by item with this checklist (check it off):

```
Pre-flight (Before Generation)
  □ Have read the <style> of template.html to confirm required classes exist
  □ Decided which Layout (1-10) to use for each page
  □ Have drawn the "Theme Rhythm Chart": explicitly defined hero dark / hero light / light / dark for each page
  □ The rhythm chart meets hard rules: no 3 consecutive pages with the same theme / at least 1 hero dark + 1 hero light (for > 8 pages) / at least 1 dark body page
  □ `<title>` has been changed to actual deck title (grep "[必填]" should yield no results)

Content
  □ The page count ratio of each act is reasonable (not top-heavy)
  □ No emojis used as icons
  □ Terminology like Skills / Harness used consistently
  □ Three levels of information are clear on each page: kicker + title + body

Layout
  □ All large titles do not have 1 word per line breaks
  □ Image grids use height:Nvh instead of aspect-ratio
  □ Images are only cropped at the bottom, top and sides are intact
  □ Serif/Sans-serif font division matches the template
  □ Pipeline groups have obvious separation

Visuals
  □ Hero pages and non-hero pages alternate
  □ WebGL background is visible on hero pages
  □ Images have slight rounded corners
  □ No heavy shadows or borders

Interaction
  □ ← → navigation works normally
  □ Number of bottom dots matches total pages
  □ Page number in chrome matches the actual page number
  □ ESC triggers index view (if preserved)
```

Only when all are checked off, is it a qualified PPT.
