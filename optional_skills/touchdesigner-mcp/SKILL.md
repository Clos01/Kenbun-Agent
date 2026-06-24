---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [python, touchdesigner, mcp]
  discovery_required: false
---

# TouchDesigner Integration (twozero MCP)

## Critical Rules
1. **NEVER guess parameter names:** Call `td_get_par_info` for the op type **FIRST**. Your training data is wrong for TD 2025.32.
2. **Handle errors immediately:** If `tdAttributeError` fires, **STOP**. Call `td_get_operator_info` on the failing node before continuing.
3. **No absolute paths in callbacks:** NEVER hardcode absolute paths in script callbacks. Use `me.parent()` / `scriptOp.parent()`.
4. **Prefer native MCP tools:** Use `td_create_operator`, `td_set_operator_pars`, `td_get_errors` etc. Only fall back to `td_execute_python` for complex multi-step logic.
5. **Request Hints:** Call `td_get_hints` before building. It returns patterns specific to the op type you're working with.

---

## Architecture
`Hermes Agent` &rarr; `MCP (Streamable HTTP)` &rarr; `twozero.tox` (port 40404) &rarr; `TD Python`

- **36 native tools:** Free plugin (no payment/license required — confirmed April 2026).
- **Context-aware:** Knows selected OP and current active network.
- **Hub Health Check:** `GET http://localhost:40404/mcp` returns JSON with instance PID, project name, and TouchDesigner version.

---

## Setup (Automated)
Run the setup script to handle dependencies:
```bash
bash "${HERMES_HOME:-$HOME/.hermes}/skills/creative/touchdesigner-mcp/scripts/setup.sh"
```
The script will check if TouchDesigner is running, download `twozero.tox` if not cached, add the `twozero_td` MCP server to the agent configuration, test port 40404, and report remaining manual steps.

### Manual Steps (one-time):
1. Drag `~/Downloads/twozero.tox` into the TD network editor &rarr; click **Install**.
2. Enable MCP: Click the twozero icon &rarr; **Settings** &rarr; **mcp** &rarr; set **"auto start MCP"** to **Yes**.
3. Restart the agent session to pick up the new MCP server.

*Verify status via:*
```bash
nc -z 127.0.0.1 40404 && echo "twozero MCP: READY"
```

---

## Environment Notes
- **Non-Commercial caps:** Resolution is capped at 1280×1280. Use `outputresolution = 'custom'` and set width/height explicitly.
- **Codecs:** `prores` (preferred on macOS) or `mjpa` as fallback. H.264/H.265/AV1 require a Commercial license.
- Always call `td_get_par_info` before setting parameters.

---

## Workflow

### Step 0: Discover (before building anything)
- Call `td_get_par_info` with `op_type` for each type you plan to use.
- Call `td_get_hints` with the topic you're building (e.g. "glsl", "audio reactive", "feedback").
- Call `td_get_focus` to see where the user is and what's selected.
- Call `td_get_network` to see what already exists in the project.

### Step 1: Clean + Build
> [!IMPORTANT]
> Split cleanup and creation into SEPARATE MCP calls. Destroying and recreating same-named nodes in a single `td_execute_python` script causes "Invalid OP object" errors.

Use `td_create_operator` for each node (handles viewport positioning automatically):
```json
td_create_operator(type="noiseTOP", parent="/project1", name="bg", parameters={"resolutionw": 1280, "resolutionh": 720})
```
For bulk creation or wiring, fall back to `td_execute_python`:
```python
# td_execute_python script:
root = op('/project1')
nodes = []
for name, optype in [('bg', noiseTOP), ('fx', levelTOP), ('out', nullTOP)]:
    n = root.create(optype, name)
    nodes.append(n.path)
# Wire chain
for i in range(len(nodes)-1):
    op(nodes[i]).outputConnectors[0].connect(op(nodes[i+1]).inputConnectors[0])
```

### Step 2: Set Parameters
Prefer the native tool (validates parameters):
```json
td_set_operator_pars(path="/project1/bg", parameters={"roughness": 0.6, "monochrome": true})
```
For expressions or modes, use `td_execute_python`:
```python
op('/project1/time_driver').par.colorr.expr = "absTime.seconds % 1000.0"
```

