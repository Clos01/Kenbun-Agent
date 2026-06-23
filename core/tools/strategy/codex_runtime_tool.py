import os
import sys
import json
import logging
import subprocess
import re
from pathlib import Path
from tools.registry import sovereign_tool
from tools.infrastructure.config import settings

logger = logging.getLogger("codex_runtime_tool")

def check_codex_installed() -> bool:
    try:
        # Check if codex is in PATH
        result = subprocess.run(
            ["codex", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def update_env_variable(key: str, value: str):
    from tools.infrastructure.config import discover_env_file
    env_path = Path(discover_env_file())
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")
        return
        
    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break
            
    if not updated:
        lines.append(f"{key}={value}")
        
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def update_codex_config(project_root: str, venv_python: str):
    codex_dir = Path.home() / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    config_toml_path = codex_dir / "config.toml"
    
    # Expose kenbun-tools MCP server
    managed_block = f"""# managed by kenbun-agent
default_permissions = ":workspace"

[mcp_servers.kenbun-tools]
command = "{venv_python}"
args = ["-m", "tools.infrastructure.server"]
env = {{ KENBUN_HOME = "{project_root}", PYTHONPATH = "{project_root}/core" }}
startup_timeout_sec = 30.0
tool_timeout_sec = 600.0
# end kenbun-agent managed section"""

    content = ""
    if config_toml_path.exists():
        content = config_toml_path.read_text(encoding="utf-8")
        
    # Replace or append the managed section
    pattern = r"# managed by kenbun-agent.*?# end kenbun-agent managed section"
    if re.search(pattern, content, re.DOTALL):
        new_content = re.sub(pattern, managed_block, content, flags=re.DOTALL)
    else:
        # Append to the end
        if content and not content.endswith("\n"):
            content += "\n"
        new_content = content + managed_block + "\n"
        
    config_toml_path.write_text(new_content, encoding="utf-8")

@sovereign_tool(name="codex_runtime", category="Strategy")
def codex_runtime(action: str = "") -> str:
    """
    Manage the OpenAI Codex App-Server Runtime integration in Kenbun.
    
    Supported Actions:
      - 'status' (or empty): Check if the Codex runtime is currently enabled or disabled.
      - 'on' (or 'codex_app_server'): Enable Codex app-server runtime.
      - 'off' (or 'auto'): Disable Codex app-server and return to default Kenbun runtime.
      
    Args:
      action: The runtime configuration action to perform ('status', 'on', 'off').
    """
    action_clean = action.strip().lower()
    
    current_mode = settings.models.openai_runtime
    
    if not action_clean or action_clean == "status":
        return json.dumps({
            "status": "success",
            "current_runtime": current_mode,
            "is_enabled": current_mode == "codex_app_server"
        }, indent=2)
        
    elif action_clean in ("on", "codex_app_server"):
        # 1. Pre-flight check
        if not check_codex_installed():
            return json.dumps({
                "status": "error",
                "message": "❌ Codex CLI is not installed on this system.\n"
                           "Please install it first by running:\n"
                           "   npm install -g @openai/codex\n"
                           "And make sure to log in using:\n"
                           "   codex login"
            }, indent=2)
            
        # 2. Update .env file
        update_env_variable("OPENAI_RUNTIME", "codex_app_server")
        
        # 3. Resolve project root and virtual environment python path
        project_root = str(settings.PROJECT_ROOT)
        venv_python = str(Path(project_root) / ".venv" / "bin" / "python")
        if not os.path.exists(venv_python):
            # Fallback to sys.executable if venv python doesn't exist
            venv_python = sys.executable
            
        # 4. Update ~/.codex/config.toml
        try:
            update_codex_config(project_root, venv_python)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Failed to update Codex config.toml: {e}"
            }, indent=2)
            
        return json.dumps({
            "status": "success",
            "message": "Successfully enabled OpenAI Codex App-Server Runtime.\n"
                       "Kenbun will route appropriate turns through Codex app-server.\n"
                       "Changes will take effect on the next session.",
            "openai_runtime": "codex_app_server"
        }, indent=2)
        
    elif action_clean in ("off", "auto"):
        update_env_variable("OPENAI_RUNTIME", "auto")
        return json.dumps({
            "status": "success",
            "message": "Successfully disabled OpenAI Codex App-Server Runtime.\n"
                       "Kenbun will use the default sovereign agent loop runtime.",
            "openai_runtime": "auto"
        }, indent=2)
        
    else:
        return json.dumps({
            "status": "error",
            "message": f"Unknown action '{action}'. Action must be status, on, or off."
        }, indent=2)
