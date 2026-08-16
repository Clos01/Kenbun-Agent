import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch

from tools.utils.sessions_db import (
    init_db,
    create_session,
    add_message,
    get_session,
    get_messages,
    list_sessions,
    update_session_title,
    delete_session,
    prune_sessions,
    get_sessions_stats
)
from tools.sensory.session_search import perform_session_search, render_search_results_markdown

@pytest.fixture
def mock_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_db = os.path.join(tmpdir, "test_state.db")
        with patch("tools.utils.sessions_db.get_db_path", return_value=temp_db), \
             patch("tools.sensory.session_search.get_db_path", return_value=temp_db):
            init_db()
            yield temp_db

def test_session_lifecycle(mock_db):
    # 1. Create session
    sess_id = create_session(source="test", user_id="user1", model="gemma", title="My Initial Title")
    assert sess_id is not None
    
    # 2. Get session details
    sess = get_session(sess_id)
    assert sess["source"] == "test"
    assert sess["user_id"] == "user1"
    assert sess["model"] == "gemma"
    assert sess["title"] == "My Initial Title"
    
    # 3. Add messages
    add_message(sess_id, "user", "Hello agent", token_count=5)
    add_message(sess_id, "assistant", "Hello human, I am Kenbun", token_count=10)
    
    # Check messages
    msgs = get_messages(sess_id)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello agent"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "Hello human, I am Kenbun"
    
    # Check updated token counts in session
    sess = get_session(sess_id)
    assert sess["token_count_input"] == 5
    assert sess["token_count_output"] == 10
    
    # 4. List sessions
    sessions = list_sessions(limit=5)
    assert len(sessions) == 1
    assert sessions[0]["id"] == sess_id
    assert sessions[0]["preview"] == "Hello human, I am Kenbun"

    # 5. Rename session
    updated_title = update_session_title(sess_id, "Renamed Session")
    assert updated_title == "Renamed Session"
    sess = get_session(sess_id)
    assert sess["title"] == "Renamed Session"

    # 6. Stats
    stats = get_sessions_stats()
    assert stats["total_sessions"] == 1
    assert stats["total_messages"] == 2
    assert stats["source_counts"]["test"] == 1

    # 7. Delete session
    success = delete_session(sess_id)
    assert success is True
    assert get_session(sess_id) is None
    assert len(get_messages(sess_id)) == 0

def test_auto_lineage_duplicate_title(mock_db):
    sess1 = create_session(title="Duplicate Title")
    sess2 = create_session(title="Duplicate Title")
    sess3 = create_session(title="Duplicate Title")
    
    assert get_session(sess1)["title"] == "Duplicate Title"
    assert get_session(sess2)["title"] == "Duplicate Title #2"
    assert get_session(sess3)["title"] == "Duplicate Title #3"

def test_fts5_full_text_search(mock_db):
    sess_id = create_session(title="Search Session")
    add_message(sess_id, "user", "I want to deploy nextjs app via docker compose")
    add_message(sess_id, "assistant", "Sure, you can use the stack deploy tool")
    
    # Run FTS query
    res = perform_session_search(query="nextjs")
    assert res["mode"] == "discovery"
    assert len(res["sessions"]) == 1
    assert res["sessions"][0]["session_id"] == sess_id
    assert "nextjs" in res["sessions"][0]["snippet"]
    
    # Check markdown rendering
    md = render_search_results_markdown(res)
    assert "Search Session" in md
    assert "nextjs" in md

def test_prune_sessions(mock_db):
    sess_id = create_session(title="Old Session")
    add_message(sess_id, "user", "Old message")
    
    # Mock last_active_at to be 100 days ago
    import datetime
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=100)).isoformat()
    
    conn = sqlite3.connect(mock_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET last_active_at = ? WHERE id = ?", (cutoff, sess_id))
    conn.commit()
    conn.close()
    
    # Prune older than 90 days
    deleted = prune_sessions(older_than_days=90)
    assert deleted == 1
    assert get_session(sess_id) is None
