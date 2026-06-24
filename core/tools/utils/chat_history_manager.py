import os
import json
import time
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from tools.infrastructure.config import settings

logger = logging.getLogger("chat_history")

# Shared lock file path
LOCK_FILE = settings.BRAIN_HEALTH_DIR / "chat_sessions.lock"

def get_sessions_file_path() -> Path:
    """Returns the absolute path to the chat sessions storage file."""
    # Ensure brain_health directory exists
    settings.BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    return settings.BRAIN_HEALTH_DIR / "chat_sessions.json"

def _acquire_lock(timeout: float = 3.0) -> bool:
    """Acquires an exclusive lock using a lockfile to prevent race conditions."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Attempt to create the lock file exclusively
            fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return True
        except FileExistsError:
            # Wait briefly before retrying
            time.sleep(0.05)
    logger.warning("Failed to acquire chat sessions lock.")
    return False

def _release_lock():
    """Releases the lock by removing the lockfile."""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception as e:
        logger.error(f"Error releasing chat lock: {e}")

def _load_sessions_unlocked() -> List[Dict]:
    """Internal function to load sessions without acquiring the lock."""
    file_path = get_sessions_file_path()
    if not file_path.exists():
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except Exception as e:
        logger.error(f"Failed to load chat sessions: {e}")
        return []

def _save_sessions_unlocked(sessions: List[Dict]) -> bool:
    """Internal function to save sessions without acquiring the lock."""
    file_path = get_sessions_file_path()
    temp_path = file_path.with_suffix(".tmp")
    try:
        # Write to temp file first to guarantee atomicity
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
            
        # Rename temp file to target file safely
        if temp_path.exists():
            temp_path.replace(file_path)
        return True
    except Exception as e:
        logger.error(f"Failed to save chat sessions: {e}")
        if temp_path.exists():
            temp_path.unlink()
        return False

def _modify_sessions(transform_fn):
    """Acquires lock once, reads, applies transform, writes, and releases."""
    acquired = _acquire_lock()
    if not acquired:
        time.sleep(0.5)
        acquired = _acquire_lock()
        if not acquired:
            logger.error("Could not acquire lock for atomic modification.")
            return None
    try:
        sessions = _load_sessions_unlocked()
        result = transform_fn(sessions)
        _save_sessions_unlocked(sessions)
        return result
    finally:
        _release_lock()

def load_sessions() -> List[Dict]:
    """Loads all chat sessions from disk. Lock-safe."""
    acquired = _acquire_lock()
    if not acquired:
        time.sleep(0.5)
        acquired = _acquire_lock()
        if not acquired:
            logger.error("Could not acquire lock to read chat sessions. Returning empty list safely.")
            return []
    try:
        return _load_sessions_unlocked()
    finally:
        _release_lock()

def save_sessions(sessions: List[Dict]) -> bool:
    """Saves chat sessions atomically to disk with strict lock protection."""
    acquired = _acquire_lock()
    if not acquired:
        time.sleep(0.5)
        acquired = _acquire_lock()
        if not acquired:
            logger.error("Could not acquire lock to write chat sessions.")
            return False
    try:
        return _save_sessions_unlocked(sessions)
    finally:
        _release_lock()

def list_sessions() -> List[Dict]:
    """Returns a list of sessions formatted as summaries for the sidebar."""
    sessions = load_sessions()
    summaries = []
    for s in sessions:
        last_msg = ""
        if s.get("messages"):
            last_msg = s["messages"][-1].get("content", "")
            
        summaries.append({
            "id": s["id"],
            "title": s.get("title", "New Transmissions"),
            "timestamp": s.get("timestamp", ""),
            "last_message": last_msg[:60] + "..." if len(last_msg) > 60 else last_msg
        })
    # Sort summaries by timestamp descending
    summaries.sort(key=lambda x: x["timestamp"], reverse=True)
    return summaries

def create_session(title: str = "New Transmissions") -> Dict:
    """Creates a new empty chat session and saves it."""
    new_session = {
        "id": f"session_{uuid.uuid4().hex[:12]}",
        "title": title,
        "timestamp": datetime.fromtimestamp(time.time()).isoformat(),
        "messages": [
            {
                "id": "initial",
                "sender": "kenbun",
                "content": "I am the Kenbun interface. I monitor the Hivemind memory and execute System 1 reflexes. How can I assist you?",
                "timestamp": datetime.fromtimestamp(time.time()).isoformat()
            }
        ]
    }
    def transform(sessions):
        sessions.append(new_session)
        return new_session
    return _modify_sessions(transform)

def get_session(session_id: str) -> Optional[Dict]:
    """Retrieves a single chat session by ID."""
    sessions = load_sessions()
    for s in sessions:
        if s["id"] == session_id:
            return s
    return None

def delete_session(session_id: str) -> bool:
    """Deletes a chat session by ID."""
    def transform(sessions):
        initial_len = len(sessions)
        sessions[:] = [s for s in sessions if s["id"] != session_id]
        return len(sessions) < initial_len
    return _modify_sessions(transform) or False

def add_message_to_session(
    session_id: str,
    sender: str,
    content: str,
    metrics: Optional[Dict] = None,
    tool_calls: Optional[List[Dict]] = None
) -> Optional[Dict]:
    """Appends a new message to a session and updates the list."""
    def transform(sessions):
        target_session = None
        for s in sessions:
            if s["id"] == session_id:
                target_session = s
                break
                
        if not target_session:
            return None
            
        new_msg = {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "sender": sender,
            "content": content,
            "timestamp": datetime.fromtimestamp(time.time()).isoformat()
        }
        if metrics:
            new_msg["metrics"] = metrics
        if tool_calls:
            new_msg["tool_calls"] = tool_calls
            
        target_session["messages"].append(new_msg)
        
        # Auto-title generation if this is the first user message
        user_messages = [m for m in target_session["messages"] if m["sender"] == "user"]
        if len(user_messages) == 1 and sender == "user":
            # Derive a short, clean title from first prompt (max 25 characters)
            raw_title = content.strip()
            if len(raw_title) > 25:
                # Find a good cutting point or just truncate
                words = raw_title.split()
                short_title = ""
                for w in words:
                    if len(short_title) + len(w) + 1 <= 22:
                        short_title += (" " if short_title else "") + w
                    else:
                        break
                target_session["title"] = short_title + "..." if short_title else raw_title[:22] + "..."
            else:
                target_session["title"] = raw_title
                
        return new_msg
        
    return _modify_sessions(transform)


def search_sessions(query: str) -> List[Dict]:
    """
    Performs a case-insensitive search across all session message contents.
    Returns a list of sessions containing matching messages, along with snippets.
    """
    sessions = load_sessions()
    results = []
    query_lower = query.lower()
    for s in sessions:
        matching_messages = []
        for msg in s.get("messages", []):
            content = msg.get("content", "")
            if query_lower in content.lower():
                # Extract a snippet around the match
                idx = content.lower().find(query_lower)
                start = max(0, idx - 40)
                end = min(len(content), idx + len(query) + 40)
                snippet = ("..." if start > 0 else "") + content[start:end] + ("..." if end < len(content) else "")
                matching_messages.append({
                    "message_id": msg.get("id"),
                    "sender": msg.get("sender"),
                    "timestamp": msg.get("timestamp"),
                    "snippet": snippet
                })
        if matching_messages:
            results.append({
                "id": s["id"],
                "title": s.get("title", "New Transmissions"),
                "timestamp": s.get("timestamp"),
                "matches": matching_messages
            })
    return results
