import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any
from tools.memory.postgres_client import get_connection

class NeuralLearner:
    """
    Handles Alpha-Go reward/decay weights and self-healing failure logs via PostgreSQL.
    """
    MAX_WEIGHT = 15.0

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        # Left for backward compatibility if any legacy code checks these paths
        self.weight_file = log_dir / "keyword_weights.json"
        self.failure_log = log_dir / "routing_failures.jsonl"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def load_weights(self, categories: List[str], keywords: Dict[str, List[str]]) -> Dict[str, float]:
        weights = {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT keyword, weight FROM keyword_weights")
                    for row in cur:
                        weights[row["keyword"]] = row["weight"]
        except Exception as e:
            logging.error(f"Failed to load keyword weights from DB: {e}")

        # Ensure defaults exist
        for cat in categories:
            for k in keywords.get(cat, []):
                if k not in weights:
                    weights[k] = 1.0
        return weights

    def save_weights(self, weights: Dict[str, float]):
        # This function is kept for structural compatibility but logic is moved to apply_feedback to be atomic.
        pass

    def apply_feedback(self, weights: Dict[str, float], matched_keywords: List[str]):
        decay_rate = 0.005
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Decay all existing weights that are > 1.0
                    cur.execute("""
                        UPDATE keyword_weights
                        SET weight = GREATEST(weight - %s, 1.0),
                            last_updated = CURRENT_TIMESTAMP
                        WHERE weight > 1.0
                    """, (decay_rate,))
                    
                    # 2. Reward matched keywords (upsert)
                    for k in matched_keywords:
                        cur.execute("""
                            INSERT INTO keyword_weights (keyword, weight)
                            VALUES (%s, 1.01 + %s)
                            ON CONFLICT (keyword) DO UPDATE 
                            SET weight = LEAST(keyword_weights.weight + 0.01 + %s, %s),
                                last_updated = CURRENT_TIMESTAMP
                        """, (k, decay_rate, decay_rate, self.MAX_WEIGHT))
                conn.commit()
        except Exception as e:
            logging.error(f"Failed to apply feedback to DB: {e}")

    def load_failures(self) -> List[Dict[str, Any]]:
        failures = []
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT created_at, task, wrong_path, correct_path FROM routing_failures")
                    for row in cur:
                        # Convert datetime to timestamp float for compatibility
                        failures.append({
                            "timestamp": row["created_at"].timestamp() if hasattr(row["created_at"], "timestamp") else row["created_at"],
                            "task": row["task"],
                            "wrong_path": row["wrong_path"],
                            "correct_path": row["correct_path"]
                        })
        except Exception as e:
            logging.error(f"Failed to load failures from DB: {e}")
        return failures

    def record_failure(self, task: str, wrong_path: str, correct_path: str):
        failure_entry = {
            "timestamp": time.time(),
            "task": task,
            "wrong_path": wrong_path,
            "correct_path": correct_path
        }
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO routing_failures (task, wrong_path, correct_path)
                        VALUES (%s, %s, %s)
                    """, (task, wrong_path, correct_path))
                conn.commit()
        except Exception as e:
            logging.error(f"Failed to record routing failure to DB: {e}")
        return failure_entry
