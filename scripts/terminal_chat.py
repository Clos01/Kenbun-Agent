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
except ImportError:
    PromptSession = None
    ANSI = None

# Sub-agent bus
try:
    from scripts.agent_bus import spawn_agent, list_agents, kill_agent, purge_agents, poll_status_lines
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from agent_bus import spawn_agent, list_agents, kill_agent, purge_agents, poll_status_lines
    except ImportError:
        spawn_agent = list_agents = kill_agent = purge_agents = poll_status_lines = None

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
        keyword = match.group(1)
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
            from tools.infrastructure.config import settings
            project_root = settings.PROJECT_ROOT.resolve()
        except Exception:
            try:
                from tools.utils.path_utils import get_project_root
                project_root = get_project_root().resolve()
            except Exception:
                project_root = Path(__file__).resolve().parent.parent

        # Enforce strict path traversal check: backup folder must be strictly under Home or Project Root
        allowed_roots = [Path.home().resolve(), project_root]
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


# Color palettes (Limestone & Sakura themed)
C_P = "\033[95m"       # Pink (Sakura)
C_G = "\033[92m"       # Green
C_Y = "\033[93m"       # Gold/Warning
C_C = "\033[96m"       # Cyan/Info
C_W = "\033[0m"        # Default Text Color (Automatically high-contrast on both Light and Dark themes)
C_D = "\033[90m"       # Dim grey
C_R = "\033[0m"        # Reset
C_RED = "\033[91m"     # Red/Danger
C_BOLD = "\033[1m"     # Bold
C_DIM = "\033[2m"      # Dim

# ── YOLO Mode state ────────────────────────────────────────────
YOLO_MODE = False

# Commands that are ALWAYS blocked even in YOLO mode (nuclear options)
YOLO_BLOCKLIST = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    ":(){ :|:& };:",    # fork bomb
    "chmod -R 777 /",
    "chown -R",
    "> /dev/sda",
    "shred /dev",
    "wipefs",
    "fdisk /dev/sd",
    "format c:",
]

def is_yolo_safe(cmd: str) -> bool:
    """
    Returns False if the command matches any blocked structural pattern.
    Uses shlex parsing to inspect command parts securely and prevent blocklist bypasses.
    Fail-closed: returns False if parsing or safety checks fail.
    """
    import shlex
    import re
    cmd_lower = cmd.lower().strip()
    
    # 1. Strict Character Whitelist (Default Deny on metacharacters, braces, backslashes, etc.)
    if not re.match(r"^[a-zA-Z0-9_\-\.\/ \'\"\+\=\:]+$", cmd):
        return False

    # 2. Prevent Command Chaining, background execution, subshell metacharacters,
    # redirection, globbing, brace expansion, parentheses, and backslash obfuscation (Fail-closed structural block).
    forbidden_metachars = {";", "&", "|", "`", "$", "\n", "\r", ">", "<", "*", "?", "\\", "{", "}", "(", ")"}
    if any(char in cmd for char in forbidden_metachars):
        return False

    # 3. Parse command using shlex to analyze structure
    try:
        parts = shlex.split(cmd)
    except ValueError:
        # If shell parsing fails (e.g. due to unclosed quotes), fail-closed
        return False

    if not parts:
        return True

    # 4. Strictly block sudo execution in YOLO mode to prevent privilege escalation
    if "sudo" in cmd_lower or "sudo" in parts:
        return False

    executable = parts[0].lower()
    args = [arg.lower() for arg in parts[1:]]
    executable_base = Path(executable).name

    # 4. Nuclear Blocklist (Default Allow, but block catastrophic commands)
    NUCLEAR_EXECUTABLES = {"mkfs", "dd", "fdisk", "format", "reboot", "shutdown", "halt"}
    if executable_base in NUCLEAR_EXECUTABLES:
        return False
    if executable_base == "rm" and "-rf" in args and "/" in args:
        return False

    # 5. Check local project override registry (Learned from interactive YOLO prompts)
    try:
        allowlist_path = get_active_project_root() / "brain_health" / ".yolo_allowlist.json"
        if allowlist_path.exists():
            with open(allowlist_path, "r") as f:
                yolo_allowlist = set(json.load(f))
                if executable_base in yolo_allowlist:
                    return True
    except Exception:
        pass

    # 6. Strict Allowlist (Mandated by System 2 Security Court)
    ALLOWED_EXECUTABLES = {"git", "ls", "npm", "zip", "cd", "pwd", "whoami", "cat", "echo", "python", "pip", "mkdir", "cp", "mv"}
    if executable_base not in ALLOWED_EXECUTABLES:
        return False


    # 6. Strict Argument Injection Prevention (Default Deny on dangerous flags)
    if executable_base == "git":
        for arg in args:
            if "--upload-pack" in arg or "--exec-path" in arg or "--config" in arg or "!" in arg:
                return False

    if executable_base == "npm":
        for arg in args:
            # Block arbitrary npm script execution and installation
            if arg in ("run", "exec", "install", "i", "link", "run-script", "publish"):
                return False

    # Load active project root deterministically (Fail-closed)
    try:
        from tools.infrastructure.config import settings
        project_root = settings.PROJECT_ROOT.resolve()
    except Exception:
        try:
            from tools.utils.path_utils import get_project_root
            project_root = get_project_root().resolve()
        except Exception:
            return False

    if project_root.parent == project_root or str(project_root).lower().rstrip("/\\") in (
        "", "/", "c:", "d:", "c:\\", "d:\\", "/users", "/home", "/private", "/var", "/etc", "/tmp"
    ):
        return False

    def is_path_in_workspace(path_str: str) -> bool:
        try:
            target_path = Path(path_str).expanduser().resolve()
            # Enforce symlink check on components to prevent TOCTOU symlink swaps
            current = target_path
            while current != current.parent:
                if current.is_symlink():
                    return False
                current = current.parent
                
            if hasattr(target_path, "is_relative_to"):
                return target_path.is_relative_to(project_root)
            else:
                target_path.relative_to(project_root)
                return True
        except Exception:
            # Resolution failed or is outside -> Fail-closed
            return False

    # Check 1: Recursive/Forced deletion target checks (Fail-closed)
    if executable_base == "rm":
        has_recursive = any("-" in arg and "r" in arg for arg in args)
        has_no_preserve = any("--no-preserve-root" in arg for arg in args)
        
        if has_no_preserve:
            return False
            
        if has_recursive or any("rf" in arg or "fr" in arg for arg in args):
            # Target check
            targets = [arg for arg in args if not arg.startswith("-")]
            if not targets:
                return False
                
            for target in targets:
                if not is_path_in_workspace(target):
                    return False
                
                # Check for sensitive top-level folders explicitly
                sensitive_paths = {"/", "/*", "~", os.path.expanduser("~").lower(), "/etc", "/var", "/usr", "/bin", "/sbin", "/boot", "/lib", "/system"}
                clean_target = target.strip("\"'").rstrip("/")
                if clean_target in sensitive_paths:
                    return False
                    
                try:
                    resolved_target = Path(clean_target).expanduser().resolve()
                    if str(resolved_target) in sensitive_paths or str(resolved_target) in ("/", os.path.expanduser("~"), str(Path.home())):
                        return False
                except Exception:
                    return False

    # Check 2: Block recursive chmod/chown on sensitive root directories or outside workspace
    if executable_base in ("chmod", "chown"):
        has_recursive = any("-" in arg and "r" in arg for arg in args)
        if has_recursive:
            targets = [arg for arg in args if not arg.startswith("-")]
            if not targets:
                return False
            for target in targets:
                if not is_path_in_workspace(target):
                    return False

    # Fallback legacy check
    cmd_condensed = "".join(cmd_lower.split())
    for danger in YOLO_BLOCKLIST:
        danger_condensed = "".join(danger.split()).lower()
        if danger_condensed in cmd_condensed:
            return False

    return True


