import json
import time
import sys
from pathlib import Path
from datetime import datetime


from tools.strategy.decision_logic import router

def run_evaluation(full_sweep=False, limit=150):
    print(f"🚀 Starting Nightly Evaluation Cycle (Full Sweep: {full_sweep})")
    
    # 1. Load test cases
    try:
        with open("brain_health/generated_cases.json", "r") as f:
            test_cases = json.load(f)
    except Exception as e:
        print(f"❌ Error loading test cases: {e}")
        return

    if not full_sweep:
        test_cases = test_cases[:limit]
        print(f"💡 Limited run: checking first {limit} cases.")

    # Reset router state for a clean benchmark
    router.reset()

    total_cases = len(test_cases)
    correct = 0
    start_time = time.time()
    
    # Metrics tracking
    per_class = {}
    misses = []
    
    for case in test_cases:
        task = case["task"]
        expected = case["expected_path"]
        
        # Initialize class metrics
        if expected not in per_class:
            per_class[expected] = {"n": 0, "correct": 0}
        per_class[expected]["n"] += 1
        
        # Run routing
        # Run routing with fast_mode enabled
        actual = router.get_strategy_path(task, fast_mode=True)
        
        if actual == expected:
            correct += 1
            per_class[expected]["correct"] += 1
        else:
            if len(misses) < 20: # Track top 20 misses
                misses.append({
                    "task": task,
                    "expected": expected,
                    "got": actual
                })

    run_seconds = time.time() - start_time
    accuracy = correct / total_cases if total_cases > 0 else 0
    
    # Format per-class accuracy
    formatted_per_class = {}
    for cls, stats in per_class.items():
        formatted_per_class[cls] = {
            "n": stats["n"],
            "accuracy": stats["correct"] / stats["n"] if stats["n"] > 0 else 0
        }

    # 2. Build record
    record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "run_seconds": round(run_seconds, 2),
        "full_sweep": full_sweep,
        "n_cases": total_cases,
        "routing_accuracy": accuracy,
        "median_latency_ms": round((run_seconds / total_cases) * 1000, 4) if total_cases > 0 else 0,
        "per_class_accuracy": formatted_per_class,
        "top_misses": misses[:10] # Save top 10 to file
    }

    # 3. Update BENCHMARKS.json
    benchmarks_path = Path("brain_health/BENCHMARKS.json")
    try:
        if benchmarks_path.exists():
            with open(benchmarks_path, "r") as f:
                data = json.load(f)
        else:
            data = {"history": []}
            
        data["history"].append(record)
        data["last_updated"] = record["date"]
        
        with open(benchmarks_path, "w") as f:
            json.dump(data, f, indent=2)
            
        print(f"✅ Evaluation Complete. Accuracy: {accuracy:.2%} ({correct}/{total_cases})")
        print(f"📊 Results saved to BENCHMARKS.json")
        
    except Exception as e:
        print(f"❌ Error updating benchmarks: {e}")

if __name__ == "__main__":
    # Check for --full flag
    full = "--full" in sys.argv
    run_evaluation(full_sweep=full)