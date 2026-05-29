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
import re
import urllib.request
import time
from pathlib import Path

# Import centralized settings
from tools.infrastructure.config import settings

from tools.strategy.strategy_manager import governor
from tools.strategy.token_governor import token_governor
from tools.utils.notifications import send_notification
from tools.audit.reflection_agent import reflect_and_distill as _reflect_and_distill
from tools.utils.sync_intelligence import run_sync
from tools.strategy.decision_logic import router
from tools.audit.guardrail_agent import run_guardrail_audit
from tools.autonomic.autonomic_corrector import corrector
from tools.audit.mars_auditor import mars_auditor
from tools.infrastructure.parallel_manager import parallel_manager
from hivemind_memory.hive_memory import hive_memory
from tools.utils.maze_protocol import backward_verify
from tools.infrastructure.pipelines.bug_fix import build_bug_fix_pipeline
from tools.infrastructure.pipelines.code_review import build_code_review_pipeline
from tools.infrastructure.pipelines.research import build_research_pipeline
from tools.infrastructure.pipelines.shadow_test import build_shadow_test_pipeline
from tools.infrastructure.pipelines.design_ui import build_design_ui_pipeline
from tools.utils.orchestrator_helpers import _prune_log
from tools.utils.telemetry import log_tool_performance

# --- 2. GHOST UTILS (Prevent Crashes) ---
TELEMETRY_PATH = settings.BRAIN_HEALTH_DIR / "live_telemetry.json"

def log_to_dashboard(message: str):
    """Sends a message to the UI dashboard by writing to live_telemetry.json."""
    print(f"🖥️ [SWARM] {message}")
    try:
        data = {"timestamp": time.time(), "message": message, "type": "log"}
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(data) + "\n")
    except (IOError, OSError, json.JSONDecodeError) as e:
        print(f"⚠️ Dashboard log failed: {e}")

