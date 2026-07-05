---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, claude-code, tmux]
  discovery_required: false
---

# Claude Code Skill
Delegate coding tasks to Claude Code (Anthropic's autonomous coding agent CLI) via the terminal. Claude Code can read files, write code, run shell commands, spawn subagents, and manage git workflows.

## Prerequisites
- Install: `npm install -g @anthropic-ai/claude-code`
- Auth: Run `claude` once to log in (or set `ANTHROPIC_API_KEY`)
- Health check: `claude doctor`
- Version check: `claude --version` (requires v2.x+)

## Quick Reference
* **Print Mode (Non-Interactive, Preferred for Automation):**
  ```bash
  claude -p "Add error handling to all API calls in src/" --allowedTools "Read,Edit" --max-turns 10
  ```
* **Interactive Mode (via tmux for Multi-Turn Sessions):**
  ```bash
  # Start session
  tmux new-session -d -s claude-work -x 140 -y 40
  tmux send-keys -t claude-work "cd /path/to/project && claude" Enter
  sleep 5
  
  # Send task
  tmux send-keys -t claude-work "Refactor the auth module" Enter
  sleep 15
  
  # Capture status
  tmux capture-pane -t claude-work -p -S -50
  
  # Exit session
  tmux send-keys -t claude-work "/exit" Enter
  ```
* **CLI Subcommands:**
  - `claude` - Start interactive REPL
  - `claude -c` - Continue the most recent conversation in this directory
  - `claude -r <id>` - Resume a specific session by ID or name
  - `claude update` - Update Claude Code to the latest version

## Dialog Handling in tmux (Critical)
* **Workspace Trust:** Press Enter to accept the default ("Yes, I trust this folder").
  ```bash
  tmux send-keys -t claude-work Enter
  ```
* **Bypass Permissions Warning:** Send Down, then Enter to select "Yes, I accept".
  ```bash
  tmux send-keys -t claude-work Down && sleep 0.3 && tmux send-keys -t claude-work Enter
  ```
