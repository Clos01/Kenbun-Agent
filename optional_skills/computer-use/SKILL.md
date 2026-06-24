---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, cua-driver]
  discovery_required: false
---

# Computer Use Skill
Drive the user's desktop in the background — clicking, typing, scrolling, dragging — without stealing the cursor, keyboard focus, or switching virtual desktops / Spaces. Supports macOS, Windows, and Linux.

## Prerequisites
- Hermes computer-use installation or `cua-driver` enabled
- Screen Recording permissions granted where applicable
- Local active desktop session (on Windows, avoid Session 0 / SSH isolation without config)

## The Canonical Workflow
1. **Capture First:** Capture screenshot with numbered overlays (SOM) and accessibility tree.
   ```bash
   computer_use(action="capture", mode="som", app="Chrome")
   ```
2. **Click by Element Index:** Click elements using their overlay numbers.
   ```bash
   computer_use(action="click", element=7)
   ```
3. **Verify:** Perform post-action verification (e.g. using `capture_after=True` or a new capture).

## Core Actions
* `capture (mode=som|vision|ax, app)` - Capture display/app state
* `click (element, coordinate=[x,y], button=left|right|middle)` - Click element/coord
* `double_click` / `right_click` / `middle_click`
* `drag (from_element, to_element)` - Drag between elements
* `scroll (direction=up|down|left|right, amount, element)` - Scroll viewport
* `type (text)` - Input text
* `key (keys="return|escape|modifier+key")` - Send key shortcuts
* `focus_app (app)` - Target specific app context

## Modifier Keys Reference
* **macOS:** `cmd+s` (Save), `cmd+t` (New tab), `cmd+w` (Close tab), `cmd+c`/`cmd+v` (Copy/Paste)
* **Windows/Linux:** `ctrl+s` (Save), `ctrl+t` (New tab), `ctrl+w` (Close tab), `ctrl+c`/`ctrl+v` (Copy/Paste)

## Safety Guardrails
- **No Unsafe Clicks:** Never click 2FA, password, payment, or permissions prompts.
- **No Secret Typing:** Never type passwords, credentials, or API keys.
- **No Host Interference:** Route inputs to background apps (avoid bringing windows forward unless asked).
