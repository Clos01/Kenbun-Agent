import sqlite3
import json
import datetime
from typing import Optional, Dict, Any
from tools.utils.sessions_db import get_db_path, init_db

def format_relative_time(timestamp_str: str) -> str:
    try:
        # Remove timezone suffix Z or offset for parsing
        clean_ts = timestamp_str
        if clean_ts.endswith("Z"):
            clean_ts = clean_ts[:-1]
        elif "+" in clean_ts:
            clean_ts = clean_ts.split("+")[0]
            
        dt = datetime.datetime.fromisoformat(clean_ts)
        now = datetime.datetime.utcnow()
        diff = now - dt
        
        if diff.days > 365:
            return f"{diff.days // 365}y ago"
        if diff.days > 30:
            return f"{diff.days // 30}mo ago"
        if diff.days > 0:
            return f"{diff.days}d ago"
        if diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        if diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        return "just now"
    except Exception:
        return timestamp_str

def perform_session_search(
    query: Optional[str] = None,
    session_id: Optional[str] = None,
    around_message_id: Optional[int] = None,
    window: int = 5,
    limit: int = 3,
    sort: str = "newest",
    role_filter: str = "user,assistant"
) -> Dict[str, Any]:
    init_db()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Mode 2: Scroll
    if session_id and around_message_id is not None:
        try:
            # 1. Fetch target session info
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            session_row = cursor.fetchone()
            if not session_row:
                return {"error": f"Session {session_id} not found."}
                
            session_data = dict(session_row)
            
            # 2. Get window of messages centered on around_message_id
            cursor.execute('''
                SELECT * FROM messages 
                WHERE session_id = ? 
                AND id >= ? - ? 
                AND id <= ? + ? 
                ORDER BY id ASC
            ''', (session_id, around_message_id, window, around_message_id, window))
            
            messages = [dict(r) for r in cursor.fetchall()]
            for m in messages:
                if m.get("tool_calls"):
                    try:
                        m["tool_calls"] = json.loads(m["tool_calls"])
                    except Exception:
                        pass
            
            # 3. Calculate counts before and after the window boundaries
            if messages:
                min_id = messages[0]["id"]
                max_id = messages[-1]["id"]
                
                cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ? AND id < ?", (session_id, min_id))
                messages_before = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ? AND id > ?", (session_id, max_id))
                messages_after = cursor.fetchone()[0]
            else:
                messages_before = 0
                messages_after = 0
                
            return {
                "mode": "scroll",
                "session_id": session_id,
                "title": session_data.get("title") or "Unnamed Session",
                "messages": messages,
                "messages_before": messages_before,
                "messages_after": messages_after
            }
        finally:
            conn.close()
            
    # Mode 1: Discovery (FTS5 Query)
    elif query:
        try:
            role_list = [r.strip() for r in role_filter.split(",")]
            
            # Search messages_fts
            # We want to filter by roles if possible. Since FTS5 does not contain the role directly,
            # we query FTS5 first, then join with messages to filter on roles.
            cursor.execute('''
                SELECT m.id, m.session_id, m.role, m.content, m.timestamp,
                       snippet(messages_fts, 0, '***', '***', '...', 10) as snippet
                FROM messages_fts f
                JOIN messages m ON m.id = f.rowid
                WHERE messages_fts MATCH ?
                ORDER BY m.id DESC
            ''', (query,))
            
            fts_hits = cursor.fetchall()
            
            # Group hits by session
            session_hits = {}
            for hit in fts_hits:
                hit_dict = dict(hit)
                sid = hit_dict["session_id"]
                if sid not in session_hits:
                    # Filter roles if role_list is specified
                    if hit_dict["role"] in role_list:
                        session_hits[sid] = hit_dict
            
            # Get details for top N sessions
            results = []
            for sid, hit in list(session_hits.items())[:limit]:
                cursor.execute("SELECT * FROM sessions WHERE id = ?", (sid,))
                sess_row = cursor.fetchone()
                if not sess_row:
                    continue
                sess = dict(sess_row)
                
                # Fetch bookend_start (first 3 user/assistant messages)
                cursor.execute('''
                    SELECT * FROM messages 
                    WHERE session_id = ? AND role IN ('user', 'assistant') 
                    ORDER BY id ASC LIMIT 3
                ''', (sid,))
                bookend_start = [dict(r) for r in cursor.fetchall()]
                
                # Fetch bookend_end (last 3 user/assistant messages)
                cursor.execute('''
                    SELECT * FROM messages 
                    WHERE session_id = ? AND role IN ('user', 'assistant') 
                    ORDER BY id DESC LIMIT 3
                ''', (sid,))
                # Reverse to keep chronological order
                bookend_end = list(reversed([dict(r) for r in cursor.fetchall()]))
                
                # Fetch ±5 messages around the match
                mid = hit["id"]
                cursor.execute('''
                    SELECT * FROM messages 
                    WHERE session_id = ? 
                    AND id >= ? - 5 
                    AND id <= ? + 5 
                    ORDER BY id ASC
                ''', (sid, mid, mid))
                around_messages = [dict(r) for r in cursor.fetchall()]
                
                # Tag the matching message inside the window
                for m in around_messages:
                    if m["id"] == mid:
                        m["is_match_hit"] = True
                    if m.get("tool_calls"):
                        try:
                            m["tool_calls"] = json.loads(m["tool_calls"])
                        except Exception:
                            pass
                
                for m in bookend_start + bookend_end:
                    if m.get("tool_calls"):
                        try:
                            m["tool_calls"] = json.loads(m["tool_calls"])
                        except Exception:
                            pass
                            
                # Counts before and after
                cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ? AND id < ?", (sid, mid - 5))
                messages_before = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ? AND id > ?", (sid, mid + 5))
                messages_after = cursor.fetchone()[0]
                
                results.append({
                    "session_id": sid,
                    "title": sess.get("title") or "Unnamed Session",
                    "when": format_relative_time(sess["last_active_at"]),
                    "source": sess["source"],
                    "snippet": hit["snippet"],
                    "bookend_start": bookend_start,
                    "messages": around_messages,
                    "bookend_end": bookend_end,
                    "match_message_id": mid,
                    "messages_before": messages_before,
                    "messages_after": messages_after
                })
                
            return {
                "mode": "discovery",
                "query": query,
                "sessions": results
            }
        finally:
            conn.close()
            
    # Mode 3: Browse (Recent Sessions)
    else:
        try:
            cursor.execute('''
                SELECT * FROM sessions 
                ORDER BY last_active_at DESC 
                LIMIT ?
            ''', (limit * 2,)) # Fetch slightly more to browse
            
            sessions = []
            for row in cursor.fetchall():
                d = dict(row)
                # Find preview
                cursor.execute('''
                    SELECT content FROM messages 
                    WHERE session_id = ? AND role IN ('user', 'assistant') 
                    ORDER BY id DESC LIMIT 1
                ''', (d["id"],))
                prev_row = cursor.fetchone()
                d["preview"] = prev_row[0] if prev_row else ""
                d["when"] = format_relative_time(d["last_active_at"])
                sessions.append(d)
                
            return {
                "mode": "browse",
                "sessions": sessions
            }
        finally:
            conn.close()

