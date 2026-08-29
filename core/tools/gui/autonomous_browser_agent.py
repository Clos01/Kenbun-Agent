"""
Autonomous Hybrid Browser & GUI Agent (Kenbun Sensory & Motor Cortex).
Enables AI-to-AI browser orchestration with Multi-Engine Routing:
1. Mode 'playwright': High-speed DOM automation, headless evaluation, screenshot & structured JSON data extraction.
2. Mode 'ui_tars': Full vision-native UI-TARS Closed-Loop execution on the P330 satellite (DISPLAY=:0).
3. Mode 'hybrid': Fast Playwright DOM navigation with automatic escalation to P330 UI-TARS on bot/visual blockers.
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import logging
import subprocess
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse

from tools.registry import sovereign_tool
from tools.infrastructure.config import settings

logger = logging.getLogger("tools.gui.autonomous_browser")

def _find_repo_root() -> str:
    curr = os.path.abspath(__file__)
    while curr and curr != "/":
        if os.path.exists(os.path.join(curr, "dashboard")):
            return curr
        curr = os.path.dirname(curr)
    return "/Users/carlosrivas/Dev/Kenbun"

# Artifacts & Screenshots directory
SCREENSHOTS_DIR = os.path.join(_find_repo_root(), "data", "artifacts", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


class AutonomousBrowserAgent:
    """Enterprise multi-engine browser agent for AI-to-AI orchestration."""

    def __init__(
        self, 
        satellite_ip: str = "100.100.199.127", 
        satellite_user: str = "its_los",
        default_timeout: int = 45
    ):
        self.satellite_ip = satellite_ip
        self.satellite_user = satellite_user
        self.default_timeout = default_timeout

    def run(
        self,
        url: str,
        goal: str = "Navigate and extract page content",
        mode: str = "hybrid",
        actions: Optional[List[Dict[str, Any]]] = None,
        extract_fields: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        Executes autonomous browser task across Playwright or P330 UI-TARS.
        Returns machine-readable JSON receipt.
        """
        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        t0 = time.time()
        mode_lower = mode.lower().strip()

        logger.info(f"🌐 [Autonomous Browser] Starting task (Session: {session_id}, Mode: {mode_lower}, URL: {url})")

        if mode_lower == "playwright":
            result = self.execute_playwright(url, goal, actions, extract_fields, session_id, headless)
        elif mode_lower in ("ui_tars", "p330", "ssh"):
            result = self.execute_p330_ssh_tars(goal, url, session_id)
        else: # "hybrid" (default)
            result = self.execute_hybrid(url, goal, actions, extract_fields, session_id, headless)

        result["duration_seconds"] = round(time.time() - t0, 3)
        result["session_id"] = session_id
        return result

    def execute_playwright(
        self,
        url: str,
        goal: str,
        actions: Optional[List[Dict[str, Any]]] = None,
        extract_fields: Optional[List[str]] = None,
        session_id: str = "default_session",
        headless: bool = True
    ) -> Dict[str, Any]:
        """Executes high-speed Playwright script via Node.js runner."""
        screenshot_filename = f"playwright_{session_id}_{int(time.time())}.png"
        screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_filename)

        actions_list = actions or []
        extract_list = extract_fields or ["title", "h1", "description", "links_count", "text_summary"]

        repo_root = _find_repo_root()
        pw_direct_path = os.path.join(repo_root, "dashboard", "scripts", "node_modules", "playwright-core")

        node_script = f"""
let chromium;
try {{
    chromium = require({json.dumps(pw_direct_path)}).chromium;
}} catch (e) {{
    try {{
        chromium = require('playwright-core').chromium;
    }} catch (e2) {{
        chromium = require('playwright').chromium;
    }}
}}
const fs = require('fs');

(async () => {{
    const output = {{
        status: 'PENDING',
        engine_used: 'playwright',
        target_url: {json.dumps(url)},
        page_title: '',
        extracted_data: {{}},
        screenshot_path: {json.dumps(screenshot_path)},
        execution_trace: [],
        blocked_by_bot: false,
        error: null
    }};

    let browser;
    try {{
        // Auto-detect browser executable (Chromium/Chrome/Edge)
        const possiblePaths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            '/usr/bin/google-chrome',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium'
        ];
        
        let execPath = undefined;
        for (const p of possiblePaths) {{
            if (fs.existsSync(p)) {{
                execPath = p;
                break;
            }}
        }}

        browser = await chromium.launch({{
            executablePath: execPath,
            headless: {json.dumps(headless)},
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
        }});

        const context = await browser.newContext({{
            viewport: {{ width: 1344, height: 756 }},
            userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        }});

        const page = await context.newPage();
        
        // Navigation with timeout guard
        await page.goto({json.dumps(url)}, {{ waitUntil: 'domcontentloaded', timeout: 25000 }});
        output.execution_trace.push({{ step: 1, action: 'goto', url: {json.dumps(url)}, status: 'ok' }});

        // Wait for network settle
        try {{
            await page.waitForLoadState('networkidle', {{ timeout: 5000 }});
        }} catch (e) {{}}

        output.page_title = await page.title();

        // Check for Cloudflare / bot challenge
        const bodyText = await page.innerText('body');
        if (bodyText.includes('Attention Required! | Cloudflare') || 
            bodyText.includes('Verify you are human') || 
            bodyText.includes('Checking your browser')) {{
            output.blocked_by_bot = true;
            output.execution_trace.push({{ step: 2, action: 'bot_detection', status: 'blocked' }});
        }}

        // Execute dynamic action sequence
        const actions = {json.dumps(actions_list)};
        for (let i = 0; i < actions.length; i++) {{
            const act = actions[i];
            try {{
                if (act.type === 'click' && act.selector) {{
                    await page.click(act.selector, {{ timeout: 4000 }});
                    output.execution_trace.push({{ step: i + 3, action: 'click', selector: act.selector, status: 'ok' }});
                }} else if (act.type === 'type' && act.selector) {{
                    await page.fill(act.selector, act.text || '', {{ timeout: 4000 }});
                    output.execution_trace.push({{ step: i + 3, action: 'type', selector: act.selector, status: 'ok' }});
                }} else if (act.type === 'press' && act.key) {{
                    await page.keyboard.press(act.key);
                    output.execution_trace.push({{ step: i + 3, action: 'press', key: act.key, status: 'ok' }});
                }}
                await page.waitForTimeout(500);
            }} catch (actErr) {{
                output.execution_trace.push({{ step: i + 3, action: act.type, status: 'failed', error: actErr.message }});
            }}
        }}

        // Extract structured fields
        const extractFields = {json.dumps(extract_list)};
        const extracted = {{}};
        
        if (extractFields.includes('title')) extracted.title = output.page_title;
        if (extractFields.includes('h1')) {{
            const h1s = await page.$$eval('h1', els => els.map(e => e.innerText.trim()).filter(Boolean));
            extracted.h1 = h1s;
        }}
        if (extractFields.includes('description')) {{
            const desc = await page.$eval('meta[name="description"]', el => el.content).catch(() => '');
            extracted.description = desc;
        }}
        if (extractFields.includes('links_count')) {{
            extracted.links_count = await page.$$eval('a', els => els.length);
        }}
        if (extractFields.includes('text_summary')) {{
            extracted.text_summary = bodyText.substring(0, 1000).replace(/\\s+/g, ' ').trim();
        }}

        output.extracted_data = extracted;

        // Capture artifact screenshot
        await page.screenshot({{ path: {json.dumps(screenshot_path)}, fullPage: false }});
        output.status = output.blocked_by_bot ? 'BOT_BLOCKED' : 'SUCCESS';

    }} catch (err) {{
        output.status = 'FAILED';
        output.error = err.message;
    }} finally {{
        if (browser) await browser.close();
        console.log(JSON.stringify(output));
    }}
}})();
"""
        try:
            env = os.environ.copy()
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            node_paths = [
                os.path.join(repo_root, "dashboard", "scripts", "node_modules"),
                os.path.join(repo_root, "dashboard", "node_modules"),
                os.path.join(repo_root, "node_modules"),
                env.get("NODE_PATH", "")
            ]
            env["NODE_PATH"] = ":".join([p for p in node_paths if p])

            # Run node script with injected module path
            proc = subprocess.run(
                ["node", "-e", node_script],
                capture_output=True,
                text=True,
                env=env,
                timeout=self.default_timeout
            )
            
            if proc.stdout.strip():
                # Parse JSON output from last line
                lines = [l.strip() for l in proc.stdout.strip().splitlines() if l.strip()]
                for l in reversed(lines):
                    if l.startswith("{") and l.endswith("}"):
                        try:
                            return json.loads(l)
                        except json.JSONDecodeError:
                            continue

            # Fallback if node exited with error
            return {
                "status": "FAILED",
                "engine_used": "playwright",
                "target_url": url,
                "error": proc.stderr or "Node process returned non-JSON output",
                "screenshot_path": screenshot_path,
                "execution_trace": []
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "engine_used": "playwright",
                "target_url": url,
                "error": str(e),
                "screenshot_path": screenshot_path,
                "execution_trace": []
            }

    def execute_p330_ssh_tars(
        self,
        goal: str,
        url: str,
        session_id: str = "default_session"
    ) -> Dict[str, Any]:
        """Dispatches visual motor cortex execution to P330 satellite on DISPLAY=:0."""
        from tools.gui.ui_tars_tools import decompose_goal_into_micro_actions

        url_clean = url.rstrip(".")
        micro_actions = decompose_goal_into_micro_actions(goal, url_clean)
        
        open_browser_code = f"""
import os
os.system("pkill -9 firefox 2>/dev/null")
time.sleep(1)
os.system("DISPLAY=:0 MOZ_CRASHREPORTER_DISABLE=1 MOZ_TELEMETRY_REPORTING=0 MOZ_DATA_REPORTING=0 GDK_BACKEND=x11 firefox '{url_clean}' >/dev/null 2>&1 &")
time.sleep(4)
""" if url_clean else ""

        remote_script = f"""
import sys
import json
import time
sys.path.insert(0, "/home/its_los")
{open_browser_code}
from tars_closed_loop_runtime import ClosedLoopGUIAgent

agent = ClosedLoopGUIAgent()
micro_plan = {json.dumps(micro_actions)}
execution_trace = []

for idx, action_item in enumerate(micro_plan, 1):
    t0 = time.time()
    result = agent.step(action_item, workflow_name="{session_id}", enable_cache=True)
    duration = time.time() - t0
    
    execution_trace.append({{
        "step": idx,
        "directive": action_item,
        "thought": result.get("thought", ""),
        "action": result.get("action_type", ""),
        "coords": result.get("coords"),
        "delta_pct": result.get("screen_delta_after", 0.0),
        "from_cache": result.get("from_cache", False),
        "latency_sec": duration
    }})
    
    if result.get("action_type") in ["finished", "call_user"]:
        break

output_envelope = {{
    "status": "SUCCESS",
    "engine_used": "ui_tars_p330",
    "target_url": "{url_clean}",
    "execution_trace": execution_trace,
    "steps_completed": len(execution_trace)
}}

print("JSON_START")
print(json.dumps(output_envelope))
print("JSON_END")
"""
        # Pre-flight static analysis guard
        try:
            from tools.codebase.code_integrity_sentinel import CodeIntegritySentinel
            sentinel = CodeIntegritySentinel()
            fixed_script, fixes = sentinel.autofix_code_string(remote_script)
            if fixes:
                logger.info(f"🛡️ [Code Sentinel] Pre-flight fixes applied: {fixes}")
                remote_script = fixed_script
        except Exception:
            pass

        cmd_write = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            f"{self.satellite_user}@{self.satellite_ip}",
            f"cat << 'EOF_P330' > /tmp/run_auto_browser_{session_id}.py\n{remote_script}\nEOF_P330"
        ]
        
        cmd_run = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            f"{self.satellite_user}@{self.satellite_ip}",
            f"DISPLAY=:0 python3 -u /tmp/run_auto_browser_{session_id}.py"
        ]

        try:
            subprocess.run(cmd_write, check=True, timeout=15)
            ssh_timeout = max(300, len(micro_actions) * 60)
            proc = subprocess.run(cmd_run, capture_output=True, text=True, timeout=ssh_timeout)
            
            raw_text = proc.stdout
            if "JSON_START" in raw_text and "JSON_END" in raw_text:
                json_chunk = raw_text.split("JSON_START")[1].split("JSON_END")[0].strip()
                return json.loads(json_chunk)
            
            return {
                "status": "SUCCESS",
                "engine_used": "ui_tars_p330",
                "target_url": url,
                "raw_output": raw_text,
                "execution_trace": []
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "engine_used": "ui_tars_p330",
                "target_url": url,
                "error": str(e),
                "execution_trace": []
            }

    def execute_hybrid(
        self,
        url: str,
        goal: str,
        actions: Optional[List[Dict[str, Any]]] = None,
        extract_fields: Optional[List[str]] = None,
        session_id: str = "default_session",
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        Attempts ultra-fast Playwright DOM first; if bot-blocked, CAPTCHA detected,
        or interactive steps fail, automatically escalates to P330 UI-TARS.
        """
        pw_result = self.execute_playwright(url, goal, actions, extract_fields, session_id, headless)

        # Evaluate escalation conditions
        needs_escalation = (
            pw_result.get("status") in ["BOT_BLOCKED", "FAILED"] or
            pw_result.get("blocked_by_bot", False) or
            any(step.get("status") == "failed" for step in pw_result.get("execution_trace", []))
        )

        if not needs_escalation:
            return pw_result

        logger.warning(f"⚠️ [Hybrid Auto-Escalate] Playwright encounter issue ({pw_result.get('status')}). Escalating to P330 UI-TARS Motor Cortex...")
        tars_result = self.execute_p330_ssh_tars(goal, url, session_id)
        tars_result["hybrid_escalated"] = True
        tars_result["playwright_attempt"] = pw_result
        return tars_result


@sovereign_tool(name="dispatch_autonomous_browser", category="Sensory")
def dispatch_autonomous_browser(
    url: str,
    goal: str = "Navigate and analyze website",
    mode: str = "hybrid",
    actions: Optional[List[Dict[str, Any]]] = None,
    extract_fields: Optional[List[str]] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Autonomous Multi-Engine Browser & GUI Agent for AI-to-AI Interoperability.
    
    Modes:
    - 'hybrid' (Default): Ultra-fast Playwright DOM execution with auto-fallback to P330 UI-TARS Vision on blockers.
    - 'playwright': High-speed DOM extraction, headless actions, and instant JSON data extraction.
    - 'ui_tars' / 'p330': Full vision-native UI-TARS Closed-Loop execution on the remote P330 GPU satellite (DISPLAY=:0).
    
    Args:
        url: Target web URL (e.g. 'https://nevermiss.ai').
        goal: High-level directive (e.g. 'Open NeverMiss AI and extract pricing/features').
        mode: Execution engine ('hybrid', 'playwright', 'ui_tars').
        actions: Optional list of click/type actions [{'type': 'click', 'selector': '#btn'}].
        extract_fields: List of fields to extract (e.g. ['title', 'h1', 'description', 'text_summary']).
        session_id: Optional session identifier for episodic caching.
    """
    agent = AutonomousBrowserAgent()
    return agent.run(
        url=url,
        goal=goal,
        mode=mode,
        actions=actions,
        extract_fields=extract_fields,
        session_id=session_id
    )
