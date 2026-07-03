---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, kenbun-agent]
  discovery_required: false
---

# Kenbun Agent Skill
Configure, extend, or contribute to Kenbun Agent (a fork of Nous Research's Hermes Agent). This skill provides CLI references, configuration details, profiles management, and troubleshooting strategies.

## Prerequisites
- Install: `curl -fsSL https://raw.githubusercontent.com/Clos01/Kenbun-Agent/main/install.sh | bash`
- Start chat session: `kenbun` or `kenbun chat`
- Interactive model setup: `kenbun model`
- Health check: `kenbun doctor`

## CLI Subcommands Reference
* **Chat Subcommands:**
  - `kenbun chat -q "query"` - Single query, non-interactive
  - `kenbun chat -m <model>` - Launch chat session with specific model
* **Configuration:**
  - `kenbun setup` - Run interactive setup wizard
  - `kenbun config` - View config
  - `kenbun config set <key> <val>` - Set config parameter
  - `kenbun config path` - Get path to `config.yaml`
  - `kenbun auth add <provider>` - Add API key or OAuth credentials
* **Tools & Skills:**
  - `kenbun tools` - Interactive curses UI to enable/disable tools
  - `kenbun skills list` - List installed skills
  - `kenbun skills install <id/url>` - Install a skill
* **Gateway & Scheduler:**
  - `kenbun gateway run` - Run messaging gateway in foreground
  - `kenbun cron list` - List cron jobs
  - `kenbun profile list` - List profiles

## Slash Commands (In-Session)
- `/new` or `/reset` - Start fresh session
- `/clear` - Clear terminal screen
- `/model <name>` - Switch model mid-session
- `/tools` - Manage enabled toolsets
- `/exit` or `/quit` - Close CLI session
- `/compact` - Compress context size
- `/help` - List all slash commands

## Profiles & Key Paths
* Config file: `~/.kenbun/config.yaml`
* Credentials env file: `~/.kenbun/.env` (profile-isolated keys)
* Skills directory: `~/.kenbun/skills/`
* Transcripts and sessions index: `~/.kenbun/sessions/`
* Main database: `~/.kenbun/state.db` (SQLite)