def is_command_destructive(cmd: str) -> tuple[bool, str]:
    """
    Checks if a command has potentially destructive or high-impact side effects.
    Returns (is_high_impact, reason_description).
    """
    cmd_lower = cmd.lower().strip()
    
    # 1. Superuser privileges
    if cmd_lower.startswith("sudo "):
        return True, "Runs with superuser (root) privileges"
        
    # 2. File / folder deletion
    if "rm " in cmd_lower and ("-r" in cmd_lower or "-f" in cmd_lower or "rf" in cmd_lower):
        return True, "Deletes files or directories recursively/permanently"
        
    # 3. System prune / clean
    if "prune" in cmd_lower:
        return True, "Wipes or cleans Docker volumes/cache permanently"
        
    # 4. Uninstall/purge commands
    if "uninstall" in cmd_lower or "purge" in cmd_lower or "apt-get remove" in cmd_lower:
        return True, "Uninstalls packages or software libraries"
        
    # 5. Dangerous disk commands
    if any(k in cmd_lower for k in ["dd ", "mkfs", "fdisk", "wipefs", "shred"]):
        return True, "Overwrites or modifies physical disk partitions"
        
    # 6. Fork bomb or kernel panic triggers
    if ":(){ :|:& };:" in cmd_lower or "reboot" in cmd_lower or "shutdown" in cmd_lower:
        return True, "Reboots or shuts down the system"
        
    return False, ""

# Helper functions for clean terminal display and dynamic layout
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def visible_len(text):
    """Calculates the printable length of a string, ignoring ANSI escape sequences."""
    return len(ANSI_ESCAPE.sub('', text))

def get_columns():
    """Gets the active terminal columns, defaulting to 80."""
    try:
        cols = shutil.get_terminal_size(fallback=(80, 24)).columns
        return cols if cols > 0 else 80
    except Exception:
        return 80

def clean_wrap_text(text, width):
    """
    Word-wraps long text to fit a given width cleanly, preserving original line breaks.
    If a single word exceeds the width, it is broken up into segments of length `width`.
    """
    if not text:
        return ""
    if width <= 0:
        width = 80
        
    wrapped_lines = []
    for line in text.splitlines():
        if not line.strip():
            wrapped_lines.append("")
            continue
        
        words = line.split(" ")
        current_line = []
        current_len = 0
        
        for word in words:
            word_len = visible_len(word)
            if word_len > width:
                # First flush current line
                if current_line:
                    wrapped_lines.append(" ".join(current_line))
                    current_line = []
                    current_len = 0
                
                # Split the long word into chunks of width while keeping ANSI codes intact
                has_ansi = bool(ANSI_ESCAPE.search(word))
                if not has_ansi:
                    for i in range(0, len(word), width):
                        wrapped_lines.append(word[i:i+width])
                else:
                    tokens = []
                    last_idx = 0
                    for m in ANSI_ESCAPE.finditer(word):
                        start, end = m.start(), m.end()
                        for c in word[last_idx:start]:
                            tokens.append((c, False))
                        tokens.append((word[start:end], True))
                        last_idx = end
                    for c in word[last_idx:]:
                        tokens.append((c, False))
                    
                    chunk_str = ""
                    chunk_len = 0
                    for tok, is_escape in tokens:
                        if is_escape:
                            chunk_str += tok
                        else:
                            if chunk_len >= width:
                                wrapped_lines.append(chunk_str)
                                chunk_str = tok
                                chunk_len = 1
                            else:
                                chunk_str += tok
                                chunk_len += 1
                    if chunk_str:
                        wrapped_lines.append(chunk_str)
            else:
                added_len = word_len + (1 if current_line else 0)
                if current_len + added_len <= width:
                    current_line.append(word)
                    current_len += added_len
                else:
                    if current_line:
                        wrapped_lines.append(" ".join(current_line))
                    current_line = [word]
                    current_len = word_len
        if current_line:
            wrapped_lines.append(" ".join(current_line))
    return "\n".join(wrapped_lines)

