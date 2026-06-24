---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, memo]
  discovery_required: false
---

# Apple Notes Skill
Use the `memo` CLI utility to manage Apple Notes directly from the terminal. Notes automatically sync across all Apple devices via iCloud.

## Prerequisites
- macOS with Notes.app
- Install `memo`: `brew tap antoniorodr/memo && brew install antoniorodr/memo/memo`
- Grant Automation access to Notes.app when prompted (System Settings → Privacy → Automation)

## Quick Reference
* **View Notes:**
  ```bash
  memo notes                        # List all notes
  memo notes -f "Folder Name"       # Filter by folder
  memo notes -s "query"             # Search notes (fuzzy)
  ```
* **Create Notes:**
  ```bash
  memo notes -a "Note Title"        # Quick add with title
  ```
* **Edit/Delete Notes:**
  ```bash
  memo notes -e                     # Interactive selection to edit
  memo notes -d                     # Interactive selection to delete
  ```
