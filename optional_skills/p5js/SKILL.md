---
kenbun:
  mode: prototype
  fidelity: high
  tech_stack: [html, js, p5js]
  discovery_required: false
---

# p5.js Production Pipeline

## When to use
Use when users request: p5.js sketches, creative coding, generative art, interactive visualizations, canvas animations, browser-based visual art, data viz, shader effects, or any p5.js project.

## What's inside
Production pipeline for interactive and generative visual art using p5.js. Creates browser-based sketches, generative art, data visualizations, interactive experiences, 3D scenes, audio-reactive visuals, and motion graphics — exported as HTML, PNG, GIF, MP4, or SVG. Covers: 2D/3D rendering, noise and particle systems, flow fields, shaders (GLSL), pixel manipulation, kinetic typography, WebGL scenes, audio analysis, mouse/keyboard interaction, and headless high-res export.

## Creative Standard
This is visual art rendered in the browser. The canvas is the medium; the algorithm is the brush.

- **Creative Concept First:** Before writing a single line of code, articulate the creative concept. What does this piece communicate? What makes the viewer stop scrolling? What separates this from a code tutorial example? The user's prompt is a starting point — interpret it with creative ambition.
- **First-Render Excellence:** The output must be visually striking on first load. If it looks like a p5.js tutorial exercise, a default configuration, or "AI-generated creative coding," it is wrong. Rethink before shipping.
- **Go Beyond Reference Vocabulary:** The noise functions, particle systems, color palettes, and shader effects in the references are a starting vocabulary. For every project, combine, layer, and invent. The catalog is a palette of paints — you write the painting.
- **Proactive Creativity:** If the user asks for "a particle system," deliver a particle system with emergent flocking behavior, trailing ghost echoes, palette-shifted depth fog, and a background noise field that breathes. Include at least one visual detail the user didn't ask for but will appreciate.
- **Dense, Layered, Considered:** Every frame should reward viewing. Never flat white backgrounds. Always compositional hierarchy. Always intentional color. Always micro-detail that only appears on close inspection.
- **Cohesive Aesthetic:** All elements must serve a unified visual language — shared color temperature, consistent stroke weight vocabulary, harmonious motion speeds. A sketch with ten unrelated effects is worse than one with three that belong together.

---

## Modes

| Mode | Input | Output | Reference |
| :--- | :--- | :--- | :--- |
| **Generative art** | Seed / parameters | Procedural visual composition (still or animated) | `references/visual-effects.md` |
| **Data visualization** | Dataset / API | Interactive charts, graphs, custom data displays | `references/interaction.md` |
| **Interactive experience** | None (user drives) | Mouse/keyboard/touch-driven sketch | `references/interaction.md` |
| **Animation / motion** | Timeline / storyboard | Timed sequences, kinetic typography, transitions | `references/animation.md` |
| **3D scene** | Concept description | WebGL geometry, lighting, camera, materials | `references/webgl-and-3d.md` |
| **Image processing** | Image file(s) | Pixel manipulation, filters, mosaic, pointillism | `references/visual-effects.md` § Pixel Manipulation |
| **Audio-reactive** | Audio file / mic | Sound-driven generative visuals | `references/interaction.md` § Audio Input |

---

## Stack
Single self-contained HTML file per project. No build step required.

- **Core:** p5.js 1.11.3 (CDN) (canvas rendering, math, transforms, event handling)
- **3D:** p5.js WebGL mode (3D geometry, camera, lighting, GLSL shaders)
- **Audio:** p5.sound.js (CDN) (FFT analysis, amplitude, mic input, oscillators)
- **Export:** Built-in `saveCanvas()` / `saveGif()` / `saveFrames()` (PNG, GIF, frame sequence output)
- **Capture:** `CCapture.js` (optional) (deterministic framerate video capture)
- **Headless:** Puppeteer + Node.js (optional) (automated high-res rendering, MP4 via ffmpeg)
- **SVG:** `p5.js-svg 1.6.0` (optional) (vector output for print — requires p5.js 1.x)
- **Natural media:** `p5.brush` (optional) (watercolor, charcoal, pen — requires p5.js 2.x + WEBGL)
- **Texture:** `p5.grain` (optional) (film grain, texture overlays)
- **Fonts:** Google Fonts / `loadFont()` (custom typography via OTF/TTF/WOFF2)

