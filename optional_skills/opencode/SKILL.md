---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, opencode, git]
  discovery_required: false
---

# OpenCode CLI Skill
Use OpenCode as an autonomous coding worker orchestrated via terminal and process tools. OpenCode is a provider-agnostic, open-source AI coding agent with a TUI and CLI.

## Prerequisites
- Install OpenCode: `npm i -g opencode-ai@latest` or `brew install anomalyco/tap/opencode`
- Auth: `opencode auth login` or set provider environment variables (e.g. `OPENROUTER_API_KEY`)
- Verify setup: `opencode auth list`

## Quick Reference
* **One-Shot Tasks (opencode run):**
  ```bash
  opencode run 'Add retry logic to API calls and update tests'
  ```
* **Attach Context Files (-f):**
  ```bash
  opencode run 'Review this config for security issues' -f config.yaml -f .env.example
  ```
* **TUI Background Session (Interactive):**
  ```bash
  opencode                        # Launches interactive TUI
  ```
* **Resuming Sessions:**
  ```bash
  opencode -c                     # Continue last session
  opencode -s ses_abc123          # Continue specific session ID
  ```
* **Check Statistics & Cost:**
  ```bash
  opencode stats                  # Display token usage and costs
  ```

## Critical TUI Navigation
- **Submit Prompt:** Enter (press twice in some terminals to finalize and send).
- **Exit Cleanly:** Use `Ctrl+C` (do **NOT** use `/exit` as it is invalid and triggers the agent selector).
- **Agent Switch:** Tab (switches between build and plan agents).
