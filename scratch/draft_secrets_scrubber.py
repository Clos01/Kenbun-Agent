import os
import re
import json
import tempfile
import threading
from pathlib import Path

# Thread lock to guarantee safe parallel writes
_backup_lock = threading.Lock()
active_brain_health_dir = None
C_Y = "\033[93m"
C_R = "\033[0m"

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
            scrubbed_msg["content"] = scrubbed_secrets(scrubbed_msg["content"])
        scrubbed_history.append(scrubbed_msg)
    
    data = {
        "history": scrubbed_history,
        "cwd": str(cwd),
        "llm_url": scrubbed_secrets(llm_url),
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
            print(f"\nDialogue Persistence Warning: Atomic session backup failed: {e}\n")