def render_search_results_markdown(data: Dict[str, Any]) -> str:
    if "error" in data:
        return f"❌ **Error:** {data['error']}"
        
    mode = data.get("mode")
    
    if mode == "scroll":
        md = []
        md.append(f"## 📜 Scrolling Session: **{data['title']}** (`{data['session_id']}`)\n")
        if data["messages_before"] > 0:
            md.append(f"*... {data['messages_before']} earlier messages ...*\n")
            
        for m in data["messages"]:
            role_marker = "●" if m["role"] == "user" else "◆" if m["role"] == "assistant" else "⚙️"
            md.append(f"**{m['role'].upper()}** {role_marker}")
            if m.get("tool_name"):
                md.append(f" (Tool: `{m['tool_name']}`)")
            md.append(f"\n{m['content']}\n")
            if m.get("tool_calls"):
                md.append(f"```json\n{json.dumps(m['tool_calls'], indent=2)}\n```\n")
            md.append("---")
            
        if data["messages_after"] > 0:
            md.append(f"\n*... {data['messages_after']} later messages ...*")
            
        return "\n".join(md)
        
    elif mode == "discovery":
        md = []
        md.append(f"## 🔍 Search Results for: `{data['query']}`\n")
        if not data["sessions"]:
            md.append("No matching sessions found.")
            return "\n".join(md)
            
        for s in data["sessions"]:
            md.append(f"### 📂 Session: **{s['title']}**")
            md.append(f"- **ID:** `{s['session_id']}` | **Platform:** `{s['source']}` | **Last active:** {s['when']}")
            md.append(f"- **Match Snippet:** *{s['snippet']}*\n")
            
            # Render Bookend Start
            md.append("<details><summary><b>🌅 Session Kickoff (First 3 turns)</b></summary>\n")
            for m in s["bookend_start"]:
                md.append(f"**{m['role'].upper()}**: {m['content'][:300]}")
                if len(m['content']) > 300: md.append("...")
                md.append("\n")
            md.append("</details>\n")
            
            # Render Window
            md.append("#### 🎯 Context around FTS Match:")
            if s["messages_before"] > 0:
                md.append(f"*... {s['messages_before']} earlier messages ...*")
                
            for m in s["messages"]:
                highlight = "🌟 " if m.get("is_match_hit") else ""
                md.append(f"- {highlight}**{m['role'].upper()}**: {m['content']}")
                
            if s["messages_after"] > 0:
                md.append(f"*... {s['messages_after']} later messages ...*")
                
            # Render Bookend End
            md.append("\n<details><summary><b>🏁 Session Resolution (Last 3 turns)</b></summary>\n")
            for m in s["bookend_end"]:
                md.append(f"**{m['role'].upper()}**: {m['content'][:300]}")
                if len(m['content']) > 300: md.append("...")
                md.append("\n")
            md.append("</details>\n")
            md.append("\n" + "="*40 + "\n")
            
        return "\n".join(md)
        
    elif mode == "browse":
        md = []
        md.append("## 📂 Recent Conversation Sessions\n")
        if not data["sessions"]:
            md.append("No recent sessions found.")
            return "\n".join(md)
            
        md.append("| Title | Source | Last Active | ID | Preview |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")
        for s in data["sessions"]:
            title = s.get("title") or "*(Unnamed)*"
            preview = s.get("preview") or ""
            preview = preview.replace("\n", " ").replace("|", "\\|")[:50]
            if len(s.get("preview") or "") > 50:
                preview += "..."
            md.append(f"| **{title}** | `{s['source']}` | {s['when']} | `{s['id'][:10]}` | {preview} |")
            
        return "\n".join(md)
        
    return "Unknown search mode."
