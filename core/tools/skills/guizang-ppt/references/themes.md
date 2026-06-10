# Theme Presets (Themes)

5 carefully curated theme palettes to ensure the "electronic magazine × e-ink" aesthetic doesn't collapse. **Users are not allowed to customize colors — wrong color matching will instantly make the screen ugly**, only choose from the following presets.

---

## How to use

1. Ask the user which one to choose (or recommend one based on the content)
2. Open the `<style>` block in `assets/template.html`
3. Find the `:root{` block at the beginning
4. **Replace entirely** the lines annotated with "Theme Colors": `--ink` / `--ink-rgb` / `--paper` / `--paper-rgb` / `--paper-tint` / `--ink-tint`
5. All other CSS use `var(--...)`, no other changes needed

---

## 🖋 Ink Classic (Monocle Default)

**Suitable for**: General sharing, commercial releases, tech products, the safe default choice for any scenario.
**Tone**: Pure ink black + warm rice white, strongest magazine feel, Monocle / Apricot / A Book Apart style.

```css
--ink:#0a0a0b;
--ink-rgb:10,10,11;
--paper:#f1efea;
--paper-rgb:241,239,234;
--paper-tint:#e8e5de;
--ink-tint:#18181a;
```

---

## 🌊 Indigo Porcelain (Indigo Porcelain)

**Suitable for**: Tech/research/data sharing, engineer culture, deep content, tech keynotes.
**Tone**: Deep indigo + porcelain white, calm, rational, profound, like an academic journal or blue-and-white porcelain.

```css
--ink:#0a1f3d;
--ink-rgb:10,31,61;
--paper:#f1f3f5;
--paper-rgb:241,243,245;
--paper-tint:#e4e8ec;
--ink-tint:#152a4a;
```

---

## 🌿 Forest Ink (Forest Ink)

**Suitable for**: Nature/sustainability/culture/non-fiction content, outdoor brands, eco themes.
**Tone**: Deep forest green + ivory, steady, breathable, like an old edition of *National Geographic*.

```css
--ink:#1a2e1f;
--ink-rgb:26,46,31;
--paper:#f5f1e8;
--paper-rgb:245,241,232;
--paper-tint:#ece7da;
--ink-tint:#253d2c;
```

---

## 🍂 Kraft Paper (Kraft Paper)

**Suitable for**: Nostalgia/humanities/reading/history/literature sharing, indie magazines, handmade brands.
**Tone**: Deep brown + warm beige, like a kraft paper envelope or an old notebook, warm, with a sense of age.

```css
--ink:#2a1e13;
--ink-rgb:42,30,19;
--paper:#eedfc7;
--paper-rgb:238,223,199;
--paper-tint:#e0d0b6;
--ink-tint:#3a2a1d;
```

---

## 🌙 Dune (Dune)

**Suitable for**: Art/design/creative/fashion sharing, gallery brochures, aesthetics-first private sessions.
**Tone**: Charcoal + sand, restrained, premium, neutral, like a desert dusk or architectural design book.

```css
--ink:#1f1a14;
--ink-rgb:31,26,20;
--paper:#f0e6d2;
--paper-rgb:240,230,210;
--paper-tint:#e3d7bf;
--ink-tint:#2d2620;
```

---

## Recommendation Reference

| If it is... | Recommended Theme |
|---|---|
| Don't know what to choose / First time using | 🖋 Ink Classic |
| AI / Tech / Product Release | 🌊 Indigo Porcelain |
| Content / Industry Observation / Culture | 🌿 Forest Ink |
| Book Review / Lifestyle / Humanities | 🍂 Kraft Paper |
| Design / Art / Brand | 🌙 Dune |

---

## Switching Principles

- **Only use one theme per deck**, do not change colors halfway
- The default main color of WebGL shaders (titanium gold dispersion / silver flow) adapts to all 5 sets (tested and acceptable)
- The border / icon driven by `currentColor` will automatically adapt to the text color of the section, no extra adjustment needed
- After selecting a theme, the `<title>` text and `chrome` copy can reinforce the semantics of the theme (e.g., Kraft Paper paired with "Vol.03 · Autumn")

## ❌ What NOT to do

- ❌ **Mixing is not allowed** (e.g., taking ink from Ink Classic, paper from Dune) — it will be completely discordant
- ❌ **Users are not allowed to just give a hex value** — politely decline and show the 5 presets to choose from
- ❌ **Do not directly modify colors elsewhere in template.html** — all scattered rgba use var, changing :root in one place is enough

After selecting a theme, tell the user in the skill conversation: "Using 🖋 Ink Classic / 🌊 Indigo Porcelain ..." and note it in the deck project records, making it easier to maintain consistency during subsequent iterations.
