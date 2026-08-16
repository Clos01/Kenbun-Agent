import os
import sys
import sqlite3
import logging
from pathlib import Path

# Add core to path so we can import internal modules
sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.infrastructure.config import settings
from tools.memory.postgres_client import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def sync_sqlite_to_postgres():
    sqlite_db_path = settings.INTELLIGENCE_DB_PATH
    if not sqlite_db_path.exists():
        # Fall back to alternative names or locations if default is missing
        alt_db = settings.BRAIN_HEALTH_DIR / "antigravity_intelligence.db"
        if alt_db.exists():
            sqlite_db_path = alt_db
        else:
            logger.error(f"❌ SQLite database not found at {sqlite_db_path} or {alt_db}")
            return

    logger.info(f"📂 Reading local SQLite stats from: {sqlite_db_path}")
    
    try:
        sqlite_conn = sqlite3.connect(sqlite_db_path)
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intelligence'")
        if not sqlite_cur.fetchone():
            logger.error("❌ Table 'intelligence' does not exist in the SQLite database.")
            sqlite_conn.close()
            return
            
        sqlite_cur.execute("SELECT tool_id, category, alpha, beta, success_count, failure_count FROM intelligence")
        rows = sqlite_cur.fetchall()
        sqlite_conn.close()
    except Exception as e:
        logger.error(f"❌ Failed to read SQLite database: {e}")
        return

    if not rows:
        logger.warning("⚠️ No tool statistics found in SQLite database.")
        return

    logger.info(f"🔍 Found {len(rows)} tool stat records to sync.")

    # Override postgres host to localhost for SSH tunneling if running locally
    if os.environ.get("POSTGRES_HOST") == "127.0.0.1" or settings.POSTGRES_HOST == "100.104.211.61":
        logger.info("🔌 Routing database calls through local tunnel (127.0.0.1)...")
    
    success_count = 0
    try:
        with get_connection() as pg_conn:
            with pg_conn.cursor() as pg_cur:
                # First ensure tables are initialized
                from tools.memory.postgres_client import init_db
                init_db()
                
                for row in rows:
                    tool_id, category, alpha, beta, success, failure = row
                    
                    # Perform additive upsert: add local successes/failures to remote database
                    # and combine alpha/beta distributions (subtracting baseline 1.0 to avoid doubling)
                    pg_cur.execute("""
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tool_id, category) DO UPDATE
                        SET alpha = bayesian_weights.alpha + EXCLUDED.alpha - 1.0,
                            beta = bayesian_weights.beta + EXCLUDED.beta - 1.0,
                            success_count = bayesian_weights.success_count + EXCLUDED.success_count,
                            failure_count = bayesian_weights.failure_count + EXCLUDED.failure_count,
                            last_updated = CURRENT_TIMESTAMP
                    """, (tool_id, category, alpha, beta, success, failure))
                    success_count += 1
                
                pg_conn.commit()
        logger.info(f"✅ Successfully synced {success_count} records to PostgreSQL!")
    except Exception as e:
        logger.error(f"❌ Failed to sync to PostgreSQL: {e}")

if __name__ == "__main__":
    sync_sqlite_to_postgres()
