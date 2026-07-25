import logging
import time
from functools import lru_cache
from tools.memory.postgres_client import get_connection

logger = logging.getLogger(__name__)

# Pipeline stages are legitimate telemetry but are NOT callable tools; they are
# recorded under this namespace so they never masquerade as tools in the dashboard.
STEP_PREFIX = "step:"


@lru_cache(maxsize=1)
def _known_tool_ids() -> frozenset:
    """Real, registered @sovereign_tool names (harvested). Cached once.

    Returns an empty set if the registry cannot be loaded, in which case callers
    fail OPEN (allow the write) so a transient registry error never drops telemetry.
    """
    try:
        from tools.harvester import harvest_and_register_tools
        from tools.registry import registry
        harvest_and_register_tools()
        return frozenset(registry.get_all_tools().keys())
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"tool_id validation: registry unavailable ({e}); failing open.")
        return frozenset()


def is_valid_tool_id(tool_id) -> bool:
    """True for a real registered tool or an explicitly namespaced pipeline step.

    This is the choke point that stops LLM-hallucinated tool_ids (invented by the
    reflection agent, e.g. 'deriveCoords', 'strategy_manager.py') from polluting
    the intelligence store with fabricated Bayesian rows.
    """
    if not tool_id or not isinstance(tool_id, str):
        return False
    if tool_id.startswith(STEP_PREFIX):
        return True
    known = _known_tool_ids()
    if not known:            # registry unavailable -> fail open
        return True
    return tool_id in known

def load_weights():
    """
    Maintains legacy structure for compatibility if anything calls this expecting a dict.
    Fetches all weights from postgres and formats them into the old dict structure.
    """
    weights = {"categories": {}, "global": {}, "last_updated": time.time()}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tool_id, category, alpha, beta FROM bayesian_weights")
                for row in cur:
                    tool = row["tool_id"]
                    cat = row["category"]
                    alpha = row["alpha"]
                    beta = row["beta"]
                    if cat == "global":
                        weights["global"][tool] = {"alpha": alpha, "beta": beta}
                    else:
                        if cat not in weights["categories"]:
                            weights["categories"][cat] = {}
                        weights["categories"][cat][tool] = {"alpha": alpha, "beta": beta}
    except Exception as e:
        logger.error(f"❌ Failed to load bayesian weights from DB: {e}")
    return weights

