import asyncio
import json
import time
from pathlib import Path
from core.tools.infrastructure.config import settings
from core.tools.infrastructure.parallel_manager import parallel_manager
from core.tools.strategy.decision_logic import router
from core.tools.utils.notifications import send_notification
from core.tools.utils.sync_intelligence import run_sync
from core.tools.audit.mars_auditor import mars_auditor

TELEMETRY_PATH = settings.BRAIN_HEALTH_DIR / "live_telemetry.json"

def log_to_dashboard(message: str):
    print(f"🖥️ [SWARM] {message}")
    try:
        data = {"timestamp": time.time(), "message": message, "type": "log"}
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(data) + "\n")
    except Exception as e:
        print(f"⚠️ Dashboard log failed: {e}")

async def check_connectivity(ip: str) -> bool:
    import platform
    try:
        system = platform.system().lower()
        if "windows" in system:
            cmd = ["ping", "-n", "1", "-w", "1000", ip]
        else:
            timeout_flag = "-t" if "darwin" in system else "-W"
            cmd = ["ping", "-c", "1", timeout_flag, "1", ip]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=1.5)
        return proc.returncode == 0
    except Exception:
        return False

def save_topology(tasks_ref: list, data: dict):
    if tasks_ref is None:
        tasks_ref = []
    tasks_ref.append(data)
    try:
        topology_data = {"timestamp": time.time(), "topology": tasks_ref, "type": "topology"}
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(topology_data) + "\n")
    except Exception as e:
        print(f"⚠️ Topology save failed: {e}")

def extract_json_array(text: str) -> str:
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

async def spawn_swarm(objective: str, tools: dict, project_path: str = "") -> str:
    from core.tools.infrastructure.agent_dispatcher import run_pipeline
    
    print(f"🐝 Swarm Objective: {objective}")
    
    mandates = ""
    rules_path = Path(project_path) / ".kenbun_rules.md"
    if rules_path.exists():
        with open(rules_path, "r") as f:
            mandates = f.read()
        print("📜 Found project mandates in .kenbun_rules.md")

    from core.tools.strategy.hme_router import hme_router
    route_info = hme_router.route_task(objective)
    integrity_instruction = ""
    if route_info.get("integrity_flag") == "CHUNKING_REQUIRED":
        print(f"⚖️ HME Integrity: High volume detected ({route_info.get('estimated_volume')}). Forcing chunked decomposition.")
        integrity_instruction = "IMPORTANT: This objective is MASSIVE. You MUST decompose it into small, atomic chunks (max 100 lines per task) to prevent LLM truncation. Do NOT combine multiple features into one task."

    queen_prompt = (
        f"OBJECTIVE: {objective}\n\n"
        f"PROJECT MANDATES:\n{mandates}\n\n"
        f"{integrity_instruction}\n"
        "As the Kenbun Queen, decompose this objective into a JSON list of atomic tasks. "
        "Strictly follow the PROJECT MANDATES if provided. "
        "Each task must have: 'id', 'label', 'worker_type' (coder, auditor, designer), and 'task_description'. "
        "OPTIMIZATION: Group parallelizable tasks (research, audits, scans) together at the start or between blocking steps to maximize swarm efficiency. "
        "Format as valid JSON: [{'id': '...', 'label': '...', 'worker_type': '...', 'task_description': '...'}]"
    )
    
    try:
        from core.tools.audit.gemini_reviewer import call_gemini_pro
        raw_decomposition = call_gemini_pro(queen_prompt)
        
        json_str = extract_json_array(raw_decomposition)
        if not json_str:
            return f"❌ Swarm decomposition format error. No JSON array found in raw output: {raw_decomposition}"
        
        tasks = json.loads(json_str)
        if not isinstance(tasks, list):
            raise ValueError(f"Swarm decomposition error. Parsed JSON is not a list: {raw_decomposition}")
            
        for i, t in enumerate(tasks):
            t["id"] = f"task-{i}"
            t["status"] = "pending"
            
            category = "bug_fix"
            if "ui" in t["label"].lower() or "designer" in t["worker_type"].lower(): category = "ui"
            if "security" in t["label"].lower(): category = "security"
            if "architecture" in t["label"].lower(): category = "architecture"
            
            mars_guidance = mars_auditor.get_guidance(category)
            if mars_guidance:
                t["task_description"] = f"{t['task_description']}\n\n{mars_guidance}"
        
    except Exception as e:
        return f"❌ Swarm decomposition failed: {e}"

    report = [
        f"# 🐝 Swarm Objective: {objective}",
        f"**Tasks identified:** {len(tasks)}",
        ""
    ]

    print(f"📋 TASKS IDENTIFIED: {[t.get('label') for t in tasks]}")
    task_groups = parallel_manager.decompose_parallel_groups(tasks)
    
    for group in task_groups:
        if len(group) > 1:
            print(f"⚡ EXECUTING PARALLEL BATCH: {len(group)} tasks")
            async_tasks = []
            for t_meta in group:
                t_meta["status"] = "active"
                desc = t_meta["task_description"]
                
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
            task_meta = group[0]
            task_meta["status"] = "active"
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
    
    print("📡 Swarm complete. Triggering intelligence sync...")
    run_sync()
    
    return "\n\n".join(report)