def draw_box(lines, title=None, border_color=C_G, text_color=C_W):
    """
    Draws a clean Limestone/Sakura styled box dynamically adjusted to terminal width.
    Each line in `lines` can contain ANSI escape codes. They will be wrapped cleanly.
    """
    cols = get_columns()
    box_width = min(cols, 80)
    if box_width < 40:
        box_width = cols
        
    content_width = box_width - 4  # 2 for border and spaces on each side
    if content_width <= 0:
        content_width = 36  # safe fallback
        
    # Border characters
    top_left = "┌"
    top_right = "┐"
    bottom_left = "└"
    bottom_right = "┘"
    horizontal = "─"
    horizontal_top = "─"
    horizontal_bottom = "─"
    vertical = "│"
    divider = "├"
    divider_right = "┤"
    
    # Print top border with title if present
    if title:
        vis_title = visible_len(title)
        if vis_title + 6 <= box_width:
            left_dash_count = (box_width - 2 - vis_title - 2) // 2
            right_dash_count = box_width - 2 - vis_title - 2 - left_dash_count
            top_border = f"{border_color}{top_left}{horizontal_top * left_dash_count} {title} {horizontal_top * right_dash_count}{top_right}{C_R}"
        else:
            top_border = f"{border_color}{top_left}{horizontal_top * (box_width - 2)}{top_right}{C_R}"
    else:
        top_border = f"{border_color}{top_left}{horizontal_top * (box_width - 2)}{top_right}{C_R}"
        
    print(top_border)
    
    for line in lines:
        if line == "---":
            print(f"{border_color}{divider}{horizontal * (box_width - 2)}{divider_right}{C_R}")
        else:
            wrapped_sublines = clean_wrap_text(line, content_width).splitlines()
            if not wrapped_sublines:
                print(f"{border_color}{vertical}{C_R} {' ' * content_width} {border_color}{vertical}{C_R}")
            for subline in wrapped_sublines:
                vis_len = visible_len(subline)
                padding = content_width - vis_len
                if padding < 0:
                    padding = 0
                print(f"{border_color}{vertical}{C_R} {text_color}{subline}{C_R}{' ' * padding} {border_color}{vertical}{C_R}")
                
    print(f"{border_color}{bottom_left}{horizontal_bottom * (box_width - 2)}{bottom_right}{C_R}")

def print_ollama_memory_education(context_type):
    """
    Prints an educational block detailing how Ollama serves weights, 
    VRAM/RAM constraints, and what the corrected configuration accomplishes.
    """
    edu_lines = [
        "🌸 KENBUN COGNITIVE ARCHITECTURE LESSON:",
        "----------------------------------------",
        "🧠 How Ollama Serves Model Weights:",
        "Ollama acts as a local runner that dynamically loads quantized model",
        "weights (stored in GGUF format) into your system's hardware memory.",
        "",
        "💾 VRAM & RAM Constraints:",
        "  • 1.5B/3B Models: Require ~2GB to 4GB of memory. Fit easily on standard",
        "    laptops (even CPU-only systems).",
        "  • 8B Models: Require ~6GB to 8GB of memory. Run fast on Apple Silicon",
        "    (M1/M2/M3) or dedicated NVIDIA GPUs.",
        "  • 70B Models: Require 40GB+ of VRAM. Fall back to CPU RAM if insufficient,",
        "    resulting in slow token generation rates (1-2 tokens/sec).",
        "",
        "🔄 Context Realignment:"
    ]
    if context_type == "mismatch_resolved":
        edu_lines.extend([
            "By correcting your URL or model name, we aligned the API client's",
            "expectations with the provider's capabilities. Cloud servers run",
            "remote inference on high-capacity servers using proprietary weights",
            "(e.g., GPT-4), whereas Ollama manages local execution on your machine."
        ])
    else: # pull_triggered
        edu_lines.extend([
            "Pulling the model downloads the weight files onto your local disk.",
            "Ollama then allocates standard VRAM/RAM buffers, registers the HTTP",
            "endpoints, and prepares to compile query vectors. This self-healing",
            "action restores local inference immediately!"
        ])
    
    edu_lines.extend([
        "---",
        "💡 Learn More: Run 'ollama list' in your terminal to see local models."
    ])
    
    draw_box(edu_lines, title="🧠 COGNITIVE EDUCATION DIAGNOSTIC", border_color=C_P, text_color=C_G)