### Version Note
- **p5.js 1.x (1.11.3)** is the default — stable, well-documented, broadest library compatibility. Use this unless a project requires 2.x features.
- **p5.js 2.x (2.2+)** adds: async `setup()` replacing `preload()`, OKLCH/OKLAB color modes, `splineVertex()`, shader `.modify()` API, variable fonts, `textToContours()`, pointer events. Required for `p5.brush`. See `references/core-api.md` § p5.js 2.0.

---

## Pipeline

`CONCEPT` &rarr; `DESIGN` &rarr; `CODE` &rarr; `PREVIEW` &rarr; `EXPORT` &rarr; `VERIFY`

1. **CONCEPT:** Articulate the creative vision: mood, color world, motion vocabulary, what makes this unique.
2. **DESIGN:** Choose mode, canvas size, interaction model, color system, export format. Map concept to technical decisions.
3. **CODE:** Write single HTML file with inline p5.js. Structure: globals &rarr; `preload()` &rarr; `setup()` &rarr; `draw()` &rarr; helpers &rarr; classes &rarr; event handlers.
4. **PREVIEW:** Open in browser, verify visual quality. Test at target resolution. Check performance.
5. **EXPORT:** Capture output: `saveCanvas()` for PNG, `saveGif()` for GIF, `saveFrames()` + ffmpeg for MP4, Puppeteer for headless batch.
6. **VERIFY:** Does the output match the concept? Is it visually striking at the intended display size? Would you frame it?

---

## Creative Direction

### Aesthetic Dimensions
- **Color system:** HSB/HSL, RGB, named palettes, procedural harmony, gradient interpolation (`references/color-systems.md`)
- **Noise vocabulary:** Perlin noise, simplex, fractal (octaved), domain warping, curl noise (`references/visual-effects.md` § Noise)
- **Particle systems:** Physics-based, flocking, trail-drawing, attractor-driven, flow-field following (`references/visual-effects.md` § Particles)
- **Shape language:** Geometric primitives, custom vertices, bezier curves, SVG paths (`references/shapes-and-geometry.md`)
- **Motion style:** Eased, spring-based, noise-driven, physics sim, lerped, stepped (`references/animation.md`)
- **Typography:** System fonts, loaded OTF, `textToPoints()` particle text, kinetic (`references/typography.md`)
- **Shader effects:** GLSL fragment/vertex, filter shaders, post-processing, feedback loops (`references/webgl-and-3d.md` § Shaders)
- **Composition:** Grid, radial, golden ratio, rule of thirds, organic scatter, tiled (`references/core-api.md` § Composition)
- **Interaction model:** Mouse follow, click spawn, drag, keyboard state, scroll-driven, mic input (`references/interaction.md`)
- **Blend modes:** `BLEND`, `ADD`, `MULTIPLY`, `SCREEN`, `DIFFERENCE`, `EXCLUSION`, `OVERLAY` (`references/color-systems.md` § Blend Modes)
- **Layering:** `createGraphics()` offscreen buffers, alpha compositing, masking (`references/core-api.md` § Offscreen Buffers)
- **Texture:** Perlin surface, stippling, hatching, halftone, pixel sorting (`references/visual-effects.md` § Texture Generation)

### Per-Project Variation Rules
Never use default configurations. For every project:
- **Custom color palette:** Never raw `fill(255, 0, 0)`. Always a designed palette with 3-7 colors.
- **Custom stroke weight vocabulary:** Thin accents (0.5), medium structure (1-2), bold emphasis (3-5).
- **Background treatment:** Never plain `background(0)` or `background(255)`. Always textured, gradient, or layered.
- **Motion variety:** Different speeds for different elements. Primary at 1x, secondary at 0.3x, ambient at 0.1x.
- **At least one invented element:** A custom particle behavior, a novel noise application, a unique interaction response.

### Project-Specific Invention
For every project, invent at least one of:
- A custom color palette matching the mood (not a preset).
- A novel noise field combination (e.g., curl noise + domain warp + feedback).
- A unique particle behavior (custom forces, custom trails, custom spawning).
- An interaction mechanic the user didn't request but that elevates the piece.
- A compositional technique that creates visual hierarchy.

