import logging
import time
from tools.memory.postgres_client import get_connection

logger = logging.getLogger(__name__)

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
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Update Global
                cur.execute("""
                    INSERT INTO bayesian_weights (tool_id, category, alpha, beta)
                    VALUES (%s, 'global', %s, %s)
                    ON CONFLICT (tool_id, category) DO UPDATE 
                    SET alpha = bayesian_weights.alpha + %s,
                        beta = bayesian_weights.beta + %s,
                        last_updated = CURRENT_TIMESTAMP
                """, (
                    tool_id,
                    1.0 if success else 0.0, 
                    0.0 if success else 1.0,
                    1.0 if success else 0.0,
                    0.0 if success else 1.0
                ))

                # 2. Update Category-specific (if not global)
                if category != "global":
                    # If category record doesn't exist, we must seed it from the current global value first.
                    cur.execute("""
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta)
                        SELECT %s, %s, alpha, beta FROM bayesian_weights WHERE tool_id = %s AND category = 'global'
                        ON CONFLICT (tool_id, category) DO NOTHING
                    """, (tool_id, category, tool_id))

                    cur.execute("""
                        UPDATE bayesian_weights
                        SET alpha = alpha + %s,
                            beta = beta + %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE tool_id = %s AND category = %s
                    """, (
                        1.0 if success else 0.0,
                        0.0 if success else 1.0,
                        tool_id, category
                    ))
                conn.commit()
    except Exception as e:
        logger.error(f"❌ DB tuning error: {e}")
        return f"❌ Tuning failed: {e}"

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
                    alpha, beta = row["alpha"], row["beta"]
                    return alpha / (alpha + beta)
    except Exception as e:
        logger.error(f"❌ Error getting confidence: {e}")
    
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
