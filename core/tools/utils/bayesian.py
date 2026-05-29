import json
import os
import time
from pathlib import Path

from tools.infrastructure.config import settings
WEIGHTS_FILE = settings.PROJECT_ROOT / "core" / "weights.json"

def load_weights():
    if not WEIGHTS_FILE.exists():
        return {"categories": {}, "global": {}, "last_updated": time.time()}
    with open(WEIGHTS_FILE, "r") as f:
        return json.load(f)

def save_weights(weights):
    weights["last_updated"] = time.time()
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(weights, f, indent=4)

def tune_swarm(tool_id: str, success: bool, category: str = "global"):
    """
    Updates the Bayesian weights for a specific tool.
    Uses Beta distribution logic: Alpha (successes) and Beta (failures).
    """
    weights = load_weights()
    
    # Update Global
    if tool_id not in weights["global"]:
        weights["global"][tool_id] = {"alpha": 1.0, "beta": 1.0}
    
    if success:
        weights["global"][tool_id]["alpha"] += 1.0
    else:
        weights["global"][tool_id]["beta"] += 1.0

    # Update Category-specific
    if category != "global":
        if category not in weights["categories"]:
            weights["categories"][category] = {}
        
        if tool_id not in weights["categories"][category]:
            # Inherit from global as a baseline if it doesn't exist
            weights["categories"][category][tool_id] = weights["global"].get(tool_id, {"alpha": 1.0, "beta": 1.0}).copy()

        if success:
            weights["categories"][category][tool_id]["alpha"] += 1.0
        else:
            weights["categories"][category][tool_id]["beta"] += 1.0

    save_weights(weights)
    return f"✅ Synaptic Weight Tuned: {tool_id} ({category}) -> {'SUCCESS' if success else 'FAILURE'}"

def get_confidence(tool_id: str, category: str = "global"):
    """Calculates the expected probability of success (Alpha / (Alpha + Beta))."""
    weights = load_weights()
    
    # Try category first
    target = weights["categories"].get(category, {}).get(tool_id)
    if not target:
        target = weights["global"].get(tool_id, {"alpha": 1.0, "beta": 1.0})
        
    alpha = target["alpha"]
    beta = target["beta"]
    return alpha / (alpha + beta)

def get_best_tool(category: str, candidate_tools: list):
    """Returns the tool from the candidates list with the highest confidence for a category."""
    confidences = {tid: get_confidence(tid, category) for tid in candidate_tools}
    best_tool = max(confidences, key=confidences.get)
    return best_tool, confidences[best_tool]

if __name__ == "__main__":
    # Test tuning
    print(tune_swarm("consult_supervisor", True, "security"))
    print(f"Confidence: {get_confidence('consult_supervisor', 'security'):.2f}")