def explain_command(cmd):
    """
    Parses a system command and prints a beautiful Limestone/Sakura styled card
    educating the user about the utility, why it is needed, and manual syntax.
    """
    cmd_clean = cmd.strip()
    cmd_lower = cmd_clean.lower()
    
    tool_name = "System CLI Command"
    why_needed = "Executing an operations command to inspect, configure, or run workspace processes."
    pro_tip = f"You can run this command directly in your shell: `{cmd_clean}`"
    
    # Identify Tool
    if cmd_lower.startswith("docker"):
        tool_name = "Docker Container Engine"
        why_needed = "Manages, starts, and inspects containerized services (like databases, services, or local LLMs) in isolated environments."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `docker ps`"
    elif "ollama" in cmd_lower:
        tool_name = "Ollama Local Weights Manager"
        why_needed = "Downloads, serves, and manages large language model weights locally on your system hardware without external network APIs."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `ollama list`"
    elif "ufw" in cmd_lower:
        tool_name = "UFW (Uncomplicated Firewall)"
        why_needed = "Controls local host network ports and regulates traffic to protect development servers from external access."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `sudo ufw status`"
    elif cmd_lower.startswith("git"):
        tool_name = "Git Version Control"
        why_needed = "Tracks file changes, manages repository state, and handles project branches."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `git status`"
    elif cmd_lower.startswith("npm") or cmd_lower.startswith("node"):
        tool_name = "Node.js Environment & Package Manager"
        why_needed = "Installs packages and runs JavaScript/TypeScript runtimes for web apps and tooling."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `npm list`"
    elif "pip" in cmd_lower or cmd_lower.startswith("python"):
        tool_name = "Python Package & Runtime Utility"
        why_needed = "Manages Python dependencies, environments (virtualenvs), and executes Python-based scripting tools."
        pro_tip = "💡 Pro-Tip: You can run this command directly in your shell: `pip list`"
    elif any(cmd_lower.startswith(x) for x in ["mkdir", "rm", "cp", "mv", "ls", "cat", "chmod", "pwd", "whoami"]):
        tool_name = "POSIX OS Filesystem Operations"
        why_needed = "Performs filesystem manipulation tasks such as creating, moving, reading, copying, or deleting files and folders."
        pro_tip = f"💡 Pro-Tip: You can run this command directly in your shell: `ls -lh`"
        
    # Explainer Fatigue Mitigation: Do not show giant explainer for basic POSIX read-only commands
    if cmd_lower.strip() in ["ls", "pwd", "whoami", "clear", "ls -l", "ls -la"]:
        return

    lines = [
        f"🛠️  Tool Running: {C_W}{tool_name}{C_G}",
        f"🎯 Active Context: {why_needed}",
        "---",
        pro_tip
    ]
    
    draw_box(lines, title="💡 EDUCATIONAL TOOL EXPLAINER", border_color=C_P, text_color=C_G)

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

class StreamingRenderer:
    """
    Intelligent streaming renderer that:
    1. Suppresses raw markdown code-fence tags (```execute, ```bash, etc)
    2. Buffers and hides code block contents until the closing fence
    3. Handles word-wrapping for normal prose in real-time
    4. Eliminates line-buffering latency for an elite streaming experience
    5. Formats inline code (backticks) as Bold Cyan for supreme CLI aesthetics
    6. Formats double asterisks as bold text
    """
    FENCE_OPEN = re.compile(r'^```(execute|bash|sh|spawn)', re.IGNORECASE)
    FENCE_CLOSE = re.compile(r'^```\s*$')

    def __init__(self, width: int):
        self.width = max(width, 40)
        self.current_line_len = 0
        self.word_buffer = ""
        self._line_buffer = ""     # accumulates current line to detect fences
        self._in_code_block = False
        self._code_lang = ""
        self._code_buffer = ""
        self._in_inline_code = False
        self._in_bold = False
        self._asterisk_count = 0

    def write(self, chunk: str):
        """Feed a streaming chunk of text."""
        for char in chunk:
            if self._in_code_block:
                self._line_buffer += char
                if char == '\n':
                    line = self._line_buffer.rstrip('\n')
                    if self.FENCE_CLOSE.match(line.strip()):
                        self._in_code_block = False
                        self._code_lang = ""
                        self._line_buffer = ""
                    else:
                        self._code_buffer += self._line_buffer
                        self._line_buffer = ""
            else:
                # If we are buffering a potential code fence line (starts with `)
                if self._line_buffer or char == '`':
                    self._line_buffer += char
                    if char == '\n':
                        line = self._line_buffer.rstrip('\n')
                        m = self.FENCE_OPEN.match(line.strip())
                        if m:
                            self._in_code_block = True
                            self._code_lang = m.group(1).lower() or "text"
                            self._code_buffer = ""
                            self._line_buffer = ""
                        else:
                            # Not a fence, process the accumulated line buffer as normal prose
                            content = self._line_buffer
                            self._line_buffer = ""
                            for c in content:
                                self._emit_char_prose(c)
                else:
                    # Normal prose — emit characters immediately with word-level buffering
                    self._emit_char_prose(char)

    def _check_and_flush_asterisks(self, current_char: str):
        """Helper to process and style double asterisks (bold) or single asterisks."""
        if self._asterisk_count > 0 and current_char != '*':
            if self._asterisk_count == 2:
                # Toggle bold style
                if not self._in_bold:
                    self._in_bold = True
                    sys.stdout.write("\033[90m**\033[1m") # Dim asterisks + Bold style
                else:
                    self._in_bold = False
                    sys.stdout.write("\033[0m\033[90m**\033[0m") # Reset + Dim asterisks + Reset
                sys.stdout.flush()
                self.current_line_len += 2
            else:
                # Print the single asterisk
                sys.stdout.write("*" * self._asterisk_count)
                sys.stdout.flush()
                self.current_line_len += self._asterisk_count
            self._asterisk_count = 0

    def _emit_char_prose(self, char: str):
        # First check and flush any buffered asterisks
        self._check_and_flush_asterisks(char)

        if char == '\n':
            if self.word_buffer:
                self._flush_word()
            sys.stdout.write('\n')
            sys.stdout.flush()
            self.current_line_len = 0
        elif char.isspace():
            if self.word_buffer:
                self._flush_word()
            if self.current_line_len > 0:
                sys.stdout.write(char)
                sys.stdout.flush()
                self.current_line_len += 1
        elif char == '*':
            if self.word_buffer:
                self._flush_word()
            self._asterisk_count += 1
            return
        elif char in '.,!?;:()[]{}<>-+_=/\\|&^%$#@~"\'`': # Handle punctuation including backtick
            if self.word_buffer:
                self._flush_word()
            
            if char == '`':
                # Toggle inline code styling
                if not self._in_inline_code:
                    self._in_inline_code = True
                    sys.stdout.write("\033[90m`\033[1;36m") # Dim grey backtick + Bold Cyan for the command
                else:
                    self._in_inline_code = False
                    sys.stdout.write("\033[0m\033[90m`\033[0m") # Reset + Dim grey backtick + Reset
                sys.stdout.flush()
                self.current_line_len += 1
                return

            if self.current_line_len + 1 > self.width:
                sys.stdout.write('\n')
                sys.stdout.flush()
                self.current_line_len = 0
            sys.stdout.write(char)
            sys.stdout.flush()
            self.current_line_len += 1
        else:
            self.word_buffer += char

    def _flush_word(self):
        w_len = visible_len(self.word_buffer)
        if self.current_line_len + w_len > self.width:
            sys.stdout.write('\n')
            sys.stdout.flush()
            self.current_line_len = 0
        sys.stdout.write(self.word_buffer)
        sys.stdout.flush()
        self.current_line_len += w_len
        self.word_buffer = ""

    def flush(self):
        """Flush any remaining buffers."""
        # Ensure any trailing asterisks are flushed before finishing
        self._check_and_flush_asterisks('\033')
        if self.word_buffer:
            self._flush_word()
        if self._line_buffer:
            content = self._line_buffer
            self._line_buffer = ""
            for c in content:
                self._emit_char_prose(c)
            self._check_and_flush_asterisks('\033')
            if self.word_buffer:
                self._flush_word()

    def get_captured_blocks(self):
        """Return (lang, content) of the last captured code block (unused but available)."""
        return self._code_lang, self._code_buffer