### Parameter Design Philosophy
Parameters should emerge from the algorithm, not from a generic menu. Expose the algorithm's character:
- **Quantities** — how many particles, branches, cells (controls density).
- **Scales** — noise frequency, element size, spacing (controls texture).
- **Rates** — speed, growth rate, decay (controls energy).
- **Thresholds** — when does behavior change? (controls drama).
- **Ratios** — proportions, balance between forces (controls harmony).

*Avoid generic controls unrelated to the algorithm like plain "color1" or "particle size" sliders that only change ellipses without altering physical behaviors.*

---

## Workflow

### Step 1: Creative Vision
Before any code, articulate:
- **Mood / atmosphere:** Contemplative? Energized? Unsettled? Playful?
- **Visual story:** What happens over time (or on interaction)? Build? Decay? Transform? Oscillate?
- **Color world:** Warm/cool? Monochrome? Complementary? What's the dominant hue? The accent?
- **Shape language:** Organic curves? Sharp geometry? Dots? Lines? Mixed?
- **Motion vocabulary:** Slow drift? Explosive burst? Breathing pulse? Mechanical precision?
- **What makes THIS different:** What is the one thing that makes this sketch unique?

### Step 2: Technical Design
- **Mode:** Select one of the 7 pipeline modes.
- **Canvas size:** landscape 1920x1080, portrait 1080x1920, square 1080x1080, or responsive `windowWidth`/`windowHeight`.
- **Renderer:** `P2D` (default) or `WEBGL` (for 3D, shaders, advanced blend modes).
- **Frame rate:** 60fps (interactive), 30fps (ambient animation), or `noLoop()` (static generative).
- **Export target:** browser display, PNG still, GIF loop, MP4 video, SVG vector.
- **Interaction model:** passive (no input), mouse-driven, keyboard-driven, audio-reactive, scroll-driven.
- **Viewer UI:** For interactive generative art, start from `templates/viewer.html` which provides seed navigation, parameter sliders, and download. For simple sketches or video export, use bare HTML.

### Step 3: Code the Sketch
For interactive generative art (seed exploration, parameter tuning), start from `templates/viewer.html`. Replace the algorithm and parameter controls while keeping the fixed sections (seed nav, actions) wired up.

For animations, video export, or simple sketches, use bare HTML:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Project Name</title>
  <script>p5.disableFriendlyErrors = true;</script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.11.3/p5.min.js"></script>
  <style>
    html, body { margin: 0; padding: 0; overflow: hidden; }
    canvas { display: block; }
  </style>
</head>
<body>
<script>
// === Configuration ===
const CONFIG = {
  seed: 42,
};

// === Color Palette ===
const PALETTE = {
  bg: '#0a0a0f',
  primary: '#e8d5b7',
};

// === Global State ===
let particles = [];

function setup() {
  createCanvas(1920, 1080);
  randomSeed(CONFIG.seed);
  noiseSeed(CONFIG.seed);
  colorMode(HSB, 360, 100, 100, 100);
}

function draw() {
  // Render frame...
}

class Particle {
  // ...
}

function windowResized() { resizeCanvas(windowWidth, windowHeight); }
</script>
</body>
</html>
```

Key implementation patterns:
- **Seeded randomness:** Always `randomSeed()` + `noiseSeed()` for reproducibility.
- **Color mode:** Use `colorMode(HSB, 360, 100, 100, 100)` for intuitive color control.
- **State separation:** `CONFIG` for parameters, `PALETTE` for colors, globals for mutable state.
- **Class-based entities:** Particles, agents, shapes as classes with `update()` + `display()` methods.
- **Offscreen buffers:** `createGraphics()` for layered composition, trails, masks.

### Step 4: Preview & Iterate
1. Open HTML file directly in browser.
2. For `loadImage()`/`loadFont()` from local files: run local python server: `python3 -m http.server` and open `http://localhost:8000/sketch.html`.
3. Check Chrome DevTools Performance tab to verify 60fps.

### Step 5: Export

