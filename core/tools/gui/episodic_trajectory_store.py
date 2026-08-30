"""
Episodic Trajectory Store for GUI Automation (Kenbun Motor Cortex).
Stores and replays verified State-Action Graph trajectories using 64-bit perceptual hashing.
Enables sub-50ms instant execution for recurring workflows on known dashboards.
"""

from __future__ import annotations

import os
import sqlite3
import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image

logger = logging.getLogger("tools.gui.trajectory_store")

def _resolve_default_db_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if "core" in current_dir:
        repo_root = current_dir.split("core")[0]
        db_path = os.path.join(repo_root, "data", "trajectories.db")
    else:
        user_home = os.path.expanduser("~")
        db_path = os.path.join(user_home, ".kenbun", "data", "trajectories.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path

DEFAULT_DB_PATH = _resolve_default_db_path()


class EpisodicTrajectoryStore:
    """SQLite-backed episodic memory for UI-TARS action trajectories."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Initializes the trajectories table and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trajectories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_name TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    state_hash TEXT NOT NULL,
                    directive TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    success_count INTEGER DEFAULT 1,
                    last_used REAL NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_traj_workflow_hash 
                ON trajectories (workflow_name, state_hash);
            """)
            conn.commit()

    @staticmethod
    def compute_perceptual_hash(image: Image.Image) -> str:
        """
        Computes a robust 64-bit perceptual gradient hash (dHash) from an image.
        Resizes to 9x8 grayscale, compares adjacent horizontal pixels.
        Returns a 16-character hexadecimal string.
        """
        # Resize to 9x8 (72 pixels) for 8x8=64 difference bits
        resized = image.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
        pixels = list(resized.getdata())
        
        diff = []
        for row in range(8):
            for col in range(8):
                idx = row * 9 + col
                left_pixel = pixels[idx]
                right_pixel = pixels[idx + 1]
                diff.append(1 if left_pixel > right_pixel else 0)
                
        # Convert 64 bits to 16 hex characters
        decimal_val = 0
        for bit in diff:
            decimal_val = (decimal_val << 1) | bit
        return f"{decimal_val:016x}"

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """Computes Hamming bit distance between two 16-character hex hashes."""
        if len(hash1) != 16 or len(hash2) != 16:
            # Fallback for different length strings
            val1 = int(hash1, 16) if hash1 else 0
            val2 = int(hash2, 16) if hash2 else 0
        else:
            val1 = int(hash1, 16)
            val2 = int(hash2, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count("1")

    def record_step(
        self,
        workflow_name: str,
        step_index: int,
        state_hash: str,
        directive: str,
        action: Dict[str, Any],
        confidence: float = 1.0
    ):
        """Records a successful state-action transition into the trajectory graph."""
        now = time.time()
        action_json = json.dumps(action)
        norm_dir = directive.strip().lower()

        with self._get_connection() as conn:
            # Check if exact match already exists
            cur = conn.cursor()
            cur.execute("""
                SELECT id, success_count FROM trajectories 
                WHERE workflow_name = ? AND state_hash = ? AND lower(directive) = ?
            """, (workflow_name, state_hash, norm_dir))
            row = cur.fetchone()

            if row:
                traj_id, succ_count = row
                conn.execute("""
                    UPDATE trajectories 
                    SET success_count = ?, last_used = ?, action_json = ?, confidence = ?
                    WHERE id = ?
                """, (succ_count + 1, now, action_json, max(confidence, 0.9), traj_id))
            else:
                conn.execute("""
                    INSERT INTO trajectories (
                        workflow_name, step_index, state_hash, directive, 
                        action_json, confidence, success_count, last_used, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (workflow_name, step_index, state_hash, directive.strip(), action_json, confidence, now, now))
            conn.commit()

    def lookup_cached_action(
        self,
        workflow_name: str,
        state_hash: str,
        directive: str,
        max_hamming_dist: int = 4
    ) -> Optional[Dict[str, Any]]:
        """
        Fuzzy-matches current screen state against stored trajectory nodes.
        Returns cached action dict if within Hamming distance threshold.
        """
        norm_dir = directive.strip().lower()
        now = time.time()

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, state_hash, action_json, success_count, confidence 
                FROM trajectories 
                WHERE workflow_name = ? AND lower(directive) = ?
                ORDER BY success_count DESC, last_used DESC
            """, (workflow_name, norm_dir))
            rows = cur.fetchall()

            for traj_id, stored_hash, action_json, succ_count, conf in rows:
                dist = self.hamming_distance(state_hash, stored_hash)
                if dist <= max_hamming_dist:
                    # Update usage telemetry
                    conn.execute("""
                        UPDATE trajectories SET last_used = ? WHERE id = ?
                    """, (now, traj_id))
                    conn.commit()

                    try:
                        action_dict = json.loads(action_json)
                        action_dict["_cache_hit"] = True
                        action_dict["_hamming_dist"] = dist
                        action_dict["_confidence"] = conf
                        return action_dict
                    except Exception as e:
                        logger.warning(f"Failed to decode cached action JSON: {e}")
                        return None

        return None

    def clear_workflow(self, workflow_name: str):
        """Prunes all cached trajectories for a given workflow."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM trajectories WHERE workflow_name = ?", (workflow_name,))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Returns overview statistics of cached trajectories."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), COUNT(DISTINCT workflow_name) FROM trajectories")
            total_records, total_workflows = cur.fetchone()
            return {
                "total_cached_steps": total_records,
                "total_workflows": total_workflows,
                "db_path": self.db_path
            }
