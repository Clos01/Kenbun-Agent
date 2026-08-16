import json
import time
import random
import os
from pathlib import Path
from tools.strategy.hme_router import hme_router
from tools.strategy.decision_logic import ROUTING_LOG

HOLDOUT_FILE = Path(__file__).parent / "routing_holdout.json"
TUNING_FILE = Path(__file__).parent / "routing_tuning.json"

def _load_live_tasks():
    if not ROUTING_LOG.exists():
        return []
    tasks = []
    seen = set()
    with open(ROUTING_LOG, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                task = data.get("task")
                assigned = data.get("assigned_path")
                if task and task not in seen and assigned != "STANDARD_EXECUTION":
                    seen.add(task)
                    tasks.append({"task": task, "expected": assigned})
            except Exception:
                pass
    return tasks

def _initialize_splits():
    tasks = _load_live_tasks()
    if not tasks:
        print(f"⚠️  No routing logs found at {ROUTING_LOG}")
        print("Run some tasks through the system first to generate live data.")
        return [], []

    # Deterministic shuffle to preserve the sealed slice
    random.Random(42).shuffle(tasks)
    
    split_idx = int(len(tasks) * 0.8)
    tuning = tasks[:split_idx]
    holdout = tasks[split_idx:]
    
    if not TUNING_FILE.exists():
        with open(TUNING_FILE, "w") as f:
            json.dump(tuning, f, indent=2)
        print(f"📦 Created tuning set ({len(tuning)} items) at {TUNING_FILE.name}")
        print("   -> Review and correct these labels to tune your router.")
            
    if not HOLDOUT_FILE.exists():
        with open(HOLDOUT_FILE, "w") as f:
            json.dump(holdout, f, indent=2)
        print(f"🔒 Created SEALED holdout set ({len(holdout)} items) at {HOLDOUT_FILE.name}")
        print("   -> DO NOT tune against these. Review labels only.")

    with open(TUNING_FILE, "r") as f:
        tuning = json.load(f)
    with open(HOLDOUT_FILE, "r") as f:
        holdout = json.load(f)
        
    return tuning, holdout

def run_benchmark():
    tuning, holdout = _initialize_splits()
    
    if not holdout:
        print("❌ Cannot run benchmark without holdout data.")
        return

    print(f"📊 Running HME Sovereign Router Benchmark on SEALED HOLDOUT (N={len(holdout)})...")
    print("-" * 60)
    
    correct = 0
    start_time = time.time()
    
    route_to_key = {
        "gemini-3-pro": "PRO_AUDITOR",
        "local-ollama": "LOCAL_WORKER",
        "gemini-3-flash": "FLASH_CODER",
        "claude-code": "SECURITY_GUARD"
    }
    
    for i, test in enumerate(holdout):
        task = test["task"]
        expected = test["expected"]
        
        # In case the log contained a raw worker name instead of a route key, fallback cleanly
        if expected in route_to_key.values():
            pass
        elif expected in route_to_key:
            expected = route_to_key[expected]
            
        route = hme_router.route_task(task)
        actual = route_to_key.get(route["worker"], "UNKNOWN")
        
        is_correct = actual == expected
        if is_correct:
            correct += 1
            status = "✅"
        else:
            status = "❌"
            
        if i < 40 or not is_correct: # Show first 40 or all errors
            print(f"[{i+1:03}] {status} Exp: {expected[:15]:15} | Act: {actual[:15]:15} | Task: {task[:25]}...")

    duration = time.time() - start_time
    accuracy = (correct / len(holdout)) * 100
    
    print("-" * 60)
    print("📈 HME BENCHMARK COMPLETE (SEALED HOLDOUT)")
    print(f"   Accuracy: {accuracy:.2f}% ({correct}/{len(holdout)})")
    print(f"   Latency:  {duration*1000:.2f}ms (Total) | {duration*1000/len(holdout):.2f}ms (Avg)")
    print("-" * 60)

if __name__ == "__main__":
    run_benchmark()
