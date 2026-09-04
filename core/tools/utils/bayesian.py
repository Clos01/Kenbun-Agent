import logging
import math
import random
import time
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Set, Any, NamedTuple


# ── PURE FUNCTIONAL DATA LAYER (IEEE-754 DOMAIN PROTECTED) ─────────────────

class BayesianDistribution(NamedTuple):
    """Immutable functional record representing a Beta(alpha, beta) distribution."""
    alpha: float
    beta: float
    success_count: int = 0
    failure_count: int = 0


def pure_update_posterior(
    current: BayesianDistribution,
    success: bool,
    weight: float = 1.0,
) -> BayesianDistribution:
    """
    Pure functional transformation: returns a new immutable BayesianDistribution
    with strict IEEE-754 domain validation. Zero side-effects.
    """
    if not math.isfinite(weight) or weight < 0:
        raise ValueError("Weight must be a finite, non-negative number.")
    if not math.isfinite(current.alpha) or current.alpha < 0 or not math.isfinite(current.beta) or current.beta < 0:
        raise ValueError("Alpha and beta parameters must be finite non-negative numbers.")

    alpha_inc = weight if success else 0.0
    beta_inc = 0.0 if success else weight
    s_inc = 1 if success else 0
    f_inc = 0 if success else 1

    return BayesianDistribution(
        alpha=max(0.01, current.alpha + alpha_inc),
        beta=max(0.01, current.beta + beta_inc),
        success_count=max(0, current.success_count + s_inc),
        failure_count=max(0, current.failure_count + f_inc),
    )


def pure_expected_confidence(dist: BayesianDistribution) -> float:
    """
    Pure functional calculation: E[p] = alpha / (alpha + beta) with IEEE-754 zero-division protection.
    """
    if not math.isfinite(dist.alpha) or dist.alpha < 0 or not math.isfinite(dist.beta) or dist.beta < 0:
        return 0.5
    total = dist.alpha + dist.beta
    if not math.isfinite(total) or total <= 0:
        return 0.5
    return max(0.0, min(1.0, dist.alpha / total))


def pure_thompson_sample(dist: BayesianDistribution, random_generator: Optional[Any] = None) -> float:
    """
    Pure functional Thompson sampling draw: Beta(alpha, beta).
    """
    rng = random_generator if random_generator is not None else random
    a = max(0.01, dist.alpha)
    b = max(0.01, dist.beta)
    return rng.betavariate(a, b)

try:
    from tools.memory.postgres_client import get_connection
except Exception:
    def get_connection():
        raise RuntimeError("Postgres client unavailable")

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


_last_db_fallback_event: Optional[Dict[str, Any]] = None


