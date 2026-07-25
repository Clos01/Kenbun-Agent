import random
import chromadb
import sqlite3
import time
from datetime import datetime
from functools import lru_cache

import sys
def print(*args, **kwargs):
    kwargs['file'] = sys.stderr
    __builtins__['print'](*args, **kwargs)

from tools.infrastructure.config import settings
PC_IP = settings.CHROMA_HOST
CHROMA_PORT = settings.CHROMA_PORT
LOCAL_DB_PATH = settings.INTELLIGENCE_DB_PATH

from dataclasses import dataclass
from enum import Enum
from typing import List
import threading

# --- CONSTANTS ---
COLD_START_PRIOR = 0.85
STABLE_PRIOR = 2.0
DETERMINISTIC_PRIOR = 5.0
DECAY_HALFLIFE_HOURS = 24  # default half-life; override with env BAYES_DECAY_HALFLIFE_HOURS

import os as _os
from datetime import timezone as _timezone


def _recency_factor(last_updated, half_life_hours=None):
    """Exponential recency weight in (0, 1].

    Returns 1.0 when the timestamp is missing, in the future, or unparseable so
    fresh/unknown data is never penalised. Older evidence decays toward the prior,
    which is what stops stale rows (e.g. one-off simulated seed data) from
    dominating the intelligence store forever.
    """
    if half_life_hours is None:
        try:
            half_life_hours = float(_os.getenv("BAYES_DECAY_HALFLIFE_HOURS", DECAY_HALFLIFE_HOURS))
        except (TypeError, ValueError):
            half_life_hours = DECAY_HALFLIFE_HOURS
    if not last_updated or half_life_hours <= 0:
        return 1.0
    try:
        ts = last_updated
        if isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(float(ts), tz=_timezone.utc)
        elif isinstance(ts, str):
            s = ts.strip()
            if not s:
                return 1.0
            try:  # some paths store str(time.time())
                ts = datetime.fromtimestamp(float(s), tz=_timezone.utc)
            except ValueError:
                ts = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_timezone.utc)
        age_hours = (datetime.now(_timezone.utc) - ts).total_seconds() / 3600.0
        if age_hours <= 0:
            return 1.0
        return 0.5 ** (age_hours / half_life_hours)
    except Exception:
        return 1.0


def _decayed_weights(success_count, failure_count, last_updated):
    """Recency-weighted Beta(1 + s', 1 + f') params derived from raw event counts.

    Uses the true success/failure counts as ground truth (rather than the stored
    alpha/beta, whose prior base has drifted across code paths) and shrinks them
    toward the uniform prior as they age.
    """
    factor = _recency_factor(last_updated)
    s = max(0.0, float(success_count or 0)) * factor
    f = max(0.0, float(failure_count or 0)) * factor
    return 1.0 + s, 1.0 + f

class PulseStatus(str, Enum):
    STABLE = "STABLE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True, slots=True)
class TelemetryPulse:
    accuracy: float
    load: float
    status: PulseStatus
    timestamp: float

    def __post_init__(self):
        # Production-grade validation
        object.__setattr__(self, 'accuracy', max(0.0, min(1.0, self.accuracy)))
        object.__setattr__(self, 'load', max(0.0, self.load))