# Keep backward-compatible alias
StreamingWordWrapper = StreamingRenderer

# Global tracking variable for active memory directory

active_brain_health_dir = None

def decrypt_value(val):
    """Decrypts values that are encrypted with 'enc:' prefix using the repository master key."""
    if not val.startswith("enc:"):
        return val
    try:
        from cryptography.fernet import Fernet
        # Resolve key file path dynamically
        possible_keys = [
            Path.cwd() / ".kenbun_master.key",
            Path.cwd() / "core" / ".kenbun_master.key",
            Path(__file__).parent.parent / ".kenbun_master.key",
            Path(__file__).parent.parent / "core" / ".kenbun_master.key"
        ]
        key = None
        for kp in possible_keys:
            if kp.exists():
                with open(kp, "rb") as f:
                    key = f.read().strip()
                break
        
        if key:
            f = Fernet(key)
            # Decrypt value (strip 'enc:' prefix)
            return f.decrypt(val[4:].encode()).decode()
    except Exception:
        # Fallback to returning raw string if decryption fails or cryptography is missing
        pass
    return val

def update_env_value(key, new_value):
    """Safely updates a specific key-value pair in .env file, symmetrically encrypting it if needed."""
    possible_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "core" / ".env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "core" / ".env"
    ]
    target_path = None
    for path in possible_paths:
        if path.exists():
            target_path = path
            break
            
    if not target_path:
        target_path = Path.cwd() / ".env"
        
    lines = []
    updated = False
    
    # Read existing lines
    if target_path.exists():
        try:
            with open(target_path, "r") as f:
                lines = f.readlines()
        except PermissionError:
            print(f"\n{C_Y}❌ Permission Denied when trying to open {target_path}. Run with appropriate permissions.{C_R}")
            return False
            
    # Symmetrically encrypt the new value using the master key
    encrypted_val = new_value
    try:
        # Resolve the tools module to load secret_manager
        sys.path.insert(0, str(target_path.parent / "core"))
        from tools.utils.secret_manager import encrypt_value
        encrypted_val = "enc:" + encrypt_value(new_value)
    except Exception:
        pass
        
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            new_lines.append(f"{key}={encrypted_val}\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        new_lines.append(f"{key}={encrypted_val}\n")
        
    try:
        with open(target_path, "w") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"\n{C_Y}❌ Failed to write back env configuration: {e}{C_R}")
        return False

def load_env_vars():
    """Manually parse .env file to load active configurations securely."""
    env = {}
    possible_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "core" / ".env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "core" / ".env"
    ]
    for path in possible_paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                val = parts[1].strip().strip('"').strip("'")
                                # Decrypt immediately on load!
                                env[key] = decrypt_value(val)
                break
            except PermissionError:
                # Catch permission errors gracefully during pre-flight diagnostics
                pass
    return env

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
        from tools.harvester import harvest_and_register_tools
        from tools.registry import registry
        
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

