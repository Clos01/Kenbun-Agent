#!/usr/bin/env python3
"""
🌸 Kenbun Termchat & Reflex Shell (CLI Agent REPL)
Allows developers to chat with Kenbun-Agent's LLM, query design guides,
and authorize the local Ollama/Cloud LLM to execute safe shell commands
and repair system errors in real time.
"""
import os
import sys
import json
import re
import time
import requests
import subprocess
import shutil
import threading
import tempfile
import signal
import unicodedata
from pathlib import Path
from typing import Optional

# Silence noisy ONNX C++ runtime warnings on CPU-only or non-standard GPU architectures
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["ORT_LOGGING_LEVEL"] = "3"

# prompt_toolkit for robust terminal input
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.patch_stdout import patch_stdout
except ImportError:
    PromptSession = None
    ANSI = None
    from contextlib import nullcontext
    patch_stdout = nullcontext


# Sub-agent bus
try:
    from scripts.agent_bus import spawn_agent, list_agents, kill_agent, purge_agents, poll_status_lines
except ImportError:
    try:
        from agent_bus import spawn_agent, list_agents, kill_agent, purge_agents, poll_status_lines
    except ImportError:
        spawn_agent = list_agents = kill_agent = purge_agents = poll_status_lines = None

from core.tools.audit.yolo_sandbox import YOLO_BLOCKLIST, is_yolo_safe, is_command_destructive
from core.tools.utils.console_ui import (
    C_P, C_G, C_Y, C_C, C_W, C_D, C_R, C_RED, C_BOLD, C_DIM,
    ANSI_ESCAPE, visible_len, get_columns, clean_wrap_text,
    draw_box as _fallback_draw_box,
    print_ollama_memory_education, explain_command, StreamingRenderer, StreamingWordWrapper
)
# 🌸 Premium Rich UI layer (Hermes-inspired)
try:
    from core.tools.cli.ui.renderer import UIRenderer
    _ui = UIRenderer()
except Exception:
    _ui = None

# ANSI escape sequence to restore standard terminal input modes and clear raw state
TERMINAL_RESET_SEQUENCE = (
    "\x1b[?1006l"  # disable SGR mouse
    "\x1b[?1003l"  # disable any-motion tracking
    "\x1b[?1002l"  # disable button-motion tracking
    "\x1b[?1000l"  # disable click tracking
    "\x1b[?1004l"  # disable focus events
    "\x1b[?2004l"  # disable bracketed paste
    "\x1b[?1049l"  # leave alt screen (if stuck there)
    "\x1b[<u"      # pop kitty keyboard mode
    "\x1b[>4m"     # reset modifyOtherKeys
    "\x1b[0m"      # reset text attributes
    "\x1b[?25h"    # ensure cursor visible
)


def draw_box(lines, title=None, border_color=C_G, text_color=C_W):
    if _ui:
        style = "default"
        if border_color == C_RED or border_color == C_R:
            style = "error"
        elif border_color == C_Y:
            style = "warning"
        elif border_color == C_G:
            style = "success"
        elif border_color == C_P:
            style = "default"
        elif border_color == C_C:
            style = "info"
            
        if isinstance(lines, str):
            lines = [lines]
        _ui.print_panel(lines, title=title or "", style=style)
    else:
        _fallback_draw_box(lines, title=title, border_color=border_color, text_color=text_color)

from core.tools.utils.env_builder import decrypt_value, update_env_value, load_env_vars
from core.tools.infrastructure.ai_gateway import (
    detect_configuration_mismatch, check_and_heal_mismatch,
    detect_model_tier, run_startup_probe, print_health_card,
    build_system_prompt
)

# Thread lock to guarantee safe parallel writes
_backup_lock = threading.Lock()

# Common keywords/placeholders that should NOT be redacted
EXCLUSIONS = {
    "true", "false", "null", "none", "default", "undefined",
    "yes", "no", "active", "inactive", "enabled", "disabled",
    "localhost", "127.0.0.1", "root", "admin", "password", "secret"
}

def scrub_secrets(text: str) -> str:
    """
    Analyzes, detects, and redacts high-entropy credentials, tokens, API keys,
    passwords, and database connection strings from dialogue, console logs,
    and session backups.
    """
    if not isinstance(text, str) or not text:
        return text

    # 1. Redact Private Keys (RSA, EC, etc.)
    private_key_pattern = r'(?s)-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----'
    text = re.sub(private_key_pattern, '******** [REDACTED PRIVATE KEY]', text)

    # 2. Redact Bearer Tokens
    text = re.sub(r'\bBearer\s+[a-zA-Z0-9\-\._~+/]+=*', 'Bearer ******** [REDACTED]', text)

    # 3. Redact Specific API Keys
    # OpenAI legacy keys
    text = re.sub(r'\bsk-[a-zA-Z0-9]{48}\b', '******** [REDACTED]', text)
    # OpenAI modern keys (sk-proj-...)
    text = re.sub(r'\bsk-proj-[a-zA-Z0-9\-_]{40,100}\b', '******** [REDACTED]', text)
    # DeepSeek keys (often sk- followed by hex or alphanumeric)
    text = re.sub(r'\bsk-[a-fA-F0-9]{32}\b', '******** [REDACTED]', text)
    text = re.sub(r'\bsk-[a-zA-Z0-9]{32}\b', '******** [REDACTED]', text)
    # Gemini API keys (AIzaSy...)
    text = re.sub(r'\bAIzaSy[a-zA-Z0-9\-_]{33}\b', '******** [REDACTED]', text)
    # Slack tokens (xoxb, xoxp, xoxr, xoxs)
    text = re.sub(r'\bxox[baprs]-[a-zA-Z0-9\-]{10,100}\b', '******** [REDACTED]', text)
    # AWS Access Key IDs
    text = re.sub(r'\bAKIA[A-Z0-9]{16}\b', '******** [REDACTED]', text)

    # 4. Redact Passwords in Database Connection Strings / URIs
    # E.g., postgresql://user:password@host:port/db
    conn_string_pattern = r'\b([a-zA-Z\+]+://)([^:\s]+):([^@\s]+)(@[^\s]+)\b'
    def replace_conn_string(match):
        protocol = match.group(1)
        user = match.group(2)
        password = match.group(3)
        host_part = match.group(4)
        
        # Don't redact if the password looks like a placeholder
        if password.lower() in EXCLUSIONS or "redacted" in password.lower() or all(c == '*' for c in password):
            return match.group(0)
            
        return f"{protocol}{user}:******** [REDACTED]{host_part}"
        
    text = re.sub(conn_string_pattern, replace_conn_string, text)

    # 5. Heuristic Key-Value Assignment Scanner (variables, envs, json fields)
    # Handles: key="value", secret: 'value', password=value, API_KEY: value, etc.
    def replace_heuristic(match):
        match.group(1)
        quote = match.group(2) or ''
        value = match.group(3)
        
        val_lower = value.lower()
        # Avoid redacting already redacted tokens, empty values, very short values, or common placeholders
        if (len(value) < 6 or
            val_lower in EXCLUSIONS or 
            "redacted" in val_lower or 
            all(c == '*' for c in value) or
            all(c == 'x' for c in val_lower)):
            return match.group(0)
            
        # Match pattern formatting exactly
        sep = ":" if ":" in match.group(0) else "="
        
        # Preserve original spacing around '=' or ':'
        orig_match = match.group(0)
        # Split by separator to get the prefix before separator
        parts = orig_match.split(sep, 1)
        prefix_part = parts[0]
        
        return f"{prefix_part}{sep}{quote}******** [REDACTED]{quote}"

    # Quoted heuristic values: key = "value"
    quoted_pattern = r'(?i)\b(key|secret|token|password|pass|pwd|auth_key|private_key|api_key|client_secret)\s*[:=]\s*(["\'])(.*?)\2'
    text = re.sub(quoted_pattern, replace_heuristic, text)

    # Unquoted heuristic values: key=value
    unquoted_pattern = r'(?i)\b(key|secret|token|password|pass|pwd|auth_key|private_key|api_key|client_secret)\s*[:=]\s*()([^\s"\',;]+)'
    text = re.sub(unquoted_pattern, replace_heuristic, text)

    return text

def sanitize_input(text):
    """
    Strips dangerous invisible Unicode characters, control sequences, and non-printable
    sequences from user raw terminal inputs before logging or appending them to history.
    Keeps only standard ASCII and printable UTF-8.
    """
    if not isinstance(text, str):
        return ""
    
    # Strict input length validation to prevent Resource Exhaustion (OOM)
    if len(text) > 65536:
        raise ValueError("Security Violation: Input length exceeds maximum allowed limit.")
    
    # 1. Strip ANSI escape sequences to prevent raw terminal control code bypasses
    ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_pattern.sub('', text)
    
    sanitized_chars = []
    for char in text:
        cat = unicodedata.category(char)
        # Cc (Control) is filtered except for \n, \r, \t
        if cat == 'Cc':
            if char in ('\n', '\r', '\t'):
                sanitized_chars.append(char)
            continue
        # Cf (Format), Cs (Surrogate), Co (Private Use), Cn (Unassigned) are stripped
        if cat in ('Cf', 'Cs', 'Co', 'Cn'):
            continue
        sanitized_chars.append(char)
        
    return "".join(sanitized_chars)

def prune_dialog_history(history, max_turns=20, max_chars=32000):
    """
    Sliding-window context history pruner.
    - Always preserves the system prompt at index 0 (history[0]).
    - If the len(history) > max_turns, prune the oldest turns (matching pairs of user-assistant messages).
    - If the sum of characters of all messages in history exceeds max_chars, prune the oldest turns.
    """
    if not history:
        return []
    if len(history) <= 1:
        return history
        
    def get_char_count(hist):
        return sum(len(m.get("content", "")) for m in hist)
        
    # Prune by max_turns (pruning matching pairs of user-assistant messages)
    while len(history) > max_turns:
        if len(history) >= 3:
            # Pop index 1 and 2 (the oldest user-assistant turn after system prompt)
            history.pop(1)
            history.pop(1)
        else:
            break
            
    # Prune by max_chars (pruning matching pairs of user-assistant messages)
    while get_char_count(history) > max_chars:
        if len(history) >= 3:
            history.pop(1)
            history.pop(1)
        else:
            break
            
    return history

def save_session_backup(history, cwd, llm_url, llm_model):
    """
    Serializes the active chat session state atomically and thread-safely
    to avoid file corruption on sudden terminal crashes or process terminations.
    All dialogue history is scrubbed defensively before serializing to disk.
    """
    global active_brain_health_dir
    with _backup_lock:
        local_dir = active_brain_health_dir
        if not local_dir:
            raise ValueError("Security Violation: Active brain health directory not set.")
        
        # Resolve project root dynamically to prevent NameError or ModuleNotFoundError
        try:
            from core.tools.infrastructure.config import settings
            project_root = settings.PROJECT_ROOT.resolve()
        except Exception:
            try:
                from core.tools.utils.path_utils import get_project_root
                project_root = get_project_root().resolve()
            except Exception:
                project_root = Path(__file__).resolve().parent.parent

        # Enforce strict path traversal check: backup folder must be strictly under Home or Project Root
        allowed_roots = [Path.home().resolve(), project_root, Path(active_brain_health_dir).resolve()]
        resolved_dir = Path(local_dir).resolve()
        if not any(resolved_dir == root or resolved_dir.is_relative_to(root) for root in allowed_roots):
            raise ValueError("Security Violation: Backup directory outside allowed boundaries.")
            
        # Strict validation on user-influenced parameters using robust whitelist to prevent shell injections (no slash allowed)
        if not re.match(r"^[a-zA-Z0-9.:\-_]+$", str(llm_model)):
            raise ValueError("Security Violation: Invalid character in LLM model name.")
            
        safe_model = str(llm_model)
        safe_url = scrub_secrets(str(llm_url))
        
        backup_path = resolved_dir / "active_session_backup.json"
        
        # Scrub the dialogue history copy defensively before persisting
        scrubbed_history = []
        for msg in history:
            scrubbed_msg = msg.copy()
            if "content" in scrubbed_msg:
                scrubbed_msg["content"] = scrub_secrets(scrubbed_msg["content"])
            scrubbed_history.append(scrubbed_msg)
        
        data = {
            "history": scrubbed_history,
            "cwd": str(cwd),
            "llm_url": safe_url,
            "llm_model": safe_model
        }
        
        temp_fd = None
        temp_path = None
        try:
            # Create a temp file in the same directory to guarantee atomic rename (same partition)
            fd, temp_path = tempfile.mkstemp(dir=str(resolved_dir), suffix=".tmp")
            temp_fd = os.fdopen(fd, 'w')
            json.dump(data, temp_fd, indent=2)
            
            # Ensure physical write to disk before atomic replace (crash prevention)
            temp_fd.flush()
            os.fsync(fd)
            temp_fd.close()
            temp_fd = None
            
            Path(temp_path).replace(backup_path)
        except Exception as e:
            # Cleanup temporary file if it failed
            if temp_fd:
                try:
                    temp_fd.close()
                except Exception:
                    pass
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            # Re-raise to prevent masking configuration or system errors
            raise e




# ── YOLO Mode state ────────────────────────────────────────────
YOLO_MODE = False





def graceful_exit_handler(signum, frame):
    """
    POSIX signal handler to gracefully exit when Ctrl+C (SIGINT) or SIGTERM is received.
    It prints a beautiful Sakura/Limestone closing card, restores terminal text color,
    deletes the active_session_backup.json if it was a clean exit, and exits cleanly.
    """
    global active_brain_health_dir
    
    # Finish any unfinished prompt line
    sys.stdout.write("\n")
    
    # Draw a professional Limestone/Sakura styled closing card
    closing_message = [
        "🌸 Thank you for using Kenbun Agent!",
        "Restoring terminal session state and performing diagnostics cleanup...",
        "---",
        "Sayonara! 👋"
    ]
    draw_box(closing_message, title="🌸 KENBUN DISCONNECTING", border_color=C_P, text_color=C_G)
    
    # Restore terminal text color (ANSI Reset)
    sys.stdout.write(C_R)
    sys.stdout.flush()
    
    # Cleanly delete active_session_backup.json
    if active_brain_health_dir:
        backup_path = Path(active_brain_health_dir) / "active_session_backup.json"
        if backup_path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass
                
    sys.exit(0)



