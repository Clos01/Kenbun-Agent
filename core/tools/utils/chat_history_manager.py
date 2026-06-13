"""Public API for chat session persistence.

This is a thin facade. The storage backend is SQLite (see chat_store_sqlite),
which replaced the original single-JSON-file + lockfile implementation to fix
the O(n)-rewrite-per-message and lock-contention scalability defects. Function
signatures and return shapes are unchanged, so api_server.py and the CLI need
no edits.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

from core.tools.utils import chat_store_sqlite

logger = logging.getLogger("chat_history")


def get_sessions_file_path() -> Path:
    """Absolute path to the chat storage file (now the SQLite database)."""
    return chat_store_sqlite.get_db_path()


def list_sessions() -> List[Dict]:
    """Sidebar summaries (id, title, timestamp, last_message), newest first."""
    return chat_store_sqlite.list_sessions()


def create_session(title: str = "New Transmissions") -> Dict:
    """Create a new session seeded with the Kenbun greeting message."""
    return chat_store_sqlite.create_session(title=title)


def get_session(session_id: str) -> Optional[Dict]:
    """Full session with its ordered message history, or None if not found."""
    return chat_store_sqlite.get_session(session_id)


def delete_session(session_id: str) -> bool:
    """Delete a session (messages cascade). True if a row was removed."""
    return chat_store_sqlite.delete_session(session_id)


def add_message_to_session(session_id: str, sender: str, content: str) -> Optional[Dict]:
    """Append a message; auto-titles the session from the first user message."""
    return chat_store_sqlite.add_message_to_session(session_id, sender, content)
