import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from tools.utils.path_utils import get_project_root
from tools.strategy.token_governor import token_governor

PROJECT_ROOT = get_project_root()
BENCHMARKS_FILE = PROJECT_ROOT / "brain_health" / "BENCHMARKS.json"

class IntelligenceEngine:
    """
    Analyzes system state (benchmarks, budget, logs) to provide 
    proactive optimization suggestions.
    """
    
    @staticmethod
    def get_autonomous_suggestions() -> List[Dict[str, Any]]:
        suggestions = []
        
        # 1. Accuracy Drift Check
        if BENCHMARKS_FILE.exists():
            try:
                with open(BENCHMARKS_FILE, "r") as f:
                    data = json.load(f)
                    
                    # Handle both list and dict structures safely
                    history = []
                    if isinstance(data, list):
                        history = data
                    elif isinstance(data, dict):
                        history = data.get("history", []) or data.get("benchmarks", []) or [data]
                        
                    if history:
                        last_run = history[-1]
                        if isinstance(last_run, dict):
                            # Check details for REJECTED / low audit scores
                            details = last_run.get("details", [])
                            if details:
                                rejected_count = sum(1 for d in details if isinstance(d, dict) and d.get("audit_status") == "REJECTED")
                                total_count = len(details)
                                
                                if total_count > 0 and (rejected_count / total_count) > 0.5:
                                    suggestions.append({
                                        "priority": "HIGH",
                                        "type": "RE-TRAIN",
                                        "message": f"Swarm audit rejection rate is high ({rejected_count}/{total_count}). I recommend re-indexing project code to optimize reasoning."
                                    })
            except Exception as e:
                logging.error(f"IntelligenceEngine Benchmark Error: {e}", exc_info=True)

        # 2. Financial Governance Check
        usage = token_governor._get_stats()
        if usage.get("total_spend", 0.0) > token_governor.daily_budget * 0.7:
            suggestions.append({
                "priority": "MEDIUM",
                "type": "COST",
                "message": f"Daily budget is 70% exhausted (${usage.get('total_spend'):.2f}). Switching to Local Fallback (Gemma 9B) for routine audits."
            })

        # 3. Default Proactive Suggestion
        if not suggestions:
            suggestions.append({
                "priority": "LOW",
                "type": "OPTIMIZE",
                "message": "System stable. I am pre-caching documentation for the current active project."
            })
            
        return suggestions

# Singleton for ease of use
intelligence_engine = IntelligenceEngine()
