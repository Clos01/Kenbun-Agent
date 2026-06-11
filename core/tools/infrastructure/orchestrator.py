"""
The Orchestrator — Meta-tool that chains all Pro Stack tools into intelligent workflows.

Instead of manually calling 7 tools in sequence, the AI calls ONE tool:
    orchestrate("bug_fix", task="Fix the auth bypass", file_path="src/login.py")

The orchestrator runs the full pipeline and returns a structured report.

Architecture: State-machine engine with 3 built-in pipelines.
Designed in collaboration with Gemini 2.0 Flash.
"""
import asyncio
import json
import urllib.request
import time
from pathlib import Path

# Import centralized settings
from core.tools.infrastructure.config import settings

from core.tools.strategy.strategy_manager import governor
from core.tools.strategy.token_governor import token_governor
from core.tools.utils.notifications import send_notification
from core.tools.audit.reflection_agent import reflect_and_distill as _reflect_and_distill
from core.tools.utils.sync_intelligence import run_sync
from core.tools.strategy.decision_logic import router
from core.tools.audit.guardrail_agent import run_guardrail_audit
from core.tools.autonomic.autonomic_corrector import corrector
from core.tools.audit.mars_auditor import mars_auditor
from core.tools.infrastructure.parallel_manager import parallel_manager
from core.hivemind_memory.hive_memory import hive_memory
from core.tools.utils.maze_protocol import backward_verify
from core.tools.infrastructure.pipelines.bug_fix import build_bug_fix_pipeline
from core.tools.infrastructure.pipelines.code_review import build_code_review_pipeline
from core.tools.infrastructure.pipelines.research import build_research_pipeline
from core.tools.infrastructure.pipelines.shadow_test import build_shadow_test_pipeline
from core.tools.infrastructure.pipelines.design_ui import build_design_ui_pipeline
from core.tools.utils.orchestrator_helpers import _prune_log
from core.tools.utils.telemetry import log_tool_performance

# --- 2. GHOST UTILS (Prevent Crashes) ---
TELEMETRY_PATH = settings.BRAIN_HEALTH_DIR / "live_telemetry.json"

def log_to_dashboard(message: str):
    """Sends a message to the UI dashboard by writing to live_telemetry.json."""
    print(f"🖥️ [ASSEMBLY] {message}")
    try:
        data = {"timestamp": time.time(), "message": message, "type": "log"}
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(data) + "\n")
    except (IOError, OSError, json.JSONDecodeError) as e:
        print(f"⚠️ Dashboard log failed: {e}")

async def check_connectivity(ip: str) -> bool:
    """Checks if the Remote PC is reachable via non-blocking ping."""
    import platform
    try:
        system = platform.system().lower()
        if "windows" in system:
            cmd = ["ping", "-n", "1", "-w", "1000", ip]
        else:
            # -c 1 (1 count), -W 1 (1s timeout on Linux), -t 1 (1s timeout on macOS)
            timeout_flag = "-t" if "darwin" in system else "-W"
            cmd = ["ping", "-c", "1", timeout_flag, "1", ip]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=1.5)
        return proc.returncode == 0
    except (asyncio.TimeoutError, Exception):
        return False

def save_topology(tasks_ref: list, data: dict):
    """Updates the real-time assembly topology for the frontend."""
    if tasks_ref is None:
        tasks_ref = []
    
    tasks_ref.append(data)
    
    try:
        topology_data = {"timestamp": time.time(), "topology": tasks_ref, "type": "topology"}
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(topology_data) + "\n")
    except (IOError, OSError, json.JSONDecodeError) as e:
        print(f"⚠️ Topology save failed: {e}")


# ============================================================
# PIPELINE DEFINITIONS
# ============================================================


# ============================================================
# PIPELINE REGISTRY
# ============================================================

PIPELINES = {
    "bug_fix": {
        "builder": build_bug_fix_pipeline,
        "description": "Fix a bug: scan → recall → checkpoint → analyze → test → remember",
    },
    "code_review": {
        "builder": build_code_review_pipeline,
        "description": "Review code: scan → Gemini review → docs → supervisor → consensus",
    },
    "research_implement": {
        "builder": build_research_pipeline,
        "description": "Research & build: Gemini research → scan → checkpoint → supervisor",
    },
    "shadow_test": {
        "builder": build_shadow_test_pipeline,
        "description": "Background testing: read → analyze → draft → supervisor → sandbox",
    },
    "design_ui": {
        "builder": build_design_ui_pipeline,
        "description": "Strategic UI Design: discovery → research → artifact generation → 5D audit",
    },
}


