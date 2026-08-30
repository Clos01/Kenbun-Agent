# Google Antigravity 2.0 Quickstart & Reference Guide

Google Antigravity 2.0 is an agent-first desktop surface and platform co-optimized with Gemini training and evaluation stacks.

## 1. Getting Started & OS Requirements
- **Download**: [antigravity.google/download](https://antigravity.google/download)
- **macOS**: Supported macOS versions with active security updates (Min Version 12 Monterey). x86 (legacy Intel) is not supported.
- **Windows**: Windows 10 (64-bit).
- **Linux**: `glibc >= 2.28`, `glibcxx >= 3.4.25` (Ubuntu 20+, Debian 10+, Fedora 36+, RHEL 8+).

## 2. Installation & Desktop Dual-Wielding
- When prompted during update or installation: select **"Replace"**.
- Re-installing the IDE during installation is recommended for developers.
- **Dock Icons**:
  - **Antigravity 2.0**: Logo on a **white background**.
  - **Antigravity IDE**: Logo on top of a **black grid**.
- **Dual-Wielding**: It is recommended to dual-wield Antigravity 2.0 with your IDE of choice (Antigravity IDE, VS Code, Cursor, JetBrains).

## 3. Creating a Project & Booting Agents
1. Click the folder with a **"+"** icon in the left sidebar.
2. Click **"New Project"**.
3. Click **Add Folder** to associate local folders or Git repositories (adding multiple folders provides full cross-repository context).
4. Click **Create**.
5. Configure isolated Project settings & security policies if desired.

### Agent Bootup Modes
- **Local Mode**: Agent operates directly in active local workspace folders.
- **New Worktree Mode**: Agent operates in an isolated Git worktree to prevent workspace pollution.

## 4. Keybinding & Navigation Shortcuts
| Action | macOS | Windows / Linux |
|---|---|---|
| Open Conversation Picker | ⌘K | Ctrl + K |
| Open File Search | ⌘P | Ctrl + P |
| Focus Input | ⌘L | Ctrl + L |
| New Conversation | ⌘N | Ctrl + N |
| Next/Previous Conversation | ⌥ Up / Down | Alt + Up / Down |

## 5. Native Slash Commands
- `/goal`: Autonomous end-to-end execution mode. Runs until the specified task is finished without asking for intermediate input.
- `/grill-me`: Pre-implementation interview mode. Asks clarifying questions to align on plan details before writing code.
- `/schedule`: Runs instructions as a one-time timer or recurring cron schedule via Scheduled Tasks.
- `/browser`: Enables browser debugging primitives using Google Chrome (requires Chrome permissions).

## 6. Synergy with Kenbun Orchestrator
When Kenbun runs under Antigravity 2.0, the `orchestrate` meta-tool integrates Kenbun's System 2/3 tools (`consult_supervisor`, `audit_guardrail`, `save_to_hivemind`, `planka_*`) with Antigravity 2.0 primitives (`/goal`, `/grill-me`, `/schedule`, `/browser`, Local/Worktree modes) while maintaining clean platform isolation when executed from Claude Desktop.