def get_discovered_or_default_tools() -> List[tuple[str, str]]:
    """Gets dynamically discovered tools, falling back to a static default list."""
    try:
        from tools.harvester import harvest_and_register_tools
        from tools.registry import registry
        harvest_and_register_tools()
        discovered = registry.get_all_tools()
        if discovered:
            return [(t_id, t_entry.category) for t_id, t_entry in discovered.items()]
    except Exception as e:
        print(f"⚠️ Bayesian Governor: Harvester error ({e}). Using static fallback.")
        
    return [
        ("token_governor", "Strategy"),
        ("telemetry_pulse", "Sensory"),
        ("fleet_monitor", "Sensory"),
        ("topology_mapper", "Observatory"),
        ("audit_supervisor", "Reasoning"),
        ("vector_sync_worker", "Memory"),
        ("bayesian_governor", "Strategy"),
        ("sovereignty_engine", "Self-Healing"),
        ("memory_classifier", "Memory"),
        ("neural_classifier", "Vector ML"),
        ("intelligence_engine", "Reflection"),
        ("scan_repo", "Execution"),
        ("run_code_safely", "Execution"),
        ("list_checkpoints", "Autonomic"),
        ("index_codebase", "Memory"),
        ("delete_from_hivemind", "Reflection"),
        ("get_brain_health", "Reflection"),
        ("audit_package_safety", "Guardrail"),
        ("ask_architect", "Reasoning"),
        ("ask_ui_expert", "Design Discovery"),
        ("consult_supervisor", "Reasoning"),
        ("audit_guardrail", "Guardrail"),
        ("autofix_linter", "Guardrail"),
        ("research_official_docs", "Execution"),
        ("review_code_with_gemini", "Cloud Execution"),
        ("research_with_gemini", "Execution"),
        ("remember_fix", "Reflection"),
        ("recall_fix", "Memory"),
        ("save_checkpoint", "Autonomic"),
        ("restore_checkpoint", "Autonomic"),
        ("orchestrate", "Strategy"),
        ("save_to_hivemind", "Reflection"),
        ("search_hivemind_concepts", "Memory"),
        ("search_codebase", "Memory"),
        ("think_about_tools", "Strategy"),
        ("patch_hivemind_concept", "Reflection"),
        ("ingest_knowledge_from_pdf", "Memory"),
        ("prune_hivemind", "Reflection"),
        ("get_intelligence_stats", "Strategy"),
        ("reflect_on_task", "Reflection")
    ]

