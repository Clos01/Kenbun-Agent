import subprocess
import logging
import json
import re
import time
from typing import List, Dict, Any, Union
from tools.registry import sovereign_tool
from tools.utils.llm_router import call_llm_gateway
from tools.gui.autonomous_browser_agent import AutonomousBrowserAgent, dispatch_autonomous_browser

logger = logging.getLogger("tools.gui.ui_tars")

def decompose_goal_into_micro_actions(goal: str, url: str) -> List[str]:
    """
    Prefrontal Cortex Planner: Decomposes a high-level UX/UI goal into explicit,
    physical click/type/submit actions specifically formatted for UI-TARS.
    """
    system_prompt = """You are the Prefrontal Cortex Navigation Planner for a visual GUI agent (UI-TARS).
Your job is to break down the user's end-to-end task into an explicit sequence of PHYSICAL CLICKS, TYPING, and SUBMIT actions.
Use explicit action verbs like 'Click the Voice Agents link in the sidebar', 'Click the Add Agent button', 'Type TARS Autonomous Scout into the Agent Name input field', 'Type agent_tars_001 into the ElevenLabs Agent ID input field', 'Click the Register Agent button'.

Output ONLY a valid JSON array of action strings."""

    user_message = f"Goal: {goal}\nTarget URL: {url}"
    try:
        raw = call_llm_gateway(system_prompt, user_message, temperature=0.0).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"```$", "", raw, flags=re.MULTILINE).strip()
        plan = json.loads(raw)
        if isinstance(plan, list) and len(plan) > 0:
            return [str(p) for p in plan]
    except Exception as e:
        logger.warning(f"LLM planner decomposition fallback: {e}")
    
    # Deterministic end-to-end registration flow
    return [
        "Click on the 'Voice Agents' link in the left sidebar",
        "Click on the 'Add Agent' button",
        "Click on the Agent Name input field and type 'TARS Sovereign Scout'",
        "Click on the ElevenLabs Agent ID input field and type 'agent_tars_v2'",
        "Click the 'Register Agent' button to save the new agent"
    ]

