"""Write/refresh the Kenbun MCP server entry in Claude Desktop's config.

Fully environment-driven and path-portable: no secrets, hosts, ports, or
absolute user paths are hardcoded. Values are resolved from the process
environment first, then from the repo-local .env file, then from safe
localhost defaults. Filesystem paths are derived from this file's location,
so the script works from any clone on any machine.
"""

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_dotenv(path):
    """Minimal .env parser (KEY=VALUE, ignores blanks/comments)."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip().strip('"').strip("'")
    return values


_dotenv = load_dotenv(os.path.join(REPO_ROOT, ".env"))


def cfg(key, default=""):
    """Resolve a config value: real environment > .env file > default."""
    return os.environ.get(key) or _dotenv.get(key, default)


config_path = os.path.expanduser(
    "~/Library/Application Support/Claude/claude_desktop_config.json"
)
with open(config_path, "r") as f:
    config = json.load(f)

config.setdefault("mcpServers", {})

# Remove any legacy kenbun-agent entries (old naming).
for legacy in ("kenbun-agent", "Kenbun-agent"):
    config["mcpServers"].pop(legacy, None)

venv_python = os.path.join(REPO_ROOT, "core", ".venv", "bin", "python3")
server_entry = os.path.join(REPO_ROOT, "core", "tools", "infrastructure", "server.py")
pythonpath = os.pathsep.join(
    [
        os.path.join(REPO_ROOT, "core"),
        os.path.join(REPO_ROOT, "core", "tools"),
        REPO_ROOT,
    ]
)

server_env = {
    "CHROMA_HOST": cfg("CHROMA_HOST", "127.0.0.1"),
    "CHROMA_PORT": cfg("CHROMA_PORT", "8000"),
    "GEMINI_API_KEY": cfg("GEMINI_API_KEY"),
    "LM_STUDIO_PORT": cfg("LM_STUDIO_PORT", "1234"),
    "PC_IP_ADDRESS": cfg("PC_IP_ADDRESS", "127.0.0.1"),
    "PRIMARY_LLM_URL": cfg("PRIMARY_LLM_URL"),
    "PRIMARY_LLM_MODEL": cfg("PRIMARY_LLM_MODEL"),
    "INTERNAL_API_URL": cfg("INTERNAL_API_URL"),
    "PYTHONPATH": pythonpath,
}
# Drop empty credentials rather than writing blank keys.
server_env = {k: v for k, v in server_env.items() if v != ""}

if not server_env.get("GEMINI_API_KEY"):
    print("⚠️  GEMINI_API_KEY not found in environment or .env — "
          "the server will start without it. Set it in .env before running.")

config["mcpServers"]["kenbun-local"] = {
    "command": venv_python,
    "args": ["-u", server_entry],
    "env": server_env,
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print("Claude config updated successfully.")