### Step 3: Wire
Use `td_execute_python` to wire:
```python
op('/project1/bg').outputConnectors[0].connect(op('/project1/fx').inputConnectors[0])
```

### Step 4: Verify
- Check for errors: `td_get_errors(path="/project1", recursive=true)`
- Check performance: `td_get_perf()`
- Inspect nodes: `td_get_operator_info(path="/project1/out", detail="full")`

### Step 5: Display / Capture
- Capture node viewer: `td_get_screenshot(path="/project1/out")`
- Open a window via script:
  ```python
  win = op('/project1').create(windowCOMP, 'display')
  win.par.winop = op('/project1/out').path
  win.par.winw = 1280; win.par.winh = 720
  win.par.winopen.pulse()
  ```

---

## MCP Tool Quick Reference

### Core:
- `td_execute_python`: Run arbitrary Python in TD.
- `td_create_operator`: Create node with parameters + auto-positioning.
- `td_set_operator_pars`: Set parameters safely (validates inputs).
- `td_get_operator_info` / `td_get_operators_info`: Inspect nodes and connections.
- `td_get_network`: See network structure at a path.
- `td_get_errors`: Find errors/warnings recursively.
- `td_get_par_info`: Get parameter names for an OP type (replaces discovery).
- `td_get_hints`: Get patterns/tips before building.
- `td_get_focus`: What network is open, what's selected.

### Read/Write:
- `td_read_dat` / `td_write_dat`: Read/Write DAT text contents.
- `td_read_chop`: Read CHOP channel values.
- `td_read_textport`: Read TD console textport output.

### Visual:
- `td_get_screenshot` / `td_get_screenshots`: Capture OP viewers to file.
- `td_get_screen_screenshot`: Capture actual screen via TD.
- `td_navigate_to`: Jump network editor viewport to a node.

### Search:
- `td_find_op` / `td_search`: Find ops or search expressions/code.

### System:
- `td_get_perf`: Performance profiling (FPS, cooking times).
- `td_list_instances`: List all running TD instances.
- `td_get_docs`: In-depth documentation on a TD topic.
- `td_agents_md` / `td_reinit_extension`: Manage extension scripting.

### Input Automation:
- `td_input_execute` / `td_input_status` / `td_input_clear`
- `td_op_screen_rect` / `td_click_screen_point` / `td_screen_point_to_global`

---

## Key Implementation Rules

### GLSL Time:
No `uTDCurrentTime` in GLSL TOP. Use the values parameters:
```json
td_set_operator_pars(path="/project1/shader", parameters={"value0name": "uTime"})
```
Then set the expression: `op('/project1/shader').par.value0.expr = "absTime.seconds"`. Define `uniform float uTime;` in GLSL.
*Fallback:* Constant TOP in `rgba32float` format.

### Feedback TOP:
Use top parameter reference, not direct input wire.

### Resolution limits:
Non-Commercial caps at 1280×1280. Use `outputresolution = 'custom'`.

### Large Shaders:
Write GLSL to `/tmp/file.glsl`, then load using `td_write_dat` or `td_execute_python`.

### Vertex/Point Access (TD 2025.32):
Use `point.P[0]`, `point.P[1]`, `point.P[2]` — **NOT** `.x`, `.y`, `.z`.

### Extensions:
Format is `op('./datName').module.ClassName(me)` in `CONSTANT` mode. Reload via `td_reinit_extension` after editing extension files.

---

## Recording / Exporting Video
```python
# via td_execute_python:
root = op('/project1')
rec = root.create(moviefileoutTOP, 'recorder')
op('/project1/out').outputConnectors[0].connect(rec.inputConnectors[0])
rec.par.type = 'movie'
rec.par.file = '/tmp/output.mov'
rec.par.videocodec = 'prores'  # Apple ProRes — NOT license-restricted on macOS
rec.par.record = True   # start recording
# rec.par.record = False  # stop (call separately later)
```
Extract frames: `ffmpeg -i /tmp/output.mov -vframes 120 /tmp/frames/frame_%06d.png`.
> [!WARNING]
> `TOP.save()` is useless for animation (captures same GPU texture). Always use MovieFileOut.