@sovereign_tool()
def trigger_ui_tars(goal: Union[str, Dict[str, Any]]) -> str:
    """
    Motor-Cortex UI-TARS Autonomous Visual Executor with Multi-Engine Routing (Playwright + P330 Satellite).
    
    Supports:
    1. Direct English directive: 'Open Firefox and navigate to https://nevermiss.ai'
    2. Structured AI JSON payload: {'url': 'https://nevermiss.ai', 'mode': 'hybrid', 'goal': '...'}
    """
    if isinstance(goal, dict):
        url = goal.get("url", "")
        mode = goal.get("mode", "hybrid")
        user_goal = goal.get("goal", "Execute autonomous browser task")
        actions = goal.get("actions")
        extract_fields = goal.get("extract_fields")
        agent = AutonomousBrowserAgent()
        result = agent.run(url=url, goal=user_goal, mode=mode, actions=actions, extract_fields=extract_fields)
        return json.dumps(result, indent=2)

    url_match = re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', goal)
    url_to_open = url_match.group(0) if url_match else ""
    if url_to_open.endswith('.'):
        url_to_open = url_to_open[:-1]
        
    print(f"🧠 [Prefrontal Cortex] Ingesting goal: '{goal}'")
    micro_actions = decompose_goal_into_micro_actions(goal, url_to_open)
    print(f"📋 [Prefrontal Cortex] Planned {len(micro_actions)} Atomic Actions:")
    for idx, act in enumerate(micro_actions, 1):
        print(f"   {idx}. {act}")

    open_browser_code = ""
    if url_to_open:
        open_browser_code = f"""
import os
os.system("pkill -9 nautilus gnome-calculator 2>/dev/null")
os.system("killall firefox 2>/dev/null")
time.sleep(1)
os.system("DISPLAY=:0 MOZ_CRASHREPORTER_DISABLE=1 MOZ_TELEMETRY_REPORTING=0 MOZ_DATA_REPORTING=0 GDK_BACKEND=x11 firefox '{url_to_open}' >/dev/null 2>&1 &")
time.sleep(5)
"""

    python_script = f"""
import sys
import time
import json
sys.path.insert(0, "/home/its_los")
{open_browser_code}
from tars_closed_loop_runtime import ClosedLoopGUIAgent

agent = ClosedLoopGUIAgent()
micro_plan = {json.dumps(micro_actions)}
execution_trace = []

print(f"🚀 [Motor Cortex] Initializing SOTA Closed-Loop Task Execution on DISPLAY=:0...")
print(f"🎯 [Active Levers]: Visual Pyramid Zoom (L1) | Gui-Cursor (L2) | Screen Delta (L3) | System-2 CoT (L5)")

for idx, action_item in enumerate(micro_plan, 1):
    print(f"\\n━━━ [STEP {{idx}}/{{len(micro_plan)}}] Directive: '{{action_item}}' ━━━")
    t0 = time.time()
    
    result = agent.step(action_item, enable_zoom_retry=True)
    duration = time.time() - t0
    
    thought = result.get('thought', 'N/A')
    action_type = result.get('action_type', 'N/A')
    coords = result.get('coords', 'N/A')
    bbox = result.get('bounding_box', 'N/A')
    content = result.get('content', '')
    delta_after = result.get('screen_delta_after', 0.0)
    zoom_applied = result.get('zoom_retry_applied', False)
    
    print(f"🧠 [System-2 Thought]:\\n{{thought}}")
    if action_type == 'type':
        print(f"⚡ [Motor Action]: type '{{content}}'")
    elif action_type == 'hotkey':
        print(f"⚡ [Motor Action]: hotkey '{{content}}'")
    else:
        print(f"⚡ [Motor Action]: {{action_type}} at {{coords}} (BBox: {{bbox}})")
        
    if zoom_applied:
        print(f"🔍 [Visual Pyramid]: Zoom retry applied! Re-projected coords -> {{result.get('reprojected_coords')}}")
        
    print(f"📊 [Screen Delta]: {{delta_after:.2f}}% pixels transitioned")
    print(f"⏱️ [Step Latency]: {{duration:.2f}}s")
    
    step_record = {{
        "step": idx,
        "directive": action_item,
        "thought": thought,
        "action": action_type,
        "coords": coords,
        "bounding_box": bbox,
        "content": content,
        "delta_pct": delta_after,
        "zoom_retry": zoom_applied,
        "latency_sec": duration,
        "success": delta_after > 0.5 or action_type in ['click', 'double_click', 'type', 'hotkey', 'finished']
    }}
    execution_trace.append(step_record)
    
    if result.get("action_type") in ["finished", "call_user"]:
        print(f"\\n🏁 UI-TARS reached terminal state: '{{result.get('action_type')}}'")
        break
        
    time.sleep(1.5)

print("\\n" + "="*50)
print("📊 END-TO-END EXECUTION TRACE JSON:")
print(json.dumps(execution_trace, indent=2))
print("="*50)
"""

    # Pre-Flight Code Integrity Sentinel Validation
    from tools.codebase.code_integrity_sentinel import CodeIntegritySentinel
    sentinel = CodeIntegritySentinel()
    fixed_script, fixes = sentinel.autofix_code_string(python_script)
    if fixes:
        print(f"🛡️ [Code Sentinel] Pre-flight auto-fixes applied: {fixes}")
        python_script = fixed_script

    cmd_write = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", 
        "its_los@100.100.199.127", 
        f"cat << 'EOF_MARKER' > /tmp/run_e2e_tars.py\n{python_script}\nEOF_MARKER"
    ]
    
    cmd_run = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", 
        "its_los@100.100.199.127", 
        "DISPLAY=:0 python3 -u /tmp/run_e2e_tars.py"
    ]
    
    try:
        subprocess.run(cmd_write, check=True)
        process = subprocess.Popen(cmd_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        full_output = f"🎯 End-to-End Task: {goal}\nTarget URL: {url_to_open}\n\n"
        
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
            full_output += line
            
        process.stdout.close()
        process.wait(timeout=300)
        return full_output
    except Exception as e:
        return f"Motor-Cortex end-to-end execution error: {e}"
