import os
import sqlite3
import datetime
import json
import uuid

def get_db_path():
    hermes_dir = os.path.expanduser("~/.hermes")
    os.makedirs(hermes_dir, exist_ok=True)
    return os.path.join(hermes_dir, "state.db")

def get_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                user_id TEXT,
                model TEXT,
                title TEXT,
                system_prompt TEXT,
                config TEXT,
                token_count_input INTEGER DEFAULT 0,
                token_count_output INTEGER DEFAULT 0,
                parent_id TEXT,
                started_at TEXT,
                ended_at TEXT,
                last_active_at TEXT
            )
        ''')
        
        # Unique index on non-NULL title
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_title 
            ON sessions(title) WHERE title IS NOT NULL;
        ''')
        
        # 2. messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                tool_calls TEXT,
                tool_name TEXT,
                token_count INTEGER DEFAULT 0,
                timestamp TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        ''')
        
        # 3. messages_fts virtual table using FTS5
        # We define content='messages' and content_rowid='id' so FTS5 indexes the messages table
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content='messages',
                content_rowid='id'
            );
        ''')
        
        # Triggers to keep FTS5 virtual table synchronized automatically
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS t_messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
            END;
        ''')
        
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS t_messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
            END;
        ''')
        
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS t_messages_au AFTER UPDATE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
                INSERT INTO messages_fts(rowid, content) VALUES(new.id, new.content);
            END;
        ''')
        
        conn.commit()
    finally:
        conn.close()

def generate_session_id(source="cli"):
    now = datetime.datetime.now()
    suffix_len = 8 if source != "cli" else 6
    hex_suffix = uuid.uuid4().hex[:suffix_len]
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{hex_suffix}"

def create_session(session_id=None, source="cli", user_id=None, model=None, title=None, system_prompt=None, config=None, parent_id=None):
    init_db()
    if not session_id:
        session_id = generate_session_id(source)
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Handle auto-lineage if title already exists (or formatting if duplicate title is attempted)
        if title:
            # Check if this title already exists in DB
            cursor.execute("SELECT id FROM sessions WHERE title = ?", (title,))
            if cursor.fetchone():
                # Title exists, let's find the next lineage number
                # e.g. "my title" -> "my title #2" -> "my title #3"
                base_title = title
                counter = 2
                while True:
                    new_title = f"{base_title} #{counter}"
                    cursor.execute("SELECT id FROM sessions WHERE title = ?", (new_title,))
                    if not cursor.fetchone():
                        title = new_title
                        break
                    counter += 1
                    
        config_str = json.dumps(config) if config else None
        
        cursor.execute('''
            INSERT INTO sessions (
                id, source, user_id, model, title, system_prompt, config, 
                parent_id, started_at, last_active_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, source, user_id, model, title, system_prompt, config_str, parent_id, timestamp, timestamp))
        
        conn.commit()
        return session_id
    finally:
        conn.close()

def get_session(session_id):
    init_db()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            if d.get("config"):
                try:
                    d["config"] = json.loads(d["config"])
                except Exception:
                    pass
            return d
        return None
    finally:
        conn.close()

def list_sessions(source=None, limit=20):
    init_db()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        if source:
            cursor.execute('''
                SELECT * FROM sessions 
                WHERE source = ? 
                ORDER BY last_active_at DESC 
                LIMIT ?
            ''', (source, limit))
        else:
            cursor.execute('''
                SELECT * FROM sessions 
                ORDER BY last_active_at DESC 
                LIMIT ?
            ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            # Find preview (most recent user message or assistant message)
            cursor.execute('''
                SELECT content FROM messages 
                WHERE session_id = ? AND role IN ('user', 'assistant') 
                ORDER BY id DESC LIMIT 1
            ''', (d["id"],))
            prev_row = cursor.fetchone()
            d["preview"] = prev_row[0] if prev_row else ""
            results.append(d)
        return results
    finally:
        conn.close()

def add_message(session_id, role, content, tool_calls=None, tool_name=None, token_count=0):
    init_db()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tool_calls_str = json.dumps(tool_calls) if tool_calls else None
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Insert message
        cursor.execute('''
            INSERT INTO messages (
                session_id, role, content, tool_calls, tool_name, token_count, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, role, content, tool_calls_str, tool_name, token_count, timestamp))
        
        # 2. Update session's last_active_at
        cursor.execute('''
            UPDATE sessions 
            SET last_active_at = ? 
            WHERE id = ?
        ''', (timestamp, session_id))
        
        # 3. Update session token counts
        if role == "user" or role == "system":
            cursor.execute('''
                UPDATE sessions 
                SET token_count_input = token_count_input + ? 
                WHERE id = ?
            ''', (token_count, session_id))
        elif role == "assistant":
            cursor.execute('''
                UPDATE sessions 
                SET token_count_output = token_count_output + ? 
                WHERE id = ?
            ''', (token_count, session_id))
            
        conn.commit()
    finally:
        conn.close()

def get_messages(session_id):
    init_db()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM messages 
            WHERE session_id = ? 
            ORDER BY id ASC
        ''', (session_id,))
        
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            if d.get("tool_calls"):
                try:
                    d["tool_calls"] = json.loads(d["tool_calls"])
                except Exception:
                    pass
            results.append(d)
        return results
    finally:
        conn.close()

def update_session_title(session_id, title):
    init_db()
    # Sanitize title: strip control characters, zero-width chars, RTL overrides
    if title:
        title = "".join(ch for ch in title if ch.isprintable())
        title = title.strip()[:100]
    
    if not title:
        return False
        
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Handle unique constraint with lineage numbers
        cursor.execute("SELECT id FROM sessions WHERE title = ? AND id != ?", (title, session_id))
        if cursor.fetchone():
            base_title = title
            counter = 2
            while True:
                new_title = f"{base_title} #{counter}"
                cursor.execute("SELECT id FROM sessions WHERE title = ? AND id != ?", (new_title, session_id))
                if not cursor.fetchone():
                    title = new_title
                    break
                counter += 1
                
        cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
        conn.commit()
        return title
    except Exception:
        return False
    finally:
        conn.close()

def delete_session(session_id):
    init_db()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()

def prune_sessions(older_than_days=90, source=None):
    init_db()
    db_path = get_db_path()
    
    # Calculate cutoff timestamp
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=older_than_days)).isoformat()
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Check initial size
        initial_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        
        # Ended sessions are those that have ended_at NOT NULL (or we can fallback to last_active_at for general ended sessions)
        if source:
            cursor.execute('''
                DELETE FROM sessions 
                WHERE last_active_at < ? AND source = ?
            ''', (cutoff, source))
        else:
            cursor.execute('''
                DELETE FROM sessions 
                WHERE last_active_at < ?
            ''', (cutoff,))
            
        rows_deleted = cursor.rowcount
        conn.commit()
        
        # Vacuum if database size might be reclaimed
        if rows_deleted > 0:
            cursor.execute("VACUUM")
            
        return rows_deleted
    finally:
        conn.close()

def get_sessions_stats():
    init_db()
    db_path = get_db_path()
    db_size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    db_size_mb = db_size_bytes / (1024 * 1024)
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT source, COUNT(*) FROM sessions GROUP BY source")
        source_counts = dict(cursor.fetchall())
        
        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "source_counts": source_counts,
            "database_size_mb": round(db_size_mb, 2)
        }
    finally:
        conn.close()
