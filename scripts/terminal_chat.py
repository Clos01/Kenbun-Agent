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
    if not active_brain_health_dir:
        return
    
    backup_path = Path(active_brain_health_dir) / "active_session_backup.json"
    
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
        "llm_url": scrub_secrets(llm_url),
        "llm_model": llm_model
    }
    
    with _backup_lock:
        temp_fd = None
        temp_path = None
        try:
            # Create a temp file in the same directory to guarantee atomic rename (same partition)
            fd, temp_path = tempfile.mkstemp(dir=str(active_brain_health_dir), suffix=".tmp")
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
            # Graceful warning printed to terminal
            print(f"\n{C_Y}⚠️  Dialogue Persistence Warning: Atomic session backup failed: {e}{C_R}\n")


# Color palettes (Limestone & Sakura themed)
C_P = "\033[95m" # Pink (Sakura)
C_G = "\033[92m" # Green (Limestone/Sage)
C_Y = "\033[93m" # Gold
C_C = "\033[96m" # Cyan
C_W = "\033[97m" # White
C_D = "\033[90m" # Grey
C_R = "\033[0m"  # Reset

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
    elif any(cmd_lower.startswith(x) for x in ["mkdir", "rm", "cp", "mv", "ls", "cat", "chmod"]):
        tool_name = "POSIX OS Filesystem Operations"
        why_needed = "Performs filesystem manipulation tasks such as creating, moving, reading, copying, or deleting files and folders."
        pro_tip = f"💡 Pro-Tip: You can run this command directly in your shell: `ls -lh`"
        
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

class StreamingWordWrapper:
    def __init__(self, width):
        self.width = width if width > 0 else 80
        self.current_line_len = 0
        self.word_buffer = ""
        self.word_visible_len = 0
        
    def write(self, chunk):
        for char in chunk:
            if char == '\n':
                if self.word_buffer:
                    if self.current_line_len + self.word_visible_len > self.width:
                        sys.stdout.write("\n" + self.word_buffer)
                    else:
                        sys.stdout.write(self.word_buffer)
                    self.word_buffer = ""
                    self.word_visible_len = 0
                sys.stdout.write("\n")
                sys.stdout.flush()
                self.current_line_len = 0
            elif char.isspace():
                if self.word_buffer:
                    if self.current_line_len + self.word_visible_len > self.width:
                        sys.stdout.write("\n" + self.word_buffer)
                        self.current_line_len = self.word_visible_len
                    else:
                        sys.stdout.write(self.word_buffer)
                        self.current_line_len += self.word_visible_len
                    self.word_buffer = ""
                    self.word_visible_len = 0
                
                if self.current_line_len + 1 > self.width:
                    sys.stdout.write("\n")
                    self.current_line_len = 0
                else:
                    sys.stdout.write(char)
                    self.current_line_len += 1
                sys.stdout.flush()
            else:
                self.word_buffer += char
                self.word_visible_len = visible_len(self.word_buffer)
                
    def flush(self):
        if self.word_buffer:
            if self.current_line_len + self.word_visible_len > self.width:
                sys.stdout.write("\n" + self.word_buffer)
            else:
                sys.stdout.write(self.word_buffer)
            self.word_buffer = ""
            self.word_visible_len = 0
        sys.stdout.flush()

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
    
    # Local model indicators
    local_keywords = ["llama", "qwen", "mistral", "gemma", "phi3", "orca", "deepseek-r1:1.5b", "deepseek-r1:8b", "deepseek-r1:70b"]
    is_local_model = any(kw in llm_model.lower() for kw in local_keywords)
    
    # Mismatch is active when calling a Cloud Provider but specifying a Local model
    if is_cloud_url and is_local_model:
        return True, "cloud_url_with_local_model"
    return False, None

