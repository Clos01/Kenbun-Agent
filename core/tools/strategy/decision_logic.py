import json
import time
import logging
import math
import threading
import os
import tempfile
import shutil
import contextlib
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None


from core.tools.memory.chroma_db_connect import get_project_collection
from core.tools.strategy.keyword_processor import KeywordProcessor
from core.tools.strategy.neural_learner import NeuralLearner

from core.tools.infrastructure.config import settings

# --- CONFIGURATION ---
PROJECT_ROOT = settings.PROJECT_ROOT
LOG_DIR = settings.BRAIN_HEALTH_DIR
ROUTING_LOG = LOG_DIR / "routing_history.jsonl"


from core.tools.strategy.bandit_learning import ContextualModelBandit

class DecisionRouter:
    """
    System 4b: Decision Tree Router.
    Orchestrates keyword matching, neural learning, and semantic signal detection
    to determine the optimal execution path for a given task.
    """
    def __init__(self):
        self.processor = KeywordProcessor()
        self.learner = NeuralLearner(LOG_DIR)
        
        # Initialize weights and failures
        self.weights = self.learner.load_weights(
            list(self.processor.keywords.keys()), 
            self.processor.keywords
        )
        self.failures = self.learner.load_failures()
        self.recent_paths: List[str] = []
        self.bandit = ContextualModelBandit(LOG_DIR / "mab_stats.json")

    def save_weights(self):
        self.learner.save_weights(self.weights)

    def record_failure(self, task: str, wrong_path: str, correct_path: str):
        failure = self.learner.record_failure(task, wrong_path, correct_path)
        self.failures.append(failure)

    def _check_self_healing(self, task: str) -> Optional[str]:
        task_lower = task.lower()
        for failure in self.failures:
            if failure["task"].lower() in task_lower or task_lower in failure["task"].lower():
                return failure["correct_path"]
        return None

    def _get_semantic_signal(self, task: str) -> Dict[str, float]:
        try:
            collection = get_project_collection("history")
            if not collection or collection.count() == 0:
                return {}

            results = collection.query(
                query_texts=[task],
                n_results=5,
                where={"type": "routing_pattern"}
            )

            if not results["metadatas"] or not results["metadatas"][0]:
                return {}

            path_scores = {}
            for i, meta in enumerate(results["metadatas"][0]):
                path = meta.get("assigned_path")
                if not path: continue
                distance = results["distances"][0][i]
                score = max(0, 1.0 - (distance / 2.0))
                path_scores[path] = path_scores.get(path, 0) + score

            return path_scores
        except Exception as e:
            logging.error(f"Semantic signal failure: {e}")
            return {}

    def analyze_task(self, task: Optional[str]) -> Dict[str, Any]:
        if not task or not isinstance(task, str):
            return {"valid": False}

        matched = self.processor.match_categories(task)
        
        def get_confidence(cat_matches: List[str]) -> float:
            return sum(self.weights.get(k, 1.0) for k in cat_matches)

        features = {
            "ui_conf": get_confidence(matched["ui"]),
            "sec_conf": get_confidence(matched["security"]),
            "perf_conf": get_confidence(matched["performance"]),
            "bug_conf": get_confidence(matched["bug"]),
            "arch_conf": get_confidence(matched["architecture"]),
            "deep_code_conf": get_confidence(matched["deep_code"]),
            "noise_conf": get_confidence(matched["noise"]),
            "matched_all": [k for sublist in matched.values() for k in sublist],
            "is_complex": len(task.split()) > 20 or len(matched["architecture"]) > 0,
            "has_noise": len(matched["noise"]) > 0,
            "valid": True
        }
        return features

    def log_decision(self, task: str, features: Dict[str, Any], path: str):
        try:
            log_entry = {
                "timestamp": time.time(),
                "task": task,
                "features": features,
                "assigned_path": path,
                "version": "1.6"
            }
            with open(ROUTING_LOG, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logging.error(f"Failed to log routing decision: {e}")

    def get_strategy_path(self, task: str, fast_mode: bool = False) -> str:
        corrected_path = self._check_self_healing(task)
        if corrected_path:
            return corrected_path

        f = self.analyze_task(task)
        if not f.get("valid"):
            return "STANDARD_EXECUTION"

        semantic_scores = {}
        if not fast_mode:
            semantic_scores = self._get_semantic_signal(task)
        
        context_bias = {}
        if self.recent_paths:
            for p in set(self.recent_paths):
                count = self.recent_paths.count(p)
                context_bias[p] = (count / len(self.recent_paths)) * 2.0

        confs = {
            "SECURITY_HARDENING_PATH": f.get("sec_conf", 0) + semantic_scores.get("SECURITY_HARDENING_PATH", 0) + context_bias.get("SECURITY_HARDENING_PATH", 0),
            "UI_COMPONENT_BUILD": f.get("ui_conf", 0) + semantic_scores.get("UI_COMPONENT_BUILD", 0) + context_bias.get("UI_COMPONENT_BUILD", 0),
            "STANDARD_BUG_FIX": f.get("bug_conf", 0) + semantic_scores.get("STANDARD_BUG_FIX", 0) + context_bias.get("STANDARD_BUG_FIX", 0),
            "ARCHITECT_RESEARCH_PATH": max(f.get("arch_conf", 0), (f.get("perf_conf", 0) if f.get("is_complex") else 0)) + semantic_scores.get("ARCHITECT_RESEARCH_PATH", 0) + context_bias.get("ARCHITECT_RESEARCH_PATH", 0),
            "CLAUDE_CODE_PATH": f.get("deep_code_conf", 0) + semantic_scores.get("CLAUDE_CODE_PATH", 0) + context_bias.get("CLAUDE_CODE_PATH", 0),
        }

        noise_penalty = f.get("noise_conf", 0) * 10 
        confidence_floor = 1.2
        
        sorted_confs = sorted(confs.items(), key=lambda x: x[1], reverse=True)
        winner, win_score = sorted_confs[0]
        runner_up, runner_score = sorted_confs[1]

        # 1. NOISE GATING: If signal is weak, don't hallucinate a complex path
        if win_score < confidence_floor or win_score <= noise_penalty:
            print(f"⚠️ LOW CONFIDENCE ({win_score:.2f}). Defaulting to STANDARD_EXECUTION.")
            path = "STANDARD_EXECUTION"
            
        # 2. MULTI-PATH ENSEMBLE: If scores are close, return both
        elif (win_score / (runner_score + 0.1)) < 1.15 and runner_score > 1.0:
            print(f"🧬 DUAL SIGNAL DETECTED: {winner} + {runner_up}")
            path = f"{winner}|{runner_up}" # Pipe-delimited ensemble
            
        # 3. SINGLE WINNER
        elif runner_score == 0 or (win_score / (runner_score + 0.1)) >= 1.15 or winner == "ARCHITECT_RESEARCH_PATH":
            if winner == "UI_COMPONENT_BUILD" and (f.get("bug_conf", 0) > 0 or semantic_scores.get("UI_FIX_PATH", 0) > 0):
                path = "UI_FIX_PATH"
            else:
                path = winner
        else:
            path = "STANDARD_EXECUTION"

        if not fast_mode and path != "STANDARD_EXECUTION":
            self.recent_paths.append(path)
            if len(self.recent_paths) > 5:
                self.recent_paths.pop(0)
            self.learner.apply_feedback(self.weights, f.get("matched_all", []))

        if not fast_mode:
            self.log_decision(task, f, path)
            
        return path

    def get_task_context(self, task: str) -> str:
        f = self.analyze_task(task)
        words = len(task.split())
        
        # Consider a task COMPLEX if security or architecture is detected, or if general features are complex or long
        if (f.get("sec_conf", 0.0) > 0.0 or 
            f.get("arch_conf", 0.0) > 0.0 or 
            f.get("is_complex") or
            words > 30):
            return "COMPLEX"
        return "SIMPLE"

    def recommend_model(self, task: str) -> str:
        context = self.get_task_context(task)
        recommended = self.bandit.select_arm(context)
        print(f"🎯 [BANDIT] Context: {context} | Recommended Model: {recommended}")
        return recommended

    def record_model_feedback(self, model: str, task: str, success: bool, latency: float, cost: float):
        model_key = model
        valid_arms = [
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.1-flash-lite-preview",
            "local"
        ]
        # Normalise common model names to our active arm keys
        if model_key not in valid_arms:
            if "3.5" in model_key and "flash" in model_key.lower():
                model_key = "gemini-3.5-flash"
            elif "lite" in model_key.lower():
                if "preview" in model_key.lower():
                    model_key = "gemini-3.1-flash-lite-preview"
                else:
                    model_key = "gemini-3.1-flash-lite"
            elif "pro" in model_key.lower():
                model_key = "gemini-3.1-pro-preview"
            elif "flash" in model_key.lower():
                model_key = "gemini-3-flash-preview"
            else:
                model_key = "local"

        context = self.get_task_context(task)
        self.bandit.record_feedback(context, model_key, success, latency, cost)
        print(f"📊 [BANDIT FEEDBACK] Model: {model_key} | Success: {success} | Latency: {latency:.3f}s | Cost: ${cost:.6f} | Context: {context}")

    def recommend_tools(self, task: str) -> List[str]:
        path = self.get_strategy_path(task)
        recommendations = {
            "UI_FIX_PATH": ["ask_ui_expert", "save_checkpoint", "run_code_safely"],
            "SECURITY_HARDENING_PATH": ["consult_supervisor", "review_code_with_gemini", "research_official_docs"],
            "STANDARD_BUG_FIX": ["recall_fix", "scan_repo", "save_checkpoint", "run_code_safely"],
            "ARCHITECT_RESEARCH_PATH": ["research_with_gemini", "ask_architect", "consult_supervisor"],
            "UI_COMPONENT_BUILD": ["research_official_docs", "ask_ui_expert", "run_code_safely"],
            "STANDARD_EXECUTION": ["research_with_gemini", "scan_repo", "consult_supervisor"]
        }
        return recommendations.get(path, recommendations["STANDARD_EXECUTION"])

# Global Instance
router = DecisionRouter()
