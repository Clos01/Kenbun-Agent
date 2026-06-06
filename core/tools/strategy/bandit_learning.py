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
                elif msvcrt:
                    try:
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                    except IOError as e:
                        raise RuntimeError(f"Could not acquire cross-process lock on {lock_path}: {e}")
                else:
                    logging.warning("Cross-process lock (fcntl/msvcrt) is not available on this platform. Thread lock active.")
                
                yield
                
            finally:
                if lock_file:
                    if fcntl:
                        try:
                            fcntl.flock(lock_file, fcntl.LOCK_UN)
                        except Exception:
                            pass
                    elif msvcrt:
                        try:
                            lock_file.seek(0)
                            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
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

    def select_arm(self, target_model_routing_context_category: str) -> str:
        """Selects the best model arm using UCB1 selection for the given context (completely thread-and-process safe)."""
        with self._lock_state():
            multi_armed_bandit_model_routing_statistics = self._load_or_ensure_stats_locked()
            routing_statistics_for_current_context = multi_armed_bandit_model_routing_statistics["contexts"].get(target_model_routing_context_category)
            if not routing_statistics_for_current_context:
                return "gemini-3.5-flash"  # Fallback

            total_routing_selections_across_all_models_in_current_context = routing_statistics_for_current_context.get("total_selections", 0)
            candidate_model_arms_routing_statistics = routing_statistics_for_current_context["arms"]

            # Cold-start: if any model arm has 0 selections, pull it first to build priors
            unplayed_model_candidate_arms_for_cold_start = [name for name, arm in candidate_model_arms_routing_statistics.items() if arm["selections"] == 0]
            if unplayed_model_candidate_arms_for_cold_start:
                return unplayed_model_candidate_arms_for_cold_start[0]

            highest_confidence_model_arm_selection = None
            highest_calculated_upper_confidence_bound_score_metric = -float("inf")

            for name, arm in candidate_model_arms_routing_statistics.items():
                running_average_reward_score_of_model_arm = arm["average_reward"]
                total_selection_count_for_model_arm = arm["selections"]
                
                # UCB1 calculation: UCB = avg_reward + C * sqrt(ln(Total_Plays) / Selections)
                upper_confidence_bound_variance_exploration_factor = self.exploration_constant * math.sqrt(
                    math.log(total_routing_selections_across_all_models_in_current_context) / total_selection_count_for_model_arm
                )
                total_upper_confidence_bound_selection_score = running_average_reward_score_of_model_arm + upper_confidence_bound_variance_exploration_factor

                if total_upper_confidence_bound_selection_score > highest_calculated_upper_confidence_bound_score_metric:
                    highest_calculated_upper_confidence_bound_score_metric = total_upper_confidence_bound_selection_score
                    highest_confidence_model_arm_selection = name

            return highest_confidence_model_arm_selection or "gemini-3.5-flash"

    def record_feedback(
        self,
        target_model_routing_context_category: str,
        selected_model_arm_identifier: str,
        evaluation_execution_success_status: bool,
        execution_latency_duration_seconds: float,
        transaction_financial_cost_value: float
    ):
        """Updates UCB1 statistics and saves to disk atomically under lock."""
        with self._lock_state():
            multi_armed_bandit_model_routing_statistics = self._load_or_ensure_stats_locked()
            routing_statistics_for_current_context = multi_armed_bandit_model_routing_statistics["contexts"].get(target_model_routing_context_category)
            if not routing_statistics_for_current_context:
                return

            target_model_arm_routing_statistics = routing_statistics_for_current_context["arms"].get(selected_model_arm_identifier)
            if not target_model_arm_routing_statistics:
                # Dynamic model addition on-the-fly if configuration changed
                target_model_arm_routing_statistics = {
                    "selections": 0,
                    "successes": 0,
                    "total_latency": 0.0,
                    "total_cost": 0.0,
                    "average_reward": 0.0
                }
                routing_statistics_for_current_context["arms"][selected_model_arm_identifier] = target_model_arm_routing_statistics

            # Multi-dimensional Utility reward calculation
            # Normalized strictly between [0, 1]
            if evaluation_execution_success_status:
                normalized_financial_cost_efficiency_score = 1.0 - min(1.0, transaction_financial_cost_value / self.max_cost)
                normalized_response_latency_efficiency_score = 1.0 - min(1.0, execution_latency_duration_seconds / self.max_latency)
                calculated_multi_dimensional_utility_reward_value = (self.w_success * 1.0) + (self.w_cost * normalized_financial_cost_efficiency_score) + (self.w_latency * normalized_response_latency_efficiency_score)
            else:
                calculated_multi_dimensional_utility_reward_value = self.penalty

            # Update stats
            target_model_arm_routing_statistics["selections"] += 1
            routing_statistics_for_current_context["total_selections"] += 1
            multi_armed_bandit_model_routing_statistics["total_selections"] += 1

            if evaluation_execution_success_status:
                target_model_arm_routing_statistics["successes"] += 1
                target_model_arm_routing_statistics["total_latency"] += execution_latency_duration_seconds
                target_model_arm_routing_statistics["total_cost"] += transaction_financial_cost_value

            # Incremental moving average update formula (prevents float overflow)
            total_cumulative_selections_for_target_model = target_model_arm_routing_statistics["selections"]
            target_model_arm_routing_statistics["average_reward"] += (calculated_multi_dimensional_utility_reward_value - target_model_arm_routing_statistics["average_reward"]) / total_cumulative_selections_for_target_model

            # Atomically save updated state to disk
            self._save_stats_to_disk_atomic_unlocked(multi_armed_bandit_model_routing_statistics)


