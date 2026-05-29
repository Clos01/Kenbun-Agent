import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

class NeuralLearner:
    """
    Handles Alpha-Go reward/decay weights and self-healing failure logs.
    """
    MAX_WEIGHT = 15.0

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.weight_file = log_dir / "keyword_weights.json"
        self.failure_log = log_dir / "routing_failures.jsonl"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def load_weights(self, categories: List[str], keywords: Dict[str, List[str]]) -> Dict[str, float]:
        if self.weight_file.exists():
            try:
                with open(self.weight_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        
        initial_weights = {}
        for cat in categories:
            for k in keywords.get(cat, []):
                initial_weights[k] = 1.0
        return initial_weights

    def save_weights(self, weights: Dict[str, float]):
        try:
            with open(self.weight_file, "w") as f:
                json.dump(weights, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save weights: {e}")

    def apply_feedback(self, weights: Dict[str, float], matched_keywords: List[str]):
        # Decay all active keywords slightly to prevent permanent gravity wells
        decay_rate = 0.005
        for k in weights:
            if weights[k] > 1.0:
                weights[k] = round(max(weights[k] - decay_rate, 1.0), 4)

        # Reward matched keywords
        for k in matched_keywords:
            current = weights.get(k, 1.0)
            weights[k] = round(min(current + 0.01 + decay_rate, self.MAX_WEIGHT), 4)
            
        self.save_weights(weights)

    def load_failures(self) -> List[Dict[str, Any]]:
        failures = []
        if self.failure_log.exists():
            try:
                with open(self.failure_log, "r") as f:
                    for line in f:
                        failures.append(json.loads(line))
            except Exception:
                pass
        return failures

    def record_failure(self, task: str, wrong_path: str, correct_path: str):
        failure_entry = {
            "timestamp": time.time(),
            "task": task,
            "wrong_path": wrong_path,
            "correct_path": correct_path
        }
        try:
            with open(self.failure_log, "a") as f:
                f.write(json.dumps(failure_entry) + "\n")
        except Exception as e:
            logging.error(f"Failed to record routing failure: {e}")
        return failure_entry