def check_and_heal_mismatch(llm_url, llm_model):
    """Audits configuration mismatch and prompts the developer for dynamic self-healing fixes."""
    has_mismatch, reason = detect_configuration_mismatch(llm_url, llm_model)
    if not has_mismatch:
        return llm_url, llm_model
        
    mismatch_lines = [
        "Kenbun has detected a routing conflict in your config:",
        "",
        f"⚡ Active Provider URL: {C_W}{llm_url}{C_G}",
        f"🌸 Active model:        {C_W}{llm_model}{C_G}",
        "---",
        f"Cloud gateways (like api.deepseek.com) cannot execute local model weights (like {llm_model}).",
        "",
        "Select an Autonomic Self-Healing patch:",
        f"{C_C}[1] Switch Model{C_G} - Swap model to target cloud model (e.g., 'deepseek-chat' for DeepSeek)",
        f"{C_C}[2] Switch URL{C_G}   - Route back to local Ollama server (http://localhost:11434/v1)",
        f"{C_C}[3] Bypass{C_G}       - Ignore and boot anyway"
    ]
    print()
    draw_box(mismatch_lines, title=f"⚠️  {C_Y}CONFIGURATION MISMATCH AUDIT TRIGGERED", border_color=C_Y, text_color=C_G)
    
    while True:
        try:
            choice = input(f"{C_C}Select self-healing action [1-3]: {C_R}").strip()
            if choice == "1":
                # Determine ideal cloud model name
                target_model = "deepseek-chat"
                if "openai" in llm_url.lower():
                    target_model = "gpt-4o-mini"
                elif "anthropic" in llm_url.lower():
                    target_model = "claude-3-5-sonnet-latest"
                elif "googleapis" in llm_url.lower():
                    target_model = "gemini-2.5-flash"
                
                print(f"\n⚙️  Applying Autopilot patch: Setting model to '{target_model}'...")
                if update_env_value("PRIMARY_LLM_MODEL", target_model):
                    print(f"✓ Model successfully corrected in '.env'.")
                    print_ollama_memory_education("mismatch_resolved")
                    return llm_url, target_model
                break
            elif choice == "2":
                target_url = "http://localhost:11434/v1"
                print(f"\n⚙️  Applying Autopilot patch: Re-routing URL to local Ollama stack...")
                if update_env_value("PRIMARY_LLM_URL", target_url):
                    print(f"✓ Gateway URL successfully re-routed in '.env'.")
                    print_ollama_memory_education("mismatch_resolved")
                    return target_url, llm_model
                break
            elif choice == "3" or not choice:
                print(f"\n⚠️ Bypassing mismatch safeguards. Booting stack in raw mode...")
                break
            else:
                print(f"{C_Y}⚠️ Invalid option. Select 1, 2, or 3.{C_R}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n⚠️ Mismatch audit interrupted. Proceeding with raw config.")
            break
            
    return llm_url, llm_model

def check_and_migrate_project_memory(old_dirs):
    """Detects if a new workspace project was created, and attaches active memories/WAL DB to it."""
    global active_brain_health_dir
    if not active_brain_health_dir:
        return
        
    cwd = Path.cwd().resolve()
    # Gather current directories (up to depth 2)
    current_dirs = set()
    try:
        for p in cwd.iterdir():
            if p.is_dir() and not p.name.startswith(".") and p.name not in ("venv", "node_modules", "brain_health"):
                current_dirs.add(p)
                try:
                    for sub in p.iterdir():
                        if sub.is_dir() and not sub.name.startswith(".") and sub.name not in ("venv", "node_modules", "brain_health"):
                            current_dirs.add(sub)
                except Exception:
                    pass
    except Exception:
        pass
        
    new_dirs = current_dirs - old_dirs
    
    if not new_dirs:
        return
        
    for nd in new_dirs:
        # Ignore standard hidden dirs
        if nd.name.startswith(".") or nd.name in ("venv", "node_modules", "brain_health"):
            continue
            
        box_lines = [
            f"Folder: {C_W}{nd.name}",
            "---",
            "Would you like to bind this chat's active memories and",
            "intelligence database directly to this new project?"
        ]
        print()
        draw_box(box_lines, title=f"📂 {C_Y}NEW PROJECT WORKSPACE DETECTED", border_color=C_G)
        
        confirm = input(f"{C_Y}Bind memories to '{nd.name}'? [Y/n]: {C_R}").strip().lower()
        if confirm != "n":
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
    core_path = "/Users/carlosrivas/Dev/kenbun-agent/core"
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
            log_dir = Path("/Users/carlosrivas/Dev/kenbun-agent/brain_health")
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
    core_path = "/Users/carlosrivas/Dev/kenbun-agent/core"
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
            Path("/Users/carlosrivas/Dev/kenbun-agent/core"),
            Path(__file__).resolve().parent.parent / "core",
            Path.cwd() / "core"
        ]
        core_path = None
        for p in possible_cores:
            if p.exists() and (p / "tools").exists():
                core_path = p
                break
        
        if not core_path:
            core_path = Path("/Users/carlosrivas/Dev/kenbun-agent/core")
            
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
            Path("/Users/carlosrivas/Dev/kenbun-agent/core"),
            Path(__file__).resolve().parent.parent / "core",
            Path.cwd() / "core"
        ]
        core_path = None
        for p in possible_cores:
            if p.exists() and (p / "tools").exists():
                core_path = p
                break
        
        if not core_path:
            core_path = Path("/Users/carlosrivas/Dev/kenbun-agent/core")
            
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