| Format | Method / Tool | Command |
| :--- | :--- | :--- |
| **PNG** | `saveCanvas('output', 'png')` in `keyPressed()` | Press `s` to save |
| **High-res PNG** | Puppeteer headless capture script | `node scripts/export-frames.js sketch.html --width 3840` |
| **GIF** | `saveGif('output', 5)` (captures 5 seconds) | Press `g` to save |
| **Frame seq** | `saveFrames('frame', 'png', 10, 30)` | Then run `ffmpeg -i frame-%04d.png -c:v libx264 out.mp4` |
| **SVG** | `createCanvas(w, h, SVG)` with `p5.js-svg` | Run `save('output.svg')` |

### Step 6: Quality Verification
- **Compare to Concept:** Does the output match the initial creative concept?
- **Resolution & Contrast:** Is it sharp at display size? High text contrast on white backgrounds (min color `#757575`).
- **Edge cases:** What happens at canvas edges? On window resize? After running for 10 minutes?

---

## Critical Implementation Notes

### Performance — Disable FES First
The Friendly Error System (FES) adds up to 10x overhead. Disable it in every production sketch:
```javascript
p5.disableFriendlyErrors = true;  // BEFORE setup()

function setup() {
  pixelDensity(1);  // prevent 2x-4x overdraw on retina screens
  createCanvas(1920, 1080);
}
```
In hot loops (particles, pixel ops), use `Math.*` instead of p5 wrappers:
```javascript
let a = Math.sin(t);          // not sin(t)
let r = Math.sqrt(dx*dx+dy*dy); // not dist()
let v = Math.random();        // not random() (when seed not needed)
```
*Never `console.log()` inside `draw()`. Never manipulate DOM in `draw()`.*

### Seeded Randomness — Always
Every generative sketch must be reproducible. Same seed, same output.
```javascript
function setup() {
  randomSeed(CONFIG.seed);
  noiseSeed(CONFIG.seed);
}
```
Never use `Math.random()` for generative content — only for performance-critical non-visual code. If you need a random seed: `CONFIG.seed = floor(random(99999))`.

### Generative Art Platform Support (fxhash / Art Blocks)
Replace p5's PRNG with the platform's deterministic random:
```javascript
const SEED = $fx.hash;
const rng = $fx.rand;

// In setup():
randomSeed(SEED);
noiseSeed(SEED);

// Replace random() with rng()
let x = rng() * width;
```

### Color Mode — Use HSB
HSB is much easier to work with than RGB for generative art:
```javascript
colorMode(HSB, 360, 100, 100, 100);
// fill(hue, sat, bri, alpha)
```
Never hardcode raw RGB values. Define a palette object, derive variations procedurally. See `references/color-systems.md`.

### Noise — Multi-Octave, Not Raw
Raw `noise(x, y)` looks like smooth blobs. Layer octaves for natural texture (fBM):
```javascript
function fbm(x, y, octaves = 4) {
  let val = 0, amp = 1, freq = 1, sum = 0;
  for (let i = 0; i < octaves; i++) {
    val += noise(x * freq, y * freq) * amp;
    sum += amp;
    amp *= 0.5;
    freq *= 2;
  }
  return val / sum;
}
```

### `createGraphics()` for Layers — Not Optional
Flat single-pass rendering looks flat. Use offscreen buffers for composition (background, trails, foreground layers).

### Performance — Vectorize Where Possible
p5.js draw calls are expensive. For thousands of particles:
- **FAST:** single shape with `beginShape(POINTS)` and `vertex(x, y)` calls.
- **FASTEST:** Write directly to `pixels` buffer inside `loadPixels()` / `updatePixels()`.

### Instance Mode for Multiple Sketches
Use instance mode to prevent window pollution when embedding multiple sketches on one page:
```javascript
const sketch = (p) => {
  p.setup = function() { p.createCanvas(800, 800); };
  p.draw = function() { p.background(0); p.ellipse(p.mouseX, p.mouseY, 50); };
};
new p5(sketch, 'canvas-container');
```

### WebGL Mode Gotchas
- Origin `(0,0)` is in the center of the canvas, not top-left. Y-axis is inverted (goes up, not down).
- Run `translate(-width/2, -height/2)` to revert to P2D-like coordinates.
- Run `push()` / `pop()` around every transform.
- Call `texture()` before rendering shapes.

### Export — Key Bindings Convention
```javascript
function keyPressed() {
  if (key === 's' || key === 'S') saveCanvas('output', 'png');
  if (key === 'g' || key === 'G') saveGif('output', 5);
  if (key === 'r' || key === 'R') { randomSeed(millis()); noiseSeed(millis()); }
  if (key === ' ') CONFIG.paused = !CONFIG.paused;
}
```

