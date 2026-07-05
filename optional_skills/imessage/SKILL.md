---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, imsg]
  discovery_required: false
---

# iMessage Skill
Use the `imsg` CLI utility to read and send iMessage/SMS via macOS Messages.app.

## Prerequisites
- macOS with Messages.app signed in
- Install `imsg`: `brew install steipete/tap/imsg`
- Grant Full Disk Access for terminal (System Settings → Privacy → Full Disk Access)

## Quick Reference
* **List Chats:**
  ```bash
  imsg chats --limit 10 --json
  ```
* **View History:**
  ```bash
  imsg history --chat-id 1 --limit 20 --json
  ```
* **Send Messages:**
  ```bash
  imsg send --to "+14155551212" --text "Hello!"
  imsg send --to "+14155551212" --text "Hi" --service imessage
  ```
