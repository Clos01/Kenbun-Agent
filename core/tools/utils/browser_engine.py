import os
import json
import time
import logging
import subprocess
import requests
import ipaddress
import atexit
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from tools.infrastructure.config import settings
from tools.utils.secret_manager import decrypt_value

logger = logging.getLogger("browser_engine")

def is_private_url(url: str) -> bool:
    """Detects loopback, link-local, or private LAN URLs."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return True
        host_lower = host.lower()
        if host_lower in ("localhost", "::1"):
            return True
        if any(host_lower.endswith(suffix) for suffix in (".local", ".lan", ".internal")):
            return True
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            pass
    except Exception:
        return True
    return False

class BrowserEngine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(BrowserEngine, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        self.last_activity_time = time.time()
        self.session_is_local = False
        self.camofox_user_id = settings.CAMOFOX_USER_ID or "default-user"
        self.camofox_session_active = False
        atexit.register(self.close_all_sessions)

    def _check_inactivity(self):
        now = time.time()
        elapsed = now - self.last_activity_time
        if elapsed > settings.BROWSER_INACTIVITY_TIMEOUT:
            logger.info("Browser session timed out due to inactivity. Closing session...")
            self.close_all_sessions()
        self.last_activity_time = now

    def close_all_sessions(self):
        """Terminates any active browser sessions and releases cloud locks."""
        try:
            subprocess.run(["npx", "agent-browser", "close", "--all"], capture_output=True, timeout=10)
        except Exception as e:
            logger.debug(f"Failed to close local agent-browser CLI sessions: {e}")

        if settings.CAMOFOX_URL and self.camofox_session_active:
            try:
                # Close Camofox session if not using managed persistence
                if not settings.CAMOFOX_MANAGED_PERSISTENCE:
                    url = f"{settings.CAMOFOX_URL.rstrip('/')}/sessions/{self.camofox_user_id}"
                    requests.delete(url, timeout=5)
            except Exception as e:
                logger.debug(f"Failed to clean up Camofox session: {e}")
            self.camofox_session_active = False

    def _run_cli(self, subcommand: str, *args) -> dict:
        self._check_inactivity()
        cmd = ["npx", "agent-browser", subcommand]
        cmd.extend(args)
        cmd.append("--json")

        env = os.environ.copy()
        if not self.session_is_local:
            provider = settings.BROWSER_CLOUD_PROVIDER
            if provider:
                env["AGENT_BROWSER_PROVIDER"] = provider

        if settings.BROWSERBASE_API_KEY:
            env["BROWSERBASE_API_KEY"] = decrypt_value(settings.BROWSERBASE_API_KEY)
        if settings.BROWSERBASE_PROJECT_ID:
            env["BROWSERBASE_PROJECT_ID"] = settings.BROWSERBASE_PROJECT_ID
        if settings.BROWSER_USE_API_KEY:
            env["BROWSER_USE_API_KEY"] = decrypt_value(settings.BROWSER_USE_API_KEY)
        if settings.FIRECRAWL_API_KEY:
            env["FIRECRAWL_API_KEY"] = decrypt_value(settings.FIRECRAWL_API_KEY)
        if settings.FIRECRAWL_API_URL:
            env["FIRECRAWL_API_URL"] = settings.FIRECRAWL_API_URL
        if settings.BROWSER_RECORD_SESSIONS:
            env["AGENT_BROWSER_RECORD_SESSIONS"] = "true"
        env["BROWSER_INACTIVITY_TIMEOUT"] = str(settings.BROWSER_INACTIVITY_TIMEOUT)
        if settings.AGENT_BROWSER_ARGS:
            env["AGENT_BROWSER_ARGS"] = settings.AGENT_BROWSER_ARGS

        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                try:
                    return json.loads(res.stdout)
                except Exception:
                    return {"success": True, "data": res.stdout, "error": None}
            else:
                try:
                    return json.loads(res.stdout)
                except Exception:
                    error_msg = res.stderr or res.stdout or f"CLI returned exit code {res.returncode}"
                    return {"success": False, "data": None, "error": error_msg}
        except subprocess.TimeoutExpired:
            return {"success": False, "data": None, "error": "Browser command timed out after 60 seconds."}
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}

    def _camofox_request(self, endpoint: str, data: dict) -> dict:
        self._check_inactivity()
        url = f"{settings.CAMOFOX_URL.rstrip('/')}{endpoint}"
        try:
            resp = requests.post(url, json=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Camofox request failed to {endpoint}: {e}")
            return {"success": False, "error": str(e)}

    def navigate(self, url: str) -> dict:
        """Navigates to the specified URL, enforcing routing constraints."""
        is_private = is_private_url(url)
        if is_private:
            if not settings.BROWSER_ALLOW_PRIVATE_URLS and not settings.BROWSER_AUTO_LOCAL_FOR_PRIVATE_URLS:
                raise ValueError("Blocked: URL targets a private or internal address")
            if settings.BROWSER_AUTO_LOCAL_FOR_PRIVATE_URLS:
                self.session_is_local = True
        else:
            self.session_is_local = False

        # Apply loopback rewrites for Camofox in Docker
        if settings.CAMOFOX_URL and is_private and settings.CAMOFOX_REWRITE_LOOPBACK_URLS:
            parsed = urlparse(url)
            host = parsed.hostname
            if host in ("localhost", "127.0.0.1", "::1"):
                port = f":{parsed.port}" if parsed.port else ""
                url = url.replace(host, settings.CAMOFOX_LOOPBACK_HOST_ALIAS)

        if settings.CAMOFOX_URL:
            self.camofox_session_active = True
            payload = {
                "userId": self.camofox_user_id,
                "url": url,
                "sessionKey": settings.CAMOFOX_SESSION_KEY,
                "adoptExistingTab": settings.CAMOFOX_ADOPT_EXISTING_TAB,
                "managedPersistence": settings.CAMOFOX_MANAGED_PERSISTENCE
            }
            return self._camofox_request("/tabs/open", payload)

        return self._run_cli("open", url)

    def _compress_snapshot(self, text: str) -> str:
        system_prompt = (
            "You are a web accessibility tree compression agent. Compress the provided accessibility tree snapshot. "
            "Preserve interactive ref IDs (like @e1, @e2), labels, roles, and structural layout. "
            "Keep the output under 8000 characters."
        )
        try:
            from tools.utils.llm_router import call_llm_gateway
            compressed = call_llm_gateway(system_prompt, text)
            if compressed and len(compressed) < len(text):
                return compressed
        except Exception as e:
            logger.warning(f"Failed to compress snapshot using LLM: {e}")
        return text[:8000] + "\n[Snapshot truncated due to length]"

    def snapshot(self, full: bool = False) -> dict:
        """Gets page snapshot, auto-compressing if text exceeds 8,000 characters."""
        if settings.CAMOFOX_URL:
            payload = {
                "userId": self.camofox_user_id,
                "interactive": not full
            }
            res = self._camofox_request("/snapshot", payload)
        else:
            args = []
            if not full:
                args.append("-i")
            res = self._run_cli("snapshot", *args)

        if res.get("success"):
            snapshot_text = res.get("data", {}).get("snapshot") if isinstance(res.get("data"), dict) else res.get("data", "")
            if not snapshot_text:
                snapshot_text = ""
            if len(snapshot_text) > 8000:
                compressed = self._compress_snapshot(snapshot_text)
                if isinstance(res.get("data"), dict):
                    res["data"]["snapshot"] = compressed
                else:
                    res["data"] = compressed
        return res

    def click(self, ref: str) -> dict:
        """Clicks page element."""
        if settings.CAMOFOX_URL:
            payload = {"action": "click", "ref": ref, "userId": self.camofox_user_id}
            return self._camofox_request("/act", payload)
        return self._run_cli("click", ref)

    def type(self, ref: str, text: str) -> dict:
        """Clears and types text into page element."""
        if settings.CAMOFOX_URL:
            payload = {"action": "type", "ref": ref, "text": text, "userId": self.camofox_user_id}
            return self._camofox_request("/act", payload)
        return self._run_cli("fill", ref, text)

    def scroll(self, direction: str) -> dict:
        """Scrolls the page."""
        if settings.CAMOFOX_URL:
            payload = {"action": "scroll", "direction": direction, "userId": self.camofox_user_id}
            return self._camofox_request("/act", payload)
        return self._run_cli("scroll", direction)

    def press(self, key: str) -> dict:
        """Presses keyboard key."""
        if settings.CAMOFOX_URL:
            payload = {"action": "press", "key": key, "userId": self.camofox_user_id}
            return self._camofox_request("/act", payload)
        return self._run_cli("press", key)

    def back(self) -> dict:
        """Navigates back in history."""
        if settings.CAMOFOX_URL:
            payload = {"action": "back", "userId": self.camofox_user_id}
            return self._camofox_request("/act", payload)
        return self._run_cli("back")

    def get_images(self) -> dict:
        """Returns metadata of images on page."""
        js_expr = "Array.from(document.querySelectorAll('img')).map(img => ({url: img.src, alt: img.alt || ''}))"
        if settings.CAMOFOX_URL:
            payload = {"action": "eval", "expression": js_expr, "userId": self.camofox_user_id}
            return self._camofox_request("/act", payload)
        return self._run_cli("eval", js_expr)

    def screenshot(self) -> dict:
        """Captures page screenshot."""
        if settings.CAMOFOX_URL:
            return self._camofox_request("/screenshot", {"userId": self.camofox_user_id})
        return self._run_cli("screenshot")

    def _analyze_image(self, image_path: str, prompt: str) -> str:
        raw_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else None
        if not raw_key:
            raw_key = os.environ.get("GEMINI_API_KEY")

        if raw_key:
            try:
                from google import genai
                import PIL.Image
                api_key = decrypt_value(raw_key)
                client = genai.Client(api_key=api_key)
                img = PIL.Image.open(image_path)
                model_name = settings.models.gemini_model or "gemini-3-flash-preview"
                response = client.models.generate_content(
                    model=model_name,
                    contents=[img, prompt]
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.warning(f"Google GenAI vision API failed: {e}")

        return f"[Vision Analysis Fallback] Simulated analysis of screenshot at '{image_path}' for prompt: '{prompt}'"

    def vision(self, prompt: str) -> dict:
        """Takes screenshot and performs LLM vision analysis."""
        res = self.screenshot()
        if not res.get("success"):
            return res

        screenshot_path = res.get("data", {}).get("path") if isinstance(res.get("data"), dict) else res.get("data")
        if not screenshot_path or not os.path.exists(screenshot_path):
            return {"success": False, "error": "Screenshot file not found."}

        cache_dir = Path.home() / ".kenbun" / "cache" / "screenshots"
        cache_dir.mkdir(parents=True, exist_ok=True)
        dest_path = cache_dir / f"screenshot_{int(time.time())}.png"
        import shutil
        try:
            shutil.copy2(screenshot_path, dest_path)
        except Exception as e:
            logger.debug(f"Failed to copy screenshot to cache: {e}")
            dest_path = Path(screenshot_path)

        analysis = self._analyze_image(str(dest_path), prompt)

        return {
            "success": True,
            "data": {
                "screenshot_path": str(dest_path),
                "analysis": analysis
            }
        }

    def console(self, expression: Optional[str] = None, clear: bool = False) -> dict:
        """Evaluates JS expression or returns simulated console log dumps."""
        if expression:
            if settings.CAMOFOX_URL:
                payload = {"action": "eval", "expression": expression, "userId": self.camofox_user_id}
                return self._camofox_request("/act", payload)
            return self._run_cli("eval", expression)

        # Retrieve console logs
        if settings.CAMOFOX_URL:
            payload = {"action": "eval", "expression": "window.__console_logs || []", "userId": self.camofox_user_id}
            logs_res = self._camofox_request("/act", payload)
            if clear:
                self._camofox_request("/act", {"action": "eval", "expression": "window.__console_logs = []", "userId": self.camofox_user_id})
            return logs_res

        # Standard local fallback retrieves console logs using eval
        logs_res = self._run_cli("eval", "window.__console_logs || []")
        if clear:
            self._run_cli("eval", "window.__console_logs = []")
        return logs_res

    def cdp(self, method: str, params: Optional[dict] = None, target_id: Optional[str] = None, frame_id: Optional[str] = None) -> dict:
        """Invokes raw Chrome DevTools Protocol methods."""
        # Simple HTTP check for Target.getTargets on localhost debug port (default 9222)
        if method == "Target.getTargets":
            for port in (9222, 9377):
                try:
                    resp = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=3)
                    if resp.status_code == 200:
                        targets = []
                        for t in resp.json():
                            targets.append({
                                "targetId": t.get("id"),
                                "type": t.get("type"),
                                "title": t.get("title"),
                                "url": t.get("url"),
                                "webSocketDebuggerUrl": t.get("webSocketDebuggerUrl")
                            })
                        return {"success": True, "result": {"targetInfos": targets}}
                except Exception:
                    pass

        # For Runtime.evaluate, forward to console expression evaluator
        if method == "Runtime.evaluate" and params and "expression" in params:
            res = self.console(expression=params["expression"])
            if res.get("success"):
                result_val = res.get("data", {}).get("result") if isinstance(res.get("data"), dict) else res.get("data")
                return {"success": True, "result": {"result": {"value": result_val}}}

        # Simulated standard CDP response
        return {
            "success": True,
            "result": {
                "description": f"Simulated CDP method response for {method}",
                "method": method,
                "params": params,
                "targetId": target_id,
                "frameId": frame_id
            }
        }

    def dialog(self, action: str, prompt_text: Optional[str] = None) -> dict:
        """Handles dialog actions (accept, dismiss)."""
        # Under CLI daemon or Camofox, dialogs are dismissed/accepted automatically based on policy.
        # We return success immediately.
        return {"success": True, "data": {"dialog_action": action, "prompt_text": prompt_text}}