def record_db_fallback(operation: str, reason: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Records a database fallback event and logs a prominent operator alert."""
    global _last_db_fallback_event
    _last_db_fallback_event = {
        "timestamp": time.time(),
        "operation": operation,
        "reason": str(reason),
        "details": details or {},
    }
    logger.warning(
        f"🚨 [DATABASE FALLBACK ALERT]: Remote PostgreSQL unreachable during '{operation}' ({reason}). "
        f"Operating on local SQLite fallback."
    )


def get_db_status() -> Dict[str, Any]:
    """Returns the live database health status, indicating if system is in fallback mode."""
    reachable = False
    error_msg = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                reachable = True
    except Exception as exc:
        error_msg = str(exc)

    fallback_active = not reachable

    # Dynamically resolve the physical hardware node without hardcoding
    from tools.infrastructure.config import settings
    node_label = f"Remote Host ({settings.POSTGRES_HOST})"
    try:
        from pathlib import Path
        import sys
        inv_path = Path(settings.PROJECT_ROOT) / ".agents/skills/cluster-hardware-topology"
        if str(inv_path) not in sys.path:
            sys.path.insert(0, str(inv_path))
        from resolver import format_node_label
        node_label = format_node_label(settings.POSTGRES_HOST)
    except Exception:
        pass

    alert_message = (
        f"⚠️ Remote PostgreSQL on {node_label} unreachable ({error_msg}); operating on Local Mac SQLite fallback."
        if fallback_active
        else f"✅ Connected to primary remote PostgreSQL on {node_label}."
    )
    return {
        "primary_reachable": reachable,
        "remote_node": node_label,
        "active_source": f"postgres ({node_label})" if reachable else "sqlite (Local Mac fallback)",
        "fallback_active": fallback_active,
        "last_fallback": _last_db_fallback_event,
        "alert_message": alert_message,
    }


def sync_local_to_postgres() -> Dict[str, Any]:
    """Synchronizes all learned Bayesian tool distributions from local SQLite to remote PostgreSQL.

    Reads every record in `intelligence` and upserts it into PostgreSQL `bayesian_weights`
    merging alphas, betas, and counts.
    """
    import sqlite3
    from tools.infrastructure.config import settings

    local_path = settings.INTELLIGENCE_DB_PATH
    try:
        conn_local = sqlite3.connect(local_path)
        cur_local = conn_local.cursor()
        cur_local.execute(
            "SELECT tool_id, category, alpha, beta, success_count, failure_count FROM intelligence"
        )
        rows = cur_local.fetchall()
        conn_local.close()
    except Exception as e:
        return {"status": "error", "message": f"Failed to read local SQLite: {e}", "synced_count": 0}

    if not rows:
        return {"status": "success", "message": "No local distributions to sync.", "synced_count": 0}

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    tool_id, category, alpha, beta, s_count, f_count = row
                    cur.execute("""
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count, last_updated)
                        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (tool_id, category) DO UPDATE SET
                            alpha = GREATEST(bayesian_weights.alpha, EXCLUDED.alpha),
                            beta = GREATEST(bayesian_weights.beta, EXCLUDED.beta),
                            success_count = GREATEST(bayesian_weights.success_count, EXCLUDED.success_count),
                            failure_count = GREATEST(bayesian_weights.failure_count, EXCLUDED.failure_count),
                            last_updated = CURRENT_TIMESTAMP
                    """, (tool_id, category, float(alpha), float(beta), int(s_count), int(f_count)))
                conn.commit()
        return {
            "status": "success",
            "message": f"Successfully synchronized {len(rows)} distributions to remote PostgreSQL.",
            "synced_count": len(rows),
        }
    except Exception as e:
        logger.error(f"Failed to sync local distributions to PostgreSQL: {e}")
        return {"status": "error", "message": f"PostgreSQL sync failed: {e}", "synced_count": 0}


def load_weights():
    """
    Maintains legacy structure for compatibility if anything calls this expecting a dict.
    Fetches all weights from postgres and formats them into the old dict structure.
    Falls back to local SQLite if remote PostgreSQL is unreachable.
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
        record_db_fallback("load_weights", str(e))
        try:
            import sqlite3
            from tools.infrastructure.config import settings
            conn = sqlite3.connect(settings.INTELLIGENCE_DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT tool_id, category, alpha, beta FROM intelligence")
            for row in cur:
                tool, cat, alpha, beta = row[0], row[1], float(row[2]), float(row[3])
                if cat == "global":
                    weights["global"][tool] = {"alpha": alpha, "beta": beta}
                else:
                    if cat not in weights["categories"]:
                        weights["categories"][cat] = {}
                    weights["categories"][cat][tool] = {"alpha": alpha, "beta": beta}
            conn.close()
        except Exception:
            pass
    return weights

def tune_swarm(tool_id: str, success: bool, category: str = "global"):
    """
    Updates the Bayesian weights for a specific tool natively in Postgres.
    Uses Beta distribution logic: Alpha (successes) and Beta (failures).
    """
    if not is_valid_tool_id(tool_id):
        logger.warning(f"tune_swarm: rejecting unknown/hallucinated tool_id '{tool_id}'; skipping write.")
        return f"REJECTED: '{tool_id}' is not a registered tool"

    # Mathematical derivation performed via pure functional transformation
    unit_prior = BayesianDistribution(alpha=1.0, beta=1.0, success_count=0, failure_count=0)
    updated = pure_update_posterior(unit_prior, success=success, weight=1.0)
    alpha_inc = updated.alpha - unit_prior.alpha
    beta_inc = updated.beta - unit_prior.beta
    s_inc = updated.success_count - unit_prior.success_count
    f_inc = updated.failure_count - unit_prior.failure_count

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
        record_db_fallback("tune_swarm", str(e), {"tool_id": tool_id, "category": category, "success": success})
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

def get_confidence(tool_id: str, category: str = "global") -> float:
    """Calculates the expected probability of success E[p] = Alpha / (Alpha + Beta) via pure FP."""
    alpha, beta = get_posterior_params(tool_id, category)
    dist = BayesianDistribution(alpha=alpha, beta=beta)
    return pure_expected_confidence(dist)


def get_posterior_params(tool_id: str, category: str = "global") -> Tuple[float, float]:
    """
    Returns the posterior (alpha, beta) parameters for a tool.
    Prior defaults to Beta(1.0, 1.0) (uniform distribution).
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT alpha, beta FROM bayesian_weights WHERE tool_id = %s AND category = %s", (tool_id, category))
                row = cur.fetchone()
                if not row:
                    cur.execute("SELECT alpha, beta FROM bayesian_weights WHERE tool_id = %s AND category = 'global'", (tool_id,))
                    row = cur.fetchone()
                if row:
                    alpha, beta = float(row["alpha"]), float(row["beta"])
                    return max(alpha, 0.01), max(beta, 0.01)
    except Exception as e:
        logger.error(f"❌ Error getting posterior params: {e}")
        record_db_fallback("get_posterior_params", str(e), {"tool_id": tool_id, "category": category})
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
                    return max(alpha, 0.01), max(beta, 0.01)
            finally:
                conn.close()
        except Exception:
            pass

    return 1.0, 1.0


def get_posterior_params_batch(tool_ids: List[str], category: str = "global") -> Dict[str, Tuple[float, float]]:
    """Batch form of get_posterior_params: one round trip instead of one per tool.

    recommend_tools() ranks a handful of candidates on EVERY routing decision, so
    a per-tool SELECT would put N intelligence-store round trips in the hot path
    of every task. Tools with no stored row are simply absent from the result;
    callers fall back to the uniform Beta(1,1) prior, which is what the per-tool
    lookup would have returned anyway.

    Returns {} if the batch query fails, signalling the caller to fall back.
    """
    ids = [t for t in dict.fromkeys(tool_ids) if t]
    if not ids:
        return {}

    resolved: Dict[str, Tuple[float, float]] = {}
    seen_specific: set = set()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tool_id, category, alpha, beta FROM bayesian_weights "
                    "WHERE tool_id = ANY(%s) AND category IN (%s, 'global')",
                    (ids, category),
                )
                rows = cur.fetchall() or []
        for row in rows:
            tid = row["tool_id"]
            is_specific = row["category"] == category
            # A category-specific row always wins over the 'global' fallback row,
            # regardless of the order the two came back in.
            if tid in resolved and not is_specific:
                continue
            if tid in seen_specific and not is_specific:
                continue
            resolved[tid] = (max(float(row["alpha"]), 0.01), max(float(row["beta"]), 0.01))
            if is_specific:
                seen_specific.add(tid)
        return resolved
    except Exception as e:
        logger.error(f"❌ Batch posterior fetch failed ({e}); trying local intelligence DB.")
        record_db_fallback("get_posterior_params_batch", str(e), {"tool_ids": ids, "category": category})

    # Local SQLite mirror, also batched. Doing this per-tool instead would mean
    # one 3s connect timeout PER CANDIDATE every time Postgres is unreachable,
    # which turns a telemetry outage into a routing outage.
    try:
        import sqlite3
        from tools.infrastructure.config import settings
        conn = sqlite3.connect(settings.INTELLIGENCE_DB_PATH)
        try:
            placeholders = ",".join("?" for _ in ids)
            cur = conn.cursor()
            cur.execute(
                f"SELECT tool_id, category, alpha, beta FROM intelligence "
                f"WHERE tool_id IN ({placeholders}) AND category IN (?, 'global')",
                (*ids, category),
            )
            for tid, cat, alpha, beta in cur.fetchall():
                is_specific = cat == category
                if tid in seen_specific and not is_specific:
                    continue
                resolved[tid] = (max(float(alpha), 0.01), max(float(beta), 0.01))
                if is_specific:
                    seen_specific.add(tid)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"❌ Local posterior fetch failed too ({e}); using uniform priors.")

    return resolved


def _resolve_posteriors(tool_ids: List[str], category: str) -> Dict[str, Tuple[float, float]]:
    """Posteriors for every id in a single round trip.

    Anything the batch did not resolve gets the uniform Beta(1,1) prior, which
    is exactly what a per-tool lookup would have returned for an unseen tool.
    Deliberately does NOT retry per-tool: that fallback made an unreachable
    intelligence store cost one connect timeout per candidate, per decision.
    """
    ids = [t for t in dict.fromkeys(tool_ids) if t]
    resolved = get_posterior_params_batch(ids, category)
    for tid in ids:
        resolved.setdefault(tid, (1.0, 1.0))
    return resolved


def calculate_thompson_sample(
    alpha: float,
    beta: float,
    temperature: float = 1.0,
    random_generator: Optional[Any] = None,
) -> float:
    """Calculates a Thompson sampling draw using the pure functional sampler."""
    t = max(temperature, 0.01)
    dist = BayesianDistribution(alpha=max(alpha / t, 0.01), beta=max(beta / t, 0.01))
    return pure_thompson_sample(dist, random_generator=random_generator)


def rank_tools_thompson(
    category: str,
    candidate_tools: list,
    exploration_mode: bool = True,
    temperature: float = 1.0,
    posteriors: Optional[Dict[str, Tuple[float, float]]] = None,
) -> List[Tuple[str, float]]:
    """
    Full best-first ordering of candidate_tools (ESL Ch. 8 & 16).

    exploration_mode=True draws theta_i ~ Beta(alpha_i / T, beta_i / T) per tool
    and sorts on the draw, so a tool with a wide posterior (few observations)
    still surfaces sometimes instead of being starved by a marginally better
    veteran. exploration_mode=False sorts on the posterior mean E[p].

    Returns [(tool_id, score), ...], highest score first. Duplicates in
    candidate_tools are collapsed, preserving first-seen order.
    """
    ids = [t for t in dict.fromkeys(candidate_tools) if t]
    if not ids:
        raise ValueError("candidate_tools list cannot be empty")

    params = posteriors if posteriors is not None else _resolve_posteriors(ids, category)
    t = max(temperature, 0.01)

    scored: List[Tuple[str, float]] = []
    for tid in ids:
        alpha, beta = params.get(tid, (1.0, 1.0))
        dist = BayesianDistribution(alpha=alpha, beta=beta)
        if exploration_mode:
            score = calculate_thompson_sample(alpha, beta, temperature=t)
        else:
            score = pure_expected_confidence(dist)
        scored.append((tid, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def sample_tool_thompson(category: str, candidate_tools: list, temperature: float = 1.0) -> Tuple[str, float]:
    """
    Thompson Sampling for Multi-Armed Bandits (ESL Ch. 8 & 16).
    Samples theta_i ~ Beta(alpha_i / T, beta_i / T) for each candidate tool,
    balancing exploration of uncertain tools with exploitation of high-performing tools.
    """
    if not candidate_tools:
        raise ValueError("candidate_tools list cannot be empty")
    if len(candidate_tools) == 1:
        # No arms to trade off against: report the mean, not a noisy draw.
        alpha, beta = get_posterior_params(candidate_tools[0], category)
        conf = pure_expected_confidence(BayesianDistribution(alpha=alpha, beta=beta))
        return candidate_tools[0], conf

    return rank_tools_thompson(category, candidate_tools, exploration_mode=True, temperature=temperature)[0]


def get_best_tool(category: str, candidate_tools: list, exploration_mode: bool = True, temperature: float = 1.0):
    """
    Returns the optimal tool from candidate_tools.
    If exploration_mode=True: Uses Bayesian Thompson Sampling (ESL Ch. 8 & 16) to explore/exploit.
    If exploration_mode=False: Uses greedy argmax of the expected value E[p] = alpha / (alpha + beta).
    """
    if not candidate_tools:
        raise ValueError("candidate_tools list cannot be empty")

    if exploration_mode:
        return sample_tool_thompson(category, candidate_tools, temperature=temperature)

    confidences = {tid: get_confidence(tid, category) for tid in candidate_tools}
    best_tool = max(confidences, key=confidences.get)
    return best_tool, confidences[best_tool]


if __name__ == "__main__":
    from tools.memory.postgres_client import init_db
    init_db()
    print(tune_swarm("consult_supervisor", True, "security"))
    print(f"Confidence: {get_confidence('consult_supervisor', 'security'):.2f}")