def run_proposed_command(cmd):
    """Executes a proposed system shell command safely with stdout/stderr capture."""
    log_event("⚙️ Executing reflex shell command: {}".format(scrub_secrets(cmd)))
    cols = get_columns()
    print(f"\n{C_Y}⚙️  Executing: {C_C}{clean_wrap_text(scrub_secrets(cmd), cols - 15)}{C_R}")
    
    # Store directory list state before execution
    cwd = Path.cwd().resolve()
    old_dirs = set()
    try:
        for p in cwd.iterdir():
            if p.is_dir() and not p.name.startswith(".") and p.name not in ("venv", "node_modules", "brain_health"):
                old_dirs.add(p)
                try:
                    for sub in p.iterdir():
                        if sub.is_dir() and not sub.name.startswith(".") and sub.name not in ("venv", "node_modules", "brain_health"):
                            old_dirs.add(sub)
                except Exception:
                    pass
    except Exception:
        pass
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=45
        )
        
        # Check if a new folder was created and prompt for memory migration!
        check_and_migrate_project_memory(old_dirs)
        
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if not output.strip():
            output = "[Success: Command executed with zero stdout/stderr output]"
        log_event("➔ Reflex command completed. Exit Code: {}".format(result.returncode))
        return result.returncode, scrub_secrets(output)
    except subprocess.TimeoutExpired:
        log_event("❌ Reflex command failed with execution timeout")
        return -1, "[Timeout Error: The system command exceeded the 45-second execution limit]"
    except Exception as e:
        log_event("❌ Reflex command failed with start exception: {}".format(e))
        return -1, f"[Execution Error: Failed to start command: {e}]"