### Headless Video Export — Use `noLoop()`
For headless rendering via Puppeteer, the sketch must use `noLoop()` in `setup()` and set `window._p5Ready = true` so the capture script can control frame advance exactly.

---

## Performance Targets
- **Frame rate (interactive):** 60fps sustained.
- **Frame rate (animated export):** 30fps minimum.
- **Particle count (P2D shapes):** 5,000-10,000 at 60fps.
- **Particle count (pixel buffer):** 50,000-100,000 at 60fps.
- **Canvas resolution:** Up to 3840x2160 (export), 1920x1080 (interactive).
- **Load time:** < 2s to first frame.

---

## References

| File | Contents |
| :--- | :--- |
| `references/core-api.md` | Canvas setup, coordinate system, draw loop, push()/pop(), offscreen buffers, composition patterns, `pixelDensity()`, responsive design |
| `references/shapes-and-geometry.md` | 2D primitives, `beginShape()`/`endShape()`, Bezier/Catmull-Rom curves, vertex() systems, custom shapes, `p5.Vector`, signed distance fields, SVG path conversion |
| `references/visual-effects.md` | Noise (Perlin, fractal, domain warp, curl), flow fields, particle systems (physics, flocking, trails), pixel manipulation, texture generation, feedback loops |
| `references/animation.md` | Frame-based animation, easing functions, `lerp()`/`map()`, spring physics, state machines, timeline sequencing, millis()-based timing |
| `references/typography.md` | text(), `loadFont()`, `textToPoints()`, kinetic typography, text masks, font metrics |
| `references/color-systems.md` | `colorMode()`, HSB/HSL/RGB, `lerpColor()`, `paletteLerp()`, procedural palettes, color harmony, `blendMode()`, gradient rendering |
| `references/webgl-and-3d.md` | WEBGL renderer, 3D primitives, camera, lighting, materials, custom geometry, GLSL shaders, framebuffers, post-processing |
| `references/interaction.md` | Mouse events, keyboard state, touch input, DOM elements, sliders, buttons, audio input (FFT/amplitude), scroll-driven animation |
| `references/export-pipeline.md` | `saveCanvas()`, `saveGif()`, `saveFrames()`, deterministic headless capture, ffmpeg frame-to-video, `CCapture.js`, SVG export, platform export (fxhash) |
| `references/troubleshooting.md` | Performance profiling, per-pixel budgets, common mistakes, browser compatibility, WebGL debugging, CORS |
| `templates/viewer.html` | Interactive viewer template: seed navigation, parameter sliders, download PNG. Start from this for explorable generative art |

---

## Creative Divergence (use only when user requests experimental/creative/unique output)
If the user asks for creative, experimental, surprising, or unconventional output, select the strategy that best fits and reason through its steps BEFORE generating code.

### 1. Conceptual Blending
- Name two distinct visual systems (e.g. particle physics + handwriting).
- Map correspondences (particles = ink drops, forces = pen pressure, fields = letterforms).
- Blend selectively — keep mappings that produce interesting emergent visuals.
- Code the blend as a unified system.

### 2. SCAMPER Transformation
Take a known generative pattern and systematically transform it:
- **Substitute:** Replace circles with text characters, lines with gradients.
- **Combine:** Merge two patterns (e.g. flow field + voronoi).
- **Adapt:** Apply a 2D pattern to a 3D projection.
- **Modify:** Exaggerate scale, warp the coordinate space.
- **Purpose:** Use a physics sim for typography, a sorting algorithm for color.
- **Eliminate:** Remove the grid, remove color, remove symmetry.
- **Reverse:** Run the simulation backward, invert the parameter space.

### 3. Distance Association
- Anchor on the user's concept (e.g. "loneliness").
- Generate associations at three distances:
  - *Close (obvious):* empty room, single figure, silence.
  - *Medium (interesting):* one fish in a school swimming the wrong way, a phone with no notifications, the gap between subway cars.
  - *Far (abstract):* prime numbers, asymptotic curves, the color of 3am.
- Develop the medium-distance associations — they are specific enough to visualize but unexpected enough to be interesting.
