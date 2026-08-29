import json
import logging
from typing import Dict, Any
from tools.audit.gemini_reviewer import call_gemini_pro
from tools.memory.hardware_bridge import hardware_bridge

logger = logging.getLogger(__name__)

def evaluate_agent_run(
    agent_id: str,
    task_id: str,
    run_id: str,
    prompt_hash: str,
    task_description: str,
    agent_output: str,
    speed_sec: float,
    token_cost: float,
    is_ui_task: bool = False
) -> Dict[str, Any]:
    """
    Evaluates the correctness, style, and quality of an agent's output.
    Stores the evaluation metrics in the hardware-agnostic database layer.
    """
    logger.info(f"📊 Evaluating agent run: {run_id} (Agent: {agent_id})")
    
    # 1. Draft evaluation prompt
    eval_prompt = f"""
As the Kenbun System 2 Auditor, evaluate the following agent execution trace and output.

TASK DESCRIPTION:
{task_description}

AGENT OUTPUT/CODE:
{agent_output}

IS UI TASK: {is_ui_task}

Evaluate the following criteria:
1. **Correctness**: Did the agent fully address and solve the task description? (Weight: 60%)
2. **Quality & Formatting**: Is the code clean, well-formatted, and free of syntax/logic errors? (Weight: 20%)
3. **Blueprint Compliance**: If this is a UI task, does it strictly adhere to the Blueprint Design System tokens (e.g. Limestone/Boston Clay palettes, Inter/Outfit typography, specific border radii)? (Weight: 20%)

Return your evaluation STRICTLY as a JSON object with the following keys:
- "correctness_score": float between 0.0 and 1.0
- "quality_score": float between 0.0 and 1.0
- "compliance_score": float between 0.0 and 1.0 (1.0 if not UI task)
- "feedback": a detailed critique pointing out specific errors, missing requirements, or areas of improvement.

JSON:
"""

    # 2. Call LLM
    try:
        raw_response = call_gemini_pro(eval_prompt)
        # Extract JSON from markdown response if present
        start_idx = raw_response.find('{')
        end_idx = raw_response.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_str = raw_response[start_idx:end_idx+1]
            eval_results = json.loads(json_str)
        else:
            raise ValueError("No JSON block found in evaluator response")
            
        correctness = float(eval_results.get("correctness_score", 0.0))
        quality = float(eval_results.get("quality_score", 0.0))
        compliance = float(eval_results.get("compliance_score", 1.0))
        feedback = str(eval_results.get("feedback", "No feedback provided."))
        
        # Calculate combined score
        score = (correctness * 0.6) + (quality * 0.2) + (compliance * 0.2)
        
    except Exception as e:
        logger.error(f"❌ Failed to parse agent evaluation: {e}")
        # Fallback evaluation on error
        score = 0.5
        compliance = 1.0
        feedback = f"Evaluator failed to parse model response. Error: {str(e)}"

    # 3. Save to database via hardware bridge
    eval_data = {
        "agent_id": agent_id,
        "task_id": task_id,
        "run_id": run_id,
        "prompt_hash": prompt_hash,
        "score": score,
        "speed_sec": speed_sec,
        "token_cost": token_cost,
        "compliance_score": compliance,
        "eval_feedback": feedback
    }
    
    saved = hardware_bridge.save_evaluation(eval_data)
    if saved:
        logger.info(f"✅ Saved evaluation for run {run_id}. Score: {score:.2%}")
    else:
        logger.warning(f"⚠️ Failed to save evaluation for run {run_id}.")
        
    return eval_data