def main():
    global active_brain_health_dir
    
    # Configure proper POSIX signal handlers to protect term state
    signal.signal(signal.SIGINT, graceful_exit_handler)
    signal.signal(signal.SIGTERM, graceful_exit_handler)
    
    env = load_env_vars()
    
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
        
    # Print beautiful banner
    cols = get_columns()
    if cols >= 70:
        print(f"\n{C_P}██╗  ██╗███████╗███╗   ██╗██████╗ ██╗   ██╗███╗   ██╗")
        print("██║ ██╔╝██╔════╝████╗  ██║██╔══██╗██║   ██║████╗  ██║")
        print("█████╔╝ █████╗  ██╔██╗ ██║██████╔╝██║   ██║██╔██╗ ██║")
        print("██╔═██╗ ██╔══╝  ██║╚██╗██║██╔══██╗██║   ██║██║╚██╗██║")
        print(f"██║  ██╗███████╗██║ ╚████║██████╔╝╚██████╔╝██║ ╚████║ {C_Y}🌸 COGNITIVE AGENT SHELL v2.8.5")
        print(f"{C_P}╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝{C_R}")
    else:
        print(f"\n{C_P}🌸 KENBUN COGNITIVE AGENT SHELL v2.8.5{C_R}")
        
    banner_lines = [
        f"🌸 Active Agent:      {C_W}{llm_model}",
        f"⚡ Ollama Gateway URL: {C_W}{llm_url}",
        f"🧠 RAG Rerouter:      {C_G}ACTIVE (Telemetry & Grounding)",
        f"⚙️  Reflex Status:     {C_Y}ACTIVE (Human-in-the-Loop Safe)",
        "",
        f"{C_Y}Commands & Capabilities:",
        f"  {C_C}/exit{C_G}     - Gracefully close Termchat & commit session post-mortem",
        f"  {C_C}/reset{C_G}    - Clear dialogue history",
        f"  {C_C}/system{C_G}   - Dump active environment parameters",
        f"  {C_C}/search{C_G}   - Direct search on UI-UX Pro Max database",
        f"  {C_C}/remember{C_G} - Save a custom note/rule in Hivemind",
        f"  {C_C}/recall{C_G}   - Query Hivemind semantically"
    ]
    draw_box(banner_lines, title=f"🌸 {C_Y}COGNITIVE AGENT SHELL", border_color=C_G, text_color=C_G)
    print()
    log_event("🌸 Termchat Session Started. Model: {}, URL: {}".format(llm_model, llm_url))

    system_prompt = (
        "You are Kenbun, an autonomous local AI system diagnostician, coding engineer, and design expert. "
        "You run natively inside the user's terminal on their Linux/macOS host machine.\n\n"
        "REFLEX SHELL LOOP (YOUR SUPERPOWER):\n"
        "You have the capability to execute system commands, check container statuses, install missing dependencies, "
        "read/write local files, inspect ports, or run diagnostics. "
        "To execute a system shell command, you MUST respond using this exact markdown block:\n"
        "```execute\n"
        "<system command to execute>\n"
        "```\n"
        "Keep commands safe, highly relevant, and direct. The user must manually approve each command via a y/N prompt before it executes. "
        "Once executed, the terminal client will automatically feed back the command's stdout/stderr and exit code directly into your context, "
        "allowing you to analyze the result and continue your self-healing loop or system configuration!\n\n"
        "AST HARVESTED TOOL RUNNER:\n"
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

    # Top-Level Exception Catcher to intercept unexpected system/OS crashes gracefully
    try:
        while True:
            try:
                # If auto_trigger is set, the system feeds back command output automatically without waiting for user input
                if auto_trigger:
                    user_input = ""
                    auto_trigger = False
                else:
                    user_input = input(f"{C_P}{username}@kenbun-agent{C_R}:{C_G}~{C_R}$ ").strip()
                    user_input = sanitize_input(user_input)
                    if not user_input:
                        continue
                    
                    # Handle Slash Commands
                    if user_input.startswith("/"):
                        cmd_parts = user_input.split(" ", 1)
                        cmd = cmd_parts[0].lower()
                        
                        if cmd == "/exit":
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
                            
                        else:
                            print(f"\n{C_Y}❌ Unknown command: {cmd}. Available commands: /exit, /reset, /search, /system, /remember, /recall{C_R}\n")
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
                    if "OPENAI_API_KEY" in env and "openai" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['OPENAI_API_KEY'])}"
                    elif "DEEPSEEK_API_KEY" in env and "deepseek" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['DEEPSEEK_API_KEY'])}"
                    elif "GEMINI_API_KEY" in env and "gemini" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['GEMINI_API_KEY'])}"

                    payload = {
                        "model": llm_model,
                        "messages": history,
                        "temperature": 0.2,
                        "stream": True
                    }
                    
                    print(f"\n{C_P}Kenbun 🌸:{C_R} ", end="", flush=True)
                    
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
                    
                    # Prepare headers and payload for fallback LLM
                    endpoint = f"{llm_url}/chat/completions"
                    headers = {"Content-Type": "application/json"}
                    if "OPENAI_API_KEY" in env and "openai" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['OPENAI_API_KEY'])}"
                    elif "DEEPSEEK_API_KEY" in env and "deepseek" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['DEEPSEEK_API_KEY'])}"
                    elif "GEMINI_API_KEY" in env and "gemini" in llm_url.lower():
                        headers["Authorization"] = f"Bearer {decrypt_value(env['GEMINI_API_KEY'])}"

                    payload = {
                        "model": llm_model,
                        "messages": history,
                        "temperature": 0.2,
                        "stream": True
                    }
                    
                    print(f"{C_P}Kenbun 🌸 (Fallback):{C_R} ", end="", flush=True)
                    
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
                wrapper = StreamingWordWrapper(cols - 2)
                wrapper.current_line_len = 22 if is_fallback else 11  # Fallback prefix is 22 chars, Primary is 11
                
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
                                chunk = data_json["choices"][0]["delta"].get("content", "")
                                wrapper.write(chunk)
                                full_reply += chunk
                            except Exception:
                                pass
                wrapper.flush()
                print("\n")
                
                # Register response
                history.append({"role": "assistant", "content": scrub_secrets(full_reply)})
                history = prune_dialog_history(history)
                save_session_backup(history, Path.cwd(), llm_url, llm_model)
                
                # Check for execute blocks: ```execute\n<command>\n```, ```bash\n<command>\n```, or ```sh\n<command>\n```
                execute_blocks = re.findall(r"```(?:execute|bash|sh)\n(.*?)\n```", full_reply, re.DOTALL | re.IGNORECASE)
                if execute_blocks:
                    for block in execute_blocks:
                        cmd = block.strip()
                        explain_command(cmd)
                        draw_box([scrub_secrets(cmd)], title=f"🚨 {C_Y}PROPOSED REFLEX ACTION DETECTED", border_color=C_G, text_color=C_W)
                        
                        confirm = input(f"{C_Y}Authorize execution of this command? [y/N]: {C_R}").strip().lower()
                        if confirm == "y":
                            code, out = run_proposed_command(cmd)
                            cols = get_columns()
                            title = f"─── Output (Exit Code: {code}) "
                            dash_len = max(0, cols - len(title) - 1)
                            print(f"\n{C_G}{title}{'─' * dash_len}{C_R}")
                            wrapped_out = clean_wrap_text(out.strip(), cols - 2)
                            print(f"{C_W}{wrapped_out}{C_R}")
                            print(f"{C_G}{'─' * cols}{C_R}\n")
                            
                            # Integration: Save reflection lesson to ChromaDB on successful healing/repair commands
                            if code == 0 and is_healing_command(cmd):
                                # Compile / retrieve error context
                                error_feedback = "None detected in active termchat window."
                                for msg in reversed(history):
                                    content = msg.get("content", "")
                                    if not content:
                                        continue
                                    if any(term in content.lower() for term in ["error", "fail", "not found", "does not exist", "exception", "stderr"]):
                                        error_feedback = content[:500]
                                        break
                                autonomic_reflection_save(
                                    task=f"Execution of reflex command: {cmd}",
                                    error=error_feedback,
                                    solution=f"Executed command successfully (Exit Code: 0). Output: {out[:300]}"
                                )
                            
                            # Feed the action result back to the LLM and trigger another turn immediately!
                            feedback = f"[SYSTEM OUT (Command: '{scrub_secrets(cmd)}', Exit Code: {code})]\n{out}"
                            history.append({"role": "user", "content": scrub_secrets(feedback)})
                            history = prune_dialog_history(history)
                            save_session_backup(history, Path.cwd(), llm_url, llm_model)
                            auto_trigger = True
                            break # Executed one, loop again to let the LLM think about this step's output
                        else:
                            print(f"\n{C_Y}⚠️ Command execution rejected by user. Bypassing.{C_R}\n")
                            feedback = f"[SYSTEM NOTICE: The user explicitly REJECTED the execution of command: '{scrub_secrets(cmd)}']"
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
                if err_msg and ("not found" in err_msg.lower() or "does not exist" in err_msg.lower() or "mismatch" in err_msg.lower()):
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
