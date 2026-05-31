import os
import sys
from pathlib import Path
import json
from datetime import datetime, timezone
import threading
from contextlib import contextmanager
import time
from typing import Optional

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

class ReaderWriterLock:
    """A standard thread-level Reader-Writer Lock using monitor synchronization."""
    def __init__(self):
        self._lock = threading.Lock()
        self._readers = 0
        self._write_active = False
        self._writers_waiting = 0
        self._readers_ok = threading.Condition(self._lock)
        self._writers_ok = threading.Condition(self._lock)

    @contextmanager
    def read_lock(self):
        with self._lock:
            # Block new readers if a write is active or a writer is waiting
            while self._write_active or self._writers_waiting > 0:
                self._readers_ok.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._lock:
                self._readers -= 1
                if self._readers == 0:
                    self._writers_ok.notify(1)

    @contextmanager
    def write_lock(self):
        with self._lock:
            self._writers_waiting += 1
            while self._write_active or self._readers > 0:
                self._writers_ok.wait()
            self._writers_waiting -= 1
            self._write_active = True
        try:
            yield
        finally:
            with self._lock:
                self._write_active = False
                if self._writers_waiting > 0:
                    self._writers_ok.notify(1)
                else:
                    self._readers_ok.notify_all()

class TokenGovernor:
    """
    Predictability & Cost Control Layer (System 4).
    Ensures background agents don't exceed a defined token budget.
    Supports thread-safe & cross-process locking, atomic file saving, and timezone-aware rollovers.
    """
    _warned_no_fcntl = False

    def __init__(self, daily_budget: float = 2.00):
        from tools.infrastructure.config import settings
        self.daily_budget = daily_budget
        
        # Canonicalization and per-access path validation setup
        self.log_file = (settings.BRAIN_HEALTH_DIR.resolve() / "usage_stats.json").resolve()
        self._validate_path(self.log_file)
            
        self.lock = threading.RLock()  # Re-entrant lock to prevent deadlocks in nested calls
        self.rw_lock = ReaderWriterLock()
        self.pricing = {
            "gemini-3.5-flash": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
            "gemini-3.1-pro-preview": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
            "gemini-3-flash-preview": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
            "gemini-3.1-flash-lite": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
            "gemini-3.1-flash-lite-preview": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
            "gemini-2.5-pro": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
            "gemini-2.0-flash": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
            "deepseek-chat": {"input": 0.14 / 1_000_000, "output": 0.28 / 1_000_000},
            "deepseek-coder": {"input": 0.14 / 1_000_000, "output": 0.28 / 1_000_000},
            "deepseek-reasoner": {"input": 0.55 / 1_000_000, "output": 2.19 / 1_000_000},
            "local": {"input": 0, "output": 0},
        }
        self._cache = None  # Single atomic tuple for cross-thread consistency: (stats_dict, timestamp_float)
        self._cache_ttl = 1.0  # 1-second cache TTL
        self._ensure_log_exists()

    def _validate_path(self, path: Path):
        """Validates that the path is strictly contained within settings.BRAIN_HEALTH_DIR."""
        from tools.infrastructure.config import settings
        base_dir = settings.BRAIN_HEALTH_DIR.resolve()
        resolved_path = path.resolve()
        # Verify strict logical containment (base_dir is a parent directory of path)
        if base_dir not in resolved_path.parents and base_dir != resolved_path:
            raise ValueError(f"Security Violation: Path traversal detected on path: {path}")

    def _get_stats(self) -> dict:
        """Returns the stats in a thread-safe and cross-process safe manner."""
        # 1. Lock-free fast-path check using atomic tuple assignment (Double-Checked Locking)
        cache = self._cache
        if cache is not None:
            stats, cache_time = cache
            if (time.monotonic() - cache_time) < self._cache_ttl:
                return stats

        # 2. Synchronized slow-path check to avoid thundering herd across threads
        with self.lock:
            # Recheck cache inside lock
            cache = self._cache
            if cache is not None:
                stats, cache_time = cache
                if (time.monotonic() - cache_time) < self._cache_ttl:
                    return stats

            try:
                # Use exclusive lock to perform read/write atomically and avoid lock upgrade anti-pattern
                with self._lock_file(shared=False, timeout=2.0):
                    stats = self._read_stats_file()
                    if stats is None or self._is_rollover_needed(stats):
                        res = self._get_stats_unlocked()
                        self._cache = (res, time.monotonic())
                        return res
                    self._cache = (stats, time.monotonic())
                    return stats
            except (TimeoutError, Exception) as e:
                # Fail-Closed Secure Architecture: return budget-depleted stats on error to prevent unauthorized spends
                print(f"⚠️ Fail-Closed: Telemetry lookup failed ({e}). Restricting token quota.", file=sys.stderr)
                return self._get_fail_closed_stats()

    def _read_stats_file(self) -> Optional[dict]:
        """Reads the stats file without checking for rollovers or performing any writes."""
        try:
            self._validate_path(self.log_file)
            with open(self.log_file, "r", encoding="utf-8") as f:
                stats = json.load(f)
            if not isinstance(stats, dict):
                return None
            return stats
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    def _is_rollover_needed(self, stats: dict) -> bool:
        """Returns True if dates have rolled over or required keys are missing."""
        if "daily_total" not in stats or "daily_spend" not in stats:
            return True
        if "monthly_total" not in stats or "monthly_spend" not in stats:
            return True
            
        current_date = datetime.now(timezone.utc)
        try:
            last_reset_date = datetime.strptime(str(stats.get("date", "2000-01-01")), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return True
            
        # Daily rollover check
        if last_reset_date != current_date.date():
            return True
            
        # Monthly rollover check
        if last_reset_date.month != current_date.month or last_reset_date.year != current_date.year:
            return True
            
        return False

    def _get_default_stats(self) -> dict:
        """Returns the default initial stats dictionary (DRY compliance)."""
        return {
            "date": str(datetime.now(timezone.utc).date()), 
            "daily_total": 0.0, 
            "monthly_total": 0.0,
            "total_spend": 0.0,
            "daily_input_tokens": 0,
            "daily_output_tokens": 0,
            "monthly_input_tokens": 0,
            "monthly_output_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "history": []
        }

    def _get_fail_closed_stats(self) -> dict:
        """Returns stats indicating budget is fully depleted to fail securely."""
        return {
            "date": str(datetime.now(timezone.utc).date()), 
            "daily_total": self.daily_budget, 
            "monthly_total": self.daily_budget * 30,
            "total_spend": self.daily_budget * 30,
            "daily_input_tokens": 0,
            "daily_output_tokens": 0,
            "monthly_input_tokens": 0,
            "monthly_output_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "history": []
        }

    @contextmanager
    def _lock_file(self, shared: bool = False, timeout: float = 2.0):
        """Acquires a thread-level ReaderWriterLock followed by a cross-process OS file lock."""
        thread_lock_ctx = self.rw_lock.read_lock() if shared else self.rw_lock.write_lock()
        with thread_lock_ctx:
            lock_file_path = self.log_file.with_suffix(".lock")
            lock_file_path.parent.mkdir(parents=True, exist_ok=True)
            # Use append mode ("a") to avoid truncating lock file on open, specifying UTF-8 encoding
            with open(lock_file_path, "a", encoding="utf-8") as lock_f:
                acquired = False
                try:
                    if HAS_FCNTL:
                        lock_mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
                        start_time = time.time()
                        while not acquired:
                            try:
                                fcntl.flock(lock_f, lock_mode | fcntl.LOCK_NB)
                                acquired = True
                            except (BlockingIOError, PermissionError):
                                if time.time() - start_time >= timeout:
                                    raise TimeoutError(
                                        f"Lock acquisition timeout: failed to acquire "
                                        f"{'shared' if shared else 'exclusive'} lock on {lock_file_path} "
                                        f"within {timeout}s"
                                    )
                                time.sleep(0.05)
                    else:
                        if not TokenGovernor._warned_no_fcntl:
                            print("⚠️ POSIX fcntl.flock not available. Falling back to thread-level locking.", file=sys.stderr)
                            TokenGovernor._warned_no_fcntl = True
                    yield
                finally:
                    if HAS_FCNTL and acquired:
                        try:
                            fcntl.flock(lock_f, fcntl.LOCK_UN)
                        except Exception:
                            pass

    def _ensure_log_exists(self):
        with self._lock_file():
            if not self.log_file.exists():
                initial_stats = self._get_default_stats()
                self._save_stats_unlocked(initial_stats)

    def _get_stats_unlocked(self):
        if not self.log_file.exists():
            stats = self._get_default_stats()
            self._save_stats_unlocked(stats)
            return stats

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                stats = json.load(f)
            if not isinstance(stats, dict):
                raise ValueError("Stats JSON must be a dictionary")
        except (json.JSONDecodeError, ValueError):
            # Prevent silent data loss: backup corrupted stats first
            try:
                corrupted_path = self.log_file.with_suffix(f".corrupted.{int(datetime.now(timezone.utc).timestamp())}")
                if self.log_file.exists():
                    os.replace(self.log_file, corrupted_path)
                    print(f"⚠️ Corrupted budget stats file detected. Backed up to {corrupted_path}")
            except Exception as backup_err:
                print(f"⚠️ Failed to backup corrupted budget stats file: {backup_err}")
                
            stats = self._get_default_stats()
            self._save_stats_unlocked(stats)
        except FileNotFoundError:
            stats = self._get_default_stats()
            self._save_stats_unlocked(stats)

        # Normalize keys
        if "daily_total" not in stats:
            stats["daily_total"] = stats.get("daily_spend", 0.0)
        if "monthly_total" not in stats:
            stats["monthly_total"] = stats.get("monthly_spend", 0.0)
        if "daily_input_tokens" not in stats:
            stats["daily_input_tokens"] = 0
        if "daily_output_tokens" not in stats:
            stats["daily_output_tokens"] = 0
        if "monthly_input_tokens" not in stats:
            stats["monthly_input_tokens"] = 0
        if "monthly_output_tokens" not in stats:
            stats["monthly_output_tokens"] = 0
        if "total_input_tokens" not in stats:
            stats["total_input_tokens"] = 0
        if "total_output_tokens" not in stats:
            stats["total_output_tokens"] = 0
        
        # Rollover check in timezone-aware UTC
        current_date = datetime.now(timezone.utc)
        try:
            last_reset_date = datetime.strptime(str(stats.get("date", "2000-01-01")), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            # Force rollover and correction of corrupted date to prevent locked state
            last_reset_date = datetime.min.date()

        modified = False
        # Daily rollover check
        if last_reset_date != current_date.date():
            print(f"🔄 Daily Budget Reset. Previous daily spend: {stats.get('daily_total', 0.0)}")
            stats["date"] = str(current_date.date())
            stats["daily_total"] = 0.0
            stats["daily_input_tokens"] = 0
            stats["daily_output_tokens"] = 0
            modified = True
            
        # Monthly rollover check
        if last_reset_date.month != current_date.month or last_reset_date.year != current_date.year:
            print(f"🔄 Billing Cycle Reset. Previous monthly spend: {stats.get('monthly_total', 0.0)}")
            stats["monthly_total"] = 0.0
            stats["monthly_input_tokens"] = 0
            stats["monthly_output_tokens"] = 0
            modified = True

        if modified:
            self._save_stats_unlocked(stats)
            
        with self.lock:
            self._cache = (stats, time.monotonic())
        return stats

    def _save_stats_unlocked(self, stats):
        import tempfile
        parent_dir = self.log_file.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        
        # Per-access path containment verification to defeat TOCTOU dynamic directory modifications
        self._validate_path(self.log_file)
        
        # Instantiate NamedTemporaryFile (automatically defaults to 0600 permissions securely on POSIX)
        with tempfile.NamedTemporaryFile(dir=parent_dir, suffix=".json", delete=False, mode="w", encoding="utf-8") as temp_file:
            temp_path = Path(temp_file.name)
            try:
                json.dump(stats, temp_file, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            except Exception:
                temp_file.close()
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                raise
            
        try:
            # Atomically replace final file
            os.replace(temp_path, self.log_file)
            
            # Directory-level fsync to guarantee durability of rename
            dir_fd = os.open(str(parent_dir), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise
            
        with self.lock:
            self._cache = (stats, time.monotonic())

    def track_usage(self, model: str, input_tokens: int, output_tokens: int, task_id: str, batch: bool = False) -> float:
        """
        Logs token usage and updates total spend and token telemetry.
        Applies a 50% discount if batch=True.
        """
        price_key = model if model in self.pricing else f"{model}-preview"
        rates = self.pricing.get(price_key, self.pricing["gemini-3-flash-preview"])
        
        cost = (input_tokens * rates["input"]) + (output_tokens * rates["output"])
        
        if batch:
            cost *= 0.5 # 50% Batch API Discount
            
        with self._lock_file():
            stats = self._get_stats_unlocked()
            stats["daily_total"] = stats.get("daily_total", 0.0) + cost
            stats["monthly_total"] = stats.get("monthly_total", 0.0) + cost
            stats["total_spend"] = stats.get("total_spend", 0.0) + cost
            
            stats["daily_input_tokens"] = stats.get("daily_input_tokens", 0) + input_tokens
            stats["daily_output_tokens"] = stats.get("daily_output_tokens", 0) + output_tokens
            stats["monthly_input_tokens"] = stats.get("monthly_input_tokens", 0) + input_tokens
            stats["monthly_output_tokens"] = stats.get("monthly_output_tokens", 0) + output_tokens
            stats["total_input_tokens"] = stats.get("total_input_tokens", 0) + input_tokens
            stats["total_output_tokens"] = stats.get("total_output_tokens", 0) + output_tokens
            
            stats["history"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task_id": task_id,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost
            })
            # Prune history to prevent indefinite JSON file bloat (Senior Mitigation)
            if len(stats["history"]) > 100:
                stats["history"] = stats["history"][-100:]
            self._save_stats_unlocked(stats)
            
        return cost

    def can_spend(self, estimated_cost: float = 0.01) -> bool:
        """Returns True if the estimated daily cost is within the remaining daily budget."""
        stats = self._get_stats()
        return (stats["daily_total"] + estimated_cost) <= self.daily_budget

    def get_remaining_budget(self) -> float:
        """Returns the remaining daily budget."""
        stats = self._get_stats()
        return max(0.0, self.daily_budget - stats["daily_total"])

    def get_budget_aware_model(self, preferred_model: str, task_critical: bool = False) -> str:
        """
        Dynamically downgrades models to preserve budget.
        - If remaining daily budget < 10% ($0.20): Force local.
        - If remaining daily budget < 50% ($1.00) and not critical: Downgrade Pro -> 3.5 Flash -> Flash -> Lite.
        """
        stats = self._get_stats()
        remaining = max(0.0, self.daily_budget - stats["daily_total"])
        remaining_pct = remaining / self.daily_budget if self.daily_budget > 0 else 0

        # CRITICAL DEPLETION: Force local for everything
        if remaining_pct < 0.10:
            print(f"⚠️ Budget Critical ({remaining_pct:.1%}). Forcing LOCAL mode.")
            return "local"

        # LOW BUDGET: Downgrade non-critical tasks
        if remaining_pct < 0.50 and not task_critical:
            if "pro" in preferred_model:
                print(f"📉 Low Budget ({remaining_pct:.1%}). Downgrading Pro -> 3.5 Flash.")
                return "gemini-3.5-flash"
            if "3.5-flash" in preferred_model:
                print(f"📉 Low Budget ({remaining_pct:.1%}). Downgrading 3.5 Flash -> Flash.")
                return "gemini-3-flash-preview"
            if "flash" in preferred_model and "lite" not in preferred_model:
                print(f"📉 Low Budget ({remaining_pct:.1%}). Downgrading Flash -> Lite.")
                return "gemini-3.1-flash-lite"

        return preferred_model

# Global Instance with dynamic environment budget
from tools.infrastructure.config import settings
token_governor = TokenGovernor(daily_budget=settings.DAILY_BUDGET)

