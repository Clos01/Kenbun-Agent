import pytest
import os
from pathlib import Path
from tools.utils import chat_history_manager

@pytest.fixture(autouse=True)
def clean_sessions_file():
    """Fixture to backup any existing chat sessions and ensure a clean test state."""
    sessions_file = chat_history_manager.get_sessions_file_path()
    backup_file = sessions_file.with_suffix(".json.bak")
    
    # Backup existing data
    if sessions_file.exists():
        if backup_file.exists():
            backup_file.unlink()
        sessions_file.rename(backup_file)
        
    yield
    
    # Restore original data
    if sessions_file.exists():
        sessions_file.unlink()
    if backup_file.exists():
        backup_file.rename(sessions_file)

def test_create_and_list_sessions():
    """Verifies creating a session registers it inside list_sessions."""
    # Initially list is empty
    summaries = chat_history_manager.list_sessions()
    assert len(summaries) == 0
    
    # Create session
    new_session = chat_history_manager.create_session(title="Test Core Architecture")
    assert new_session["title"] == "Test Core Architecture"
    assert new_session["id"].startswith("session_")
    
    # Listing should now return 1 summary
    summaries = chat_history_manager.list_sessions()
    assert len(summaries) == 1
    assert summaries[0]["id"] == new_session["id"]
    assert summaries[0]["title"] == "Test Core Architecture"

def test_get_session_by_id():
    """Verifies getting a single session by its unique ID."""
    session = chat_history_manager.create_session(title="Test Retrieval Operations")
    
    fetched = chat_history_manager.get_session(session["id"])
    assert fetched is not None
    assert fetched["id"] == session["id"]
    assert fetched["title"] == "Test Retrieval Operations"
    
    # Non-existent session
    assert chat_history_manager.get_session("session_nonexistent_xyz") is None

def test_delete_session():
    """Verifies pruning/deleting an active chat session."""
    session = chat_history_manager.create_session(title="Temporary Session Log")
    assert chat_history_manager.get_session(session["id"]) is not None
    
    # Delete
    success = chat_history_manager.delete_session(session["id"])
    assert success is True
    
    # Listing should now be empty
    assert len(chat_history_manager.list_sessions()) == 0
    assert chat_history_manager.get_session(session["id"]) is None
    
    # Double deletion fails safely
    assert chat_history_manager.delete_session(session["id"]) is False

def test_add_messages_and_auto_title():
    """Verifies messages can be appended, and first message updates session title."""
    session = chat_history_manager.create_session(title="New Transmissions")
    
    # Append message
    msg = chat_history_manager.add_message_to_session(session["id"], "user", "How do I optimize Docker?")
    assert msg["sender"] == "user"
    assert msg["content"] == "How do I optimize Docker?"
    
    # Verify first prompt auto-updated title
    fetched = chat_history_manager.get_session(session["id"])
    assert fetched["title"] == "How do I optimize Docker?"
    assert len(fetched["messages"]) == 2  # initial + user msg
    
    # Append second message, should NOT update title
    chat_history_manager.add_message_to_session(session["id"], "kenbun", "Use multi-stage builds.")
    fetched = chat_history_manager.get_session(session["id"])
    assert fetched["title"] == "How do I optimize Docker?"  # Title unchanged
    assert len(fetched["messages"]) == 3