class BayesianGovernor:
    """
    The Bayesian Governor (System 4).
    Stores tool intelligence weights directly in the remote ChromaDB
    to keep the local machine (Mac) 100% stateless, with a local SQLite fallback.
    """
    def __init__(self):
        self.pc_ip = PC_IP
        self.chroma_port = CHROMA_PORT
        self.client = None
        self.collection = None
        self.local_conn = None
        self.use_local = False
        self._lock = threading.RLock() # Atomic Consolidation Lock
        self._db_initialized = False

    def _ensure_db(self):
        """Ensures that either the remote or local database is initialized thread-safely."""
        if self._db_initialized:
            return
        with self._lock:
            if self._db_initialized:
                return
            self._init_remote_db()
            if self.use_local:
                self._init_local_db()
            self._db_initialized = True

    def _init_remote_db(self):
        """Initializes connection to the remote weight store or falls back to local."""
        import socket
        
        # Quick reachability check to prevent long hangs on hotspot
        try:
            if not PC_IP:
                raise ValueError("PC_IP_ADDRESS not set")
            
            # 2 second timeout for reachability of ChromaDB
            with socket.create_connection((self.pc_ip, int(self.chroma_port)), timeout=2):
                pass
            
            # 2 second timeout for reachability of PostgreSQL
            with socket.create_connection((settings.POSTGRES_HOST, int(settings.POSTGRES_PORT)), timeout=2):
                pass
            
            # Try to connect to PostgreSQL to verify auth/credentials
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                pass
            
            self.client = chromadb.HttpClient(host=self.pc_ip, port=int(self.chroma_port))
            self.collection = self.client.get_or_create_collection(name="system_4_intelligence")
            
            # Bootstrap default tools in remote ChromaDB if collection is empty
            if self.collection.count() == 0:
                default_tools = get_discovered_or_default_tools()
                timestamp = str(time.time())
                for tool_id, category in default_tools:
                    self.collection.upsert(
                        ids=[tool_id],
                        documents=[f"{tool_id} intelligence weights"],
                        metadatas=[{
                            "category": category,
                            "alpha": 2.0,
                            "beta": 2.0,
                            "success_count": 0,
                            "failure_count": 0,
                            "timestamp": timestamp,
                            "project": settings.PROJECT_NAME
                        }]
                    )
                print(f"✅ Bayesian Governor: Bootstrapped {len(default_tools)} default tools in remote ChromaDB.")
            
            self.use_local = False
        except Exception as e:
            print(f"⚠️ System 4: Remote PC {self.pc_ip} / DB unreachable ({e}). Using local SQLite.")
            self.use_local = True

    def _init_local_db(self):
        if self.local_conn: return
        try:
            # Absolute Path Hardening
            self.local_conn = sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)
            self.local_conn.execute("PRAGMA journal_mode=WAL;")
            print(f"✅ Bayesian Governor: Connected to {LOCAL_DB_PATH} in WAL mode")

            # Migration check
            cursor = self.local_conn.cursor()
            cursor.execute("PRAGMA table_info(intelligence)")
            columns = cursor.fetchall()
            if columns:
                pk_cols = [col[1] for col in columns if col[5] > 0]
                if pk_cols == ["tool_id"]:
                    print("🔄 Running self-healing migration for intelligence table schema...")
                    cursor.execute("ALTER TABLE intelligence RENAME TO intelligence_old")
                    cursor.execute('''
                        CREATE TABLE intelligence (
                            tool_id TEXT,
                            category TEXT DEFAULT 'global',
                            alpha REAL DEFAULT 2.0,
                            beta REAL DEFAULT 2.0,
                            success_count INTEGER DEFAULT 0,
                            failure_count INTEGER DEFAULT 0,
                            timestamp TEXT,
                            PRIMARY KEY (tool_id, category)
                        )
                    ''')
                    cursor.execute('''
                        INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                        SELECT tool_id, COALESCE(category, 'global'), alpha, beta, success_count, failure_count, timestamp
                        FROM intelligence_old
                    ''')
                    cursor.execute("DROP TABLE intelligence_old")
                    self.local_conn.commit()
                    print("✅ Self-healing migration completed.")
        except Exception as e:
            print(f"❌ Bayesian Governor: Failed to connect or migrate DB at {LOCAL_DB_PATH}: {e}")
            return

        cursor = self.local_conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS intelligence (
                tool_id TEXT,
                category TEXT DEFAULT 'global',
                alpha REAL DEFAULT 2.0,
                beta REAL DEFAULT 2.0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                timestamp TEXT,
                PRIMARY KEY (tool_id, category)
            )
        ''')
        self.local_conn.commit()

        # Bootstrap default tools if table is empty to prevent UI layout gaps
        try:
            cursor.execute("SELECT COUNT(*) FROM intelligence")
            if cursor.fetchone()[0] == 0:
                default_tools = get_discovered_or_default_tools()
                timestamp = str(time.time())
                cursor.executemany('''
                    INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                    VALUES (?, ?, 2.0, 2.0, 0, 0, ?)
                ''', [(t[0], t[1] or 'global', timestamp) for t in default_tools])
                self.local_conn.commit()
                print(f"✅ Bayesian Governor: Bootstrapped {len(default_tools)} default tools in SQLite.")
        except Exception as e:
            print(f"⚠️ Bayesian Governor: Bootstrapping default tools failed: {e}")

    @lru_cache(maxsize=128)
    def get_tool_stats(self, tool_id: str, category: str = 'global'):
        """Retrieves weights from PostgreSQL or local SQLite."""
        self._ensure_db()
        if self.use_local and self.local_conn:
            try:
                with self._lock:
                    cursor = self.local_conn.cursor()
                    cursor.execute("SELECT alpha, beta, success_count, failure_count, timestamp FROM intelligence WHERE tool_id = ? AND category = ?", (tool_id, category))
                    row = cursor.fetchone()
                    if row:
                        a, b = _decayed_weights(row[2], row[3], row[4])
                        return a, b, int(row[2]), int(row[3])
                    elif category != 'global':
                        cursor.execute("SELECT alpha, beta, success_count, failure_count, timestamp FROM intelligence WHERE tool_id = ? AND category = 'global'", (tool_id,))
                        row = cursor.fetchone()
                        if row:
                            a, b = _decayed_weights(row[2], row[3], row[4])
                            return a, b, int(row[2]), int(row[3])
            except Exception as e:
                print(f"Debug: Error getting local stats for {tool_id} ({category}): {e}")
            return 2.0, 2.0, 0, 0

        try:
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT alpha, beta, success_count, failure_count, last_updated FROM bayesian_weights WHERE tool_id = %s AND category = %s", (tool_id, category))
                    row = cur.fetchone()
                    if row:
                        a, b = _decayed_weights(row["success_count"], row["failure_count"], row["last_updated"])
                        return a, b, int(row["success_count"]), int(row["failure_count"])
                    elif category != 'global':
                        cur.execute("SELECT alpha, beta, success_count, failure_count, last_updated FROM bayesian_weights WHERE tool_id = %s AND category = 'global'", (tool_id,))
                        row = cur.fetchone()
                        if row:
                            a, b = _decayed_weights(row["success_count"], row["failure_count"], row["last_updated"])
                            return a, b, int(row["success_count"]), int(row["failure_count"])
        except Exception as e:
            print(f"Debug: Error getting remote stats for {tool_id} ({category}): {e}")
            # Fallback to local SQLite if remote query fails
            if self.local_conn:
                try:
                    with self._lock:
                        cursor = self.local_conn.cursor()
                        cursor.execute("SELECT alpha, beta, success_count, failure_count FROM intelligence WHERE tool_id = ? AND category = ?", (tool_id, category))
                        row = cursor.fetchone()
                        if row:
                            return float(row[0]), float(row[1]), int(row[2]), int(row[3])
                        elif category != 'global':
                            cursor.execute("SELECT alpha, beta, success_count, failure_count FROM intelligence WHERE tool_id = ? AND category = 'global'", (tool_id,))
                            row = cursor.fetchone()
                            if row:
                                return float(row[0]), float(row[1]), int(row[2]), int(row[3])
                except Exception as local_err:
                    print(f"Debug: Fallback to local stats also failed: {local_err}")
        return 2.0, 2.0, 0, 0

    def update_intelligence(self, tool_id: str, category: str, success: bool):
        """Updates weights in the remote store or local SQLite fallback."""
        self._ensure_db()
        # Clear the lru_cache to reflect new learning
        self.get_tool_stats.cache_clear()
        
        # In update_intelligence(), call get_tool_stats(tool_id, category=category).
        _, _, _, _ = self.get_tool_stats(tool_id, category=category)
        
        alpha_inc = 1.0 if success else 0.0
        beta_inc = 0.0 if success else 1.0
        s_inc = 1 if success else 0
        f_inc = 0 if success else 1
        timestamp = str(time.time())

        # Determine if we need to update category-specific row too
        category = category or 'global'

        if self.use_local and self.local_conn:
            try:
                with self._lock:
                    cursor = self.local_conn.cursor()
                    # 1. Update global row
                    cursor.execute('''
                        INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                        VALUES (?, 'global', ?, ?, ?, ?, ?)
                        ON CONFLICT(tool_id, category) DO UPDATE SET
                            alpha = alpha + ?,
                            beta = beta + ?,
                            success_count = success_count + ?,
                            failure_count = failure_count + ?,
                            timestamp = excluded.timestamp
                    ''', (tool_id, 2.0 + alpha_inc, 2.0 + beta_inc, s_inc, f_inc, timestamp, alpha_inc, beta_inc, s_inc, f_inc))
                    
                    # 2. Update category row if not global
                    if category != 'global':
                        cursor.execute('''
                            INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(tool_id, category) DO UPDATE SET
                                alpha = alpha + ?,
                                beta = beta + ?,
                                success_count = success_count + ?,
                                failure_count = failure_count + ?,
                                timestamp = excluded.timestamp
                        ''', (tool_id, category, 2.0 + alpha_inc, 2.0 + beta_inc, s_inc, f_inc, timestamp, alpha_inc, beta_inc, s_inc, f_inc))
                    self.local_conn.commit()
            except Exception as e:
                print(f"Debug: Error updating local stats for {tool_id}: {e}")
            finally:
                self.get_tool_stats.cache_clear()
            return

        # Remote update to PostgreSQL
        try:
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Update global row
                    cur.execute('''
                        INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count, last_updated)
                        VALUES (%s, 'global', %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (tool_id, category) DO UPDATE SET
                            alpha = bayesian_weights.alpha + EXCLUDED.alpha - 1.0,
                            beta = bayesian_weights.beta + EXCLUDED.beta - 1.0,
                            success_count = bayesian_weights.success_count + EXCLUDED.success_count,
                            failure_count = bayesian_weights.failure_count + EXCLUDED.failure_count,
                            last_updated = CURRENT_TIMESTAMP
                    ''', (tool_id, 1.0 + alpha_inc, 1.0 + beta_inc, s_inc, f_inc))
                    
                    # 2. Update category row if not global
                    if category != 'global':
                        cur.execute('''
                            INSERT INTO bayesian_weights (tool_id, category, alpha, beta, success_count, failure_count, last_updated)
                            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                            ON CONFLICT (tool_id, category) DO UPDATE SET
                                alpha = bayesian_weights.alpha + EXCLUDED.alpha - 1.0,
                                beta = bayesian_weights.beta + EXCLUDED.beta - 1.0,
                                success_count = bayesian_weights.success_count + EXCLUDED.success_count,
                                failure_count = bayesian_weights.failure_count + EXCLUDED.failure_count,
                                last_updated = CURRENT_TIMESTAMP
                        ''', (tool_id, category, 1.0 + alpha_inc, 1.0 + beta_inc, s_inc, f_inc))
                    conn.commit()
        except Exception as e:
            print(f"Debug: Error updating remote stats for {tool_id}: {e}")
            # Fallback to local SQLite update if remote fails
            if self.local_conn:
                try:
                    with self._lock:
                        cursor = self.local_conn.cursor()
                        # 1. Update global row
                        cursor.execute('''
                            INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                            VALUES (?, 'global', ?, ?, ?, ?, ?)
                            ON CONFLICT(tool_id, category) DO UPDATE SET
                                alpha = alpha + ?,
                                beta = beta + ?,
                                success_count = success_count + ?,
                                failure_count = failure_count + ?,
                                timestamp = excluded.timestamp
                        ''', (tool_id, 2.0 + alpha_inc, 2.0 + beta_inc, s_inc, f_inc, timestamp, alpha_inc, beta_inc, s_inc, f_inc))
                        
                        # 2. Update category row if not global
                        if category != 'global':
                            cursor.execute('''
                                INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(tool_id, category) DO UPDATE SET
                                    alpha = alpha + ?,
                                    beta = beta + ?,
                                    success_count = success_count + ?,
                                    failure_count = failure_count + ?,
                                    timestamp = excluded.timestamp
                            ''', (tool_id, category, 2.0 + alpha_inc, 2.0 + beta_inc, s_inc, f_inc, timestamp, alpha_inc, beta_inc, s_inc, f_inc))
                        self.local_conn.commit()
                except Exception as local_err:
                    print(f"Debug: Fallback local update also failed: {local_err}")
        finally:
            self.get_tool_stats.cache_clear()

    def get_all_stats(self):
        """Returns all tool stats with temporal decay applied (Bridge Version) using PostgreSQL or local SQLite."""
        self._ensure_db()
        results = []
        if self.use_local and self.local_conn:
            try:
                with self._lock:
                    cursor = self.local_conn.cursor()
                    cursor.execute("SELECT tool_id, category, alpha, beta, success_count, failure_count, timestamp FROM intelligence")
                    rows = cursor.fetchall()
                    for row in rows:
                        t_id, cat, alpha, beta, s, f, ts = row
                        d_alpha, d_beta = _decayed_weights(s, f, ts)
                        results.append({
                            "tool_id": t_id,
                            "category": cat or "General",
                            "alpha": round(d_alpha, 2),
                            "beta": round(d_beta, 2),
                            "success_count": s,
                            "failure_count": f,
                            "recency": round(_recency_factor(ts), 3),
                            "timestamp": ts
                        })
            except Exception as e:
                print(f"Error fetching local stats: {e}")
            return results

        try:
            from tools.memory.postgres_client import get_connection
            
            tool_data = {}
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT tool_id, category, alpha, beta, success_count, failure_count, last_updated FROM bayesian_weights")
                    for row in cur:
                        t_id = row["tool_id"]
                        cat = row["category"]
                        alpha = row["alpha"]
                        beta = row["beta"]
                        s = row["success_count"]
                        f = row["failure_count"]
                        ts = row["last_updated"]

                        # We have 'global' and specific categories. Prefer specific categories over 'global'.
                        if t_id not in tool_data or (cat != 'global' and tool_data[t_id]['category'] == 'global'):
                            d_alpha, d_beta = _decayed_weights(s, f, ts)
                            tool_data[t_id] = {
                                "tool_id": t_id,
                                "category": cat,
                                "alpha": round(d_alpha, 2),
                                "beta": round(d_beta, 2),
                                "success_count": int(s),
                                "failure_count": int(f),
                                "recency": round(_recency_factor(ts), 3),
                                "timestamp": str(ts)
                            }
            return list(tool_data.values())
        except Exception as e:
            print(f"Debug: Postgres fetch failed: {e}")
            # Fallback to local SQLite if remote fetch fails
            if self.local_conn:
                try:
                    with self._lock:
                        cursor = self.local_conn.cursor()
                        cursor.execute("SELECT tool_id, category, alpha, beta, success_count, failure_count, timestamp FROM intelligence")
                        rows = cursor.fetchall()
                        for row in rows:
                            t_id, cat, alpha, beta, s, f, ts = row
                            results.append({
                                "tool_id": t_id,
                                "category": cat or "General",
                                "alpha": round(float(alpha), 2),
                                "beta": round(float(beta), 2),
                                "success_count": s,
                                "failure_count": f,
                                "timestamp": ts
                            })
                except Exception as local_err:
                    print(f"Debug: Fallback local fetch also failed: {local_err}")
        
        return results

    def sample_strategy(self, tools: list):
        """Thompson Sampling using remote or local weights."""
        best_score = -1
        best_tool = None
        
        for tool_id in tools:
            alpha, beta, _, _ = self.get_tool_stats(tool_id)
            score = random.betavariate(alpha, beta)
            if score > best_score:
                best_score = score
                best_tool = tool_id
        
        return best_tool, best_score

    def get_tool_confidence(self, tool_id: str) -> float:
        """Returns the mean of the distribution (Success Probability)."""
        alpha, beta, _, _ = self.get_tool_stats(tool_id)
        if alpha + beta == 0:
            return 0.5
        return alpha / (alpha + beta)

    def get_avg_success_rate(self) -> float:
        """
        Aggregate success rate across all tools.
        Returns 0.0 if no tools are registered (No Data state).
        """
        stats = self.get_all_stats()
        if not stats:
            return 0.0
        
        valid_stats = [t["alpha"] / (t["alpha"] + t["beta"]) for t in stats if (t["alpha"] + t["beta"]) > 0]
        if not valid_stats:
            return 0.0
            
        return sum(valid_stats) / len(valid_stats)

    def get_system_load_telemetry(self) -> float:
        """
        Calculates a 'load' factor based on the number of active nodes and entropy.
        In a production version, this would query system metrics.
        """
        stats = self.get_all_stats()
        base_load = min(len(stats) * 0.5, 8.0) # Base load on tool count
        import random
        return round(base_load + random.uniform(0.1, 1.5), 2)

    def get_telemetry_pulse(self) -> TelemetryPulse:
        """
        Senior-Level Abstraction: Consolidates system health into a frozen TelemetryPulse.
        Ensures thread-safety via RLock and formal validation.
        """
        with self._lock:
            avg_success = self.get_avg_success_rate()
            current_load = self.get_system_load_telemetry()
            
            # Cold Start Handling: Default to COLD_START_PRIOR if no data
            display_accuracy = avg_success if avg_success > 0 else COLD_START_PRIOR
            
            # Calculate stability status
            status = PulseStatus.STABLE
            if avg_success < 0.4: status = PulseStatus.CRITICAL
            elif avg_success < 0.7: status = PulseStatus.WARNING
            
            return TelemetryPulse(
                accuracy=float(display_accuracy),
                load=float(current_load),
                status=status,
                timestamp=time.time()
            )

# Global Instance
governor = BayesianGovernor()
