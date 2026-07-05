import logging
import psycopg
from psycopg.rows import dict_row
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

def get_connection():
    """Returns a synchronous psycopg connection."""
    conn_str = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}?connect_timeout=3"
    return psycopg.connect(conn_str, row_factory=dict_row)

def init_db():
    """Initializes the PostgreSQL schemas if they do not exist."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. bayesian_weights
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bayesian_weights (
                        tool_id VARCHAR(255) NOT NULL,
                        category VARCHAR(255) NOT NULL DEFAULT 'global',
                        alpha FLOAT NOT NULL DEFAULT 1.0,
                        beta FLOAT NOT NULL DEFAULT 1.0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (tool_id, category)
                    );
                """)
                
                # 2. keyword_weights
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS keyword_weights (
                        keyword VARCHAR(255) PRIMARY KEY,
                        weight FLOAT NOT NULL DEFAULT 1.0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # 3. routing_failures
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS routing_failures (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        task TEXT NOT NULL,
                        wrong_path VARCHAR(255) NOT NULL,
                        correct_path VARCHAR(255) NOT NULL
                    );
                """)

                # 4. agent_evaluations
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS agent_evaluations (
                        id SERIAL PRIMARY KEY,
                        agent_id VARCHAR(255) NOT NULL,
                        task_id VARCHAR(255) NOT NULL,
                        run_id VARCHAR(255) NOT NULL,
                        prompt_hash VARCHAR(64) NOT NULL,
                        score FLOAT NOT NULL DEFAULT 0.0,
                        speed_sec FLOAT,
                        token_cost FLOAT,
                        compliance_score FLOAT,
                        eval_feedback TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 5. agent_prompts
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS agent_prompts (
                        prompt_hash VARCHAR(64) PRIMARY KEY,
                        agent_id VARCHAR(255) NOT NULL,
                        system_prompt TEXT NOT NULL,
                        meta_data JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                logger.info("✅ PostgreSQL tables initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize PostgreSQL tables: {e}")
