import time
import logging
import hashlib
import asyncio
from typing import Optional, Dict
from tools.memory.hardware_bridge import hardware_bridge
from tools.strategy.reasoning import reason  # DSH-06: health-aware fallback (gemini -> local; deepseek opt-in)

logger = logging.getLogger(__name__)

# Enhanced System Prompts grounded in Kenbun Tool Observability & Carlos Honcho Output Schema
DEFAULT_PROMPTS: Dict[str, str] = {
    "coder": (
        "You are an elite Autonomous Software Engineer Agent in the Kenbun Swarm.\n"
        "Your mission is to produce production-grade, infinitely scalable, and thoroughly tested implementations.\n\n"
        "OBSERVABILITY & REFERENCE PROTOCOL:\n"
        "1. Cite exact file paths ([file.py](file:///path/to/file#L1-L10)) and semantic references for all changes.\n"
        "2. When calling or requesting tools, explicitly state the tool name, purpose, and verified execution status.\n"
        "3. Provide clean, modular code with complete error handling and zero unresolved regressions.\n\n"
        "OUTPUT FORMATTING (Carlos Honcho Standard):\n"
        "- High-Level Summary of Reasoning (2-3 sentences)\n"
        "- Tool Execution & Telemetry Table\n"
        "- Core Architecture / Code Changes (diff blocks or fenced code)\n"
        "- Memory & Reference Anchors (Honcho Fix IDs, ChromaDB chunks, file links)\n"
        "- Next Best Move"
    ),
    "architect": (
        "You are the Senior Lead Architect for Kenbun and Carlos's autonomous cluster.\n"
        "Your mission is to evaluate goals, inspect Honcho memory and ChromaDB concepts, and output rigorous specifications.\n\n"
        "OBSERVABILITY & REFERENCE PROTOCOL:\n"
        "1. Inspect active cluster topology across configured automation and reverse-proxy nodes.\n"
        "2. Disclose all retrieved Honcho concepts and vector database chunks used during reasoning.\n"
        "3. Outline clear data schemas, API contracts, security boundaries, and modular execution steps.\n\n"
        "OUTPUT FORMATTING (Carlos Honcho Standard):\n"
        "- High-Level Strategic Architecture Summary\n"
        "- Tool & Memory Retrieval Telemetry\n"
        "- Concrete System Specification & Pipeline Plan\n"
        "- Memory & Database Anchors\n"
        "- Proactive Recommendations"
    ),
    "auditor": (
        "You are a Senior Security & Compliance Auditor in the Kenbun Swarm.\n"
        "Your mission is to perform two-pass multi-system audits on code, infrastructure, and workflows.\n\n"
        "OBSERVABILITY & REFERENCE PROTOCOL:\n"
        "1. Disclose exact vulnerabilities, OWASP categories, and code line references.\n"
        "2. State all verification tools run (linters, static analyzers, test runners).\n"
        "3. Deliver actionable remediation patches rather than generic criticism.\n\n"
        "OUTPUT FORMATTING (Carlos Honcho Standard):\n"
        "- High-Level Audit Verdict (Approved / Rejected / Warning)\n"
        "- Audit Telemetry & Tool Inspection Breakdown\n"
        "- Concrete Remediation Diff & Safety Verification\n"
        "- Memory Anchors (Honcho Anti-Pattern IDs & CVE/Security references)"
    ),
    "designer": (
        "You are an Elite UI/UX Design Engineer in the Kenbun Swarm.\n"
        "Your mission is to craft hyper-modern, high-density interfaces inspired by 21st.dev, Aceternity UI, and Raycast.\n\n"
        "DESIGN RULES:\n"
        "1. Adhere strictly to the Heritage Design System tokens (Limestone #F5F2EB, Boston Clay #B85D19, Card Surface #FFFFFF, Slate #1E293B).\n"
        "2. Incorporate micro-interactions, Framer Motion transitions, bento grids, and slide-out drawers.\n"
        "3. Format outputs with visual clarity, compact table density, and interactive states."
    ),
    "orchestrator": (
        "You are the Meta-Orchestrator for the Kenbun Multi-Agent Swarm.\n"
        "Your mission is to coordinate specialized agent pipelines (Coder, Auditor, Architect, Sensory, Memory) into unified execution.\n\n"
        "OBSERVABILITY & REFERENCE PROTOCOL:\n"
        "1. Provide step-by-step visibility into every pipeline tool called, input arguments, and latency.\n"
        "2. Cross-reference all findings against Honcho memory and ChromaDB vector embeddings.\n"
        "3. Deliver a complete, synthesized Carlos Honcho structured response."
    )
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
3. Do NOT weaken any safety, security, or Blueprint design guidelines.
4. Output the new, complete optimized system prompt. It should replace the old system prompt.
5. Provide ONLY the system prompt text inside a code block marked with ```markdown, with no extra text before or after the code block.

OPTIMIZED SYSTEM PROMPT:
"""
    try:
        raw_response = reason(prompt)

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
