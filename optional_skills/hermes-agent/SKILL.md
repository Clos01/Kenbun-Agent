---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, hermes-agent]
  discovery_required: false
---

# Hermes Agent Skill
Configure, extend, or contribute to Nous Research's Hermes Agent. This skill provides CLI references, configuration details, profiles management, and troubleshooting strategies.

## Prerequisites
- Install: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
- Start chat session: `hermes` or `hermes chat`
- Interactive model setup: `hermes model`
- Health check: `hermes doctor`

## CLI Subcommands Reference
* **Chat Subcommands:**
  - `hermes chat -q "query"` - Single query, non-interactive
  - `hermes chat -m <model>` - Launch chat session with specific model
* **Configuration:**
  - `hermes setup` - Run interactive setup wizard
  - `hermes config` - View config
  - `hermes config set <key> <val>` - Set config parameter
  - `hermes config path` - Get path to `config.yaml`
  - `hermes auth add <provider>` - Add API key or OAuth credentials
* **Tools & Skills:**
  - `hermes tools` - Interactive curses UI to enable/disable tools
  - `hermes skills list` - List installed skills
  - `hermes skills install <id/url>` - Install a skill
* **Gateway & Scheduler:**
  - `hermes gateway run` - Run messaging gateway in foreground
  - `hermes cron list` - List cron jobs
  - `hermes profile list` - List profiles

## Slash Commands (In-Session)
- `/new` or `/reset` - Start fresh session
- `/clear` - Clear terminal screen
- `/model <name>` - Switch model mid-session
- `/tools` - Manage enabled toolsets
- `/exit` or `/quit` - Close CLI session
- `/compact` - Compress context size
- `/help` - List all slash commands

## Profiles & Key Paths
* Config file: `~/.hermes/config.yaml`
* Credentials env file: `~/.hermes/.env` (profile-isolated keys)
* Skills directory: `~/.hermes/skills/`
* Transcripts and sessions index: `~/.hermes/sessions/`
* Main database: `~/.hermes/state.db` (SQLite)
