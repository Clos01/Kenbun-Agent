import asyncio
import json
import urllib.request
import time
from core.tools.infrastructure.config import settings
from core.tools.strategy.strategy_manager import governor
from core.tools.strategy.token_governor import token_governor
from core.tools.audit.guardrail_agent import run_guardrail_audit
from core.tools.autonomic.autonomic_corrector import corrector
from core.tools.audit.mars_auditor import mars_auditor
from core.tools.infrastructure.parallel_manager import parallel_manager
from hivemind_memory.hive_memory import hive_memory
from core.tools.utils.maze_protocol import backward_verify

from core.tools.infrastructure.pipelines.bug_fix import build_bug_fix_pipeline
from core.tools.infrastructure.pipelines.code_review import build_code_review_pipeline
from core.tools.infrastructure.pipelines.research import build_research_pipeline
from core.tools.infrastructure.pipelines.shadow_test import build_shadow_test_pipeline
from core.tools.infrastructure.pipelines.design_ui import build_design_ui_pipeline
from core.tools.utils.orchestrator_helpers import _prune_log
from core.tools.utils.telemetry import log_tool_performance
from core.tools.infrastructure.queue_manager import log_to_dashboard, save_topology

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

async def _get_active_brain() -> str:
    primary_url = settings.PRIMARY_LLM_URL
    fallback_url = settings.FALLBACK_LLM_URL
    
    try:
        url = f"{primary_url}/models"
        with urllib.request.urlopen(url, timeout=0.5):
            return f"🧠 [PRIMARY-GATEWAY] ({settings.PRIMARY_LLM_MODEL})"
    except Exception:
        pass
        
    try:
        url = f"{fallback_url}/models"
        with urllib.request.urlopen(url, timeout=0.5):
            return f"🧠 [FALLBACK-GATEWAY] ({settings.FALLBACK_LLM_MODEL})"
    except Exception:
        pass
        
    return "☁️ [CLOUD-GATEWAY] (Failover Active)"

def get_timeout_multiplier() -> float:
    primary_url = settings.PRIMARY_LLM_URL
    if primary_url.endswith("/"):
        primary_url = primary_url[:-1]
    base_url = f"{primary_url}/models"
    try:
        with urllib.request.urlopen(base_url, timeout=1) as response:
            data = json.loads(response.read().decode())
            model_id = data["data"][0]["id"].lower()
            
            if "70b" in model_id: return 4.0
            if "32b" in model_id: return 2.5
            if "14b" in model_id: return 1.5
    except Exception:
        pass
    
    return settings.ASSEMBLY_TIMEOUT_MULTIPLIER

async def run_pipeline(
    workflow: str,
    task: str,
    tools: dict,
    project_path: str = "",
    file_path: str = "",
    code_snippet: str = "",
    tech_key: str = "",
    tasks_ref: list = None,
    task_index: int = -1
) -> str:
    if workflow not in PIPELINES:
        return f"❌ Unknown pipeline: {workflow}"
        
    report = []
    log_to_dashboard(f"Initializing ⚡️ {workflow.upper()} Pipeline...")
    
    pipeline_def = PIPELINES[workflow]
    state = {
        "task": task,
        "project_path": project_path,
        "file_path": file_path,
        "code_snippet": code_snippet,
        "tech_key": tech_key,
        "report": report
    }
    
    try:
        if tasks_ref and task_index >= 0:
            tasks_ref[task_index]["status"] = "active"
            tasks_ref[task_index]["model"] = await _get_active_brain()
            save_topology(tasks_ref, {"event": "pipeline_start", "workflow": workflow})
            
        pipeline_funcs = pipeline_def["builder"]()
        
        for step_name, tool_name, logic_fn in pipeline_funcs:
            print(f"[{workflow.upper()}] Step: {step_name} (Tool: {tool_name})")
            log_to_dashboard(f"Running: {step_name}...")
            
            if tool_name not in tools:
                msg = f"⚠️ Tool {tool_name} not provided to pipeline. Skipping."
                print(msg)
                report.append(msg)
                continue
                
            start_time = time.time()
            success = False
            
            try:
                def _run_tool():
                    return logic_fn(state, tools[tool_name])
                    
                multiplier = get_timeout_multiplier()
                timeout_val = settings.BASE_TIMEOUT * multiplier
                
                result = await asyncio.wait_for(asyncio.to_thread(_run_tool), timeout=timeout_val)
                report.append(f"✅ **{step_name}:** Success")
                success = True
            except asyncio.TimeoutError:
                msg = f"❌ **{step_name}:** TIMEOUT ({timeout_val}s)"
                print(msg)
                report.append(msg)
                corrector.record_failure(workflow, tool_name, "timeout")
                governor.record_failure(tool_name)
            except Exception as e:
                msg = f"❌ **{step_name}:** ERROR - {e}"
                print(msg)
                report.append(msg)
                corrector.record_failure(workflow, tool_name, "crash")
                governor.record_failure(tool_name)
                
            elapsed = time.time() - start_time
            log_tool_performance(tool_name, elapsed, success)
            if success:
                governor.record_success(tool_name)
                corrector.record_success(workflow, tool_name)
                
            if tasks_ref and task_index >= 0:
                save_topology(tasks_ref, {"event": "step_complete", "step": step_name})
                
        if tasks_ref and task_index >= 0:
            tasks_ref[task_index]["status"] = "completed"
            save_topology(tasks_ref, {"event": "pipeline_complete", "workflow": workflow})
            
    except Exception as e:
        report.append(f"❌ FATAL PIPELINE CRASH: {e}")
        
    print("🛡️ System 2: Running MARS Boundary Audit...")
    mars_cat = "bug_fix"
    if workflow == "ui_design": mars_cat = "ui"
    if workflow == "security_audit": mars_cat = "security"
    
    current_diff = state.get("last_diff", "")
    if not current_diff and "code_snippet" in state:
        current_diff = state["code_snippet"]
        
    if current_diff:
        is_on_curve, message = mars_auditor.evaluate_boundary(mars_cat, current_diff)
        if not is_on_curve:
            report.append(f"\n⚠️ **MARS BOUNDARY BREACH:** {message}")
            print(f"   ⚠️ MARS Breach: {message}")
        else:
            report.append(f"\n✅ **MARS BOUNDARY VERIFIED:** {message}")

    return "\n\n".join(report)
