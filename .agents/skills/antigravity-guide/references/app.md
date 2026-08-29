# Antigravity 2.0 Reference

Google Antigravity 2.0 is an agent-first desktop application that launches and monitors agents independently of an IDE. It is co-optimized across product, agent harness, and model layers with Gemini evaluation stacks.

## 1. Installation & OS Compatibility
- **Download**: `antigravity.google/download`
- **macOS**: macOS 12 (Monterey) or higher. x86 builds are not supported.
- **Windows**: Windows 10 (64-bit).
- **Linux**: `glibc >= 2.28`, `glibcxx >= 3.4.25`.
- **Installation Note**: Select "Replace" when updating. The application icon displays the Antigravity logo on a white background, distinguishing it from the Antigravity IDE (black grid background).

## 2. Projects & Agent Spawn Modes
- **Projects**: Group local directories and Git repositories into isolated workspace boundaries. Association of multiple folders gives the agent full cross-repository context.
- **Agent Modes**:
  - **Local Mode**: Operates directly inside the active folders.
  - **New Worktree Mode**: Operates in an isolated Git worktree for safe code experimentation.

## 3. Navigation Shortcuts & Slash Commands
### Keyboard Navigation
- Open Conversation Picker: `⌘K` (macOS) / `Ctrl + K` (Windows/Linux)
- Open File Search: `⌘P` (macOS) / `Ctrl + P` (Windows/Linux)
- Focus Input: `⌘L` (macOS) / `Ctrl + L` (Windows/Linux)
- New Conversation: `⌘N` (macOS) / `Ctrl + N` (Windows/Linux)
- Next/Previous Conversation: `⌥ Up/Down` (macOS) / `Alt + Up/Down` (Windows/Linux)

### Core Slash Commands
- `/goal`: Runs until the specified task is completely finished without prompting for intermediate input.
- `/grill-me`: Conducts an interview-style questionnaire before implementing code to align on requirements.
- `/schedule`: Schedules one-time timers or recurring cron tasks via the Scheduled Tasks manager.
- `/browser`: Engages Chrome browser automation primitives for web browsing tasks.

## 4. Agent Settings & Permissions
- **Global Settings**: Model Selection, Tool Execution Policy, Terminal Sandbox, Internet & File Access Policies, Command Allow/Deny Lists, Browser Allowlist, Artifact Review Mode.
- **Project-Level Settings**: Per-project overrides for sandbox policies, auto-execution permissions, and file boundary access rules.

## 5. Architectural Positioning
Antigravity 2.0 is designed to dual-wield alongside an IDE (whether Antigravity IDE or third-party IDEs like VS Code, Cursor, JetBrains). In upcoming releases, the Agent Manager will be decoupled from the Antigravity IDE, transforming the IDE into a pure agent-powered surface while Antigravity 2.0 serves as the primary agent orchestration desktop platform.