# Global tracking variable for active memory directory

active_brain_health_dir = None



def get_design_suggestions(query):
    """Fallback search using scripts/search.py if available."""
    search_script = Path(__file__).parent / "search.py"
    if not search_script.exists():
        search_script = Path(__file__).parent.parent / "src" / "ui-ux-pro-max" / "scripts" / "search.py"
    
    if search_script.exists():
        try:
            res = subprocess.run(
                ["python3", str(search_script), query, "-n", "2"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
    return None

def read_secure_file(path_obj: Path, base_dir: Path, max_bytes: int = 51200) -> Optional[str]:
    """
    Securely reads a file inside base_dir, preventing TOCTOU, intermediate/leaf symlinks,
    and path traversal.
    """
    # Verify required flags are present on the host OS
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("os.O_NOFOLLOW is required for secure file operations.")
    
    from contextlib import ExitStack
    stack = ExitStack()
    try:
        # Resolve the base directory to get its canonical absolute path
        resolved_base = base_dir.resolve(strict=True)
        
        # Purely lexical path validation of the target path to prevent path traversal
        # We do not call .resolve() on path_obj to eliminate the TOCTOU window between
        # resolution and step-by-step opening.
        target_abs = Path(os.path.normpath(resolved_base / path_obj))
        
        # Verify boundary condition lexically
        if not target_abs.is_relative_to(resolved_base):
            raise ValueError(f"Path traversal detected: {path_obj} is outside {base_dir}")
            
        rel_path = target_abs.relative_to(resolved_base)
        parts = rel_path.parts
        
        # 1. Open the base directory first (O_DIRECTORY blocks regular files)
        # We include O_NOFOLLOW to ensure resolved_base itself wasn't replaced by a symlink.
        flags_base = os.O_RDONLY | os.O_NOFOLLOW
        if hasattr(os, "O_DIRECTORY"):
            flags_base |= os.O_DIRECTORY
        if hasattr(os, "O_CLOEXEC"):
            flags_base |= os.O_CLOEXEC
            
        current_dir_fd = os.open(str(resolved_base), flags_base)
        stack.callback(os.close, current_dir_fd)
        
        # 2. Traverse down each component step-by-step
        file_fd = -1
        for idx, part in enumerate(parts):
            # Strict validation: block lexical directory traversal tokens
            if part in ("..", ".", "/"):
                raise ValueError("Invalid path component in secure file read.")
                
            is_last = (idx == len(parts) - 1)
            
            # Formulate open flags. O_NOFOLLOW is mandatory at every step.
            flags = os.O_RDONLY | os.O_NOFOLLOW
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
                
            if not is_last:
                if hasattr(os, "O_DIRECTORY"):
                    flags |= os.O_DIRECTORY
                # Open the directory component relative to current_dir_fd
                next_fd = os.open(part, flags, dir_fd=current_dir_fd)
                stack.callback(os.close, next_fd)
                current_dir_fd = next_fd
            else:
                # Open leaf file relative to current_dir_fd
                file_fd = os.open(part, flags, dir_fd=current_dir_fd)
                stack.callback(os.close, file_fd)
                
        if file_fd == -1:
            raise FileNotFoundError("Target leaf file not opened.")
            
        # 3. Verify stats on the open descriptor (prevents metadata TOCTOU)
        stat_info = os.fstat(file_fd)
        import stat
        if not stat.S_ISREG(stat_info.st_mode):
            raise ValueError("Target path is not a regular file.")
        if stat_info.st_size > max_bytes:
            raise ValueError("Target file exceeds maximum allowed size.")
            
        # 4. Read from file descriptor
        raw_bytes = os.read(file_fd, max_bytes)
        return raw_bytes.decode("utf-8")
        
    except (FileNotFoundError, PermissionError, ValueError) as e:
        log_event(f"ℹ️ Secure file access exception (handled): {e}")
        return None
    except UnicodeDecodeError as e:
        log_event(f"⚠️ Secure file decode error: {e}")
        return None
    except Exception as e:
        log_event(f"🚨 Unhandled secure file reader error: {e}")
        return None
    finally:
        stack.close()

def get_harvested_tools():
    """Dynamically sweeps the core directory and returns all registered sovereign tools."""
    try:
        project_root = get_active_project_root()
        core_path = project_root / "core"
        if not core_path.exists() or not (core_path / "tools").exists():
            return {}
            
        # We DO NOT dynamically inject into sys.path to prevent module hijacking.
        # PYTHONPATH is verified at boot time.
        from core.tools.harvester import harvest_and_register_tools
        from core.tools.registry import registry
        
        harvest_and_register_tools(core_path / "tools")
        return registry.get_all_tools()
    except Exception as e:
        log_event(f"⚠️ Tool Harvester warning: {e}")
        return {}

def get_harvested_skills():
    """Scans and parses frontmatter from all design and template SKILL.md files."""
    skills = {}
    try:
        project_root = get_active_project_root()
        skills_dir = project_root / "core" / "tools" / "skills"
            
        if skills_dir.exists() and skills_dir.is_dir():
            # Resource constraint: limit folder count to prevent Denial of Service (DoS)
            folders = [p for p in skills_dir.iterdir() if p.is_dir()]
            if len(folders) > 100:
                folders = folders[:100]
                
            for p in folders:
                folder_name = p.name
                skill_md_path = p / "SKILL.md"
                content = read_secure_file(skill_md_path, skills_dir)
                if not content:
                    continue
                    
                yaml_meta = {}
                desc = ""
                triggers = []
                
                match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
                if match:
                    yaml_str = match.group(1)
                    # Hardened secure YAML parsing utilizing PyYAML's SafeLoader
                    try:
                        import yaml
                        yaml_meta = yaml.load(yaml_str, Loader=yaml.SafeLoader) or {}
                    except Exception:
                        pass
                        
                name = yaml_meta.get("name", folder_name) if isinstance(yaml_meta, dict) else folder_name
                if isinstance(yaml_meta, dict):
                    desc = yaml_meta.get("description", "")
                    triggers = yaml_meta.get("triggers", [])
                    if not isinstance(triggers, list):
                        triggers = []
                
                if not desc:
                    m_hdr = re.search(r"^#\s+(.*?)$", content, re.MULTILINE)
                    desc = m_hdr.group(1).strip() if m_hdr else "No description provided."
                    
                skills[name] = {
                    "name": name,
                    "path": str(p),
                    "description": desc,
                    "triggers": triggers,
                    "content": content
                }
    except Exception as e:
        log_event(f"⚠️ Skills Harvester warning: {e}")
    return skills

def get_active_project_root():
    """Robust helper matching config.py path discovery."""
    if os.getenv("PROJECT_ROOT"):
        return Path(os.getenv("PROJECT_ROOT"))
    docker_path = Path("/app")
    if docker_path.exists() and (docker_path / "tools").exists():
        return docker_path
    current = Path(__file__).resolve().parent.parent
    return current

def gather_system_telemetry():
    """Gathers real-time diagnostic and environment telemetry (Zero-overhead)."""
    telemetry = []
    
    # 1. Check Docker socket permissions
    sock_path = "/var/run/docker.sock"
    has_sock = os.path.exists(sock_path)
    has_access = os.access(sock_path, os.W_OK) if has_sock else False
    
    telemetry.append(f"Docker Socket: Exists={has_sock}, WriteAccess={has_access}")
    
    # 2. Check Docker daemon status quickly
    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            res = subprocess.run([docker_bin, "info"], capture_output=True, text=True, timeout=2)
            telemetry.append(f"Docker Daemon Status: Active={res.returncode == 0}")
        except Exception:
            telemetry.append("Docker Daemon Status: Unresponsive/Offline")
    else:
        telemetry.append("Docker Daemon Status: CLI Not Installed")
        
    # 3. Check active containers
    if docker_bin:
        try:
            res = subprocess.run([docker_bin, "ps", "--format", "{{.Names}}: {{.Status}}"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                containers = res.stdout.strip().replace("\n", ", ")
                telemetry.append(f"Active Containers: [{containers}]")
            else:
                telemetry.append("Active Containers: None running")
        except Exception:
            pass
            
    # 4. Check active ports
    try:
        # Check if UFW is active
        ufw_check = subprocess.run(["sudo", "-n", "ufw", "status"], capture_output=True, text=True, timeout=1)
        if ufw_check.returncode == 0:
            status = "active" if "active" in ufw_check.stdout.lower() else "inactive"
            telemetry.append(f"UFW Firewall: Status={status}")
    except Exception:
        pass
        
    return "\n".join(telemetry)



def check_and_migrate_project_memory(old_dirs, original_cwd=None):
    """Detects if a new workspace project was created, and attaches active memories/WAL DB to it."""
    global active_brain_health_dir
    if not active_brain_health_dir:
        return
        
    cwd = original_cwd if original_cwd else Path.cwd().resolve()
    try:
        cwd = Path(cwd).resolve()
    except Exception:
        pass

    # Gather current directories recursively up to depth 3 (pruning hidden/system paths)
    def scan_dirs_recursive(path, depth, max_depth=3):
        if depth > max_depth:
            return set()
        dirs = set()
        try:
            for p in path.iterdir():
                if p.is_dir() and not p.name.startswith(".") and p.name not in ("venv", "node_modules", "brain_health"):
                    dirs.add(p)
                    dirs.update(scan_dirs_recursive(p, depth + 1, max_depth))
        except Exception:
            pass
        return dirs

    current_dirs = scan_dirs_recursive(cwd, 1, 3)
        
    new_dirs = list(current_dirs - old_dirs)
    
    if not new_dirs:
        return
        
    # Sort new directories by path depth in descending order to process the deepest leaf first
    new_dirs.sort(key=lambda x: len(x.parts), reverse=True)
    
    for nd in new_dirs:
        # Ignore standard hidden dirs
        if nd.name.startswith(".") or nd.name in ("venv", "node_modules", "brain_health"):
            continue
            
        # Security Guard: Canonicalize path and validate against allowed boundaries (project root or home)
        try:
            nd = nd.resolve()
            project_root = get_active_project_root().resolve()
            is_valid_workspace = False
            try:
                nd.relative_to(project_root)
                is_valid_workspace = True
            except ValueError:
                try:
                    nd.relative_to(Path.home())
                    is_valid_workspace = True
                except ValueError:
                    pass
            
            if not is_valid_workspace:
                log_event(f"Security Block: Prevented workspace migration to unauthorized target: {nd}")
                continue
        except Exception as e:
            log_event(f"Error canonicalizing workspace path {nd}: {e}")
            continue
            
        box_lines = [
            f"Folder: {C_W}{nd.name}",
            "---",
            "Would you like to bind this chat's active memories and",
            "intelligence database directly to this new project?"
        ]
        print()
        draw_box(box_lines, title=f"📂 {C_Y}NEW PROJECT WORKSPACE DETECTED", border_color=C_G)
        
        confirm = input(f"{C_Y}Bind memories to '{nd.name}'? [Y/n]: {C_R}")
        
        # Security Guard: Strip ANSI escape sequences to prevent spoofing or command bypasses
        confirm_cleaned = ANSI_ESCAPE.sub('', confirm).strip().lower()
        
        if confirm_cleaned in ("/exit", "/quit", "exit", "quit"):
            print(f"\n{C_P}🌸 Sayonara! Terminating agent session...{C_R}\n")
            log_event("🌸 Termchat Session Terminated cleanly via migration prompt exit")
            if active_brain_health_dir:
                backup_path = Path(active_brain_health_dir) / "active_session_backup.json"
                if backup_path.exists():
                    try:
                        backup_path.unlink()
                    except Exception:
                        pass
            sys.exit(0)
            
        if confirm_cleaned != "n":
            # 1. Create target brain_health dir inside new folder
            target_bh = nd / "brain_health"
            target_bh.mkdir(parents=True, exist_ok=True)
            
            try:
                # Copy WAL database files if they exist
                for f_name in ["kenbun_intelligence.db", "chat_sessions.json"]:
                    old_f = active_brain_health_dir / f_name
                    target_f = target_bh / f_name
                    if old_f.exists() and old_f.resolve() != target_f.resolve():
                        shutil.copy2(old_f, target_f)
                        
                print(f"\n{C_G}✓ Successfully migrated active memories and database to:{C_R}")
                print(f"  {C_C}{target_bh.resolve()}{C_R}\n")
                
                # 2. Change active directory context and reload variables!
                os.chdir(str(nd))
                active_brain_health_dir = target_bh
                
                # Proactively create a .kenbun workspace marker
                (nd / ".kenbun").mkdir(exist_ok=True)
                
                # 3. Save project creation memory to ChromaDB Hivemind
                title = f"Project Workspace Created: {nd.name}"
                content = (
                    f"PROJECT WORKSPACE DETECTED & BOUND\n"
                    f"==================================\n"
                    f"Folder Name: {nd.name}\n"
                    f"Location: {nd.resolve()}\n"
                    f"Creation & Binding Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Status: Active Project Bound.\n"
                )
                save_concept_to_hivemind(title, content, tags="project-workspace,folder-creation", category="concepts")
                log_event(f"Bound memory and saved project concept for folder: {nd.name}")
                break
            except Exception as e:
                print(f"\n{C_Y}❌ Failed to migrate memories: {e}{C_R}\n")

# ========================================================
# 🧠 COGNITIVE HIVEMIND & REFLECTION INTEGRATION HELPER SUITE
# ========================================================

def log_event(msg):
    """Logs a diagnostic event directly to shared mcp_debug.log for Dozzle aggregation and live_telemetry.json for Dashboard."""
    try:
        root = get_active_project_root()
        log_file = root / "mcp_debug.log"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [TERMCHAT] {msg}\n")
    except Exception:
        pass

    global active_brain_health_dir
    if active_brain_health_dir:
        try:
            telemetry_path = Path(active_brain_health_dir) / "live_telemetry.json"
            data = {"timestamp": time.time(), "message": f"[TERMCHAT] {msg}", "type": "log"}
            with open(telemetry_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")
        except Exception:
            pass


def save_concept_to_hivemind(title, content, tags, category="concepts"):
    """
    Saves a concept to the Hivemind (ChromaDB) with graceful error handling.
    """
    project_root = Path(__file__).resolve().parent.parent
    core_path = str(project_root / "core")
    if core_path not in sys.path: pass
    
    try:
        from core.tools.memory.knowledge_manager import learn_concept
        res = learn_concept(title, content, tags, category)
        return res
    except Exception as e:
        err_msg = f"ERROR: Failed to save to Hivemind. ChromaDB connection failed or core path error: {e}"
        # Log to local file fallback
        try:
            log_dir = project_root / "brain_health"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "failed_hivemind_memories.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": time.time(),
                    "title": title,
                    "content": content,
                    "tags": tags,
                    "category": category,
                    "error": str(e)
                }) + "\n")
            err_msg += f"\n⚠️  Saved backup locally to: {log_file}"
        except Exception as log_err:
            err_msg += f"\n⚠️  Could not write local log backup: {log_err}"
        return err_msg

def search_hivemind(query, category="concepts"):
    """
    Searches the Hivemind (ChromaDB) semantically with graceful error handling.
    """
    project_root = Path(__file__).resolve().parent.parent
    core_path = str(project_root / "core")
    if core_path not in sys.path: pass
    
    try:
        from core.tools.memory.knowledge_manager import list_concepts
        res = list_concepts(query, n_results=5, category=category)
        return res
    except Exception as e:
        return json.dumps([{"error": f"Failed to search Hivemind. ChromaDB is unreachable or core path error: {e}"}])

def is_healing_command(cmd: str) -> bool:
    """
    Heuristically checks if a command is a system repair, configuration, or package setup.
    """
    cmd_lower = cmd.lower()
    healing_keywords = [
        "pull", "install", "restart", "start", "enable", "config", "setup",
        "ufw", "iptables", "firewall", "chmod", "chown", "bootstrap", "heal",
        "repair", "fix", "docker exec", "docker run", "docker-compose up", "service", "systemctl"
    ]
    return any(kw in cmd_lower for kw in healing_keywords)

def autonomic_reflection_save(task: str, error: str, solution: str, tags: str = "auto-lesson"):
    """
    Dynamically inserts core directory in sys.path and calls
    tools.memory.knowledge_manager.record_post_mortem to record the lesson in ChromaDB history.
    """
    try:
        # Dynamically find the core path
        possible_cores = [
            Path(__file__).resolve().parent.parent / "core",
            Path.cwd() / "core"
        ]
        core_path = None
        for p in possible_cores:
            if p.exists() and (p / "tools").exists():
                core_path = p
                break
        
        if not core_path:
            core_path = Path(__file__).resolve().parent.parent / "core"
            
        sys_path_str = str(core_path.resolve())
        if sys_path_str not in sys.path: pass
            
        from core.tools.memory.knowledge_manager import record_post_mortem
        res = record_post_mortem(task, error, solution, tags)
        print(f"\n{C_P}🧠 Hivemind Reflection Engine Saved Auto-Lesson: {C_G}{res}{C_R}\n")
        return res
    except Exception as e:
        print(f"\n{C_Y}⚠️  Reflection Engine Warning: Failed to record auto-lesson: {e}{C_R}\n")
        return None

def save_clean_exit_reflection(history):
    """
    Summarizes the chat session, extracts commands run, and records a post-mortem
    reflection note in the Hivemind titled 'Session Post-Mortem: <Timestamp>'.
    """
    try:
        # Extract commands executed
        executed_commands = []
        for msg in history:
            content = msg.get("content", "")
            if not content:
                continue
            # Look for reflex command executions in user/system feedback
            commands = re.findall(r"```execute\n(.*?)\n```", content, re.DOTALL)
            for c in commands:
                executed_commands.append(c.strip())
            # Look for SYSTEM OUT command executions
            sys_outs = re.findall(r"\[SYSTEM OUT \(Command: '(.*?)', Exit Code:", content)
            for c in sys_outs:
                executed_commands.append(c.strip())
                
        # Deduplicate while preserving order
        seen = set()
        executed_commands = [c for c in executed_commands if not (c in seen or seen.add(c))]
        
        # Compile a summary of dialogue
        user_queries = []
        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user" and not content.startswith("[SYSTEM OUT") and not content.startswith("[SYSTEM NOTICE"):
                if "[USER INSTRUCTION]:" in content:
                    parts = content.split("[USER INSTRUCTION]:", 1)
                    user_queries.append(parts[1].strip())
                else:
                    user_queries.append(content.strip())

        # Build accomplishments details
        accomplishments = []
        if user_queries:
            accomplishments.append("User Queries addressed:")
            for q in user_queries[:5]:  # Limit to top 5
                accomplishments.append(f" - {q}")
        if executed_commands:
            accomplishments.append("\nCommands successfully executed:")
            for cmd in executed_commands:
                accomplishments.append(f" - {cmd}")
        else:
            accomplishments.append("\nNo shell commands were executed in this session.")
            
        accomplishments_str = "\n".join(accomplishments)
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        title = f"Session Post-Mortem: {timestamp}"
        
        # Dynamically insert core in sys.path
        possible_cores = [
            Path(__file__).resolve().parent.parent / "core",
            Path.cwd() / "core"
        ]
        core_path = None
        for p in possible_cores:
            if p.exists() and (p / "tools").exists():
                core_path = p
                break
        
        if not core_path:
            core_path = Path(__file__).resolve().parent.parent / "core"
            
        sys_path_str = str(core_path.resolve())
        if sys_path_str not in sys.path: pass
            
        from core.tools.memory.knowledge_manager import learn_concept
        
        content = (
            f"SESSION SUMMARY POST-MORTEM ({timestamp})\n"
            f"=========================================\n"
            f"ACCOMPLISHMENTS:\n{accomplishments_str}\n\n"
            f"TOTAL DIALOGUE TURNS: {len(history) // 2}\n"
        )
        
        res = learn_concept(title, content, "session-post-mortem,clean-exit", category="history")
        print(f"\n{C_P}🧠 Session Post-Mortem saved to Hivemind: {C_G}{res}{C_R}\n")
        return res
    except Exception as e:
        print(f"\n{C_Y}⚠️  Reflection Engine Warning: Failed to save session post-mortem: {e}{C_R}\n")
        return None

def check_interactive_command(parts: list[str]) -> Optional[str]:
    if not parts:
        return None
        
    executable = Path(parts[0]).name.lower()
    
    # Helper to check if a specific flag is set in the arguments (handles combined short flags like -yq)
    def has_flag(flag_char: str, full_flag: str) -> bool:
        for part in parts[1:]:
            if part.startswith("--") and part == full_flag:
                return True
            elif part.startswith("-") and not part.startswith("--"):
                if flag_char in part[1:]:
                    return True
        return False

    # 1. Text editors and pagers
    editors = {"nano", "vim", "vi", "emacs", "neovim", "nvim", "micro", "ed", "less", "more", "most"}
    if executable in editors:
        return f"Command '{executable}' is an interactive text editor/pager. Since Kenbun runs commands non-interactively, it will hang. Please use a file edit tool or 'cat << \"EOF\" > ...' to write/edit files."
        
    # 2. Interactive system monitors
    monitors = {"top", "htop", "btop", "atop", "iotop", "iftop", "watch"}
    if executable in monitors:
        return f"Command '{executable}' is an interactive system monitor/loop. Please run a non-interactive equivalent (e.g. 'ps aux', 'df -h', or 'free -m')."
        
    # 3. Interactive shells / REPLs without execution flags
    if executable in {"python", "python3", "node", "ruby", "irb", "php"}:
        if len(parts) == 1:
            return f"Command '{executable}' will open an interactive REPL shell. To run code, write a script file and run it, or pass the command string (e.g. '{executable} -c \"...\"')."
            
    if executable in {"bash", "zsh", "sh"}:
        if len(parts) == 1 or not (has_flag("c", "--cmd") or has_flag("s", "--stdin")):
            return f"Command '{executable}' without '-c' opens an interactive shell. Please run with '-c' (e.g. '{executable} -c \"your command\"')."
            
    # 4. Git commits without a message
    if executable == "git" and len(parts) > 1 and parts[1] == "commit":
        has_msg = (
            has_flag("m", "--message") or 
            has_flag("F", "--file") or 
            has_flag("C", "--reuse-message") or 
            has_flag("c", "--reedit-message") or 
            "--amend" in parts
        )
        if not has_msg:
            return "Command 'git commit' without a message flag will open an interactive text editor. Please pass a message using the '-m' flag (e.g. 'git commit -m \"message\"')."
            
    # 5. Package managers without -y
    if executable in {"apt", "apt-get", "yum", "dnf", "pacman", "zypper", "apk"}:
        is_modifying = any(arg in parts for arg in ("install", "remove", "upgrade", "update", "dist-upgrade", "purge", "add", "del"))
        if is_modifying:
            has_yes = (
                has_flag("y", "--yes") or 
                has_flag("q", "--quiet") or 
                "--noconfirm" in parts
            )
            if not has_yes:
                return f"Command '{executable}' requires user confirmation. Please append a yes/quiet flag (e.g. '-y' or '--noconfirm') to run non-interactively."
            
    return None

class TerminalSession:
    """Class-based execution context for isolated state tracking and secure command execution."""
    def __init__(self):
        self.cwd = Path.cwd().resolve()

    def execute_command(self, cmd: str) -> tuple[int, str]:
        """Executes a proposed system shell command safely with stdout/stderr capture."""
        log_event("⚙️ Executing reflex shell command: {}".format(scrub_secrets(cmd)))
        cols = get_columns()
        print(f"\n{C_Y}⚙️  Executing: {C_C}{clean_wrap_text(scrub_secrets(cmd), cols - 15)}{C_R}")
        
        # Store directory list state before execution relative to logical session directory
        cwd = self.cwd
        old_dirs = set()
    
        # Performance Optimization: Only scan files if command suggests folder operations
        scan_keywords = ("mkdir", "clone", "git", "tar", "unzip", "cp", "mv", "touch", "rm")
        should_scan = any(kw in cmd for kw in scan_keywords)
    
        if should_scan:
            try:
                ignore_dirs = {"venv", ".venv", "node_modules", "brain_health", "__pycache__", "dist", "build"}
                for p in cwd.iterdir():
                    if p.is_dir() and not p.name.startswith(".") and p.name not in ignore_dirs:
                        old_dirs.add(p)
                        try:
                            for sub in p.iterdir():
                                if sub.is_dir() and not sub.name.startswith(".") and sub.name not in ignore_dirs:
                                    old_dirs.add(sub)
                        except Exception:
                            pass
            except Exception:
                pass
    
        try:
            import shlex
        
            try:
                parts = shlex.split(cmd)
            except ValueError as e:
                return -1, f"[Execution Error: Failed to parse command safely: {e}]"
            
            if not parts:
                return 0, "[Success: Empty command]"
            
            # Check if the command is interactive and will hang/fail
            interactive_warning = check_interactive_command(parts)
            if interactive_warning:
                log_event(f"⚠️ Interactive command blocked: {interactive_warning}")
                return -1, f"[UX Blocked: {interactive_warning}]"
            
            executable = parts[0]
        
            # Explicit handling for shell builtin 'cd'
            if executable == "cd":
                target = parts[1] if len(parts) > 1 else str(Path.home())
                try:
                    # Fix: Resolve target path relative to the virtual agent CWD, NOT the host process CWD
                    resolved_path = (self.cwd / target).resolve()
                
                    # Apply Security Sandbox Guard with strict prefix validation (Project root only)
                    project_root = get_active_project_root().resolve()
                    is_safe_boundary = resolved_path.is_relative_to(project_root)
                
                    if is_safe_boundary and resolved_path.exists() and resolved_path.is_dir():
                        self.cwd = resolved_path
                        log_event(f"Synchronized logical working directory context to safe path: {resolved_path}")
                        return 0, "[Success: Directory changed]"
                    else:
                        return 1, f"Security Block: Refused context shift to unauthorized or non-existent path: {target}"
                except Exception as e:
                    return 1, f"cd error: {e}"
        
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=45
            )
        
            # Check if a new folder was created and prompt for memory migration relative to original_cwd!
            if should_scan:
                check_and_migrate_project_memory(old_dirs, original_cwd=cwd)
        
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if not output.strip():
                output = "[Success: Command executed with zero stdout/stderr output]"
            log_event("➔ Reflex command completed. Exit Code: {}".format(result.returncode))
            return result.returncode, scrub_secrets(output)
        except subprocess.TimeoutExpired as e:
            log_event("❌ Reflex command failed with execution timeout")
            stdout = e.stdout or ""
            stderr = e.stderr or ""
            output = f"[Timeout Error: The system command exceeded the 45-second execution limit]\n{stdout}"
            if stderr:
                output += f"\n[stderr]\n{stderr}"
            return -1, scrub_secrets(output)
        except Exception as e:
            log_event("❌ Reflex command failed with start exception: {}".format(e))
            return -1, f"[Execution Error: Failed to start command: {e}]"
        finally:
            try:
                # Restore terminal input modes to recover from any raw/interactive drift caused by the command
                sys.stdout.write(TERMINAL_RESET_SEQUENCE)
                sys.stdout.flush()
            except Exception:
                pass


# Global session instance for the main REPL thread
_active_terminal_session = TerminalSession()

def run_proposed_command(cmd: str) -> tuple[int, str]:
    """Proxy function to maintain backwards compatibility with REPL call sites."""
    return _active_terminal_session.execute_command(cmd)

def install_shift_enter_alias() -> int:
    try:
        from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
        from prompt_toolkit.keys import Keys
    except Exception:
        return 0
    alt_enter = (Keys.Escape, Keys.ControlM)
    changed = 0
    for seq in ("\x1b[13;2u", "\x1b[27;2;13~", "\x1b[27;2;13u", "\x1b[13;5u", "\x1b[27;5;13~", "\x1b[27;5;13u"):
        if ANSI_SEQUENCES.get(seq) != alt_enter:
            ANSI_SEQUENCES[seq] = alt_enter
            changed += 1
    return changed

def check_and_start_docker_swarm(project_root: Path):
    """Automatically spins up the Docker Swarm stack if it is down."""
    import subprocess
    import shutil
    import time
    
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return
        
    try:
        res = subprocess.run([docker_bin, "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=2)
        is_running = "fastmcp_server" in res.stdout or "ollama_server" in res.stdout
    except Exception:
        is_running = False
        
    compose_file = project_root / "docker-compose.yml"
    if not compose_file.exists():
        return
        
    # Auto-heal docker-compose.yml drift
    try:
        git_bin = shutil.which("git")
        if git_bin and (project_root / ".git").exists():
            status_res = subprocess.run([git_bin, "status", "--porcelain", "docker-compose.yml"], capture_output=True, text=True, cwd=str(project_root))
            if status_res.stdout.strip():
                print(f"\n\033[38;5;226m⚠️ [SWARM HEALER] Detected unauthorized modifications to docker-compose.yml.\033[0m")
                print("\033[38;5;246mThis usually causes port mismatches and 'Hivemind offline' errors.\033[0m")
                print("Would you like to auto-heal it by resetting to the official repository version?")
                choice = input("Auto-heal? [Y/n]: ").strip().lower()
                if choice != 'n':
                    subprocess.run([git_bin, "checkout", "docker-compose.yml"], cwd=str(project_root), check=True)
                    print("\033[38;5;224m✓ Successfully restored docker-compose.yml.\033[0m")
                    print(f"\033[38;5;218m🌸 Restarting Swarm to apply corrected configuration...\033[0m")
                    subprocess.run([docker_bin, "compose", "up", "-d", "--force-recreate"], cwd=str(project_root), check=True)
                    print(f"\033[38;5;224m✓ Swarm containers are online.\033[0m")
                    return # Skip normal boot since we just force-recreated
    except Exception:
        pass
        
    if is_running:
        return # Swarm is already running properly and compose file is clean
        
    print(f"\n\033[38;5;218m🌸 Automating Swarm Boot Sequence...\033[0m")
    try:
        subprocess.run([docker_bin, "compose", "up", "-d"], cwd=str(project_root), check=True)
        print(f"\033[38;5;224m✓ Swarm containers are online.\033[0m")
        time.sleep(1)
    except Exception as e:
        print(f"\033[38;5;226m⚠️ Failed to auto-start Docker Swarm: {e}\033[0m")


def check_case_collisions(directory: Path) -> list[tuple[str, str]]:
    """Detects if there are files in the directory that differ only by case."""
    seen = {}
    collisions = []
    try:
        for p in directory.iterdir():
            lower_name = p.name.lower()
            if lower_name in seen:
                collisions.append((seen[lower_name], p.name))
            else:
                seen[lower_name] = p.name
    except Exception:
        pass
    return collisions


def main():
    global active_brain_health_dir, YOLO_MODE
    
    # 1. Low-Level Systems Memory Optimization (C# Heap Pinning equivalent)
    # Freeze the initial CPython heap containing all core static imports and modules
    # to permanently exclude them from future cyclic garbage collection sweeps.
    import gc
    gc.collect(2)
    gc.freeze()
    
    # Tune generational GC thresholds (Gen 0 ceiling at 50,000 allocations) to prevent
    # garbage collection thrashing during high-frequency REPL command iterations.
    gc.set_threshold(50000, 10, 10)
    
    # Support starting directly in YOLO mode via command line flags
    import sys
    if "--yolo" in sys.argv or "-y" in sys.argv:
        YOLO_MODE = True
        
    # Configure proper POSIX signal handlers to protect term state
    signal.signal(signal.SIGINT, graceful_exit_handler)
    signal.signal(signal.SIGTERM, graceful_exit_handler)
    
    env = load_env_vars()
    chroma_host = env.get("CHROMA_HOST", "localhost")
    chroma_port = env.get("CHROMA_PORT", "8000")
    
    # Initialize connection pooling session
    session = requests.Session()
    
    # Extract configs
    llm_url = env.get("PRIMARY_LLM_URL", "http://localhost:11434/v1")
    llm_model = env.get("PRIMARY_LLM_MODEL", "gemma4:12b")
    
    # Resolve initial brain health dir per v2.8.0 specification
    cwd = Path.cwd().resolve()
    
    # Pre-flight case-sensitivity integrity check to avoid Linux volume mount errors
    collisions = check_case_collisions(cwd)
    if collisions:
        print(f"\n{C_Y}⚠️ [PORTABILITY WARNING] Case-Sensitivity Collision Detected in Active Directory!{C_R}")
        for c1, c2 in collisions:
            print(f"  ➔ Duplicate file names differing only by case: '{c1}' and '{c2}'")
        print(f"{C_D}This will cause non-deterministic behavior inside Linux Docker containers.{C_R}\n")
        
    system_root = get_active_project_root()
    if cwd != system_root and ((cwd / ".git").exists() or (cwd / ".kenbun").exists()):
        active_brain_health_dir = cwd / "brain_health"
    else:
        if cwd != system_root:
            print(f"\n\033[38;5;226m⚠️ [SECURITY WARNING] Path Bleed Detected!\033[0m")
            print(f"You launched Kenbun from: \033[38;5;246m{cwd}\033[0m")
            print(f"But the resolved core is: \033[38;5;246m{system_root}\033[0m")
            print("\n\033[38;5;218mTo prevent executing commands in the wrong folder (Security Violation),\033[0m")
            print("\033[38;5;218mplease navigate to your project directory before running kenbun.\033[0m")
            print("\nIf your global CLI symlink is broken, we highly recommend fixing it using uv:")
            print("  \033[1mcd ~/.kenbun-agent && uv tool install -e .\033[0m")
            print("\n\033[38;5;224mPress ENTER to continue anyway (at your own risk), or Ctrl+C to abort.\033[0m")
            try:
                input()
            except KeyboardInterrupt:
                import sys
                sys.exit(1)
        active_brain_health_dir = system_root / "brain_health"
    active_brain_health_dir.mkdir(parents=True, exist_ok=True)
    
    check_and_start_docker_swarm(system_root)
    
    # Audit and dynamically self-heal cloud/local mismatches before displaying banner
    llm_url, llm_model = check_and_heal_mismatch(llm_url, llm_model)
    
    # Proactive URL Normalization for standard local/tailscale APIs (Ollama compatibility endpoint)
    if "localhost" in llm_url:
        llm_url = llm_url.replace("localhost", "127.0.0.1")
        
    if ("localhost" in llm_url or "127.0.0.1" in llm_url or ".ts.net" in llm_url or "100." in llm_url or "192.168." in llm_url) and not llm_url.endswith("/v1"):
        if not llm_url.endswith("/"):
            llm_url += "/"
        llm_url += "v1"
        
    # Detect model tier for adaptive prompt
    model_tier = detect_model_tier(llm_model, llm_url)

    # Pre-flight API Credentials Decryption Integrity Audit
    is_gemini_key_failed = "GEMINI_API_KEY" in env and env["GEMINI_API_KEY"].startswith("enc:")
    is_openai_key_failed = "OPENAI_API_KEY" in env and env["OPENAI_API_KEY"].startswith("enc:")
    is_anthropic_key_failed = "ANTHROPIC_API_KEY" in env and env["ANTHROPIC_API_KEY"].startswith("enc:")
    is_deepseek_key_failed = "DEEPSEEK_API_KEY" in env and env["DEEPSEEK_API_KEY"].startswith("enc:")
    
    active_key_failed = False
    active_provider = ""
    is_gemini_route = "gemini" in llm_url.lower() or "googleapis" in llm_url.lower() or "generativelanguage" in llm_url.lower()
    
    if is_gemini_route and is_gemini_key_failed:
        active_key_failed = True
        active_provider = "Google Gemini"
    elif "openai" in llm_url.lower() and not is_gemini_route and is_openai_key_failed:
        active_key_failed = True
        active_provider = "OpenAI"
    elif "anthropic" in llm_url.lower() and is_anthropic_key_failed:
        active_key_failed = True
        active_provider = "Anthropic"
    elif "deepseek" in llm_url.lower() and is_deepseek_key_failed:
        active_key_failed = True
        active_provider = "DeepSeek"

    if active_key_failed:
        print()
        draw_box([
            f"{C_RED}{C_BOLD}⚠️  API CREDENTIAL DECRYPTION FAILURE ⚠️{C_R}",
            "",
            f"Your encrypted {C_Y}{active_provider} API Key{C_R} failed to decrypt.",
            "This happens if '.kenbun_master.key' was deleted or regenerated.",
            "",
            f"Please run the Guided Setup: {C_G}python3 scripts/bootstrap.py{C_R}",
            f"and select Option {C_C}[3] (Configure API Keys){C_R} to re-enter them.",
        ], title=f"{C_RED}🚨 SECURITY INTEGRITY ALERT", border_color=C_RED, text_color=C_Y)
        print()

    # 🌸 Premium Rich banner — Hermes-style panel layout
    print(f"{C_D}  Probing system health...{C_R}", end="\r")
    probe_results = run_startup_probe(llm_url, llm_model, chroma_host, chroma_port)
    print(" " * 40, end="\r")  # clear probe line

    health_summary = {
        "Ollama":   probe_results.get("ollama_status", "unknown"),
        "ChromaDB": probe_results.get("chroma_status", "unknown"),
        "Docker":   probe_results.get("docker_status", "unknown"),
    }

    if _ui:
        _ui.print_banner(
            model=llm_model,
            health=health_summary,
            version="2.9.0",
            yolo_mode=YOLO_MODE,
        )
    else:
        # Fallback ANSI banner
        cols = get_columns()
        if cols >= 70:
            print(f"\n{C_P}██╗  ██╗███████╗███╗   ██╗██████╗ ██╗   ██╗███╗   ██╗")
            print(f"██║ ██╔╝██╔════╝████╗  ██║██╔══██╗██║   ██║████╗  ██║")
            print(f"█████╔╝ █████╗  ██╔██╗ ██║██████╔╝██║   ██║██╔██╗ ██║")
            print(f"██╔═██╗ ██╔══╝  ██║╚██╗██║██╔══██╗██║   ██║██║╚██╗██║")
            print(f"██║  ██╗███████╗██║ ╚████║██████╔╝╚██████╔╝██║ ╚████║  {C_Y}COGNITIVE AGENT SHELL v2.9.0")
            print(f"{C_P}╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝{C_R}")
        else:
            print(f"\n{C_P}🌸 KENBUN COGNITIVE AGENT SHELL v2.9.0{C_R}")
        tier_label = {"nano": f"{C_Y}Nano{C_R}", "standard": f"{C_G}Standard{C_R}", "cloud": f"{C_C}Cloud API{C_R}"}.get(model_tier, model_tier)
        draw_box(
            [f"  🌸 Model: {C_W}{llm_model}{C_R} [{tier_label}]", f"  ⚡ Gateway: {C_W}{llm_url}{C_R}"],
            title=f"🌸 {C_Y}COGNITIVE AGENT SHELL", border_color=C_G, text_color=C_G
        )
        print_health_card(probe_results)
    print()

    log_event("🌸 Termchat Session Started. Model: {}, URL: {}, Tier: {}".format(llm_model, llm_url, model_tier))

    system_prompt = build_system_prompt(model_tier, llm_model)
    # Append AST tool runner note for all tiers
    system_prompt += (
        "You have access to Kenbun's harvested agent tools. To call a tool, use the /run command in the chat (e.g. /run search_hivemind_concepts query=\"test\") or invoke them natively via the tool dispatcher — do NOT wrap tool calls as 'kenbun <toolname>' shell commands, as this spawns a recursive subprocess and will always time out. For system operations, use standard shell commands (e.g. docker, git, ls) directly in execute blocks. "
        "If the user asks you to create a new project directory (e.g. `mkdir my-new-project`), once created, your terminal chat client will automatically "
        "detect the folder birth, prompt the user for approval, and seamlessly MIGRATE and ATTACH all your active chat memories, SQLite databases, "
        "and logs straight inside the new project's local 'brain_health' directory!"
    )

    history = [
        {"role": "system", "content": system_prompt}
    ]

    # Startup scanner for interrupted session
    backup_path = active_brain_health_dir / "active_session_backup.json"
    if backup_path.exists():
        try:
            with open(backup_path, "r") as f:
                backup_data = json.load(f)
            
            backup_history = backup_data.get("history", [])
            has_messages = len([m for m in backup_history if m.get("role") != "system"]) > 0
            
            if has_messages:
                print()
                draw_box([
                    "Kenbun has detected a previously interrupted chat",
                    "session. Would you like to restore and resume?"
                ], title="🌸 KENBUN SESSION RECOVERY DETECTED", border_color=C_P, text_color=C_W)
                
                confirm = input(f'{C_P}🌸 Restore and resume session? [Y/n]: {C_R}').strip().lower()
                if confirm != "n":
                    history = []
                    for msg in backup_history:
                        scrubbed_msg = msg.copy()
                        if "content" in scrubbed_msg:
                            scrubbed_msg["content"] = scrub_secrets(scrubbed_msg["content"])
                        history.append(scrubbed_msg)
                    saved_cwd = backup_data.get("cwd")
                    if saved_cwd and os.path.exists(saved_cwd):
                        try:
                            os.chdir(saved_cwd)
                            cwd = Path.cwd().resolve()
                            if cwd != system_root and ((cwd / ".git").exists() or (cwd / ".kenbun").exists()):
                                active_brain_health_dir = cwd / "brain_health"
                            else:
                                active_brain_health_dir = system_root / "brain_health"
                            active_brain_health_dir.mkdir(parents=True, exist_ok=True)
                            print(f"\n{C_G}✓ Restored active directory context: {C_C}{saved_cwd}{C_R}")
                        except Exception as e:
                            print(f"\n{C_Y}⚠️ Failed to restore directory context: {e}{C_R}")
                    
                    if "llm_url" in backup_data:
                        llm_url = backup_data["llm_url"]
                    if "llm_model" in backup_data:
                        llm_model = backup_data["llm_model"]
                        
                    print(f"{C_G}✓ Session state and dialogue history successfully restored!{C_R}\n")
                else:
                    try:
                        backup_path.unlink()
                    except Exception:
                        pass
        except Exception as e:
            print(f"\n{C_Y}⚠️ Failed to load or restore session backup: {e}{C_R}\n")


    username = os.environ.get("USER", "amontano")
    auto_trigger = False

    # Initialize robust PromptSession for history and multiline
    pt_session = None
    if PromptSession is not None:
        pt_session = PromptSession()
        install_shift_enter_alias()

    # ── Layer 5: Intent-First Boot ─────────────────────────────────────────────
    # Ask the user ONE goal-setting question before dropping into the loop.
    # Psychology: commitment priming raises task completion by ~40%.
    intent_map = {
        "1": "code",
        "2": "debug",
        "3": "system",
        "4": "chat",
    }
    intent_context = ""
    try:
        while True:
            yolo_banner = f" {C_RED}{C_BOLD}(⚡ YOLO MODE ACTIVE){C_R}" if YOLO_MODE else ""
            print(f"\n{C_P}Kenbun 🌸:{C_R} I'm online and ready. What are we working on today?{yolo_banner}")
            print(f"  {C_C}[1]{C_R} Code   — Build or scaffold something new")
            print(f"  {C_C}[2]{C_R} Debug  — Fix an error or diagnose an issue")
            print(f"  {C_C}[3]{C_R} System — Manage this machine or containers")
            print(f"  {C_C}[4]{C_R} Chat   — Just talk or explore ideas")
            if YOLO_MODE:
                print(f"  {C_C}[5]{C_R} {C_G}Disable YOLO Mode{C_R} (Restores manual confirmation)")
            else:
                print(f"  {C_C}[5]{C_R} {C_RED}Enable YOLO Mode{C_R}  — Auto-approve all shell commands (nuclear-safe)")
            
            prompt_label = "  Pick [1-5] or press Enter to skip: "
            if pt_session:
                raw_intent = pt_session.prompt(ANSI(f"{C_P}{prompt_label}{C_R}")).strip()
            else:
                raw_intent = input(f"{C_P}{prompt_label}{C_R}").strip()
            
            if raw_intent == "5":
                YOLO_MODE = not YOLO_MODE
                if YOLO_MODE:
                    draw_box([
                        f"{C_RED}{C_BOLD}⚡ YOLO MODE ACTIVATED ⚡{C_R}",
                        "",
                        "Commands proposed by Kenbun will execute automatically.",
                        "Nuclear commands (rm -rf /, mkfs, dd, fork bombs)",
                        "are ALWAYS blocked regardless of this setting.",
                        "",
                        "Please select your category [1-4] or skip.",
                    ], title=f"{C_RED}⚡ YOLO MODE ON", border_color=C_RED, text_color=C_Y)
                else:
                    print(f"\n{C_G}✓ YOLO mode disabled. Manual approval restored.{C_R}")
                break
            
            intent = intent_map.get(raw_intent, "")
            if intent:
                ctx_labels = {
                    "code": "The user wants to build or scaffold new code.",
                    "debug": "The user has an error or issue to diagnose and fix.",
                    "system": "The user wants to manage their machine, Docker, or containers.",
                    "chat": "The user wants a conversational session.",
                }
                intent_context = f"[SESSION CONTEXT: {ctx_labels[intent]}]"
                history.append({"role": "system", "content": intent_context})
                print(f"\n{C_G}  ✓ Session primed for: {intent.upper()}{C_R}\n")
            break
    except (KeyboardInterrupt, EOFError):
        pass

    # Top-Level Exception Catcher to intercept unexpected system/OS crashes gracefully
    try:
        while True:
            try:
                # If auto_trigger is set, the system feeds back command output automatically without waiting for user input
                if auto_trigger:
                    user_input = ""
                    auto_trigger = False
                else:
                    # Show sub-agent status lines if any are active
                    if poll_status_lines:
                        status_lines = poll_status_lines()
                        for sl in status_lines:
                            print(f"{C_D}{sl}{C_R}")
                    prompt_str = f"{C_P}{username}@kenbun-agent{C_R}:{C_G}~{C_R}$ "
                    with patch_stdout():
                        if pt_session:
                            user_input = pt_session.prompt(ANSI(prompt_str)).strip()
                        else:
                            user_input = input(prompt_str).strip()

                    user_input = sanitize_input(user_input)
                    if not user_input:
                        continue
                    
                    # Handle Slash Commands
                    if user_input.startswith("/"):
                        cmd_parts = user_input.split(" ", 1)
                        cmd = cmd_parts[0].lower()
                        
                        if cmd in ("/help", "/?"):
                            log_event("❓ Displayed commands directory via /help")
                            help_lines = [
                                f"  {C_BOLD}{C_C}/help{C_R}{C_G} (/?){C_D}           ➟ Show this guide{C_R}",
                                f"  {C_BOLD}{C_C}/exit{C_R}{C_D}              ➟ Gracefully close session{C_R}",
                                f"  {C_BOLD}{C_C}/reset{C_R}{C_D}             ➟ Clear dialogue history{C_R}",
                                f"  {C_BOLD}{C_C}/system{C_R}{C_D}            ➟ Show environment config{C_R}",
                                f"  {C_BOLD}{C_C}/skin [name]{C_R}{C_D}       ➟ Change CLI skin theme{C_R}",
                                f"  {C_BOLD}{C_C}/spawn <cmd>{C_R}{C_D}       ➟ Run command in background agent{C_R}",
                                f"  {C_BOLD}{C_C}/agents{C_R}{C_D}            ➟ List all running background agents{C_R}",
                                f"  {C_BOLD}{C_C}/kill <id>{C_R}{C_D}         ➟ Kill a background agent{C_R}",
                                f"  {C_BOLD}{C_C}/recall <query>{C_R}{C_D}    ➟ Search Hivemind memories{C_R}",
                                f"  {C_BOLD}{C_C}/remember t=c{C_R}{C_D}      ➟ Save a note to Hivemind{C_R}",
                                f"  {C_BOLD}{C_C}/search <topic>{C_R}{C_D}    ➟ Search UI/UX design database{C_R}",
                                f"  {C_BOLD}{C_C}/tools [name]{C_R}{C_D}     ➟ List or inspect harvested sovereign tools{C_R}",
                                f"  {C_BOLD}{C_C}/skills [name]{C_R}{C_D}    ➟ List or inspect design & template skills{C_R}",
                                f"  {C_BOLD}{C_C}/run <tool> [args]{C_R}{C_D}  ➟ Live REPL execution of a harvested tool{C_R}",
                                f"  {C_BOLD}{C_RED}/yolo{C_R}{C_D}              ➟ Toggle YOLO mode (auto-approve commands){C_R}",
                            ]
                            yolo_status = f"{C_RED}⚡ YOLO MODE: ON  — Commands execute automatically!{C_R}" if YOLO_MODE else f"{C_D}  YOLO MODE: off — Commands need your approval{C_R}"
                            print()
                            draw_box(help_lines + ["", yolo_status], title=f"🌸 {C_Y}KENBUN COMMANDS", border_color=C_P, text_color=C_W)
                            print()
                            continue
                            
                        elif cmd == "/exit":
                            print(f"\n{C_P}🌸 Sayonara! Terminating agent session...{C_R}\n")
                            log_event("🌸 Termchat Session Terminated cleanly via /exit")
                            # Save clean exit session reflection post-mortem in ChromaDB
                            save_clean_exit_reflection(history)
                            if active_brain_health_dir:
                                backup_path = Path(active_brain_health_dir) / "active_session_backup.json"
                                if backup_path.exists():
                                    try:
                                        backup_path.unlink()
                                    except Exception:
                                        pass
                            break
                            
                        elif cmd == "/reset":
                            log_event("🧹 Dialogue history purged via /reset")
                            history = [history[0]]
                            save_session_backup(history, Path.cwd(), llm_url, llm_model)
                            print(f"\n{C_Y}🧹 Dialogue history purged.{C_R}\n")
                            continue
                            
                        elif cmd == "/system":
                            log_event("⚙️ Dumped environment parameters via /system")
                            # Fetch fresh config from loaded env
                            fresh_env = load_env_vars()
                            cols = get_columns()
                            print(f"\n{C_G}🏛  Active Configuration Check:{C_R}")
                            for k, v in fresh_env.items():
                                if "KEY" in k or "SECRET" in k or "TOKEN" in k:
                                    v = "******** (Masked Securely)"
                                else:
                                    v = scrub_secrets(v)
                                prefix = f"  • {C_C}{k:<24}{C_R}= "
                                pref_len = visible_len(prefix)
                                wrapped_val = clean_wrap_text(v, cols - pref_len - 2)
                                wrapped_lines = wrapped_val.splitlines()
                                if wrapped_lines:
                                    print(f"{prefix}{wrapped_lines[0]}")
                                    for wl in wrapped_lines[1:]:
                                        print(f"{' ' * pref_len}{wl}")
                                else:
                                    print(f"{prefix}")
                            print()
                            continue
                            
                        elif cmd == "/search":
                            if len(cmd_parts) < 2:
                                print(f"\n{C_Y}⚠️ Usage: /search <design topic / style / palette>{C_R}\n")
                                continue
                            query = cmd_parts[1]
                            log_event(f"🔍 Direct UI-UX Pro Max search query: {query}")
                            print(f"\n{C_G}🔍 Searching UI-UX Pro Max database for: '{query}'...{C_R}")
                            res = get_design_suggestions(query)
                            if res:
                                cols = get_columns()
                                wrapped_res = clean_wrap_text(res, cols - 2)
                                print(f"\n{C_W}{wrapped_res}{C_R}\n")
                            else:
                                print(f"\n{C_Y}❌ No matches or search scripts found.{C_R}\n")
                            continue
                            
                        elif cmd == "/remember":
                            if len(cmd_parts) < 2 or "=" not in cmd_parts[1]:
                                print(f"\n{C_Y}⚠️ Usage: /remember <title> = <content>{C_R}\n")
                                continue
                            parts = cmd_parts[1].split("=", 1)
                            title = parts[0].strip()
                            content = parts[1].strip()
                            if not title or not content:
                                print(f"\n{C_Y}⚠️ Usage: /remember <title> = <content>{C_R}\n")
                                continue
                            log_event(f"🧠 Saving memory rule: '{title}'")
                            print(f"\n{C_G}🧠 Saving memory to Hivemind: '{title}'...{C_R}")
                            res = save_concept_to_hivemind(title, content, tags="user-memories", category="concepts")
                            print(f"\n{C_W}{res}{C_R}\n")
                            continue
                            
                        elif cmd == "/recall":
                            if len(cmd_parts) < 2:
                                print(f"\n{C_Y}⚠️ Usage: /recall <query>{C_R}\n")
                                continue
                            query = cmd_parts[1].strip()
                            print(f"\n{C_G}🔍 Searching Hivemind semantically for: '{query}'...{C_R}")
                            res = search_hivemind(query, category="concepts")
                            try:
                                results = json.loads(res)
                            except Exception:
                                results = []
                            
                            # Check if the results is a list (valid JSON results) or dict with 'error' or a string error
                            if isinstance(results, dict) and "error" in results:
                                draw_box([f"❌ {results['error']}"], title="🌸 HIVE RECALL ERROR", border_color=C_P, text_color=C_W)
                            elif not results or not isinstance(results, list):
                                if isinstance(res, str) and res.startswith("ERROR"):
                                    draw_box([f"❌ {res}"], title="🌸 HIVE RECALL ERROR", border_color=C_P, text_color=C_W)
                                else:
                                    draw_box(["No matching memories found in the Hivemind."], title="🌸 HIVE RECALL (0 Results)", border_color=C_P, text_color=C_W)
                            elif len(results) == 1 and "error" in results[0]:
                                draw_box([f"❌ {results[0]['error']}"], title="🌸 HIVE RECALL ERROR", border_color=C_P, text_color=C_W)
                            else:
                                box_lines = []
                                for idx, item in enumerate(results, 1):
                                    title_str = item.get("title", "Untitled")
                                    content_str = item.get("content", "")
                                    tags_str = item.get("tags", "")
                                    c_id = item.get("id", "N/A")
                                    
                                    box_lines.append(f"{C_Y}[{idx}] {title_str} (ID: {c_id}){C_R}")
                                    if tags_str:
                                        box_lines.append(f"{C_D}Tags: {tags_str}{C_R}")
                                    
                                    # Strip and append lines
                                    for line in content_str.splitlines():
                                        box_lines.append(f"  {line}")
                                    
                                    if idx < len(results):
                                        box_lines.append("---")
                                        
                                draw_box(box_lines, title=f"🌸 HIVE RECALL Results ({len(results)})", border_color=C_P, text_color=C_G)
                            print()
                            continue
                            
                        elif cmd == "/tools":
                            tools = get_harvested_tools()
                            if len(cmd_parts) < 2:
                                if not tools:
                                    print(f"\n{C_D}  No harvested sovereign tools active.{C_R}\n")
                                else:
                                    by_cat = {}
                                    for t_name, entry in tools.items():
                                        cat = entry.category
                                        if cat not in by_cat:
                                            by_cat[cat] = []
                                        by_cat[cat].append(entry)
                                    
                                    tool_lines = []
                                    for cat, entries in sorted(by_cat.items()):
                                        tool_lines.append(f"{C_Y}Category: {cat}{C_R}")
                                        for entry in sorted(entries, key=lambda x: x.name):
                                            desc_line = entry.description.splitlines()[0][:60] if entry.description else "No description."
                                            tool_lines.append(f"  • {C_G}{entry.name:<25}{C_R}{C_D}➟ {desc_line}{C_R}")
                                        tool_lines.append("")
                                    if tool_lines and tool_lines[-1] == "":
                                        tool_lines.pop()
                                    
                                    draw_box(tool_lines, title=f"🌸 HARVESTED SOVEREIGN TOOLS ({len(tools)})", border_color=C_P, text_color=C_W)
                                    print(f"\n  Use {C_C}/tools <tool_name>{C_R} for details or {C_C}/run <tool_name> arg=val{C_R} to execute.\n")
                            else:
                                target_tool = cmd_parts[1].strip()
                                entry = tools.get(target_tool)
                                if not entry:
                                    print(f"\n{C_Y}❌ Tool '{target_tool}' not found.{C_R}\n")
                                else:
                                    import inspect
                                    sig = inspect.signature(entry.handler)
                                    details = [
                                        f"{C_Y}Name:{C_R}        {C_G}{entry.name}{C_R}",
                                        f"{C_Y}Category:{C_R}    {entry.category}",
                                        f"{C_Y}Signature:{C_R}   {entry.name}{sig}",
                                        f"{C_Y}Async:{C_R}       {entry.is_async}",
                                        f"{C_Y}Required Env:{C_R} {', '.join(entry.requires_env) if entry.requires_env else 'None'}",
                                        "---",
                                        f"{C_Y}Description:{C_R}"
                                    ]
                                    for line in entry.description.splitlines():
                                        details.append(f"  {line}")
                                    draw_box(details, title=f"🌸 TOOL: {entry.name.upper()}", border_color=C_G, text_color=C_W)
                                    print()
                            continue

                        elif cmd == "/skills":
                            skills = get_harvested_skills()
                            if len(cmd_parts) < 2:
                                if not skills:
                                    print(f"\n{C_D}  No harvested template skills active.{C_R}\n")
                                else:
                                    skill_lines = []
                                    for s_name, s_data in sorted(skills.items()):
                                        desc_line = s_data["description"].splitlines()[0][:60]
                                        skill_lines.append(f"  • {C_G}{s_name:<25}{C_R}{C_D}➟ {desc_line}{C_R}")
                                    draw_box(skill_lines, title=f"🌸 ACTIVE DESIGN SKILLS ({len(skills)})", border_color=C_P, text_color=C_W)
                                    print(f"\n  Use {C_C}/skills <skill_name>{C_R} to inspect the full design workflow.\n")
                            else:
                                target_skill = cmd_parts[1].strip()
                                s_data = skills.get(target_skill)
                                if not s_data:
                                    print(f"\n{C_Y}❌ Skill '{target_skill}' not found.{C_R}\n")
                                else:
                                    details = [
                                        f"{C_Y}Name:{C_R}        {C_G}{s_data['name']}{C_R}",
                                        f"{C_Y}Path:{C_R}        {s_data['path']}",
                                        f"{C_Y}Triggers:{C_R}    {', '.join(s_data['triggers']) if s_data['triggers'] else 'None'}",
                                        "---",
                                        f"{C_Y}SKILL BLUEPRINT & INSTRUCTIONS:{C_R}"
                                    ]
                                    for line in s_data["content"].splitlines():
                                        details.append(f"  {line}")
                                    draw_box(details, title=f"🌸 SKILL: {s_data['name'].upper()}", border_color=C_G, text_color=C_W)
                                    print()
                            continue

                        elif cmd == "/run":
                            if len(cmd_parts) < 2:
                                print(f"\n{C_Y}⚠️ Usage: /run <tool_name> [param1=val1 param2=val2 ...]{C_R}\n")
                                continue
                            run_parts = cmd_parts[1].strip().split(" ", 1)
                            tool_name = run_parts[0]
                            tools = get_harvested_tools()
                            entry = tools.get(tool_name)
                            if not entry:
                                print(f"\n{C_Y}❌ Tool '{tool_name}' not found.{C_R}\n")
                                continue
                                
                            kwargs = {}
                            args = []
                            if len(run_parts) > 1:
                                param_str = run_parts[1].strip()
                                for token in re.findall(r'[^\s"]+|"[^"]*"', param_str):
                                    if "=" in token:
                                        k, v = token.split("=", 1)
                                        v = v.strip('"')
                                        kwargs[k] = v
                                    else:
                                        args.append(token.strip('"'))
                            
                            missing_envs = [ev for ev in entry.requires_env if not os.environ.get(ev)]
                            if missing_envs:
                                print(f"\n{C_RED}❌ Missing required environment variables: {', '.join(missing_envs)}{C_R}\n")
                                continue
                                
                            print(f"\n{C_G}🚀 Executing tool '{tool_name}' with args={args} kwargs={kwargs}...{C_R}")
                            log_event(f"🚀 Manual REPL run of tool '{tool_name}': args={args}, kwargs={kwargs}")
                            
                            try:
                                if entry.is_async:
                                    import asyncio
                                    try:
                                        loop = asyncio.get_event_loop()
                                        if loop.is_running():
                                            future = asyncio.run_coroutine_threadsafe(entry.handler(*args, **kwargs), loop)
                                            result = future.result()
                                        else:
                                            result = loop.run_until_complete(entry.handler(*args, **kwargs))
                                    except RuntimeError:
                                        result = asyncio.run(entry.handler(*args, **kwargs))
                                else:
                                    result = entry.handler(*args, **kwargs)
                                    
                                print(f"\n{C_G}✓ Result:{C_R}")
                                if isinstance(result, (dict, list)):
                                    print(json.dumps(result, indent=2))
                                else:
                                    print(result)
                                print()
                            except Exception as e:
                                print(f"\n{C_RED}❌ Tool execution failed: {e}{C_R}\n")
                            continue
                            
                        else:
                            # /spawn, /agents, /kill, /yolo commands
                            if cmd == "/yolo":
                                YOLO_MODE = not YOLO_MODE
                                if YOLO_MODE:
                                    draw_box([
                                        f"{C_RED}{C_BOLD}⚡ YOLO MODE ACTIVATED ⚡{C_R}",
                                        "",
                                        "Commands proposed by Kenbun will execute automatically.",
                                        "Nuclear commands (rm -rf /, mkfs, dd, fork bombs)",
                                        "are ALWAYS blocked regardless of this setting.",
                                        "",
                                        f"Type {C_C}/yolo{C_RED} again to return to safe mode.",
                                    ], title=f"{C_RED}⚡ YOLO MODE ON", border_color=C_RED, text_color=C_Y)
                                else:
                                    print(f"\n{C_G}✓ YOLO mode OFF. Manual approval restored.{C_R}\n")
                                continue

                            elif cmd == "/skin":
                                if not _ui:
                                    print(f"\n{C_Y}⚠️ Skin system is only available when Rich is installed.{C_R}\n")
                                else:
                                    args_str = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
                                    if args_str:
                                        msg = _ui.switch_skin(args_str)
                                        print(f"\n{msg}\n")
                                    else:
                                        table_str = _ui.list_skins_table()
                                        draw_box(table_str.split("\n"), title="🎨 active skin", border_color=C_P, text_color=C_W)
                                        print()
                                continue

                            elif cmd == "/spawn":
                                if spawn_agent and len(cmd_parts) > 1:
                                    task_cmd = cmd_parts[1].strip()
                                    task_name = task_cmd[:40]
                                    aid = spawn_agent(task_name, task_cmd)
                                    print(f"\n{C_G}🟡 Agent spawned:{C_R} [{aid}] {task_name}")
                                    print(f"  Use {C_C}/agents{C_R} to check status.\n")
                                elif spawn_agent is None:
                                    print(f"\n{C_Y}⚠️ Sub-agent bus not available.{C_R}\n")
                                else:
                                    print(f"\n{C_Y}Usage: /spawn <shell command>{C_R}\n")
                                continue

                            elif cmd in ("/agents", "/tasks"):
                                if list_agents:
                                    agents = list_agents()
                                    if not agents:
                                        print(f"\n{C_D}  No active agents.{C_R}\n")
                                    else:
                                        agent_lines = []
                                        for a in agents:
                                            icon = {"RUNNING": "🟡", "DONE": "✅", "ERROR": "❌", "KILLED": "🛑"}.get(a["status"], "⚪")
                                            agent_lines.append(f"  {icon} [{a['id']}] {a['task']}  ({a['status']})")
                                            if a.get("error") and a["status"] in ("ERROR", "TIMEOUT"):
                                                agent_lines.append(f"     Error: {a['error'][:80]}")
                                        draw_box(agent_lines, title=f"🤖 {C_Y}ACTIVE AGENTS", border_color=C_G, text_color=C_W)
                                        print()
                                continue

                            elif cmd == "/kill":
                                if kill_agent and len(cmd_parts) > 1:
                                    aid = cmd_parts[1].strip()
                                    ok = kill_agent(aid)
                                    print(f"\n{'🛑 Killed: ' if ok else '⚠️ Not found: '}{aid}\n")
                                else:
                                    print(f"\n{C_Y}Usage: /kill <agent-id>{C_R}\n")
                                continue

                            else:
                                print(f"\n{C_Y}❌ Unknown command: {cmd}. Type {C_C}/help{C_Y} for available commands.{C_R}\n")
                                continue

                    # ========================================================
                    # 🧠 INTENT-BASED DYNAMIC RAG & TELEMETRY PRE-FLIGHT
                    # ========================================================
                    log_event("👤 Dialogue Turn: {}".format(scrub_secrets(user_input)))
                    grounding_context = []
                    
                    # A. Design / UI / Style Intent Grounding
                    design_keywords = ["color", "palette", "font", "css", "theme", "design", "style", "ui", "ux", "brutalism", "minimalism", "bento", "chart"]
                    if any(kw in user_input.lower() for kw in design_keywords):
                        print(f"{C_D}🔍 RAG: Fetching canonical UI-UX Pro Max tokens for query...{C_R}", end="\r")
                        suggestions = get_design_suggestions(user_input)
                        if suggestions:
                            grounding_context.append(f"[DESIGN SYSTEM GROUNDING (Canonical UI-UX Pro Max reference)]:\n{suggestions}")
                    
                    # B. Diagnostic / System Intent Grounding
                    system_keywords = ["docker", "status", "port", "compose", "ip", "run", "daemon", "permission", "error", "fail", "ufw", "firewall", "logs", "active"]
                    if any(kw in user_input.lower() for kw in system_keywords):
                        print(f"{C_D}⚙️  RAG: Collecting real-time VM system & container telemetry...{C_R}", end="\r")
                        telemetry = gather_system_telemetry()
                        if telemetry:
                            grounding_context.append(f"[REAL-TIME SYSTEM DIAGNOSTIC TELEMETRY (Current VM status)]:\n{telemetry}")

                    # C. Past Lessons & Memories Grounding
                    memory_keywords = ["remember", "recall", "memory", "past", "history", "lesson", "post-mortem", "previous", "learn", "concept"]
                    if any(kw in user_input.lower() for kw in memory_keywords):
                        print(f"{C_D}🧠 RAG: Retrieving relevant lessons & past concepts from Hivemind...{C_R}", end="\r")
                        memories_res = search_hivemind(user_input, category="concepts")
                        try:
                            memories_list = json.loads(memories_res)
                        except Exception:
                            memories_list = []
                        if memories_list and isinstance(memories_list, list) and len(memories_list) > 0 and "error" not in memories_list[0]:
                            memory_blocks = []
                            for idx, item in enumerate(memories_list[:3], 1):
                                m_title = item.get("title", "Untitled")
                                m_content = item.get("content", "")
                                memory_blocks.append(f"Memory #{idx}: {m_title}\n{m_content}")
                            grounding_context.append(f"[MEMORIES & PAST LESSONS (Grounding from Hivemind)]:\n" + "\n---\n".join(memory_blocks))

                    # Compile final grounded input
                    final_input = user_input
                    if grounding_context:
                        # Clean the terminal line where progress was printed
                        cols = get_columns()
                        print(" " * cols, end="\r") 
                        context_str = "\n\n".join(grounding_context)
                        final_input = f"{context_str}\n\n[USER INSTRUCTION]:\n{user_input}"

                    final_input = scrub_secrets(final_input)
                    if final_input.strip():
                        history.append({"role": "user", "content": final_input})
                        history = prune_dialog_history(history)
                        save_session_backup(history, Path.cwd(), llm_url, llm_model)

                # Prepare streaming request and execute with fallback logic
                response = None
                max_retries = 3
                is_fallback = False
                
                try:
                    # Primary request parameters
                    actual_url = llm_url
                    actual_model = llm_model
                    is_gemini_route = "gemini" in llm_url.lower() or "googleapis" in llm_url.lower() or "generativelanguage" in llm_url.lower()
                    headers = {"Content-Type": "application/json"}
                    
                    if "GEMINI_API_KEY" in env and is_gemini_route:
                        headers["Authorization"] = f"Bearer {decrypt_value(env['GEMINI_API_KEY'])}"
                        if "cloudaidoc-pa.googleapis.com" in llm_url.lower():
                            actual_url = "https://generativelanguage.googleapis.com/v1beta/openai"
                            if actual_model == "code-assist":
                                actual_model = "gemini-1.5-pro"
                    elif ("cloudaidoc-pa.googleapis.com" in llm_url.lower() or "googleapis.com" in llm_url.lower()) and is_gemini_route:
                        try:
                            from google.auth.transport.requests import Request as AuthRequest
                            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
                            
                            # Check if local credentials file exists
                            proj_creds_path = Path(__file__).resolve().parent.parent / ".google_credentials.json"
                            credentials = None
                            project_id = None
                            
                            if proj_creds_path.exists():
                                from google.oauth2.credentials import Credentials
                                credentials = Credentials.from_authorized_user_file(str(proj_creds_path))
                                credentials.refresh(AuthRequest())
                                log_event("Successfully acquired Google OAuth access token via custom client credentials in termchat")
                                # Read project ID from custom credentials JSON
                                try:

                                    with open(proj_creds_path, "r") as f:
                                        creds_data = json.load(f)
                                        project_id = creds_data.get("project_id") or creds_data.get("quota_project_id")
                                except Exception:
                                    pass
                            else:
                                import google.auth
                                credentials, project_id = google.auth.default(scopes=scopes)
                                credentials.refresh(AuthRequest())
                                log_event("Successfully acquired Google OAuth access token via ADC in termchat")
                                # Read quota_project_id from ADC credentials file if google.auth.default didn't return one
                                if not project_id:
                                    try:
                                        adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
                                        if adc_path.exists():

                                            with open(adc_path, "r") as f:
                                                adc_data = json.load(f)
                                                project_id = adc_data.get("quota_project_id")
                                                if project_id:
                                                    log_event(f"Resolved quota_project_id from ADC file: {project_id}")
                                    except Exception:
                                        pass
                                
                            headers["Authorization"] = f"Bearer {credentials.token}"
                            
                            if "googleapis.com" in llm_url.lower():
                                gcp_project = project_id or env.get("GOOGLE_CLOUD_PROJECT") or env.get("GCP_PROJECT") or env.get("PROJECT_ID")
                                gcp_location = env.get("VERTEX_AI_LOCATION") or env.get("GOOGLE_CLOUD_REGION") or env.get("LOCATION") or "us-central1"
                                
                                if gcp_project:
                                    actual_url = f"https://{gcp_location}-aiplatform.googleapis.com/v1/projects/{gcp_project}/locations/{gcp_location}/endpoints/openapi"
                                    if actual_model == "code-assist":
                                        actual_model = "google/gemini-2.5-flash"
                                    log_event(f"Rewriting cloudaidoc endpoint to Vertex AI: {actual_url} ({actual_model})")
                                else:
                                    # Use generativelanguage.googleapis.com with x-goog-user-project header for OAuth
                                    actual_url = "https://generativelanguage.googleapis.com/v1beta/openai"
                                    if actual_model == "code-assist":
                                        actual_model = "gemini-2.5-flash"
                                    # CRITICAL: generativelanguage.googleapis.com requires x-goog-user-project for OAuth auth
                                    # Try to find any project reference to set the header
                                    fallback_project = env.get("GOOGLE_CLOUD_QUOTA_PROJECT") or env.get("GOOGLE_CLOUD_PROJECT") or env.get("GCP_PROJECT")
                                    if not fallback_project:
                                        try:
                                            adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
                                            if adc_path.exists():

                                                with open(adc_path, "r") as f:
                                                    fallback_project = json.load(f).get("quota_project_id")
                                        except Exception:
                                            pass
                                    if fallback_project:
                                        headers["x-goog-user-project"] = fallback_project
                                        log_event(f"Set x-goog-user-project={fallback_project} for generativelanguage.googleapis.com OAuth")
                                    else:
                                        log_event("WARNING: No quota project found for OAuth. API may return 500. Run: gcloud auth application-default set-quota-project YOUR_PROJECT")
                                    log_event(f"Rewriting cloudaidoc to AI Studio OAuth: {actual_url} ({actual_model})")
                        except Exception as oauth_err:
                            log_event(f"Failed to acquire Google OAuth access token: {oauth_err}")
                            print()
                            draw_box([
                                "Google Cloud CLI credentials not found or not consented!",
                                "To use the Google OAuth provider, you must install the CLI and log in:",
                                "",
                                "  1. Install: sudo snap install google-cloud-cli --classic",
                                "  2. Login:   gcloud auth application-default login",
                                "     (Ensure you check the Google Cloud Platform consent checkbox)",
                                "  - Or configure custom Client ID/Secret via bootstrap setup menu.",
                            ], title="🚨 GOOGLE AUTHENTICATION REQUIRED", border_color=C_RED, text_color=C_Y)
                            print()
                    elif "OPENAI_API_KEY" in env and "openai" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['OPENAI_API_KEY'])}"
                    elif "DEEPSEEK_API_KEY" in env and "deepseek" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['DEEPSEEK_API_KEY'])}"

                    endpoint = f"{actual_url}/chat/completions"
                    payload = {
                        "model": actual_model,
                        "messages": history,
                        "temperature": 0.7 if model_tier == "nano" else 0.2,
                        "stream": True
                    }
                    
                    if _ui:
                        _ui.print_response_header(llm_model)
                        with _ui.spinner("Thinking..."):
                            for attempt in range(max_retries + 1):
                                try:
                                    response = session.post(endpoint, json=payload, headers=headers, stream=True, timeout=30)
                                    break
                                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                                    if attempt < max_retries:
                                        backoff = 2 ** attempt
                                        time.sleep(backoff)
                                    else:
                                        raise e
                    else:
                        print(f"\n{C_P}{C_BOLD}Kenbun ({llm_model}){C_R} {C_D}▸{C_R} ", end="", flush=True)
                        
                        # Retry loop with exponential backoff for primary LLM endpoint
                        for attempt in range(max_retries + 1):
                            try:
                                response = session.post(endpoint, json=payload, headers=headers, stream=True, timeout=30)
                                break
                            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                                if attempt < max_retries:
                                    backoff = 2 ** attempt
                                    print(f"\n{C_Y}⚠️ Connection/Timeout on primary LLM: {e}. Retrying in {backoff}s... (Attempt {attempt + 1}/{max_retries}){C_R}")
                                    time.sleep(backoff)
                                else:
                                    raise e
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as primary_err:
                    # Catch primary connection failure, and trigger fallback gateway
                    fallback_url = env.get("FALLBACK_LLM_URL", "").strip()
                    fallback_model = env.get("FALLBACK_LLM_MODEL", "").strip()
                    
                    if not fallback_url or not fallback_model:
                        # No fallback configured, re-raise the original error
                        raise primary_err
                    
                    is_fallback = True
                    print() # Advance line from "Kenbun 🌸:" prefix
                    
                    # Display warning card
                    fallback_lines = [
                        "Kenbun failed to connect to primary LLM after retries.",
                        "",
                        f"➔ Failed URL: {C_W}{llm_url}{C_Y}",
                        f"➔ Error:      {C_W}{str(primary_err)}{C_Y}",
                        "---",
                        "Switching to FALLBACK GATEWAY automatically...",
                        f"⚡ Fallback URL:   {C_G}{fallback_url}{C_Y}",
                        f"📦 Fallback Model: {C_G}{fallback_model}{C_Y}"
                    ]
                    draw_box(fallback_lines, title="🚨 PRIMARY GATEWAY OFFLINE (FALLBACK DETECTED)", border_color=C_Y, text_color=C_Y)
                    print()
                    
                    # Permanently transition to the fallback configuration for the duration of session
                    llm_url = fallback_url
                    llm_model = fallback_model
                    model_tier = detect_model_tier(llm_model, llm_url)
                    
                    # Prepare headers and payload for fallback LLM
                    actual_url = llm_url
                    actual_model = llm_model
                    is_gemini_route = "gemini" in llm_url.lower() or "googleapis" in llm_url.lower() or "generativelanguage" in llm_url.lower()
                    headers = {"Content-Type": "application/json"}
                    
                    if "GEMINI_API_KEY" in env and is_gemini_route:
                        headers["Authorization"] = f"Bearer {decrypt_value(env['GEMINI_API_KEY'])}"
                        if "cloudaidoc-pa.googleapis.com" in llm_url.lower():
                            actual_url = "https://generativelanguage.googleapis.com/v1beta/openai"
                            if actual_model == "code-assist":
                                actual_model = "gemini-1.5-pro"
                    elif ("cloudaidoc-pa.googleapis.com" in llm_url.lower() or "googleapis.com" in llm_url.lower()) and is_gemini_route:
                        try:
                            from google.auth.transport.requests import Request as AuthRequest
                            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
                            
                            # Check if local credentials file exists
                            proj_creds_path = Path(__file__).resolve().parent.parent / ".google_credentials.json"
                            credentials = None
                            project_id = None
                            
                            if proj_creds_path.exists():
                                from google.oauth2.credentials import Credentials
                                credentials = Credentials.from_authorized_user_file(str(proj_creds_path))
                                credentials.refresh(AuthRequest())
                                log_event("Successfully acquired Google OAuth access token via custom client credentials in termchat")
                                # Read project ID from custom credentials JSON
                                try:

                                    with open(proj_creds_path, "r") as f:
                                        creds_data = json.load(f)
                                        project_id = creds_data.get("project_id") or creds_data.get("quota_project_id")
                                except Exception:
                                    pass
                            else:
                                import google.auth
                                credentials, project_id = google.auth.default(scopes=scopes)
                                credentials.refresh(AuthRequest())
                                log_event("Successfully acquired Google OAuth access token via ADC in termchat")
                                if not project_id:
                                    try:
                                        adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
                                        if adc_path.exists():

                                            with open(adc_path, "r") as f:
                                                adc_data = json.load(f)
                                                project_id = adc_data.get("quota_project_id")
                                    except Exception:
                                        pass
                                
                            headers["Authorization"] = f"Bearer {credentials.token}"
                            
                            if "googleapis.com" in llm_url.lower():
                                gcp_project = project_id or env.get("GOOGLE_CLOUD_PROJECT") or env.get("GCP_PROJECT") or env.get("PROJECT_ID")
                                gcp_location = env.get("VERTEX_AI_LOCATION") or env.get("GOOGLE_CLOUD_REGION") or env.get("LOCATION") or "us-central1"
                                
                                if gcp_project:
                                    actual_url = f"https://{gcp_location}-aiplatform.googleapis.com/v1/projects/{gcp_project}/locations/{gcp_location}/endpoints/openapi"
                                    if actual_model == "code-assist":
                                        actual_model = "google/gemini-2.5-flash"
                                    log_event(f"Rewriting cloudaidoc endpoint to Vertex AI: {actual_url} ({actual_model})")
                                else:
                                    actual_url = "https://generativelanguage.googleapis.com/v1beta/openai"
                                    if actual_model == "code-assist":
                                        actual_model = "gemini-2.5-flash"
                                    fallback_project = env.get("GOOGLE_CLOUD_QUOTA_PROJECT") or env.get("GOOGLE_CLOUD_PROJECT") or env.get("GCP_PROJECT")
                                    if not fallback_project:
                                        try:
                                            adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
                                            if adc_path.exists():

                                                with open(adc_path, "r") as f:
                                                    fallback_project = json.load(f).get("quota_project_id")
                                        except Exception:
                                            pass
                                    if fallback_project:
                                        headers["x-goog-user-project"] = fallback_project
                                    log_event(f"Rewriting cloudaidoc to AI Studio OAuth: {actual_url} ({actual_model})")
                        except Exception as oauth_err:
                            log_event(f"Failed to acquire Google OAuth access token: {oauth_err}")
                            print()
                            draw_box([
                                "Google Cloud CLI credentials not found or not consented!",
                                "To use the Google OAuth provider, you must install the CLI and log in:",
                                "",
                                "  1. Install: sudo snap install google-cloud-cli --classic",
                                "  2. Login:   gcloud auth application-default login",
                                "     (Ensure you check the Google Cloud Platform consent checkbox)",
                                "  - Or configure custom Client ID/Secret via bootstrap setup menu.",
                            ], title="🚨 GOOGLE AUTHENTICATION REQUIRED", border_color=C_RED, text_color=C_Y)
                            print()
                    elif "OPENAI_API_KEY" in env and "openai" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['OPENAI_API_KEY'])}"
                    elif "DEEPSEEK_API_KEY" in env and "deepseek" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['DEEPSEEK_API_KEY'])}"

                    endpoint = f"{actual_url}/chat/completions"
                    payload = {
                        "model": actual_model,
                        "messages": history,
                        "temperature": 0.7 if model_tier == "nano" else 0.2,
                        "stream": True
                    }
                    
                    if _ui:
                        _ui.print_response_header(llm_model)
                        with _ui.spinner("Thinking (fallback)..."):
                            for attempt in range(max_retries + 1):
                                try:
                                    response = session.post(endpoint, json=payload, headers=headers, stream=True, timeout=30)
                                    break
                                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as fallback_err:
                                    if attempt < max_retries:
                                        backoff = 2 ** attempt
                                        time.sleep(backoff)
                                    else:
                                        raise fallback_err
                    else:
                        print(f"\n{C_P}{C_BOLD}Kenbun ({llm_model}){C_R} {C_D}(fallback ▸){C_R} ", end="", flush=True)
                        
                        # Retry loop with exponential backoff for fallback LLM endpoint
                        for attempt in range(max_retries + 1):
                            try:
                                response = session.post(endpoint, json=payload, headers=headers, stream=True, timeout=30)
                                break
                            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as fallback_err:
                                if attempt < max_retries:
                                    backoff = 2 ** attempt
                                    print(f"\n{C_Y}⚠️ Connection/Timeout on fallback LLM: {fallback_err}. Retrying in {backoff}s... (Attempt {attempt + 1}/{max_retries}){C_R}")
                                    time.sleep(backoff)
                                else:
                                    raise fallback_err

                response.raise_for_status()
                
                full_reply = ""
                if _ui and _ui._console:
                    from rich.markdown import Markdown
                    
                    def clean_markdown_stream(text: str) -> str:
                        cleaned = re.sub(r"```(?:execute|bash|sh|spawn)\n.*?\n```", "", text, flags=re.DOTALL | re.IGNORECASE)
                        cleaned = re.sub(r"```(?:execute|bash|sh|spawn)\n.*$", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
                        return cleaned

                    with _ui.live_stream() as live:
                        for line in response.iter_lines():
                            if line:
                                decoded = line.decode("utf-8").strip()
                                if decoded.startswith("data: "):
                                    data_str = decoded[6:]
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        data_json = json.loads(data_str)
                                        choices = data_json.get("choices", [])
                                        if not choices:
                                            continue
                                        chunk = choices[0].get("delta", {}).get("content") or ""
                                        full_reply += chunk
                                        cleaned = clean_markdown_stream(full_reply)
                                        if live:
                                            live.update(Markdown(cleaned))
                                    except Exception as e:
                                        log_event(f"STREAM PARSE ERROR: {repr(e)} on chunk: {data_str}")
                                else:
                                    if decoded.startswith("{") or decoded.startswith("["):
                                        log_event(f"API WARNING: {decoded}")
                else:
                    cols = get_columns()
                    wrapper = StreamingRenderer(cols - 4)
                    wrapper.current_line_len = 20 if is_fallback else 9
                    
                    for line in response.iter_lines():
                        if line:
                            decoded = line.decode("utf-8").strip()
                            if decoded.startswith("data: "):
                                data_str = decoded[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data_json = json.loads(data_str)
                                    choices = data_json.get("choices", [])
                                    if not choices:
                                        continue
                                    chunk = choices[0].get("delta", {}).get("content") or ""
                                    wrapper.write(chunk)
                                    full_reply += chunk
                                except Exception as e:
                                    print(f"\n{C_RED}STREAM PARSE ERROR:{C_R} {repr(e)} on chunk: {data_str[:50]}...", flush=True)
                                    log_event(f"STREAM PARSE ERROR: {repr(e)} on chunk: {data_str}")
                            else:
                                if decoded.startswith("{") or decoded.startswith("["):
                                    print(f"\n{C_Y}API WARNING:{C_R} {decoded}", flush=True)
                                    log_event(f"API WARNING: {decoded}")
                    wrapper.flush()
                print("\n")
                
                # Register response
                history.append({"role": "assistant", "content": scrub_secrets(full_reply)})
                history = prune_dialog_history(history)
                save_session_backup(history, Path.cwd(), llm_url, llm_model)
                
                # Check for execute blocks: ```execute\n<command>\n```, ```bash\n<command>\n```, or ```sh\n<command>\n```
                execute_blocks = re.findall(r"```(?:execute|bash|sh)\n(.*?)\n```", full_reply, re.DOTALL | re.IGNORECASE)

                # Check for spawn blocks
                spawn_blocks = re.findall(r"```spawn\n(.*?)\n```", full_reply, re.DOTALL | re.IGNORECASE)
                if spawn_blocks and spawn_agent:
                    for sb in spawn_blocks:
                        sc = sb.strip()
                        
                        # Security Guardrail: Explicit User Authorization / YOLO check for spawn RCE
                        if YOLO_MODE:
                            is_safe = is_yolo_safe(sc)
                            if not is_safe:
                                print(f"\n{C_Y}⚠️  YOLO blocked suspicious spawn. User confirmation required.{C_R}")
                                if input(f"Spawn Agent: {sc[:60]}... (y/n): ").strip().lower() != 'y':
                                    continue
                        else:
                            print(f"\n{C_P}Kenbun wants to spawn a background agent:{C_R}")
                            if input(f"Approve spawn: {sc}? (y/n): ").strip().lower() != 'y':
                                print(f"{C_Y}Spawn cancelled by user.{C_R}")
                                continue
                                
                        aid = spawn_agent(sc[:40], sc)
                        print(f"\n{C_G}🟡 Background agent:{C_R} [{aid}] {sc[:60]}")
                        print(f"  {C_D}Use /agents to track.{C_R}\n")

                if execute_blocks:
                    # Execute ONE block at a time then let LLM react
                    cmd = execute_blocks[0].strip()
                    if len(execute_blocks) > 1:
                        print(f"\n{C_D}  (Kenbun proposed {len(execute_blocks)} commands — running the first one){C_R}")

                    # ── YOLO Mode fast-path ───────────────────────────────────────
                    if YOLO_MODE:
                        is_safe = is_yolo_safe(cmd)
                        
                        # Handle interactive YOLO override for blocked commands
                        if not is_safe:
                            # Re-verify it's not a nuclear command before prompting
                            parts = []
                            try:
                                import shlex
                                parts = shlex.split(cmd)
                            except: pass
                            
                            is_nuclear = False
                            if parts:
                                base = Path(parts[0]).name.lower()
                                args_lower = [a.lower() for a in parts[1:]]
                                if base in {"mkfs", "dd", "fdisk", "format", "reboot", "shutdown", "halt"}:
                                    is_nuclear = True
                                if base == "rm" and "-rf" in args_lower and "/" in args_lower:
                                    is_nuclear = True
                                    
                            if is_nuclear:
                                print(f"\n{C_RED}🛑 YOLO BLOCKED:{C_R} This command is on the nuclear blocklist and will NOT run.")
                            else:
                                print(f"\n{C_Y}🛑 YOLO BLOCKED:{C_R} {cmd}")
                                prompt_str = f"{C_C}Do you want to run this anyway and whitelist the executable for this project? [y/N]: {C_R}"
                                if pt_session:
                                    # Use prompt_toolkit to prevent stray newlines from auto-submitting
                                    override = pt_session.prompt(ANSI(prompt_str)).strip().lower()
                                else:
                                    override = input(prompt_str).strip().lower()
                                if override == "y":
                                    # Save to allowlist
                                    if parts:
                                        base = Path(parts[0]).name.lower()
                                        try:
                                            allowlist_path = get_active_project_root() / "brain_health" / ".yolo_allowlist.json"
                                            allowlist_path.parent.mkdir(parents=True, exist_ok=True)
                                            yolo_allowlist = []
                                            if allowlist_path.exists():
                                                with open(allowlist_path, "r") as f:
                                                    yolo_allowlist = json.load(f)
                                            if base not in yolo_allowlist:
                                                yolo_allowlist.append(base)
                                                with open(allowlist_path, "w") as f:
                                                    json.dump(yolo_allowlist, f, indent=4)
                                                print(f"{C_G}✓ Executable '{base}' added to project YOLO allowlist.{C_R}")
                                        except Exception as e:
                                            print(f"{C_Y}Failed to save allowlist: {e}{C_R}")
                                    is_safe = True
                                else:
                                    print(f"{C_Y}Skipping command.{C_R}")
                                    
                        if is_safe:
                            cols2 = get_columns()
                            print(f"\n{C_RED}⚡ YOLO:{C_R} {C_W}{cmd}{C_R}")
                            print(f"{C_RED}{'─' * min(cols2, 60)}{C_R}")
                            code, out = run_proposed_command(cmd)
                            wrapped_out = clean_wrap_text(out.strip(), cols2 - 2)
                            print(f"{C_W}{wrapped_out}{C_R}")
                            print(f"{C_RED}{'─' * min(cols2, 60)}{C_R}\n")
                            if code == 0 and is_healing_command(cmd):
                                error_feedback = "None"
                                for msg in reversed(history):
                                    content = msg.get("content", "")
                                    if content and any(t in content.lower() for t in ["error", "fail", "not found"]):
                                        error_feedback = content[:500]
                                        break
                                autonomic_reflection_save(
                                    task=f"YOLO execution: {cmd}",
                                    error=error_feedback,
                                    solution=f"Exit {code}: {out[:300]}"
                                )
                            feedback = f"[SYSTEM OUT (YOLO, cmd: '{scrub_secrets(cmd)}', exit: {code})]\n{out}"
                            history.append({"role": "user", "content": scrub_secrets(feedback)})
                            history = prune_dialog_history(history)
                            save_session_backup(history, Path.cwd(), llm_url, llm_model)
                            auto_trigger = True
                    else:
                        # ── Normal safe mode ────────────────────────────────────────
                        explain_command(cmd)
                        
                        # High-impact command dynamic warning audit
                        is_high, reason = is_command_destructive(cmd)
                        if is_high:
                            print()
                            draw_box([
                                f"{C_RED}{C_BOLD}⚠️  ATTENTION: HIGH-IMPACT / DESTRUCTIVE COMMAND DETECTED ⚠️{C_R}",
                                "",
                                f"  • {C_Y}Type:{C_R} {reason}",
                                "  • This command will execute directly on your host machine.",
                                "",
                                f"{C_RED}{C_BOLD}Please review carefully before authorizing execution!{C_R}"
                            ], title=f"{C_RED}🚨 SYSTEM SECURITY WARNING", border_color=C_RED, text_color=C_Y)
                            print()

                        draw_box([scrub_secrets(cmd)], title=f"🚀 {C_Y}PROPOSED ACTION", border_color=C_G, text_color=C_W)

                        if pt_session:
                            raw_conf = pt_session.prompt(ANSI(f"{C_G}  Authorize? {C_D}[y/N/{C_RED}yolo{C_D}]:{C_R} ")).strip().lower()
                        else:
                            raw_conf = input(f"{C_G}  Authorize? {C_D}[y/N/yolo]:{C_R} ").strip().lower()

                        if raw_conf == "yolo":
                            YOLO_MODE = True
                            print(f"\n{C_RED}⚡ YOLO mode enabled! Auto-executing this and future commands.{C_R}\n")
                            raw_conf = "y"

                        if raw_conf == "y":
                            code, out = run_proposed_command(cmd)
                            cols2 = get_columns()
                            title = f"{C_G}─── Output (exit: {code}) "
                            dash_len = max(0, cols2 - visible_len(title) - 1)
                            print(f"\n{title}{'─' * dash_len}{C_R}")
                            wrapped_out = clean_wrap_text(out.strip(), cols2 - 2)
                            print(f"{C_W}{wrapped_out}{C_R}")
                            print(f"{C_G}{'─' * cols2}{C_R}\n")
                            if code == 0 and is_healing_command(cmd):
                                error_feedback = "None detected."
                                for msg in reversed(history):
                                    content = msg.get("content", "")
                                    if content and any(t in content.lower() for t in ["error", "fail", "not found", "does not exist", "exception", "stderr"]):
                                        error_feedback = content[:500]
                                        break
                                autonomic_reflection_save(
                                    task=f"Execution of reflex command: {cmd}",
                                    error=error_feedback,
                                    solution=f"Executed command successfully (Exit Code: 0). Output: {out[:300]}"
                                )
                            feedback = f"[SYSTEM OUT (Command: '{scrub_secrets(cmd)}', Exit Code: {code})]\n{out}"
                            history.append({"role": "user", "content": scrub_secrets(feedback)})
                            history = prune_dialog_history(history)
                            save_session_backup(history, Path.cwd(), llm_url, llm_model)
                            auto_trigger = True
                        else:
                            print(f"\n{C_D}  Command skipped.{C_R}\n")
                            feedback = f"[SYSTEM NOTICE: User skipped command: '{scrub_secrets(cmd)}']"
                            history.append({"role": "user", "content": scrub_secrets(feedback)})
                            history = prune_dialog_history(history)
                            save_session_backup(history, Path.cwd(), llm_url, llm_model)
                            
            except requests.exceptions.HTTPError as http_err:
                response_obj = http_err.response
                err_msg = ""
                if response_obj is not None:
                    try:
                        err_msg = response_obj.text
                        err_json = response_obj.json()
                        if isinstance(err_json, dict):
                            err_msg = err_json.get("error", err_json.get("message", response_obj.text))
                            if isinstance(err_msg, dict):
                                err_msg = err_msg.get("message", str(err_msg))
                    except Exception:
                        err_msg = response_obj.text
                
                # Cleanly print the client error box
                status_code = response_obj.status_code if response_obj else 'Unknown'
                print()
                draw_box([err_msg or str(http_err)], title=f"❌ API SERVER ERROR (HTTP {status_code})", border_color=C_Y, text_color=C_W)
                print()
                
                # Check for missing model trigger (Self-Healing Autopilot)
                # Ensure it is NOT a cloud URL, since cloud models cannot be pulled via Ollama
                is_cloud_url = any(domain in llm_url.lower() for domain in ["api.deepseek.com", "api.openai.com", "api.anthropic.com", "googleapis.com"])
                
                # Check if it was a web routing 404 error rather than a missing local weight file
                is_routing_error = any(kw in err_msg.lower() for kw in ["url", "route", "completions"]) if err_msg else False
                
                if response_obj and response_obj.status_code == 404:
                    print(f"{C_Y}💡 Kenbun Diagnostic Tip:{C_R}")
                    print(f"  Your PRIMARY_LLM_URL is set to: {C_W}{llm_url}{C_R}")
                    print(f"  The server returned a 404 (Not Found) error for '/chat/completions'.")
                    print(f"  This usually means the URL is incorrect or doesn't support the OpenAI-compatible chat API.")
                    if "googleapis.com" in llm_url.lower() and "openai" not in llm_url.lower():
                        print(f"  ➔ {C_G}Tip: For Google AI Studio, ensure your URL ends with '/v1beta/openai'{C_R}")
                    print()
                
                if not is_cloud_url and not is_routing_error and err_msg and ("not found" in err_msg.lower() or "does not exist" in err_msg.lower() or "mismatch" in err_msg.lower()):
                    print_ollama_memory_education("pull_triggered")
                    draw_box([
                        f"Kenbun has detected that '{llm_model}' is not pulled.",
                        "Proposing automatic model pull..."
                    ], title=f"🛠️  {C_Y}AUTONOMIC SELF-HEALING: MODEL NOT FOUND", border_color=C_G, text_color=C_G)
                    print()
                    
                    # Propose dynamic pull command inside compose container or host
                    pull_cmd = f"docker exec -i portable_ollama ollama pull {llm_model} || ollama pull {llm_model}"
                    explain_command(pull_cmd)
                    draw_box([pull_cmd], title=f"🚨 {C_Y}PROPOSED SELF-HEALING ACTION", border_color=C_G, text_color=C_W)
                    print()
                    
                    confirm = input(f"{C_Y}Authorize model pull execution? [y/N]: {C_R}").strip().lower()
                    if confirm == "y":
                        code, out = run_proposed_command(pull_cmd)
                        cols = get_columns()
                        title = f"─── Output (Exit Code: {code}) "
                        dash_len = max(0, cols - len(title) - 1)
                        print(f"\n{C_G}{title}{'─' * dash_len}{C_R}")
                        wrapped_out = clean_wrap_text(out.strip(), cols - 2)
                        print(f"{C_W}{wrapped_out}{C_R}")
                        print(f"{C_G}{'─' * cols}{C_R}\n")
                        
                        # Integration: Save reflection lesson to ChromaDB for autonomic model pulls
                        if code == 0:
                            autonomic_reflection_save(
                                task=f"Pull Ollama model '{llm_model}' using command '{pull_cmd}'",
                                error=f"HTTP Error: API endpoint returned model not found or mismatch error message: '{err_msg}'",
                                solution=f"Successfully pulled and registered '{llm_model}' (Exit Code: 0)."
                            )
                        
                        print(f"{C_G}✓ Model pull completed. Please retry your message!{C_R}\n")
                        # Pop the last user message to let the user clean retry
                        if history and history[-1]["role"] == "user":
                            history.pop()
                            save_session_backup(history, Path.cwd(), llm_url, llm_model)
                auto_trigger = False
                
            except KeyboardInterrupt:
                # KeyboardInterrupt will not trigger normally under signal.signal(SIGINT),
                # but we preserve it for any libraries that raise it manually
                print(f"\n\n{C_P}🌸 Dialogue interrupted. Type /exit to close termchat.{C_R}\n")
                auto_trigger = False
            except Exception as e:
                # Format generic connection failures cleanly
                print()
                import traceback
                traceback.print_exc()
                draw_box([
                    str(e),
                    "---",
                    "Recommended Actions:",
                    "➔ Verify the LLM Server URL is correct and active.",
                    "➔ Run: docker compose up -d --build (if using Ollama)"
                ], title="❌ API CONNECTION FAILURE", border_color=C_Y, text_color=C_W)
                print()
                auto_trigger = False
    except Exception as err:
        sys.stdout.write("\n")
        error_lines = [
            "An unexpected system exception bypassed the inner shell execution context.",
            "",
            f"➔ Exception: {C_W}{type(err).__name__}: {err}{C_P}",
            "---",
            "Restoring terminal configuration before aborting.",
            "Please check logs or report this error if it persists."
        ]
        draw_box(error_lines, title="🚨 CRITICAL SYSTEM SHIELD TRIGGERED", border_color=C_P, text_color=C_G)
        sys.stdout.write(C_R)
        sys.stdout.flush()
        
        # Cleanly delete active_session_backup.json on error crash to prevent corrupted bootloop
        if active_brain_health_dir:
            backup_path = Path(active_brain_health_dir) / "active_session_backup.json"
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except Exception:
                    pass
        sys.exit(1)

if __name__ == "__main__":
    main()
