import asyncio
from tools.infrastructure.orchestrator import spawn_swarm
from tools.audit.gemini_reviewer import gemini_code_review, gemini_research
from tools.audit.supervisor_agent import run_supervisor_audit
from tools.memory.repo_mapper import scan_repo
from tools.utils.error_memory import remember_fix, recall_fix
from tools.utils.backtracker import save_checkpoint, restore_checkpoint
from tools.execution.sandbox_runner import run_code_safely
from tools.utils.bayesian import tune_swarm
from tools.audit.consult_architect import consult_brain
from tools.utils.maze_protocol import backward_verify
from tools.audit.guardrail_agent import run_guardrail_audit
from tools.audit.linter_autofix import autofix_linter

async def test_swarm_performance():
    """
    Triggers a swarm objective to verify:
    1. Parallel Task Decomposition.
    2. Hivemind Recall integration.
    3. Concurrency Slot Management.
    """
    objective = "Fix hydration mismatch and optimize JSON-LD schema in the Next.js portfolio."
    
    # Mock Tools
    tools = {
        "scan_repo": scan_repo,
        "review_code_with_gemini": gemini_code_review,
        "research_with_gemini": gemini_research,
        "consult_supervisor": run_supervisor_audit,
        "remember_fix": remember_fix,
        "recall_fix": recall_fix,
        "save_checkpoint": save_checkpoint,
        "restore_checkpoint": restore_checkpoint,
        "run_code_safely": run_code_safely,
        "tune_swarm": tune_swarm,
        "consult_hivemind": consult_brain,
        "maze_verification": backward_verify,
        "guardrail_audit": run_guardrail_audit,
        "autofix_linter": autofix_linter
    }

    print("🏁 Starting Master Swarm Performance Test...")
    report = await spawn_swarm(objective, tools, project_path=".")
    
    print("\n" + "="*50)
    print("📋 SWARM REPORT PREVIEW:")
    print(report[:1000] + "...")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(test_swarm_performance())
