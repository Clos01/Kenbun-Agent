import os
import sys
import json
from pathlib import Path
import logging

# Ensure project root is in path
sys.path.append(str(Path(__file__).parent.parent))

from tools.infrastructure.config import settings
from tools.memory.postgres_client import init_db, get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_bayesian_weights():
    weights_file = settings.PROJECT_ROOT / "core" / "weights.json"
    if not weights_file.exists():
        logger.info("No weights.json found, skipping.")
        return

    logger.info("Migrating weights.json to PostgreSQL...")
    with open(weights_file, "r") as f:
        data = json.load(f)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Migrate Global
                global_data = data.get("global", {})
                for tool_id, vals in global_data.items():
                    cur.execute("""
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta)
                        VALUES (%s, 'global', %s, %s)
                        ON CONFLICT (tool_id, category) DO NOTHING
                    """, (tool_id, vals.get("alpha", 1.0), vals.get("beta", 1.0)))

                # Migrate Categories
                categories_data = data.get("categories", {})
                for cat, tools in categories_data.items():
                    for tool_id, vals in tools.items():
                        cur.execute("""
                            INSERT INTO bayesian_weights (tool_id, category, alpha, beta)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (tool_id, category) DO NOTHING
                        """, (tool_id, cat, vals.get("alpha", 1.0), vals.get("beta", 1.0)))
            conn.commit()
            logger.info("✅ Migrated bayesian_weights successfully.")
            
            # Rename file to prevent confusion
            weights_file.rename(weights_file.with_suffix(".json.migrated"))
    except Exception as e:
        logger.error(f"❌ Failed to migrate bayesian weights: {e}")

def migrate_keyword_weights():
    weights_file = settings.BRAIN_HEALTH_DIR / "keyword_weights.json"
    if not weights_file.exists():
        logger.info("No keyword_weights.json found, skipping.")
        return

    logger.info("Migrating keyword_weights.json to PostgreSQL...")
    try:
        with open(weights_file, "r") as f:
            data = json.load(f)
            
        with get_connection() as conn:
            with conn.cursor() as cur:
                for keyword, weight in data.items():
                    cur.execute("""
                        INSERT INTO keyword_weights (keyword, weight)
                        VALUES (%s, %s)
                        ON CONFLICT (keyword) DO NOTHING
                    """, (keyword, weight))
            conn.commit()
            logger.info("✅ Migrated keyword_weights successfully.")
            weights_file.rename(weights_file.with_suffix(".json.migrated"))
    except Exception as e:
        logger.error(f"❌ Failed to migrate keyword weights: {e}")

def migrate_routing_failures():
    failures_file = settings.BRAIN_HEALTH_DIR / "routing_failures.jsonl"
    if not failures_file.exists():
        logger.info("No routing_failures.jsonl found, skipping.")
        return

    logger.info("Migrating routing_failures.jsonl to PostgreSQL...")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                with open(failures_file, "r") as f:
                    for line in f:
                        if not line.strip(): continue
                        data = json.loads(line)
                        cur.execute("""
                            INSERT INTO routing_failures (task, wrong_path, correct_path)
                            VALUES (%s, %s, %s)
                        """, (data.get("task", "Unknown"), data.get("wrong_path", ""), data.get("correct_path", "")))
            conn.commit()
            logger.info("✅ Migrated routing_failures successfully.")
            failures_file.rename(failures_file.with_suffix(".jsonl.migrated"))
    except Exception as e:
        logger.error(f"❌ Failed to migrate routing failures: {e}")

if __name__ == "__main__":
    logger.info("Initializing Database...")
    init_db()
    
    migrate_bayesian_weights()
    migrate_keyword_weights()
    migrate_routing_failures()
    
    logger.info("Migration script completed.")