def detect_configuration_mismatch(llm_url, llm_model):
    """Detects mismatch between cloud provider URLs and local Ollama model names."""
    is_cloud_url = any(domain in llm_url.lower() for domain in ["api.deepseek.com", "api.openai.com", "api.anthropic.com", "googleapis.com"])
    local_keywords = ["llama", "qwen", "mistral", "gemma", "phi3", "orca", "deepseek-r1"]
    is_local_model = any(kw in llm_model.lower() for kw in local_keywords)
    if is_cloud_url and is_local_model:
        return True, "cloud_url_with_local_model"
    return False, None

def check_and_heal_mismatch(llm_url, llm_model):
    """
    SILENT auto-healer — no user prompts.
    Detects cloud URL + local model mismatch and automatically aligns the
    model to the correct cloud provider, preserving their cloud key and URL.
    """
    has_mismatch, _ = detect_configuration_mismatch(llm_url, llm_model)
    if not has_mismatch:
        return llm_url, llm_model

    # Determine the best cloud model name based on the cloud URL
    target_model = "gpt-4o-mini"
    provider_name = "OpenAI"
    if "anthropic" in llm_url.lower():
        target_model = "claude-3-5-sonnet-latest"
        provider_name = "Anthropic"
    elif "googleapis" in llm_url.lower():
        target_model = "gemini-2.5-flash"
        provider_name = "Google AI Studio"
    elif "deepseek" in llm_url.lower():
        target_model = "deepseek-chat"
        provider_name = "DeepSeek"

    # Symmetrically encrypt the healed model name if Fernet key is active
    try:
        from cryptography.fernet import Fernet
        possible_keys = [
            Path.cwd() / ".kenbun_master.key",
            Path.cwd() / "core" / ".kenbun_master.key",
            Path(__file__).parent.parent / ".kenbun_master.key",
            Path(__file__).parent.parent / "core" / ".kenbun_master.key"
        ]
        key = None
        for kp in possible_keys:
            if kp.exists():
                with open(kp, "rb") as fk:
                    key = fk.read().strip()
                break
        if key:
            f = Fernet(key)
            encrypted_model = f"enc:{f.encrypt(target_model.encode()).decode()}"
            update_env_value("PRIMARY_LLM_MODEL", encrypted_model)
        else:
            update_env_value("PRIMARY_LLM_MODEL", target_model)
    except Exception:
        update_env_value("PRIMARY_LLM_MODEL", target_model)

    print(f"{C_G}⚡ Auto-heal:{C_R} Cloud URL detected with local model. Aligned model to {C_G}{target_model}{C_R} ({provider_name})")
    return llm_url, target_model

def detect_model_tier(llm_model: str, llm_url: str) -> str:
    """
    Returns the capability tier of the active model:
      'nano'     — ≤3B params (llama3.2:1b, deepseek-r1:1.5b, phi3:mini)
      'standard' — 3B-14B (llama3.2:3b, gemma3:9b, mistral:7b)
      'cloud'    — Remote APIs (gpt-*, gemini-*, claude-*)
    """
    is_cloud = any(d in llm_url.lower() for d in ["openai.com", "anthropic.com", "googleapis.com", "deepseek.com"])
    if is_cloud:
        return "cloud"
    nano_patterns = [":1b", ":1.5b", ":0.5b", ":2b", "phi3:mini", "tinyllama"]
    if any(p in llm_model.lower() for p in nano_patterns):
        return "nano"
    return "standard"

def run_startup_probe(llm_url: str, llm_model: str, chroma_host: str = "localhost", chroma_port: str = "8000") -> dict:
    """
    Runs parallel health checks against Ollama/Cloud APIs, ChromaDB, and Docker.
    Returns a dict of { service: (ok: bool, detail: str) }.
    """
    import threading as _t
    results = {}
    lock = _t.Lock()

    def probe_ollama():
        # Check if cloud provider (e.g. Google Gemini, OpenAI, DeepSeek, Anthropic)
        is_cloud = any(domain in llm_url.lower() for domain in ["api.deepseek.com", "api.openai.com", "api.anthropic.com", "googleapis.com", "azure.com"])
        if is_cloud:
            try:
                # Fast socket connection check on port 443 to verify internet/endpoint reachability
                from urllib.parse import urlparse
                parsed = urlparse(llm_url)
                hostname = parsed.hostname or "google.com"
                
                import socket
                socket.create_connection((hostname, 443), timeout=1.5)
                with lock:
                    results["ollama"] = (True, f"ONLINE  •  {llm_model} ({hostname})")
            except Exception as e:
                with lock:
                    results["ollama"] = (False, f"Cloud gateway unreachable — {str(e)[:50]}")
        else:
            try:
                import requests as _r
                base = llm_url.replace("/v1", "").replace("/v1beta/openai", "")
                _r.get(f"{base}/api/tags", timeout=3)
                with lock:
                    results["ollama"] = (True, f"{llm_model}  •  {base.split('://')[-1]}")
            except Exception as e:
                with lock:
                    results["ollama"] = (False, f"Unreachable — {str(e)[:60]}")

    def probe_chroma():
        try:
            import requests as _r
            _r.get(f"http://{chroma_host}:{chroma_port}/api/v2/heartbeat", timeout=2)
            with lock:
                results["chromadb"] = (True, f"ACTIVE  •  {chroma_host}:{chroma_port}")
        except Exception:
            try:
                import requests as _r
                _r.get(f"http://{chroma_host}:{chroma_port}/api/v1/heartbeat", timeout=2)
                with lock:
                    results["chromadb"] = (True, f"ACTIVE  •  {chroma_host}:{chroma_port}")
            except Exception:
                with lock:
                    results["chromadb"] = (False, f"Offline — start docker compose")

    def probe_docker():
        try:
            r = subprocess.run(["docker", "info"], capture_output=True, timeout=3)
            ok = r.returncode == 0
            with lock:
                results["docker"] = (ok, "Running" if ok else "Daemon offline")
        except Exception:
            with lock:
                results["docker"] = (False, "Not installed or offline")

    threads = [_t.Thread(target=f, daemon=True) for f in [probe_ollama, probe_chroma, probe_docker]]
    for th in threads: th.start()
    for th in threads: th.join(timeout=4)
    return results

