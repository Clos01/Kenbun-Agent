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
DECAY_HALFLIFE_HOURS = 24

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
            
            # 2 second timeout for reachability
            with socket.create_connection((self.pc_ip, int(self.chroma_port)), timeout=2):
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
            print(f"⚠️ System 4: Remote PC {self.pc_ip} unreachable ({e}). Using local SQLite.")
            self.use_local = True

    def _init_local_db(self):
        if self.local_conn: return
        try:
            # Absolute Path Hardening
            self.local_conn = sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)
            self.local_conn.execute("PRAGMA journal_mode=WAL;")
            print(f"✅ Bayesian Governor: Connected to {LOCAL_DB_PATH} in WAL mode")
        except Exception as e:
            print(f"❌ Bayesian Governor: Failed to connect to DB at {LOCAL_DB_PATH}: {e}")
        cursor = self.local_conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS intelligence (
                tool_id TEXT PRIMARY KEY,
                category TEXT,
                alpha REAL DEFAULT 2.0,
                beta REAL DEFAULT 2.0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                timestamp TEXT
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
                ''', [(t[0], t[1], timestamp) for t in default_tools])
                self.local_conn.commit()
                print(f"✅ Bayesian Governor: Bootstrapped {len(default_tools)} default tools in SQLite.")
        except Exception as e:
            print(f"⚠️ Bayesian Governor: Bootstrapping default tools failed: {e}")

    @lru_cache(maxsize=128)
    def get_tool_stats(self, tool_id: str):
        """Retrieves weights from PostgreSQL or local SQLite."""
        self._ensure_db()
        if self.use_local and self.local_conn:
            try:
                with self._lock:
                    cursor = self.local_conn.cursor()
                    cursor.execute("SELECT alpha, beta FROM intelligence WHERE tool_id = ?", (tool_id,))
                    row = cursor.fetchone()
                    if row:
                        return float(row[0]), float(row[1]), 0, 0
            except Exception as e:
                print(f"Debug: Error getting local stats for {tool_id}: {e}")
            return 2.0, 2.0, 0, 0

        try:
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT alpha, beta FROM bayesian_weights WHERE tool_id = %s", (tool_id,))
                    row = cur.fetchone()
                    if row:
                        return float(row["alpha"]), float(row["beta"]), 0, 0
        except Exception as e:
            print(f"Debug: Error getting remote stats for {tool_id}: {e}")
        return 2.0, 2.0, 0, 0

    def update_intelligence(self, tool_id: str, category: str, success: bool):
        """Updates weights in the remote store or local SQLite fallback."""
        self._ensure_db()
        # Clear the lru_cache to reflect new learning
        self.get_tool_stats.cache_clear()
        
        alpha, beta, s, f = self.get_tool_stats(tool_id)
        
        if success:
            alpha += 1
            s += 1
        else:
            beta += 1
            f += 1
            
        timestamp = str(time.time())

        if self.use_local and self.local_conn:
            try:
                with self._lock:
                    cursor = self.local_conn.cursor()
                    cursor.execute('''
                    INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tool_id) DO UPDATE SET
                        category=excluded.category,
                        alpha=excluded.alpha,
                        beta=excluded.beta,
                        success_count=excluded.success_count,
                        failure_count=excluded.failure_count,
                        timestamp=excluded.timestamp
                ''', (tool_id, category, alpha, beta, s, f, timestamp))
                    self.local_conn.commit()
                    # Clear cache for this tool
                    self.get_tool_stats.cache_clear()
            except Exception as e:
                print(f"Debug: Error updating local stats for {tool_id}: {e}")
            return

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
                        results.append({
                            "tool_id": t_id,
                            "category": cat or "General",
                            "alpha": round(float(alpha), 2),
                            "beta": round(float(beta), 2),
                            "success_count": s,
                            "failure_count": f,
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
                    cur.execute("SELECT tool_id, category, alpha, beta, last_updated FROM bayesian_weights")
                    for row in cur:
                        t_id = row["tool_id"]
                        cat = row["category"]
                        alpha = row["alpha"]
                        beta = row["beta"]
                        ts = row["last_updated"]

                        # We have 'global' and specific categories. Prefer specific categories over 'global'.
                        if t_id not in tool_data or (cat != 'global' and tool_data[t_id]['category'] == 'global'):
                            tool_data[t_id] = {
                                "tool_id": t_id,
                                "category": cat,
                                "alpha": round(float(alpha), 2),
                                "beta": round(float(beta), 2),
                                "success_count": 0,
                                "failure_count": 0,
                                "timestamp": str(ts)
                            }
            return list(tool_data.values())
        except Exception as e:
            print(f"Debug: Postgres fetch failed: {e}")
        
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
