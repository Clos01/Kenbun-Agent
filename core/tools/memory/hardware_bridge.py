import os
import sys
import logging
import sqlite3
import json
import time
import subprocess
import platform
from typing import Optional, Dict, Any, List
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

# Fallback SQLite Database Path
LOCAL_DB_PATH = settings.INTELLIGENCE_DB_PATH

class HardwareBridge:
    def __init__(self):
        self._capabilities = None
        self._sqlite_conn = None

    def detect_capabilities(self) -> Dict[str, Any]:
        """Detects hardware capabilities (GPU, RAM) and service availability."""
        if self._capabilities is not None:
            return self._capabilities

        caps = {
            "gpu_available": False,
            "gpu_device": "CPU",
            "ram_gb": 8.0,
            "has_chroma": False,
            "has_postgres": False,
            "tier": "edge"
        }

        # 1. Detect GPU
        system = platform.system().lower()
        if "darwin" in system:
            # Check Apple Silicon
            try:
                res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
                if "apple" in res.stdout.lower():
                    caps["gpu_available"] = True
                    caps["gpu_device"] = "Apple Silicon Unified Memory"
            except Exception:
                pass
        else:
            # Linux / Windows: check for nvidia-smi
            try:
                subprocess.run(["nvidia-smi"], capture_output=True, check=True)
                caps["gpu_available"] = True
                caps["gpu_device"] = "NVIDIA CUDA"
            except Exception:
                pass

        # 2. Detect RAM
        try:
            if "darwin" in system:
                res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
                caps["ram_gb"] = float(res.stdout.strip()) / (1024**3)
            elif "linux" in system:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if "MemTotal" in line:
                            kb = int(line.split()[1])
                            caps["ram_gb"] = kb / (1024**2)
                            break
        except Exception:
            pass

        # 3. Check ChromaDB availability
        try:
            from tools.memory.honcho_connect import get_chroma_client
            chroma = get_chroma_client()
            if chroma:
                caps["has_chroma"] = True
        except Exception:
            pass

        # 4. Check PostgreSQL availability
        try:
            from tools.memory.postgres_client import get_connection
            with get_connection() as conn:
                caps["has_postgres"] = True
        except Exception:
            pass

        # Determine Tier
        if caps["gpu_available"] and caps["ram_gb"] >= 16.0 and caps["has_postgres"] and caps["has_chroma"]:
            caps["tier"] = "heavy"
        elif caps["ram_gb"] >= 8.0:
            caps["tier"] = "standard"
        else:
            caps["tier"] = "edge"

        self._capabilities = caps
        logger.info(f"💻 Hardware Bridge Detected: {caps}")
        return caps

    def get_sqlite_conn(self):
        if self._sqlite_conn is None:
            try:
                # Ensure the parent directory exists
                LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                self._sqlite_conn = sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)
                self._sqlite_conn.execute("PRAGMA journal_mode=WAL;")
                # Initialize SQLite fallback tables
                cursor = self._sqlite_conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_evaluations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        prompt_hash TEXT NOT NULL,
                        score REAL NOT NULL DEFAULT 0.0,
                        speed_sec REAL,
                        token_cost REAL,
                        compliance_score REAL,
                        eval_feedback TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_prompts (
                        prompt_hash TEXT PRIMARY KEY,
                        agent_id TEXT NOT NULL,
                        system_prompt TEXT NOT NULL,
                        meta_data TEXT NOT NULL DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                self._sqlite_conn.commit()
            except Exception as e:
                logger.error(f"❌ Failed to connect/init SQLite fallback DB: {e}")
        return self._sqlite_conn

    def save_evaluation(self, eval_data: Dict[str, Any]) -> bool:
        """Saves agent performance metrics to Postgres (if available) or SQLite (fallback)."""
        caps = self.detect_capabilities()
        if caps["has_postgres"]:
            try:
                from tools.memory.postgres_client import get_connection
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO agent_evaluations (
                                agent_id, task_id, run_id, prompt_hash, score, speed_sec, token_cost, compliance_score, eval_feedback
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            eval_data["agent_id"],
                            eval_data["task_id"],
                            eval_data["run_id"],
                            eval_data["prompt_hash"],
                            eval_data["score"],
                            eval_data.get("speed_sec"),
                            eval_data.get("token_cost"),
                            eval_data.get("compliance_score"),
                            eval_data.get("eval_feedback")
                        ))
                        conn.commit()
                return True
            except Exception as e:
                logger.warning(f"⚠️ Postgres save failed, falling back to SQLite: {e}")
        
        # SQLite Fallback
        try:
            conn = self.get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_evaluations (
                    agent_id, task_id, run_id, prompt_hash, score, speed_sec, token_cost, compliance_score, eval_feedback
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                eval_data["agent_id"],
                eval_data["task_id"],
                eval_data["run_id"],
                eval_data["prompt_hash"],
                eval_data["score"],
                eval_data.get("speed_sec"),
                eval_data.get("token_cost"),
                eval_data.get("compliance_score"),
                eval_data.get("eval_feedback")
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ SQLite save failed: {e}")
            return False

    def get_evaluations(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves history of evaluations for a specific agent."""
        caps = self.detect_capabilities()
        if caps["has_postgres"]:
            try:
                from tools.memory.postgres_client import get_connection
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id, agent_id, task_id, run_id, prompt_hash, score, speed_sec, token_cost, compliance_score, eval_feedback, created_at
                            FROM agent_evaluations
                            WHERE agent_id = %s
                            ORDER BY created_at DESC
                            LIMIT %s
                        """, (agent_id, limit))
                        cols = ["id", "agent_id", "task_id", "run_id", "prompt_hash", "score", "speed_sec", "token_cost", "compliance_score", "eval_feedback", "created_at"]
                        return [dict(zip(cols, row)) for row in cur.fetchall()]
            except Exception as e:
                logger.warning(f"⚠️ Postgres read failed, falling back to SQLite: {e}")

        # SQLite Fallback
        try:
            conn = self.get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, agent_id, task_id, run_id, prompt_hash, score, speed_sec, token_cost, compliance_score, eval_feedback, created_at
                FROM agent_evaluations
                WHERE agent_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (agent_id, limit))
            cols = ["id", "agent_id", "task_id", "run_id", "prompt_hash", "score", "speed_sec", "token_cost", "compliance_score", "eval_feedback", "created_at"]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"❌ SQLite read failed: {e}")
            return []

    def save_prompt(self, prompt_hash: str, agent_id: str, system_prompt: str, meta_data: Dict[str, Any]) -> bool:
        """Saves an optimized system prompt to the DB."""
        caps = self.detect_capabilities()
        meta_json = json.dumps(meta_data)
        if caps["has_postgres"]:
            try:
                from tools.memory.postgres_client import get_connection
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO agent_prompts (prompt_hash, agent_id, system_prompt, meta_data)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (prompt_hash) DO UPDATE
                            SET system_prompt = EXCLUDED.system_prompt, meta_data = EXCLUDED.meta_data
                        """, (prompt_hash, agent_id, system_prompt, meta_json))
                        conn.commit()
                return True
            except Exception as e:
                logger.warning(f"⚠️ Postgres save prompt failed, falling back to SQLite: {e}")

        # SQLite Fallback
        try:
            conn = self.get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_prompts (prompt_hash, agent_id, system_prompt, meta_data)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(prompt_hash) DO UPDATE SET
                    system_prompt=excluded.system_prompt,
                    meta_data=excluded.meta_data
            """, (prompt_hash, agent_id, system_prompt, meta_json))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ SQLite save prompt failed: {e}")
            return False

    def get_prompt(self, prompt_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific prompt by hash."""
        caps = self.detect_capabilities()
        if caps["has_postgres"]:
            try:
                from tools.memory.postgres_client import get_connection
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT prompt_hash, agent_id, system_prompt, meta_data, created_at
                            FROM agent_prompts
                            WHERE prompt_hash = %s
                        """, (prompt_hash,))
                        row = cur.fetchone()
                        if row:
                            return {
                                "prompt_hash": row[0],
                                "agent_id": row[1],
                                "system_prompt": row[2],
                                "meta_data": row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                                "created_at": row[4]
                            }
            except Exception as e:
                logger.warning(f"⚠️ Postgres read prompt failed, falling back to SQLite: {e}")

        # SQLite Fallback
        try:
            conn = self.get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prompt_hash, agent_id, system_prompt, meta_data, created_at
                FROM agent_prompts
                WHERE prompt_hash = ?
            """, (prompt_hash,))
            row = cursor.fetchone()
            if row:
                return {
                    "prompt_hash": row[0],
                    "agent_id": row[1],
                    "system_prompt": row[2],
                    "meta_data": json.loads(row[3]),
                    "created_at": row[4]
                }
        except Exception as e:
            logger.error(f"❌ SQLite read prompt failed: {e}")
        return None

    def get_latest_prompt(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Gets the most recently optimized prompt for a target agent."""
        caps = self.detect_capabilities()
        if caps["has_postgres"]:
            try:
                from tools.memory.postgres_client import get_connection
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT prompt_hash, agent_id, system_prompt, meta_data, created_at
                            FROM agent_prompts
                            WHERE agent_id = %s
                            ORDER BY created_at DESC
                            LIMIT 1
                        """, (agent_id,))
                        row = cur.fetchone()
                        if row:
                            return {
                                "prompt_hash": row[0],
                                "agent_id": row[1],
                                "system_prompt": row[2],
                                "meta_data": row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                                "created_at": row[4]
                            }
            except Exception as e:
                logger.warning(f"⚠️ Postgres read latest prompt failed, falling back to SQLite: {e}")

        # SQLite Fallback
        try:
            conn = self.get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prompt_hash, agent_id, system_prompt, meta_data, created_at
                FROM agent_prompts
                WHERE agent_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (agent_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "prompt_hash": row[0],
                    "agent_id": row[1],
                    "system_prompt": row[2],
                    "meta_data": json.loads(row[3]),
                    "created_at": row[4]
                }
        except Exception as e:
            logger.error(f"❌ SQLite read latest prompt failed: {e}")
        return None

# Singleton Instance
hardware_bridge = HardwareBridge()
