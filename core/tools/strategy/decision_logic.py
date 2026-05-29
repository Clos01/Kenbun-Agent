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
from typing import List, Dict, Any, Optional, Set
from functools import lru_cache

try:
    import fcntl
except ImportError:
    fcntl = None

from tools.utils.path_utils import get_project_root
from tools.memory.chroma_db_connect import get_project_collection
from tools.strategy.keyword_processor import KeywordProcessor
from tools.strategy.neural_learner import NeuralLearner

from tools.infrastructure.config import settings

# --- CONFIGURATION ---
PROJECT_ROOT = settings.PROJECT_ROOT
LOG_DIR = settings.BRAIN_HEALTH_DIR
ROUTING_LOG = LOG_DIR / "routing_history.jsonl"

class ContextualModelBandit:
    """
    Contextual Multi-Armed Bandit using UCB1 Action Selection.
    Learns to dynamically route between models (Lite, Flash, Pro, Local)
    based on cost, latency, and success rewards under SIMPLE and COMPLEX contexts.
    
    Thread-safe, process-safe, cached with mtime-validation, and atomically written to disk
    to scale reliably under high-concurrency systems.
    """
    def __init__(self, stats_path: Path):
        self.stats_path = stats_path
        self.exploration_constant = 1.5
        self.max_cost = 0.05      # Scale cost normalization
        self.max_latency = 10.0   # Scale latency normalization
        
        # Mathematically bounded rewards: sum of weights = 1.0 (rewards strictly in [0, 1])
        self.w_success = 0.2
        self.w_cost = 0.5
        self.w_latency = 0.3
        self.penalty = 0.0        # Reward penalty for failure clamped to 0.0
        self.models = [
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.1-flash-lite-preview",
            "local"
        ]
        self._lock = threading.Lock()
        self._stats = None  # Lazily loaded on demand
        
        # Cache metadata to completely bypass disk I/O under high traffic
        self._last_loaded_mtime = 0.0
        self._last_loaded_size = 0

        # Race-free startup initialization: serialize first-time creation under locks
        with self._lock_state():
            self._ensure_stats_exist_unlocked()

    @contextlib.contextmanager
    def _lock_state(self):
        """Cross-process and cross-thread lock for MAB stats R/W safety."""
        # 1. Acquire thread-level lock first
        with self._lock:
            # 2. Acquire process-level flock
            lock_path = self.stats_path.with_suffix(".lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            
            lock_file = None
            try:
                # Open with "a" to prevent file truncation
                lock_file = open(lock_path, "a")
                if fcntl:
                    try:
                        fcntl.flock(lock_file, fcntl.LOCK_EX)
                    except IOError as e:
                        # Fail-closed: raise exception to prevent concurrent corrupting writes
                        raise RuntimeError(f"Could not acquire cross-process lock on {lock_path}: {e}")
                else:
                    logging.warning("Cross-process lock (fcntl) is not available on this platform. Thread lock active.")
                
                yield
                
            finally:
                if lock_file:
                    if fcntl:
                        try:
                            fcntl.flock(lock_file, fcntl.LOCK_UN)
                        except Exception:
                            pass
                    try:
                        lock_file.close()
                    except Exception:
                        pass

    def _load_or_ensure_stats_locked(self) -> Dict[str, Any]:
        """Lazy-loads MAB stats from disk only if changed, otherwise returns the in-memory cache."""
        self._ensure_stats_exist_unlocked()
        
        # Cache Invalidation check using file metadata (mtime & size)
        try:
            mtime = os.path.getmtime(self.stats_path)
            size = os.path.getsize(self.stats_path)
        except Exception:
            mtime = 0.0
            size = 0
            
        if self._stats is None or mtime > self._last_loaded_mtime or size != self._last_loaded_size:
            self._stats = self._load_stats_from_disk_unlocked()
            self._last_loaded_mtime = mtime
            self._last_loaded_size = size
            
        return self._stats

    def _ensure_stats_exist_unlocked(self):
        """Create the stats file if it doesn't exist, or dynamically reconcile missing models with backup recovery."""
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        
        default_stats = {
            "total_selections": 0,
            "contexts": {
                "SIMPLE": {"total_selections": 0, "arms": {}},
                "COMPLEX": {"total_selections": 0, "arms": {}}
            }
        }
        
        for ctx in ["SIMPLE", "COMPLEX"]:
            for model in self.models:
                default_stats["contexts"][ctx]["arms"][model] = {
                    "selections": 0,
                    "successes": 0,
                    "total_latency": 0.0,
                    "total_cost": 0.0,
                    "average_reward": 0.0
                }
        
        if not self.stats_path.exists():
            self._save_stats_to_disk_atomic_unlocked(default_stats)
        else:
            # Reconcile existing file: ensure all contexts and models exist
            try:
                with open(self.stats_path, "r") as f:
                    stats = json.load(f)
                self._reconcile_stats_schema(stats, default_stats)
            except Exception as e:
                logging.error(f"MAB stats file corrupted or unreadable: {e}. Attempting self-healing recovery...")
                
                # Try to restore from backup if one exists and is valid
                bak_path = self.stats_path.with_suffix(".bak")
                restored = False
                if bak_path.exists():
                    try:
                        with open(bak_path, "r") as f:
                            stats = json.load(f)
                        self._reconcile_stats_schema(stats, default_stats)
                        self._save_stats_to_disk_atomic_unlocked(stats)
                        logging.info("Successfully self-healed and restored MAB stats from backup file.")
                        restored = True
                    except Exception as bak_err:
                        logging.error(f"Backup file is also corrupted or unreadable: {bak_err}")
                
                if not restored:
                    # Create a backup of the corrupted file for developer inspection before overwriting
                    try:
                        shutil.copy(self.stats_path, bak_path)
                        logging.info(f"Corrupted MAB stats archived to backup file: {bak_path}")
                    except Exception as arch_err:
                        logging.error(f"Failed to archive corrupted MAB stats: {arch_err}")
                    
                    # Reset to default
                    self._save_stats_to_disk_atomic_unlocked(default_stats)
                    logging.info("MAB stats reset to default due to unrecoverable file corruption.")

    def _reconcile_stats_schema(self, stats: Dict[str, Any], default_stats: Dict[str, Any]):
        """Helper to reconcile the stats schema to guarantee all expected models and contexts exist."""
        modified = False
        if "total_selections" not in stats:
            stats["total_selections"] = 0
            modified = True
        if "contexts" not in stats:
            stats["contexts"] = default_stats["contexts"]
            modified = True
        
        for ctx in ["SIMPLE", "COMPLEX"]:
            if ctx not in stats["contexts"]:
                stats["contexts"][ctx] = {"total_selections": 0, "arms": {}}
                modified = True
            if "total_selections" not in stats["contexts"][ctx]:
                stats["contexts"][ctx]["total_selections"] = 0
                modified = True
            if "arms" not in stats["contexts"][ctx]:
                stats["contexts"][ctx]["arms"] = {}
                modified = True
            
            for model in self.models:
                if model not in stats["contexts"][ctx]["arms"]:
                    stats["contexts"][ctx]["arms"][model] = {
                        "selections": 0,
                        "successes": 0,
                        "total_latency": 0.0,
                        "total_cost": 0.0,
                        "average_reward": 0.0
                    }
                    modified = True
        
        if modified:
            logging.info("MAB stats schema out of sync. Reconciled and updated missing models.")
            self._save_stats_to_disk_atomic_unlocked(stats)

    def _load_stats_from_disk_unlocked(self) -> Dict[str, Any]:
        """Loads MAB stats from disk without locking. Private helper called under active lock."""
        try:
            with open(self.stats_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to read MAB stats: {e}")
            return {
                "total_selections": 0,
                "contexts": {
                    "SIMPLE": {"total_selections": 0, "arms": {}},
                    "COMPLEX": {"total_selections": 0, "arms": {}}
                }
            }

    def _save_stats_to_disk_atomic_unlocked(self, stats: Dict[str, Any]):
        """Atomic double-write helper for both primary stats file and backup files."""
        temp_file = None
        temp_bak = None
        try:
            # 1. Atomic write to primary stats path using temporary file + swap
            with tempfile.NamedTemporaryFile("w", dir=self.stats_path.parent, delete=False, suffix=".tmp") as f:
                json.dump(stats, f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Force OS write buffer sync
                temp_file = Path(f.name)
            os.replace(temp_file, self.stats_path)
            
            # Keep cache metadata in sync with active disk state
            try:
                self._last_loaded_mtime = os.path.getmtime(self.stats_path)
                self._last_loaded_size = os.path.getsize(self.stats_path)
            except Exception:
                pass
            
            # 2. Atomic write to backup path (.bak) using temporary file + swap
            bak_path = self.stats_path.with_suffix(".bak")
            with tempfile.NamedTemporaryFile("w", dir=self.stats_path.parent, delete=False, suffix=".tmp") as f:
                json.dump(stats, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
                temp_bak = Path(f.name)
            os.replace(temp_bak, bak_path)
            
        except Exception as e:
            logging.error(f"Failed atomic write to MAB stats: {e}")
            # Safe cleanup of unswapped temporary files
            for p in [temp_file, temp_bak]:
                if p and p.exists():
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    def load_stats(self) -> Dict[str, Any]:
        """
        Returns a read-only deepcopy of current cached stats.
        Note: For write safety, only record_feedback handles model stats mutations internally.
        """
        with self._lock_state():
            stats = self._load_or_ensure_stats_locked()
            import copy
            return copy.deepcopy(stats)

    def _save_stats(self, stats: Dict[str, Any]):
        """Private internal helper to overwrite stats cache and atomically flush under lock."""
        with self._lock_state():
            self._stats = stats
            self._save_stats_to_disk_atomic_unlocked(self._stats)

    def select_arm(self, context: str) -> str:
        """Selects the best model arm using UCB1 selection for the given context (completely thread-and-process safe)."""
        with self._lock_state():
            stats = self._load_or_ensure_stats_locked()
            ctx_data = stats["contexts"].get(context)
            if not ctx_data:
                return "gemini-3.5-flash"  # Fallback

            total_plays = ctx_data.get("total_selections", 0)
            arms = ctx_data["arms"]

            # Cold-start: if any model arm has 0 selections, pull it first to build priors
            unplayed_arms = [name for name, arm in arms.items() if arm["selections"] == 0]
            if unplayed_arms:
                return unplayed_arms[0]

            best_arm = None
            best_ucb = -float("inf")

            for name, arm in arms.items():
                avg_reward = arm["average_reward"]
                selections = arm["selections"]
                
                # UCB1 calculation: UCB = avg_reward + C * sqrt(ln(Total_Plays) / Selections)
                exploration_term = self.exploration_constant * math.sqrt(
                    math.log(total_plays) / selections
                )
                ucb_score = avg_reward + exploration_term

                if ucb_score > best_ucb:
                    best_ucb = ucb_score
                    best_arm = name

            return best_arm or "gemini-3.5-flash"

    def record_feedback(self, context: str, model: str, success: bool, latency: float, cost: float):
        """Updates UCB1 statistics and saves to disk atomically under lock."""
        with self._lock_state():
            stats = self._load_or_ensure_stats_locked()
            ctx_data = stats["contexts"].get(context)
            if not ctx_data:
                return

            arm = ctx_data["arms"].get(model)
            if not arm:
                # Dynamic model addition on-the-fly if configuration changed
                arm = {
                    "selections": 0,
                    "successes": 0,
                    "total_latency": 0.0,
                    "total_cost": 0.0,
                    "average_reward": 0.0
                }
                ctx_data["arms"][model] = arm

            # Multi-dimensional Utility reward calculation
            # Normalized strictly between [0, 1]
            if success:
                cost_score = 1.0 - min(1.0, cost / self.max_cost)
                latency_score = 1.0 - min(1.0, latency / self.max_latency)
                reward = (self.w_success * 1.0) + (self.w_cost * cost_score) + (self.w_latency * latency_score)
            else:
                reward = self.penalty

            # Update stats
            arm["selections"] += 1
            ctx_data["total_selections"] += 1
            stats["total_selections"] += 1

            if success:
                arm["successes"] += 1
                arm["total_latency"] += latency
                arm["total_cost"] += cost

            # Incremental moving average update formula (prevents float overflow)
            n = arm["selections"]
            arm["average_reward"] += (reward - arm["average_reward"]) / n

            # Atomically save updated state to disk
            self._save_stats_to_disk_atomic_unlocked(stats)


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

    @lru_cache(maxsize=128)
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

    @lru_cache(maxsize=128)
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
