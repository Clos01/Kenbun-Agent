---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, applescript, screencapture]
  discovery_required: false
---

# Find My (Apple) Skill
Track Apple devices and AirTags via the FindMy.app on macOS using AppleScript and screen captures.

## Prerequisites
- macOS with Find My app and iCloud signed in
- Screen Recording permission for terminal (System Settings → Privacy → Screen Recording)
- Optional: `brew install steipete/tap/peekaboo` for UI automation

## Quick Reference
* **Open Find My App:**
  ```bash
  osascript -e 'tell application "FindMy" to activate'
  ```
* **Switch to Devices Tab:**
  ```bash
  osascript -e 'tell application "System Events" to tell process "FindMy" to click button "Devices" of toolbar 1 of window 1'
  ```
* **Capture UI Screenshot:**
  ```bash
  screencapture -w -o /tmp/findmy.png
  ```
