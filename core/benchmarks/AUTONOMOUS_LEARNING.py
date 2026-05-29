import json
from pathlib import Path
import sys


from tools.strategy.decision_logic import router

def autonomous_learn():
    print("🧠 System 4: Starting Autonomous Learning Loop...")
    
    # 1. Load the generated cases
    with open("brain_health/generated_cases.json", "r") as f:
        test_cases = json.load(f)
    
    failures_recorded = 0
    
    for case in test_cases:
        actual_path = router.get_strategy_path(case["task"])
        expected_path = case["expected_path"]
        
        if actual_path != expected_path:
            # Record the failure for self-healing
            router.record_failure(case["task"], actual_path, expected_path)
            failures_recorded += 1
            
    print(f"✅ Learning Complete. Recorded {failures_recorded} corrected paths into Self-Healing memory.")

if __name__ == "__main__":
    autonomous_learn()