def print_health_card(probe_results: dict) -> bool:
    """
    Prints a compact system health card. Returns True if all services OK.
    """
    icons = {True: f"{C_G}✓{C_R}", False: f"{C_Y}✗{C_R}"}
    labels = {"ollama": "Ollama", "chromadb": "ChromaDB", "docker": "Docker"}
    lines = []
    all_ok = True
    for key in ["ollama", "chromadb", "docker"]:
        ok, detail = probe_results.get(key, (False, "Not checked"))
        if not ok:
            all_ok = False
        icon = icons[ok]
        label = f"{labels[key]:<10}"
        lines.append(f"  {icon} {label}  {detail}")
    draw_box(lines, title=f"🌐 {C_Y}SYSTEM HEALTH", border_color=C_G if all_ok else C_Y, text_color=C_W)
    return all_ok

def build_system_prompt(tier: str, llm_model: str) -> str:
    """
    Returns a model-tier-aware system prompt.
    Nano models get a simplified, focused prompt to prevent hallucination.
    """
    base = (
        f"You are Kenbun, an AI assistant running inside a local terminal on the user's machine. "
        f"You are currently powered by the LLM: {llm_model}. Do not hallucinate your architecture or claim to be LLaMA unless that is your actual active model.\n"
        "Your job is to have a helpful conversation and assist with coding, system diagnosis, and design tasks.\n"
    )
    execute_block = (
        "\nCOMMAND EXECUTION:\n"
        "When you need to run a real system command, output it in this exact format:\n"
        "```execute\n<the shell command>\n```\n"
        "The user will approve it before it runs. Only use this for actual system tasks — "
        "NOT for answering questions or explaining things.\n"
    )
    spawn_block = (
        "\nBACKGROUND AGENTS:\n"
        "For long-running tasks (model pulls, builds, large file ops), use:\n"
        "```spawn\n<the shell command>\n```\n"
        "This runs the task in the background without blocking our conversation.\n"
    )
    memory_block = (
        "\nMEMORY:\n"
        "You have access to a local Hivemind (ChromaDB). The user can:\n"
        "  /remember <title> = <content>  — save a note\n"
        "  /recall <query>               — search memories\n"
    )

    if tier == "nano":
        return (
            base +
            "Keep all responses short and direct. No walls of text.\n"
            "Converse naturally. Only use the execute block if the user explicitly asks "
            "you to run something or you need live system data to answer.\n" +
            execute_block
        )
    elif tier == "standard":
        return base + execute_block + spawn_block + memory_block
    else:  # cloud
        return (
            base +
            "You have full reasoning capability. Use multi-step thinking for complex problems. "
            "Delegate long-running tasks to background agents using spawn blocks.\n" +
            execute_block + spawn_block + memory_block +
            "\nAST HARVESTED TOOL RUNNER:\n"
            "You can run any kenbun CLI tool via the execute block (e.g., `kenbun recall`, `kenbun search`).\n"
        )

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
                    if old_f.exists():
                        shutil.copy2(old_f, target_bh / f_name)
                        
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
    if core_path not in sys.path:
        sys.path.insert(0, core_path)
    
    try:
        from tools.memory.knowledge_manager import learn_concept
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
    if core_path not in sys.path:
        sys.path.insert(0, core_path)
    
    try:
        from tools.memory.knowledge_manager import list_concepts
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
        if sys_path_str not in sys.path:
            sys.path.insert(0, sys_path_str)
            
        from tools.memory.knowledge_manager import record_post_mortem
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
        if sys_path_str not in sys.path:
            sys.path.insert(0, sys_path_str)
            
        from tools.memory.knowledge_manager import learn_concept
        
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
            import shutil
        
            try:
                parts = shlex.split(cmd)
            except ValueError as e:
                return -1, f"[Execution Error: Failed to parse command safely: {e}]"
            
            if not parts:
                return 0, "[Success: Empty command]"
            
            executable = parts[0]
        
            # Explicit handling for shell builtin 'cd'
            if executable == "cd":
                target = parts[1] if len(parts) > 1 else str(Path.home())
                try:
                    resolved_path = Path(target).resolve()
                
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
        
            # Absolute path resolution
            abs_path = shutil.which(executable)
            if not abs_path:
                return 127, f"{executable}: command not found"
            
            parts[0] = abs_path
        
            result = subprocess.run(
                parts,
                shell=False,
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
    llm_model = env.get("PRIMARY_LLM_MODEL", "llama3.2:3b")
    
    # Resolve initial brain health dir per v2.8.0 specification
    cwd = Path.cwd().resolve()
    system_root = get_active_project_root()
    if cwd != system_root and ((cwd / ".git").exists() or (cwd / ".kenbun").exists()):
        active_brain_health_dir = cwd / "brain_health"
    else:
        active_brain_health_dir = system_root / "brain_health"
    active_brain_health_dir.mkdir(parents=True, exist_ok=True)
    
    # Audit and dynamically self-heal cloud/local mismatches before displaying banner
    llm_url, llm_model = check_and_heal_mismatch(llm_url, llm_model)
    
    # Proactive URL Normalization for standard local/tailscale APIs (Ollama compatibility endpoint)
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

    # Print banner (compact)
    cols = get_columns()
    if cols >= 70:
        print(f"\n{C_P}██╗  ██╗███████╗███╗   ██╗██████╗ ██╗   ██╗███╗   ██╗")
        print("██║ ██╔╝██╔════╝████╗  ██║██╔══██╗██║   ██║████╗  ██║")
        print("█████╔╝ █████╗  ██╔██╗ ██║██████╔╝██║   ██║██╔██╗ ██║")
        print("██╔═██╗ ██╔══╝  ██║╚██╗██║██╔══██╗██║   ██║██║╚██╗██║")
        print(f"██║  ██╗███████╗██║ ╚████║██████╔╝╚██████╔╝██║ ╚████║  {C_Y}COGNITIVE AGENT SHELL v2.9.0")
        print(f"{C_P}╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝{C_R}")
    else:
        print(f"\n{C_P}🌸 KENBUN COGNITIVE AGENT SHELL v2.9.0{C_R}")

    # Compact banner — only the essentials
    tier_label = {"nano": f"{C_Y}Nano (lightweight){C_R}", "standard": f"{C_G}Standard{C_R}", "cloud": f"{C_C}Cloud API{C_R}"}.get(model_tier, model_tier)
    banner_lines = [
        f"  🌸 Model:   {C_W}{llm_model}{C_R}  [{tier_label}]",
        f"  ⚡ Gateway: {C_W}{llm_url}{C_R}",
        f"  💡 Commands: {C_G}/tools{C_R} (inspect tools) | {C_G}/skills{C_R} (design blueprints) | {C_G}/run{C_R} (execute) | {C_G}/help{C_R}",
    ]
    draw_box(banner_lines, title=f"🌸 {C_Y}COGNITIVE AGENT SHELL", border_color=C_G, text_color=C_G)
    print()

    # Run startup health probe and show card
    print(f"{C_D}  Probing system health...{C_R}", end="\r")
    probe_results = run_startup_probe(llm_url, llm_model, chroma_host, chroma_port)
    print(" " * 40, end="\r")  # clear probe line
    print_health_card(probe_results)
    print()

    # 🌸 Quick-Start Guide for Sovereign CLI Actions
    guide_lines = [
        f"  • {C_C}/tools{C_R}           ➟ List all harvested sovereign tools grouped by category",
        f"  • {C_C}/tools <tool>{C_R}    ➟ Inspect parameters, signature, and async requirements",
        f"  • {C_C}/skills{C_R}          ➟ Discover design and template skills from the catalog",
        f"  • {C_C}/run <tool> args{C_R} ➟ Direct live parameter execution with sync/async auto-safety",
        "",
        f"  {C_D}Example:{C_R} {C_G}/run search_hivemind_concepts query=\"lemon\"{C_R}"
    ]
    draw_box(guide_lines, title="🌸 SOVEREIGN CLI QUICK-START GUIDE", border_color=C_Y, text_color=C_W)
    print()

    log_event("🌸 Termchat Session Started. Model: {}, URL: {}, Tier: {}".format(llm_model, llm_url, model_tier))

    system_prompt = build_system_prompt(model_tier, llm_model)
    # Append AST tool runner note for all tiers
    system_prompt += (
        "You can execute any of Kenbun's harvested agent tools globally by running standard 'kenbun <command>' wrappers directly via the execute block. "
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
                    endpoint = f"{llm_url}/chat/completions"
                    headers = {"Content-Type": "application/json"}
                    is_gemini_route = "gemini" in llm_url.lower() or "googleapis" in llm_url.lower() or "generativelanguage" in llm_url.lower()
                    
                    if "GEMINI_API_KEY" in env and is_gemini_route:
                        headers["Authorization"] = f"Bearer {decrypt_value(env['GEMINI_API_KEY'])}"
                    elif "OPENAI_API_KEY" in env and "openai" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['OPENAI_API_KEY'])}"
                    elif "DEEPSEEK_API_KEY" in env and "deepseek" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['DEEPSEEK_API_KEY'])}"

                    payload = {
                        "model": llm_model,
                        "messages": history,
                        "temperature": 0.7 if model_tier == "nano" else 0.2,
                        "stream": True
                    }
                    
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
                    endpoint = f"{llm_url}/chat/completions"
                    headers = {"Content-Type": "application/json"}
                    is_gemini_route = "gemini" in llm_url.lower() or "googleapis" in llm_url.lower() or "generativelanguage" in llm_url.lower()
                    
                    if "GEMINI_API_KEY" in env and is_gemini_route:
                        headers["Authorization"] = f"Bearer {decrypt_value(env['GEMINI_API_KEY'])}"
                    elif "OPENAI_API_KEY" in env and "openai" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['OPENAI_API_KEY'])}"
                    elif "DEEPSEEK_API_KEY" in env and "deepseek" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['DEEPSEEK_API_KEY'])}"

                    payload = {
                        "model": llm_model,
                        "messages": history,
                        "temperature": 0.7 if model_tier == "nano" else 0.2,
                        "stream": True
                    }
                    
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
                
                cols = get_columns()
                wrapper = StreamingRenderer(cols - 4)
                wrapper.current_line_len = 20 if is_fallback else 9
                
                full_reply = ""
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
                            # Not a data line, could be an API error embedded in the stream body!
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
