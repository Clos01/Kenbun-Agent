---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, codex, git]
  discovery_required: false
---

# Codex CLI Skill
Delegate coding tasks to OpenAI Codex CLI via the terminal. Codex is an autonomous coding agent CLI.

## Prerequisites
- Install Codex: `npm install -g @openai/codex`
- Auth: Configure `OPENAI_API_KEY` or setup Codex OAuth credentials
- Must run inside a git repository
- Use `pty=true` in terminal calls (or run interactively)

## Quick Reference
* **One-Shot Tasks:**
  ```bash
  codex exec 'Add dark mode toggle to settings'
  ```
* **For Scratch Work (initializes a temporary git repo):**
  ```bash
  cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'
  ```
* **Bypass Sandbox (for bubblewrap/user-namespace permission issues):**
  ```bash
  codex exec --sandbox danger-full-access 'Task description'
  ```
* **Key Flags:**
  - `exec "prompt"` - One-shot execution
  - `--full-auto` - Auto-approves file changes in the workspace sandbox
  - `--yolo` - Direct host execution, bypasses sandbox and approvals (use with caution)
  
## PR Reviews and Parallel Execution
* **PR Review:**
  ```bash
  REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main
  ```
* **Parallel Worktrees:**
  ```bash
  git worktree add -b fix/issue-78 /tmp/issue-78 main
  codex --yolo exec 'Fix issue #78' --workdir /tmp/issue-78
  ```