async def check_connectivity(ip: str) -> bool:
    """Checks if the Remote PC is reachable via non-blocking ping."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-t", "1", ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=1.5)
        return proc.returncode == 0
    except (asyncio.TimeoutError, Exception):
        return False

def save_topology(tasks_ref: list, data: dict):
    """Updates the real-time swarm topology for the frontend."""
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
    """Robustly extracts the first JSON array found in text."""
    if not text:
        return None
    start = text.find('[')
    end = text.rfind(']')
    if start == -1 or end == -1 or end < start:
        return None
    return text[start:end+1]


async def spawn_swarm(objective: str, tools: dict, project_path: str = "") -> str:
    """
    High-level swarm engine.
    1. Queen decomposes objective into tasks.
    2. Bayesian Governor assigns workers.
    3. Workers execute and report back.
    """
    print(f"🐝 Swarm Objective: {objective}")
    
    # --- 0. PROJECT MANDATES ---
    mandates = ""
    rules_path = Path(project_path) / ".kenbun_rules.md"
    if rules_path.exists():
        with open(rules_path, "r") as f:
            mandates = f.read()
        print("📜 Found project mandates in .kenbun_rules.md")

    # --- 1. INTEGRITY GATING (HME Router) ---
    from tools.strategy.hme_router import hme_router
    route_info = hme_router.route_task(objective)
    integrity_instruction = ""
    if route_info.get("integrity_flag") == "CHUNKING_REQUIRED":
        print(f"⚖️ HME Integrity: High volume detected ({route_info.get('estimated_volume')}). Forcing chunked decomposition.")
        integrity_instruction = "IMPORTANT: This objective is MASSIVE. You MUST decompose it into small, atomic chunks (max 100 lines per task) to prevent LLM truncation. Do NOT combine multiple features into one task."

    # --- 2. DECOMPOSITION (The Queen) ---
    queen_prompt = (
        f"OBJECTIVE: {objective}\n\n"
        f"PROJECT MANDATES:\n{mandates}\n\n"
        f"{integrity_instruction}\n"
        "As the Kenbun Queen, decompose this objective into a JSON list of atomic tasks. "
        "Strictly follow the PROJECT MANDATES if provided. "
        "Each task must have: 'id', 'label', 'worker_type' (coder, auditor, designer), and 'task_description'. "
        "OPTIMIZATION: Group parallelizable tasks (research, audits, scans) together at the start or between blocking steps to maximize swarm efficiency. "
        "Format as valid JSON: [{{'id': '...', 'label': '...', 'worker_type': '...', 'task_description': '...'}}]"
    )
    
    try:
        # Use Gemini 3.1 Pro for high-reasoning decomposition
        from tools.audit.gemini_reviewer import call_gemini_pro
        raw_decomposition = call_gemini_pro(queen_prompt)
        
        # Simple extraction of JSON from markdown if needed
        json_str = extract_json_array(raw_decomposition)
        if not json_str:
            return f"❌ Swarm decomposition format error. No JSON array found in raw output: {raw_decomposition}"
        
        tasks = json.loads(json_str)
        if not isinstance(tasks, list):
            raise ValueError(f"Swarm decomposition error. Parsed JSON is not a list: {raw_decomposition}")
            
        # Initialize tasks with pending status for the Flowchart
        for i, t in enumerate(tasks):
            t["id"] = f"task-{i}"
            t["status"] = "pending"
            
            # --- MARS BOUNDARY INJECTION ---
            category = "bug_fix"
            if "ui" in t["label"].lower() or "designer" in t["worker_type"].lower(): category = "ui"
            if "security" in t["label"].lower(): category = "security"
            if "architecture" in t["label"].lower(): category = "architecture"
            
            mars_guidance = mars_auditor.get_guidance(category)
            if mars_guidance:
                t["task_description"] = f"{t['task_description']}\n\n{mars_guidance}"
        
    except (json.JSONDecodeError, ValueError, Exception) as e:
        return f"❌ Swarm decomposition failed: {e}"

    report = [
        f"# 🐝 Swarm Objective: {objective}",
        f"**Tasks identified:** {len(tasks)}",
        ""
    ]

    # --- 2. EXECUTION ---
    print(f"📋 TASKS IDENTIFIED: {[t.get('label') for t in tasks]}")
    task_groups = parallel_manager.decompose_parallel_groups(tasks)
    
    for group in task_groups:
        if len(group) > 1:
            print(f"⚡ EXECUTING PARALLEL BATCH: {len(group)} tasks")
            async_tasks = []
            for t_meta in group:
                t_meta["status"] = "active"
                worker_type = t_meta["worker_type"]
                label = t_meta["label"]
                desc = t_meta["task_description"]
                
                # Determine workflow
                workflow_path = router.get_strategy_path(desc)
                workflow_map = {
                    "SECURITY_HARDENING_PATH": "code_review",
                    "UI_COMPONENT_BUILD": "research_implement",
                    "STANDARD_BUG_FIX": "bug_fix",
                    "ARCHITECT_RESEARCH_PATH": "research_implement",
                    "UI_FIX_PATH": "bug_fix",
                    "STANDARD_EXECUTION": "bug_fix"
                }
                wf = workflow_map.get(workflow_path, "bug_fix")
                
                async_tasks.append(
                    parallel_manager.run_task(
                        run_pipeline,
                        workflow=wf,
                        task=desc,
                        tools=tools,
                        project_path=project_path,
                        tasks_ref=tasks,
                        task_index=tasks.index(t_meta)
                    )
                )
            
            group_results = await asyncio.gather(*async_tasks)
            for res, t_meta in zip(group_results, group):
                t_meta["status"] = "completed"
                report.append(res)
        else:
            # Sequential / Blocking task
            task_meta = group[0]
            task_meta["status"] = "active"
            label = task_meta["label"]
            desc = task_meta["task_description"]
            
            workflow_path = router.get_strategy_path(desc)
            workflow_map = {
                "SECURITY_HARDENING_PATH": "code_review",
                "UI_COMPONENT_BUILD": "research_implement",
                "STANDARD_BUG_FIX": "bug_fix",
                "ARCHITECT_RESEARCH_PATH": "research_implement",
                "UI_FIX_PATH": "bug_fix",
                "STANDARD_EXECUTION": "bug_fix"
            }
            workflow = workflow_map.get(workflow_path, "bug_fix")
            
            task_result = await run_pipeline(
                workflow=workflow,
                task=desc,
                tools=tools,
                project_path=project_path,
                tasks_ref=tasks,
                task_index=tasks.index(task_meta)
            )
            task_meta["status"] = "completed"
            report.append(task_result)

    summary = f"Swarm completed {len(tasks)} tasks."
    send_notification("Kenbun Swarm", summary)
    
    # Trigger background sync to remote PC
    print("📡 Swarm complete. Triggering intelligence sync...")
    run_sync()
    
    return "\n\n".join(report)


# ============================================================
# STATE MACHINE ENGINE
# ============================================================

MAX_STEPS = 20  # Safety: prevent infinite loops
TOOL_TIMEOUT = settings.BASE_TIMEOUT  # Safety: baseline timeout

async def _get_active_brain() -> str:
    """Detects where the "Brain" is currently located based on active configuration."""
    primary_url = settings.models.primary_llm_url
    fallback_url = settings.models.fallback_llm_url
    
    # Check primary
    try:
        url = f"{primary_url}/models"
        with urllib.request.urlopen(url, timeout=0.5) as response:
            return f"🧠 [PRIMARY-GATEWAY] ({settings.models.primary_llm_model})"
    except (urllib.error.URLError, Exception):
        pass
        
    # Check fallback
    try:
        url = f"{fallback_url}/models"
        with urllib.request.urlopen(url, timeout=0.5) as response:
            return f"🧠 [FALLBACK-GATEWAY] ({settings.models.fallback_llm_model})"
    except (urllib.error.URLError, Exception):
        pass
        
    return "☁️ [CLOUD-GATEWAY] (Failover Active)"

def get_timeout_multiplier() -> float:
    """Detects the loaded model in the primary gateway and adjusts the timeout multiplier."""
    primary_url = settings.models.primary_llm_url
    if primary_url.endswith("/"):
        primary_url = primary_url[:-1]
    base_url = f"{primary_url}/models"
    try:
        with urllib.request.urlopen(base_url, timeout=1) as response:
            data = json.loads(response.read().decode())
            model_id = data["data"][0]["id"].lower()
            
            # Logic: Larger models = Higher Latency
            if "70b" in model_id:
                return 4.0
            if "32b" in model_id:
                return 2.5
            if "14b" in model_id:
                return 1.5
    except (urllib.error.URLError, Exception):
        pass
    
    return settings.SWARM_TIMEOUT_MULTIPLIER

# Re-evaluate multiplier at runtime based on model
# Removed static DYNAMIC_MULTIPLIER


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
    """
    Execute a named pipeline using the state-machine engine.

    Args:
        workflow: Pipeline name ("bug_fix", "code_review", "research_implement")
        task: Natural language task description
        tools: Dict of tool functions keyed by name
        project_path: Project root for scan_repo
        file_path: Target file
        code_snippet: Code to review/fix
        tech_key: Tech key for doc grounding

    Returns:
        Formatted report of the entire pipeline execution.
    """
    if workflow not in PIPELINES:
        available = "\n".join(f"  • **{k}** — {v['description']}" for k, v in PIPELINES.items())
        return f"❌ Unknown workflow: `{workflow}`\n\nAvailable workflows:\n{available}"

    # --- INITIALIZE STATE ---
    state = {
        "task": task,
        "project_path": project_path,
        "file_path": file_path,
        "code_snippet": code_snippet,
        "tech_key": tech_key,
        "repo_map": None,
        "past_fixes": None,
        "research_result": None,
        "gemini_analysis": None,
        "review_result": None,
        "sandbox_result": None,
        "supervisor_result": None,
        "checkpoint_result": None,
        "memory_result": None,
        "backtrack_count": 0,
    }

    # --- BUILD PIPELINE ---
    pipeline_def = PIPELINES[workflow]
    steps = pipeline_def["builder"](tools)

    # --- EXECUTE ---
    report = [
        f"# 🎯 Orchestrator: `{workflow}`",
        f"**Task:** {task}",
        f"**Pipeline:** {pipeline_def['description']}",
        f"**Remaining Budget:** ${token_governor.get_remaining_budget():.4f}",
        "",
    ]
    
    # --- RECALL (The Hivemind) ---
    past_lessons = hive_memory.query(task, project=settings.PROJECT_NAME)
    if past_lessons:
        report.append("## 🧠 Hivemind Recall: Similar Past Fixes")
        for lesson in past_lessons:
            report.append(f"- **Project:** {lesson['project']}\n- **Lesson:** {lesson['task']}\n")
        state["memory_result"] = past_lessons

    step_count = 0
    consecutive_failures = 0

    for step in steps:
        step_count += 1
        if step_count > MAX_STEPS:
            report.append(f"\n⚠️ Safety limit reached ({MAX_STEPS} steps). Stopping.")
            break

        # --- COST CHECK (System 4) ---
        if not token_governor.can_spend(0.001):  # Minimal check
            report.append("\n⛔ **Budget Exceeded.** TokenGovernor has halted the swarm.")
            break
            
        # --- CIRCUIT BREAKER (System 2 Fallback) ---
        if consecutive_failures >= 3:
            report.append("\n⛔ **Circuit Breaker Tripped.** 3 consecutive tool failures detected. Halting pipeline. **Recommendation:** Run `consult_supervisor` to diagnose the underlying logic flaw.")
            print(f"   ⛔ Circuit Breaker tripped. Halting pipeline.")
            break

        step_id = step["id"]
        label = step["label"]

        # --- DYNAMIC EVALUATION (System 5: Reasoning) ---
        skip_fn = step.get("skip_if")
        if skip_fn and skip_fn(state):
            report.append(f"⏭️ Skipped: {label} (Logic condition met)")
            log_to_dashboard(f"STEP SKIPPED: {label}")
            continue

        # Optional: Ask Gemini if we actually need this step (Agentic Pruning)
        if step.get("optional") and state.get("research_result"):
             # Logic to prune redundant steps if research was enough
             pass

        # --- PREPARE INPUT ---
        try:
            input_fn = step["input"]
            tool_input = input_fn(state)
        except Exception as e:
            report.append(f"⚠️ Input prep failed for `{step_id}`: {e}")
            continue

        # --- EXECUTE TOOL ---
        print(f"🔧 [{step_count}] {label}")
        try:
            # --- STRATEGY LAYER (System 4) ---
            confidence = governor.get_tool_confidence(step_id)
            save_topology(tasks_ref, {"active_system": "governor", "tool": step_id, "status": "strategizing"})
            report.append(f"### Step {step_count}: {label}")
            report.append(f"> 🧠 **System 4 Confidence:** {confidence:.2%}")

            # --- TELEMETRY ---
            brain_source = await _get_active_brain()
            log_to_dashboard(f"{brain_source} | TOOL START: {step_id}")
            log_to_dashboard(f"INPUT -> {str(tool_input)[:100]}...")

            # Dynamic calibration per-step
            current_multiplier = get_timeout_multiplier()
            effective_timeout = TOOL_TIMEOUT * current_multiplier
            start_time = time.time()
            if asyncio.iscoroutinefunction(step["tool"]):
                result = await asyncio.wait_for(step["tool"](**tool_input), timeout=effective_timeout)
            else:
                # Wrap synchronous tools in a thread to avoid blocking the event loop
                result = await asyncio.wait_for(asyncio.to_thread(step["tool"], **tool_input), timeout=effective_timeout)
            duration = time.time() - start_time

            log_to_dashboard(f"OUTPUT <- {str(result)[:100]}...")
            save_topology(tasks_ref, {"active_system": "execution", "tool": step_id, "status": "success"})

            # --- UPDATE INTELLIGENCE & TELEMETRY ---
            governor.update_intelligence(step_id, workflow, success=True)
            log_tool_performance(step_id, success=True, duration=duration)
            consecutive_failures = 0 # Reset circuit breaker on success

            # Store result in state
            output_key = step.get("output_key")
            if output_key:
                state[output_key] = result
            
            # Add to full log for reflection - SAFELY & PRUNED
            safe_result = str(result) if result is not None else "None"
            new_log_entry = f"\n[STEP {step_count}] {label}\nRESULT: {safe_result[:1000]}...\n"
            state["full_log"] = _prune_log(state.get("full_log", "") + new_log_entry, 8000)

            # Truncate result for report (keep it readable) - SAFELY
            safe_result = str(result) if result is not None else "None"
            result_preview = safe_result[:800] if len(safe_result) > 800 else safe_result
            report.append(f"```\n{result_preview}\n```")
            report.append("")

        except asyncio.TimeoutError:
            duration = TOOL_TIMEOUT * settings.SWARM_TIMEOUT_MULTIPLIER
            error_msg = f"⏱️ `{step_id}` TIMED OUT after {duration}s. Swarm watchdog intervened."
            report.append(error_msg)
            print(f"   {error_msg}")
            consecutive_failures += 1
        except Exception as e:
            duration = time.time() - start_time if "start_time" in locals() else 0
            error_msg = f"❌ `{step_id}` failed: {e}"
            report.append(error_msg)
            print(f"   {error_msg}")
            consecutive_failures += 1

            # --- UPDATE INTELLIGENCE & TELEMETRY (FAILURE) ---
            governor.update_intelligence(step_id, workflow, success=False)
            log_tool_performance(step_id, success=False, duration=duration)

            # --- BACKTRACKING OR FALLBACK ---
            on_failure = step.get("on_failure")
            fallback_tool_id = step.get("fallback_to")
            
            if fallback_tool_id and fallback_tool_id in tools:
                report.append(f"\n🔄 **Neural Failover:** Pivoting to `{fallback_tool_id}` (Local fallback)")
                print(f"   🔄 Failover: Rerouting task to {fallback_tool_id}...")
                
                # Execute fallback tool with smart input mapping
                fallback_tool = tools[fallback_tool_id]
                try:
                    # Smart mapping: Gemini inputs -> Supervisor inputs
                    if fallback_tool_id == "consult_supervisor":
                        mapped_input = {
                            "user_proposal": state.get("task", "Analyze this code"),
                            "code_snippet": tool_input.get("code_snippet", "") if isinstance(tool_input, dict) else ""
                        }
                    else:
                        mapped_input = tool_input

                    fallback_result = await fallback_tool(**mapped_input) if asyncio.iscoroutinefunction(fallback_tool) else fallback_tool(**mapped_input)
                    
                    # Store result and continue
                    output_key = step.get("output_key")
                    if output_key:
                        state[output_key] = fallback_result
                    report.append(f"✅ Fallback successful: {str(fallback_result)[:200]}...")
                    continue # Success in fallback, proceed to next step
                except Exception as fe:
                    report.append(f"⚠️ Fallback also failed: {fe}")

            if on_failure == "backtrack" and state.get("file_path"):
                state["backtrack_count"] += 1
                if state["backtrack_count"] <= 2:
                    report.append(f"\n🔄 **Backtracking** (attempt {state['backtrack_count']}/2)")
                    try:
                        restore_tool = tools.get("restore_checkpoint")
                        if restore_tool:
                            restore_result = restore_tool(
                                file_path=state["file_path"],
                                label="pre_fix",
                            )
                            report.append(f"Restored checkpoint: {restore_result[:200]}")
                    except Exception as restore_err:
                        report.append(f"⚠️ Restore failed: {restore_err}")
                else:
                    report.append("\n⛔ **Max backtrack attempts reached.** Manual intervention needed.")

            # Continue to next step if we can't fix it
            continue

    # --- MAZE PROTOCOL GATE (System 2) ---
    if workflow in ["bug_fix", "research_implement"] and project_path:
        print("🌀 System 2: Executing Maze Protocol (Backward Verification)...")
        # Find the primary file to verify (usually state['target_file'] or similar)
        target_file = state.get("file_path") or state.get("target_file")
        if target_file:
            maze_ok = backward_verify(target_file, project_path, run_tests=True)
            if not maze_ok:
                report.append("\n⚠️ **MAZE PROTOCOL WARNING:** This modification failed backward verification or caused regressions. Manual review advised.")
                print(f"   ⚠️ Maze Protocol failed for {target_file}")
            else:
                report.append("\n✅ **MAZE PROTOCOL VERIFIED:** Changes are rooted and behaviorally sound.")

    # --- AUTOMATIC REFLECTION (System 5) ---
    if workflow in ["bug_fix", "research_implement"] and "reflect_and_distill" in tools:
        print("🧠 System 5: Triggering post-swarm reflection...")
        logs = "\n".join(report)
        reflection_data = tools["reflect_and_distill"](task, logs)
        
        if isinstance(reflection_data, dict):
            report.append("\n## 🧠 Architectural Reflection")
            report.append(reflection_data.get("report", ""))
            
            # Apply Bayesian Tuning
            tuning_payload = reflection_data.get("tuning_payload", [])
            if tuning_payload and "tune_swarm" in tools:
                print(f"⚖️ Tuning Swarm: Applying {len(tuning_payload)} updates...")
                for tune in tuning_payload:
                    tools["tune_swarm"](tune["tool_id"], tune["success"], tune["category"])
                
                # --- NEW: AUTONOMIC CORRECTOR INJECTION ---
                print("🛠️ Autonomic Corrector: Queueing tuning payload for background processing...")
                corrector.queue_tuning(tuning_payload)
                corrector.run_correction_cycle() # Run immediately for now to verify
        else:
            # Fallback for simple string returns
            report.append("\n## 🧠 Architectural Reflection")
            report.append(str(reflection_data))

    # --- MARS BOUNDARY VERIFICATION (The Spline Audit) ---
    print("🛡️ System 2: Running MARS Boundary Audit...")
    # Extract workflow-based category
    mars_cat = "bug_fix"
    if workflow == "ui_design": mars_cat = "ui"
    if workflow == "security_audit": mars_cat = "security"
    
    # Check current diff if available in state
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


# --- 6. PRO STACK ENTRY POINT ---

def orchestrate(workflow: str, task: str, file_path: str = "", project_path: str = ".", code_snippet: str = "", tech_key: str = ""):
    """
    Synchronous entry point for the Pro Stack.
    Usage: orchestrate("bug_fix", task="Fix the leak", file_path="app.py")
    """
    import asyncio
    from tools.audit.gemini_reviewer import gemini_code_review, gemini_research
    from tools.audit.supervisor_agent import run_supervisor_audit
    from tools.memory.repo_mapper import scan_repo
    from tools.utils.error_memory import remember_fix, recall_fix
    from tools.utils.path_utils import get_project_root
    from tools.utils.backtracker import save_checkpoint, restore_checkpoint
    from tools.execution.sandbox_runner import run_code_safely as run_code_safely
    from tools.utils.bayesian import tune_swarm
    from tools.audit.consult_architect import consult_brain
    from tools.audit.discovery_agent import generate_discovery_form
    from tools.audit.linter_autofix import autofix_linter

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
        "tune_swarm": tune_swarm,
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

def swarm(objective: str, project_path: str = "."):
    """
    Synchronous entry point for triggering a full autonomous swarm.
    Usage: swarm("Build a new landing page for the burger shop")
    """
    import asyncio
    from tools.audit.gemini_reviewer import gemini_code_review, gemini_research
    from tools.audit.supervisor_agent import run_supervisor_audit
    from tools.memory.repo_mapper import scan_repo
    from tools.utils.error_memory import remember_fix, recall_fix
    from tools.utils.backtracker import save_checkpoint, restore_checkpoint
    from tools.execution.sandbox_runner import run_code_safely
    from tools.utils.bayesian import tune_swarm
    from tools.audit.guardrail_agent import run_guardrail_audit
    from tools.utils.maze_protocol import backward_verify
    from tools.audit.linter_autofix import autofix_linter

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
        "tune_swarm": tune_swarm,
        "autofix_linter": autofix_linter
    }

    return asyncio.run(spawn_swarm(objective, tools, project_path))

if __name__ == "__main__":
    # Example usage
    import argparse
    parser = argparse.ArgumentParser(description="Kenbun Orchestrator")
    parser.add_argument("workflow", help="Pipeline to run (bug_fix, code_review, etc.)")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--file", default="", help="Target file path")
    
    args = parser.parse_args()
    print(orchestrate(args.workflow, task=args.task, file_path=args.file))
