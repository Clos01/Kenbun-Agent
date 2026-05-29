import os
import sqlite3
import chromadb
from pathlib import Path

from tools.infrastructure.config import settings

PC_IP = settings.SWARM_PC_IP
CHROMA_PORT = settings.CHROMA_PORT
LOCAL_DB_PATH = settings.INTELLIGENCE_DB_PATH

def run_sync():
    """Syncs local SQLite intelligence to remote ChromaDB."""
    if not LOCAL_DB_PATH.exists():
        print("ℹ️ No local intelligence database to sync.")
        return

    print("🔄 Starting Intelligence Sync (Local ➔ Remote)...")
    
    try:
        # Connect to local
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        cursor.execute("SELECT tool_id, category, alpha, beta, success_count, failure_count, timestamp FROM intelligence")
        local_rows = cursor.fetchall()
        
        if not local_rows:
            print("ℹ️ Local database is empty. Nothing to sync.")
            return

        # Connect to remote
        try:
            client = chromadb.HttpClient(host=PC_IP, port=int(CHROMA_PORT))
            collection = client.get_or_create_collection(name="system_4_intelligence")
            # Heartbeat check
            client.heartbeat()
        except Exception as conn_err:
            print(f"⚠️ Remote PC offline. Skipping sync. ({conn_err})")
            return
        
        sync_count = 0
        for row in local_rows:
            tool_id, category, alpha, beta, s, f, ts = row
            
            # Check if remote has newer data
            remote_res = collection.get(ids=[tool_id])
            if remote_res["ids"]:
                remote_ts = float(remote_res["metadatas"][0].get("timestamp", 0))
                if float(ts) <= remote_ts:
                    continue # Remote is already up to date or newer
            
            # Update remote
            collection.upsert(
                ids=[tool_id],
                metadatas=[{
                    "category": category,
                    "alpha": alpha,
                    "beta": beta,
                    "success_count": s,
                    "failure_count": f,
                    "timestamp": ts
                }],
                documents=[f"Intelligence profile for {tool_id}"]
            )
            sync_count += 1
            
        print(f"✅ Sync Complete: {sync_count} tool profiles updated on remote PC.")
        conn.close()
    except Exception as e:
        print(f"❌ Sync Failed: {e}")

if __name__ == "__main__":
    run_sync()
