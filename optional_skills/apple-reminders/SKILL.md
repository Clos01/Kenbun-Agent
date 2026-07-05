---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, remindctl]
  discovery_required: false
---

# Apple Reminders Skill
Use the `remindctl` CLI utility to manage Apple Reminders directly from the terminal. Tasks automatically sync across all Apple devices via iCloud.

## Prerequisites
- macOS with Reminders.app
- Install `remindctl`: `brew install steipete/tap/remindctl`
- Grant Reminders permission when prompted
- Verify status: `remindctl status`

## Quick Reference
* **View Reminders:**
  ```bash
  remindctl                    # Today's reminders
  remindctl list               # List all reminder lists
  ```
* **Create Reminders:**
  ```bash
  remindctl add "Buy milk"
  remindctl add --title "Call mom" --list Personal --due tomorrow
  ```
* **Complete/Delete:**
  ```bash
  remindctl complete <id>      # Complete by ID
  remindctl delete <id> --force # Delete by ID
  ```