# ============================================================
# HELPERS
# ============================================================


def extract_json_array(text: str) -> str:
    """Robustly extracts the first JSON array found in text using a stack-based matcher."""
    if not text:
        return None
    start_idx = text.find('[')
    if start_idx == -1:
        return None
    
    depth = 0
    in_string = False
    escape = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if escape:
            escape = False
            continue
            
        if char == '\\':
            escape = True
            continue
            
        if char == '"':
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '[':
                depth += 1
            elif char == ']':
                depth -= 1
                if depth == 0:
                    return text[start_idx:i+1]
                    
    return None


from core.tools.infrastructure.routers.router_logic import spawn_assembly, run_pipeline
# ============================================================
# STATE MACHINE ENGINE
# ============================================================

# --- 6. PRO STACK ENTRY POINT ---

def orchestrate(workflow: str, task: str, file_path: str = "", project_path: str = ".", code_snippet: str = "", tech_key: str = ""):
    """
    Synchronous entry point for the Pro Stack.
    Usage: orchestrate("bug_fix", task="Fix the leak", file_path="app.py")
    """
    import asyncio
    from core.tools.audit.gemini_reviewer import gemini_code_review, gemini_research
    from core.tools.audit.supervisor_agent import run_supervisor_audit
    from core.tools.memory.repo_mapper import scan_repo
    from core.tools.utils.error_memory import remember_fix, recall_fix
    from core.tools.utils.backtracker import save_checkpoint, restore_checkpoint
    from core.tools.execution.sandbox_runner import run_code_safely as run_code_safely
    from core.tools.utils.bayesian import tune_assembly
    from core.tools.audit.consult_architect import consult_brain
    from core.tools.audit.discovery_agent import generate_discovery_form
    from core.tools.audit.linter_autofix import autofix_linter

    # Map actual functions to the tool registry
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
        "reflect_and_distill": _reflect_and_distill,
        "guardrail_audit": run_guardrail_audit,
        "maze_verification": backward_verify,
        "tune_assembly": tune_assembly,
        "consult_hivemind": consult_brain,
        "generate_discovery_form": generate_discovery_form,
        "autofix_linter": autofix_linter
    }

    # Run the async pipeline
    return asyncio.run(run_pipeline(
        workflow=workflow,
        task=task,
        tools=tools,
        project_path=project_path,
        file_path=file_path,
        code_snippet=code_snippet,
        tech_key=tech_key
    ))

def assembly(objective: str, project_path: str = "."):
    """
    Synchronous entry point for triggering a full autonomous assembly.
    Usage: assembly("Build a new landing page for the burger shop")
    """
    import asyncio
    from core.tools.audit.gemini_reviewer import gemini_code_review, gemini_research
    from core.tools.audit.supervisor_agent import run_supervisor_audit
    from core.tools.memory.repo_mapper import scan_repo
    from core.tools.utils.error_memory import remember_fix, recall_fix
    from core.tools.utils.backtracker import save_checkpoint, restore_checkpoint
    from core.tools.execution.sandbox_runner import run_code_safely
    from core.tools.utils.bayesian import tune_assembly
    from core.tools.audit.guardrail_agent import run_guardrail_audit
    from core.tools.utils.maze_protocol import backward_verify
    from core.tools.audit.linter_autofix import autofix_linter

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
        "reflect_and_distill": _reflect_and_distill,
        "guardrail_audit": run_guardrail_audit,
        "maze_verification": backward_verify,
        "tune_assembly": tune_assembly,
        "autofix_linter": autofix_linter
    }

    return asyncio.run(spawn_assembly(objective, tools, project_path))

if __name__ == "__main__":
    # Example usage
    import argparse
    parser = argparse.ArgumentParser(description="Kenbun Orchestrator")
    parser.add_argument("workflow", help="Pipeline to run (bug_fix, code_review, etc.)")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--file", default="", help="Target file path")
    
    args = parser.parse_args()
    print(orchestrate(args.workflow, task=args.task, file_path=args.file))
