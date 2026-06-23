import time
import logging
import hashlib
import json
import asyncio
from typing import Dict, Any, Optional
from tools.infrastructure.config import settings
from tools.memory.hardware_bridge import hardware_bridge
from tools.audit.gemini_reviewer import call_gemini_pro

logger = logging.getLogger(__name__)

# Fallback basic system prompts
DEFAULT_PROMPTS = {
    "coder": "You are a professional software engineer agent. Write clean, modular, and well-tested code.",
    "auditor": "You are a security auditor. Inspect code for vulnerabilities, syntax errors, and style compliance.",
    "designer": "You are a Heritage UI designer. Adhere strictly to Limestone and Boston Clay palette tokens."
}

def get_agent_prompt(agent_id: str) -> str:
    """Gets the latest prompt for an agent, falling back to defaults."""
    record = hardware_bridge.get_latest_prompt(agent_id)
    if record:
        return record["system_prompt"]
    return DEFAULT_PROMPTS.get(agent_id, "You are a helpful AI assistant.")

def optimize_agent_prompt(
    agent_id: str,
    original_prompt: str,
    failed_task: str,
    failed_output: str,
    eval_score: float,
    feedback: str
) -> Optional[str]:
    """
    Invokes Gemini to analyze a failed execution and draft an improved system prompt.
    """
    logger.info(f"🔄 Optimizing prompt for agent '{agent_id}' (Current score: {eval_score:.2%})")
    
    prompt = f"""
You are the Kenbun Self-Improvement Driver. Your objective is to optimize the system prompt of an AI Agent to improve its performance.

AGENT ID: {agent_id}

CURRENT SYSTEM PROMPT:
\"\"\"
{original_prompt}
\"\"\"

THE AGENT FAILED ON THIS TASK:
\"\"\"
{failed_task}
\"\"\"

AGENT'S SUBOPTIMAL OUTPUT:
\"\"\"
{failed_output}
\"\"\"

EVALUATION VERDICT (Score: {eval_score:.2%}):
\"\"\"
{feedback}
\"\"\"

INSTRUCTIONS FOR OPTIMIZATION:
1. Analyze the failure and the auditor feedback.
2. Incorporate best practices from state-of-the-art agent architectures (e.g., Nous Hermes reasoning cues, Figure AI Helix step-by-step physical action grounding, explicit XML tags, strict boundary rules).
3. Do NOT weaken any safety, security, or Heritage design guidelines.
4. Output the new, complete optimized system prompt. It should replace the old system prompt.
5. Provide ONLY the system prompt text inside a code block marked with ```markdown, with no extra text before or after the code block.

OPTIMIZED SYSTEM PROMPT:
"""
    try:
        raw_response = call_gemini_pro(prompt)
        
        # Extract prompt from markdown block
        start_tag = "```markdown"
        end_tag = "```"
        
        if start_tag in raw_response:
            start_idx = raw_response.find(start_tag) + len(start_tag)
            end_idx = raw_response.find(end_tag, start_idx)
            new_prompt = raw_response[start_idx:end_idx].strip()
        elif "```" in raw_response:
            # General code block fallback
            start_idx = raw_response.find("```") + 3
            # Check for language specifier line
            newline_idx = raw_response.find("\n", start_idx)
            if newline_idx != -1 and newline_idx - start_idx < 10:
                start_idx = newline_idx + 1
            end_idx = raw_response.find("```", start_idx)
            new_prompt = raw_response[start_idx:end_idx].strip()
        else:
            new_prompt = raw_response.strip()
            
        if not new_prompt or len(new_prompt) < 10:
            logger.warning("⚠️ Optimization returned an empty or too short prompt.")
            return None
            
        return new_prompt
    except Exception as e:
        logger.error(f"❌ Gemini optimization failed: {e}")
        return None

def run_self_improvement_cycle() -> int:
    """
    Scans recent evaluations and improves poorly performing prompts.
    Returns the number of optimized prompts.
    """
    logger.info("🤖 Starting self-improvement cycle...")
    optimized_count = 0
    
    # Check budget before proceeding
    from tools.strategy.token_governor import token_governor
    if token_governor.get_remaining_budget() < 0.10:
        logger.warning("💸 Budget too low for self-improvement cycle. Skipping.")
        return 0
        
    # We inspect standard agent categories
    agents_to_check = ["coder", "auditor", "designer"]
    for agent_id in agents_to_check:
        evaluations = hardware_bridge.get_evaluations(agent_id, limit=5)
        if not evaluations:
            continue
            
        # Look for the worst execution that is below threshold (0.85)
        poor_runs = [e for e in evaluations if e["score"] < 0.85]
        if not poor_runs:
            logger.info(f"✅ Agent '{agent_id}' has stable performance in recent runs.")
            continue
            
        # Pick the lowest scoring run
        worst_run = min(poor_runs, key=lambda x: x["score"])
        logger.info(f"⚠️ Found suboptimal run for agent '{agent_id}': Run ID {worst_run['run_id']} (Score: {worst_run['score']:.2%})")
        
        # Get the prompt that was used (or default)
        original_prompt = get_agent_prompt(agent_id)
        
        # Extract task description (we will fetch from trace or fallback to general description)
        task_desc = worst_run.get("task_id", "A general task") # Simple mapping for trace
        feedback = worst_run.get("eval_feedback", "Needs improvement.")
        
        # Fetch the suboptimal output from the trace if possible (simulated for now, or fallback)
        suboptimal_output = "No code output preserved in evaluation log."
        
        # Optimize prompt
        new_prompt = optimize_agent_prompt(
            agent_id=agent_id,
            original_prompt=original_prompt,
            failed_task=task_desc,
            failed_output=suboptimal_output,
            eval_score=worst_run["score"],
            feedback=feedback
        )
        
        if new_prompt:
            prompt_hash = hashlib.sha256(new_prompt.encode("utf-8")).hexdigest()
            meta_data = {
                "parent_hash": worst_run["prompt_hash"],
                "trigger_run_id": worst_run["run_id"],
                "score_before": worst_run["score"],
                "timestamp": time.time()
            }
            
            # Save the optimized prompt
            saved = hardware_bridge.save_prompt(
                prompt_hash=prompt_hash,
                agent_id=agent_id,
                system_prompt=new_prompt,
                meta_data=meta_data
            )
            if saved:
                logger.info(f"🚀 Saved optimized system prompt for '{agent_id}' (Hash: {prompt_hash[:8]})")
                optimized_count += 1
                
    return optimized_count

class SelfImprovementDaemon:
    def __init__(self, interval_seconds: int = 3600):
        self.interval = interval_seconds
        self.running = False
        
    async def start(self):
        self.running = True
        logger.info(f"✨ Self Improvement Daemon started (Interval: {self.interval}s)")
        while self.running:
            try:
                run_self_improvement_cycle()
            except Exception as e:
                logger.error(f"❌ Error in self-improvement daemon: {e}")
            await asyncio.sleep(self.interval)
            
    def stop(self):
        self.running = False
        logger.info("🛑 Self Improvement Daemon stopped")