### Before Recording: Checklist
1. Verify `FPS > 0` via `td_get_perf`. (If `FPS=0` the recording will be empty).
2. Verify shader output is not black via `td_get_screenshot`.
3. If recording with audio: cue audio to start first, then delay recording by 3 frames.
4. Set output path before starting record.

---

## Audio-Reactive GLSL (Proven Recipe)

### Correct Signal Chain:
1. `AudioFileIn CHOP` (`playmode=sequential`)
2. `AudioSpectrum CHOP` (`FFT=512`, `outputmenu=setmanually`, `outlength=256`, `timeslice=ON`)
3. `Math CHOP` (`gain=10`)
4. `CHOP to TOP` (`dataformat=r`, `layout=rowscropped`)
5. `GLSL TOP input 1` (spectrum texture, 256x2)
- **Time input:** `Constant TOP` (`rgba32float`, time) &rarr; `GLSL TOP input 0`
- **Output:** `GLSL TOP` &rarr; `Null TOP` &rarr; `MovieFileOut`

### Critical Audio-Reactive Rules:
- **TimeSlice must stay ON** for AudioSpectrum. OFF processes the entire file leading to overflow.
- Set **Output Length manually** to 256. Default outputs 22050 samples.
- **DO NOT use Lag CHOP** for spectrum smoothing. Lag CHOP operates in timeslice mode and averages spectrum values to near-zero.
- **DO NOT use Filter CHOP** for the same reason.
- Perform smoothing inside the GLSL shader using temporal lerp with a feedback texture: `mix(prevValue, newValue, 0.3)`.
- Math gain must sit around `10` (not 5). Raw spectrum values are ~0.19 in bass range.

### GLSL Spectrum Sampling:
```glsl
// Input 0 = time (1x1 rgba32float), Input 1 = spectrum (256x2)
float iTime = texture(sTD2DInputs[0], vec2(0.5)).r;

// Sample multiple points per band and average for stability (y=0.25 for first channel):
float bass = (texture(sTD2DInputs[1], vec2(0.02, 0.25)).r +
              texture(sTD2DInputs[1], vec2(0.05, 0.25)).r) / 2.0;
float mid  = (texture(sTD2DInputs[1], vec2(0.2, 0.25)).r +
              texture(sTD2DInputs[1], vec2(0.35, 0.25)).r) / 2.0;
float hi   = (texture(sTD2DInputs[1], vec2(0.6, 0.25)).r +
              texture(sTD2DInputs[1], vec2(0.8, 0.25)).r) / 2.0;
```

---

## Operator Quick Reference

| Family | Color | Python Class / MCP Type | Suffix |
| :--- | :--- | :--- | :--- |
| **TOP** | Purple | `noiseTOP`, `glslTOP`, `compositeTOP`, `levelTOP`, `nullTOP` | TOP |
| **CHOP** | Green | `audiofileinCHOP`, `audiospectrumCHOP`, `mathCHOP`, `lfoCHOP` | CHOP |
| **SOP** | Blue | `gridSOP`, `sphereSOP`, `transformSOP`, `noiseSOP` | SOP |
| **DAT** | White | `textDAT`, `tableDAT`, `scriptDAT`, `webserverDAT` | DAT |
| **MAT** | Yellow | `phongMAT`, `pbrMAT`, `glslMAT`, `constMAT` | MAT |
| **COMP** | Gray | `geometryCOMP`, `containerCOMP`, `cameraCOMP`, `windowCOMP` | COMP |

---

## References
- `references/pitfalls.md` — Hard-won lessons.
- `references/operators.md` — Operator parameters and use cases.
- `references/network-patterns.md` — Audio-reactive, generative, and GLSL instancing scripts.
- `references/mcp-tools.md` — Complete parameter schemas for the 36 MCP tools.
- `references/python-api.md` — Scripting references, custom classes and extensions.
- `references/troubleshooting.md` — Port check, extension re-init and networking diagnostics.
- `references/glsl.md` — GLSL uniform bindings and vertex/fragment shader templates.
- `references/postfx.md` — Shaders for bloom, chromatic aberration, and CRT scanlines.
- `references/audio-reactive.md` — Beat detection and envelope following.
- `references/animation.md` — LFOs, ValueTrackers, and interpolation curves.
