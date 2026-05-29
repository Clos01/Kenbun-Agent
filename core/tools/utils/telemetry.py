import os
import json
import time
from pathlib import Path
from datetime import datetime

from tools.infrastructure.config import settings

# --- CONFIGURATION ---
BENCHMARK_PATH = settings.BRAIN_HEALTH_DIR / "BENCHMARKS.json"

def log_tool_performance(tool_id: str, success: bool, duration: float):
    """
    Updates BENCHMARKS.json with tool execution metrics.
    """
    if not BENCHMARK_PATH.exists():
        return

    try:
        with open(BENCHMARK_PATH, "r") as f:
            content = json.load(f)
        
        # BENCHMARKS.json is a list. Target the first system entry.
        if isinstance(content, list) and len(content) > 0:
            data = content[0]
        else:
            return

        # Update last_updated
        data["last_updated"] = datetime.now().isoformat()

        # Simple logic: update the most recent benchmark entry
        if data.get("benchmarks"):
            latest = data["benchmarks"][-1]
            metrics = latest.get("metrics", {})
            
            # Increment logical depth if it's a tool call
            metrics["logical_depth_score"] = metrics.get("logical_depth_score", 0) + 1
            
            # Update approval rate (simplified as success rate for now)
            curr_rate = metrics.get("supervisor_approval_rate", 0.0)
            # Bayesian-ish moving average
            new_rate = (curr_rate * 0.9) + (0.1 if success else 0.0)
            metrics["supervisor_approval_rate"] = round(new_rate, 2)
            
            # Tool efficiency (duration-based)
            curr_efficiency = metrics.get("tool_efficiency_ratio", 0.0)
            # Higher is better, so maybe 1/duration. Guard against 0 duration.
            eff_signal = min(1.0, 1.0/duration) if duration > 0 else 1.0
            new_efficiency = (curr_efficiency * 0.9) + (eff_signal * 0.1)
            metrics["tool_efficiency_ratio"] = round(new_efficiency, 2)

        with open(BENCHMARK_PATH, "w") as f:
            json.dump(content, f, indent=2)

    except Exception as e:
        print(f"⚠️ Telemetry failed: {e}")

def create_new_benchmark_baseline():
    """Creates a fresh baseline entry in BENCHMARKS.json."""
    if not BENCHMARK_PATH.exists():
        return

    try:
        with open(BENCHMARK_PATH, "r") as f:
            content = json.load(f)

        if isinstance(content, list) and len(content) > 0:
            data = content[0]
        else:
            return

        new_entry = {
            "id": f"UPGRADE_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "logical_depth_score": 0,
                "supervisor_approval_rate": 0.0,
                "rag_relevance_avg": 0.0,
                "tool_efficiency_ratio": 0.0
            },
            "status": "active"
        }
        
        data["benchmarks"].append(new_entry)
        
        # Keep only last 10 entries to prevent file bloating
        if len(data["benchmarks"]) > 10:
            data["benchmarks"] = data["benchmarks"][-10:]

        with open(BENCHMARK_PATH, "w") as f:
            json.dump(content, f, indent=2)

    except Exception as e:
        print(f"⚠️ Failed to create new benchmark baseline: {e}")