def tune_swarm(tool_id: str, success: bool, category: str = "global"):
    """
    Updates the Bayesian weights for a specific tool natively in Postgres.
    Uses Beta distribution logic: Alpha (successes) and Beta (failures).
    """
    if not is_valid_tool_id(tool_id):
        logger.warning(f"tune_swarm: rejecting unknown/hallucinated tool_id '{tool_id}'; skipping write.")
        return f"REJECTED: '{tool_id}' is not a registered tool"

    alpha_inc = 1.0 if success else 0.0
    beta_inc = 0.0 if success else 1.0
    s_inc = 1 if success else 0
    f_inc = 0 if success else 1

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Ensure 'global' exists
                cur.execute("""
                    INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count)
                    VALUES (%s, 'global', 1.0, 1.0, 0, 0)
                    ON CONFLICT (tool_id, category) DO NOTHING
                """, (tool_id,))

                # 2. Ensure category-specific exists
                if category != "global":
                    cur.execute("""
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count)
                        SELECT %s, %s, alpha, beta, success_count, failure_count FROM bayesian_weights
                        WHERE tool_id = %s AND category = 'global'
                        ON CONFLICT (tool_id, category) DO NOTHING
                    """, (tool_id, category, tool_id))

                # 3. Update global
                cur.execute("""
                    UPDATE bayesian_weights
                    SET alpha = alpha + %s,
                        beta = beta + %s,
                        success_count = success_count + %s,
                        failure_count = failure_count + %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE tool_id = %s AND category = 'global'
                """, (alpha_inc, beta_inc, s_inc, f_inc, tool_id))

                # 4. Update category-specific
                if category != "global":
                    cur.execute("""
                        UPDATE bayesian_weights
                        SET alpha = alpha + %s,
                            beta = beta + %s,
                            success_count = success_count + %s,
                            failure_count = failure_count + %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE tool_id = %s AND category = %s
                    """, (alpha_inc, beta_inc, s_inc, f_inc, tool_id, category))

                conn.commit()
    except Exception as e:
        logger.error(f"❌ DB tuning error: {e}. Falling back to SQLite...")
        try:
            import sqlite3
            from tools.infrastructure.config import settings
            conn = sqlite3.connect(settings.INTELLIGENCE_DB_PATH)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                cur = conn.cursor()
                # 1. Ensure 'global' exists in local SQLite
                cur.execute("""
                    INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count)
                    VALUES (?, 'global', 1.0, 1.0, 0, 0)
                    ON CONFLICT (tool_id, category) DO NOTHING
                """, (tool_id,))

                # 2. Ensure category-specific exists in local SQLite
                if category != "global":
                    cur.execute("""
                        INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count)
                        SELECT ?, ?, alpha, beta, success_count, failure_count FROM intelligence
                        WHERE tool_id = ? AND category = 'global'
                        ON CONFLICT (tool_id, category) DO NOTHING
                    """, (tool_id, category, tool_id))

                # 3. Update global in local SQLite
                timestamp = str(time.time())
                cur.execute("""
                    UPDATE intelligence
                    SET alpha = alpha + ?,
                        beta = beta + ?,
                        success_count = success_count + ?,
                        failure_count = failure_count + ?,
                        timestamp = ?
                    WHERE tool_id = ? AND category = 'global'
                """, (alpha_inc, beta_inc, s_inc, f_inc, timestamp, tool_id))

                # 4. Update category-specific in local SQLite
                if category != "global":
                    cur.execute("""
                        UPDATE intelligence
                        SET alpha = alpha + ?,
                            beta = beta + ?,
                            success_count = success_count + ?,
                            failure_count = failure_count + ?,
                            timestamp = ?
                        WHERE tool_id = ? AND category = ?
                    """, (alpha_inc, beta_inc, s_inc, f_inc, timestamp, tool_id, category))

                conn.commit()
            finally:
                conn.close()
        except Exception as sqlite_err:
            logger.error(f"❌ SQLite fallback tuning error: {sqlite_err}")
            return f"❌ Tuning failed: {e} (SQLite fallback also failed: {sqlite_err})"

    return f"✅ Synaptic Weight Tuned: {tool_id} ({category}) -> {'SUCCESS' if success else 'FAILURE'}"

def get_confidence(tool_id: str, category: str = "global"):
    """Calculates the expected probability of success (Alpha / (Alpha + Beta))."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Try category first
                cur.execute("SELECT alpha, beta FROM bayesian_weights WHERE tool_id = %s AND category = %s", (tool_id, category))
                row = cur.fetchone()
                if not row:
                    # Fallback to global
                    cur.execute("SELECT alpha, beta FROM bayesian_weights WHERE tool_id = %s AND category = 'global'", (tool_id,))
                    row = cur.fetchone()
                
                if row:
                    alpha, beta = float(row["alpha"]), float(row["beta"])
                    if alpha + beta == 0:
                        return 0.5
                    return alpha / (alpha + beta)
    except Exception as e:
        logger.error(f"❌ Error getting confidence: {e}")
        try:
            import sqlite3
            from tools.infrastructure.config import settings
            conn = sqlite3.connect(settings.INTELLIGENCE_DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute("SELECT alpha, beta FROM intelligence WHERE tool_id = ? AND category = ?", (tool_id, category))
                row = cur.fetchone()
                if not row and category != 'global':
                    cur.execute("SELECT alpha, beta FROM intelligence WHERE tool_id = ? AND category = 'global'", (tool_id,))
                    row = cur.fetchone()
                if row:
                    alpha, beta = float(row[0]), float(row[1])
                    if alpha + beta == 0:
                        return 0.5
                    return alpha / (alpha + beta)
            finally:
                conn.close()
        except Exception as sqlite_err:
            logger.error(f"❌ SQLite fallback confidence error: {sqlite_err}")
    
    # Default fallback
    return 0.5

def get_best_tool(category: str, candidate_tools: list):
    """Returns the tool from the candidates list with the highest confidence for a category."""
    confidences = {tid: get_confidence(tid, category) for tid in candidate_tools}
    best_tool = max(confidences, key=confidences.get)
    return best_tool, confidences[best_tool]

if __name__ == "__main__":
    from tools.memory.postgres_client import init_db
    init_db()
    print(tune_swarm("consult_supervisor", True, "security"))
    print(f"Confidence: {get_confidence('consult_supervisor', 'security'):.2f}")
