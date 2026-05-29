import os
import asyncio
import time
import json
import aiohttp
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field

from tools.strategy.strategy_manager import governor
from tools.utils.llm_utils import extract_json
from tools.infrastructure.topology_manager import log_swarm_event

from tools.infrastructure.config import settings

# --- CONFIGURATION ---
@dataclass
class AuditConfig:
    pc_ip: str = settings.SWARM_PC_IP
    ollama_port: int = settings.workers.p330_ollama_port
    log_dir: Path = settings.BRAIN_HEALTH_DIR
    log_file: str = "audit_history.jsonl"
    
    @property
    def ollama_url(self) -> str:
        return f"http://{self.pc_ip}:{self.ollama_port}/api/chat"

    @property
    def full_log_path(self) -> Path:
        return self.log_dir / self.log_file

config = AuditConfig()

# Default Ensemble Members (Optimized for user's Parallel=4 setting)
DEFAULT_MODELS = [
    {"id": "gemma2:latest", "role": "Architect", "weight_bonus": 1.2},
    {"id": "llama3.2:latest", "role": "Security", "weight_bonus": 1.0},
    {"id": "phi3:latest", "role": "Logic", "weight_bonus": 0.8}
]

class WeightedVoteCalculator:
    """Handles the mathematical consensus logic."""
    
    def __init__(self, models: List[Dict[str, Any]], thresholds: Dict[str, float] = None):
        self.models = models
        self.thresholds = thresholds or {"approved": 0.3, "rejected": -0.3}

    def calculate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_score = 0
        total_weight = 0
        votes = []
        
        for i, res in enumerate(results):
            model = self.models[i]
            model_id = model["id"]
            
            # Fetch historical weight from System 4 Bayesian Governor
            alpha, beta, _, _ = governor.get_tool_stats(f"audit_{model_id}")
            historical_success_prob = alpha / (alpha + beta) if (alpha + beta) > 0 else 0.5
            
            # Final Weight = Historical Success * Role Bonus
            weight = historical_success_prob * model.get("weight_bonus", 1.0)
            
            if "error" in res:
                continue
            
            decision = res.get("decision", "REJECTED").upper()
            confidence = float(res.get("confidence", 0.5))
            
            # Vote Value: APPROVED (+1), REJECTED (-1)
            vote_val = 1 if decision == "APPROVED" else -1
            weighted_vote = vote_val * weight * confidence
            
            total_score += weighted_vote
            total_weight += weight
            
            votes.append({
                "model": model_id,
                "role": model.get("role", "Auditor"),
                "decision": decision,
                "confidence": confidence,
                "weight": weight
            })

        if total_weight == 0:
            return {"verdict": "ERROR", "score": 0, "votes": votes, "reason": "All models failed or returned no weight."}
            
        normalized_score = total_score / total_weight
        
        if normalized_score > self.thresholds["approved"]:
            verdict = "APPROVED"
        elif normalized_score < self.thresholds["rejected"]:
            verdict = "REJECTED"
        else:
            verdict = "HUNG_JURY"
            
        return {
            "verdict": verdict,
            "score": normalized_score,
            "votes": votes
        }

class ConsensusEngine:
    """
    System 2 Ensemble Auditor.
    Runs parallel local models to reach a weighted majority verdict on code tasks.
    """
    
    def __init__(self, models: List[Dict[str, Any]] = None):
        self.models = models or DEFAULT_MODELS
        self.calculator = WeightedVoteCalculator(self.models)

    async def _call_ollama(self, model_id: str, system_prompt: str, user_message: str) -> Dict[str, Any]:
        """Async call to a local Ollama model."""
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(config.ollama_url, json=payload, timeout=45) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['message']['content']
                        
                        parsed = extract_json(content)
                        if parsed:
                            return parsed
                        
                        # Fallback: Parse string for keywords
                        decision = "APPROVED" if "APPROVE" in content.upper() else "REJECTED"
                        return {"decision": decision, "reason": content[:200]}
                    else:
                        return {"error": f"Ollama HTTP {response.status}"}
        except Exception as e:
            return {"error": str(e)}

    async def run_audit(self, user_proposal: str, code_snippet: str = "") -> Dict[str, Any]:
        """Dispatches parallel audits and calculates the weighted consensus."""
        print(f"📡 [ENSEMBLE] Dispatching parallel audits to {len(self.models)} models...")
        
        system_prompt = (
            "You are a Senior Security Auditor for the Kenbun Swarm. "
            "Review the code proposal for architectural flaws, security risks, or logic bombs. "
            "Return ONLY a JSON object with: 'decision' (APPROVED/REJECTED), 'confidence' (0.0-1.0), and 'reason'."
        )
        user_message = f"PROPOSAL: {user_proposal}\n\nCODE:\n{code_snippet}"
        
        # 1. Parallel Execution
        tasks = [self._call_ollama(m["id"], system_prompt, user_message) for m in self.models]
        results = await asyncio.gather(*tasks)
        
        # 2. Logic Separation: Delegate math to calculator
        verdict_data = self.calculator.calculate(results)
        
        if verdict_data["verdict"] == "ERROR":
            return verdict_data

        # 3. Persistence for Analysis
        audit_entry = {
            "timestamp": time.time(),
            "proposal": user_proposal,
            "verdict": verdict_data["verdict"],
            "score": verdict_data["score"],
            "votes": verdict_data["votes"]
        }
        self._log_audit(audit_entry)
        
        # 4. Shadow Observability Ping
        log_swarm_event("DECISION", {
            "tool": "ensemble_audit",
            "confidence": verdict_data["score"],
            "result": verdict_data["verdict"],
            "logic": f"Consensus Reached. Score: {verdict_data['score']:.2f}",
            "output": "Consensus reached via weighted majority. Score: {verdict_data['score']:.2f}" if verdict_data["verdict"] != "HUNG_JURY" else "Models are in conflict. Escalating to Cloud..."
        })
            
        return {
            "verdict": verdict_data["verdict"],
            "score": verdict_data["score"],
            "votes": verdict_data["votes"],
            "reason": "Consensus reached via weighted majority." if verdict_data["verdict"] != "HUNG_JURY" else "Models are in conflict. Escalating to Cloud..."
        }

    def _log_audit(self, entry: Dict[str, Any]):
        log_path = config.full_log_path
        try:
            # We use JSONL for better performance at scale
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"⚠️ Failed to log audit: {e}")

# Global Instance
ensemble = ConsensusEngine()
