import os
import re
import logging
import shutil
from tools.infrastructure.config import settings

logger = logging.getLogger("computer_use_engine")

DANGEROUS_KEYS = {
    "empty-trash", "force-delete", "lock-screen", "logout", "force-logout",
    "poweroff", "shutdown", "reboot"
}

DANGEROUS_PATTERNS = [
    r"curl\s+.*\s*\|\s*bash",
    r"wget\s+.*\s*\|\s*bash",
    r"sudo\s+rm\s+",
    r"rm\s+-rf",
    r"fork\s*bomb",
    r":\(\)\{\s*:\s*\|\s*:\s*&\s*\};:",
    r"dd\s+if=/dev/",
    r"mkfs\.",
    r">/dev/null\s+2>&1"
]

def validate_action_safety(action: str, kwargs: dict):
    """Enforces shell injections, dangerous keyboard shortcuts, and password entry blocks."""
    # Check typing text
    if action == "type" and "text" in kwargs:
        text = str(kwargs["text"])
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                raise ValueError(f"Blocked: Dangerous pattern in type text: '{pattern}'")
        if any(pwd in text.lower() for pwd in ("password", "passwd", "secret_key", "api_key", "token")):
            raise ValueError("Blocked: Typing passwords or credentials is forbidden for security.")

    # Check key combinations
    if action == "key" and "keys" in kwargs:
        keys = str(kwargs["keys"]).lower()
        if any(dk in keys for dk in DANGEROUS_KEYS):
            raise ValueError(f"Blocked: Destructive key combo detected: '{keys}'")

class ComputerUseEngine:
    def __init__(self):
        self.cmd = settings.CUA_DRIVER_CMD or "cua-driver"
        self.telemetry_enabled = "1" if settings.CUA_TELEMETRY else "0"
        self.backend = settings.COMPUTER_USE_BACKEND or "mcp"

    def _is_driver_available(self) -> bool:
        return shutil.which(self.cmd) is not None

    async def execute(self, action: str, **kwargs) -> dict:
        """Validates safety, determines backend routing, and executes the computer_use action."""
        # 1. Enforce Safety Guardrails
        validate_action_safety(action, kwargs)

        # 2. Check Backend Routing & Driver Availability
        if self.backend == "noop" or not self._is_driver_available():
            logger.info(f"Using simulated fallback for computer_use action: '{action}'")
            return self._execute_simulated(action, **kwargs)

        # 3. Connect to cua-driver MCP stdio server
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            # Setup environment (override telemetry options)
            env = os.environ.copy()
            env["CUA_DRIVER_RS_TELEMETRY_ENABLED"] = self.telemetry_enabled

            server_params = StdioServerParameters(
                command=self.cmd,
                args=["mcp"],
                env=env
            )

            # Map arguments for the single computer_use tool call
            payload = {"action": action}
            payload.update(kwargs)

            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Call the single 'computer_use' tool exposed by cua-driver
                    tool_resp = await session.call_tool("computer_use", payload)
                    
                    # Format standard return format
                    if hasattr(tool_resp, "content"):
                        # Extract text contents or base64 screenshots
                        results = []
                        for content in tool_resp.content:
                            if hasattr(content, "text"):
                                results.append(content.text)
                            elif hasattr(content, "data"):
                                results.append(content.data)
                        return {
                            "success": True,
                            "data": "\n".join(results) if len(results) > 1 else (results[0] if results else "")
                        }
                    return {"success": True, "data": str(tool_resp)}

        except Exception as e:
            logger.error(f"Failed to connect to cua-driver MCP stdio server: {e}")
            return {"success": False, "error": str(e)}

    def _execute_simulated(self, action: str, **kwargs) -> dict:
        """Simulates computer use events for testing and environment portability."""
        if action == "capture":
            mode = kwargs.get("mode", "som")
            if mode == "som":
                return {
                    "success": True,
                    "data": {
                        "screenshot": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                        "elements": [
                            {"id": 1, "role": "button", "name": "Mail Box", "box": [10, 20, 100, 40]},
                            {"id": 2, "role": "searchbox", "name": "Search", "box": [120, 20, 300, 40]}
                        ]
                    }
                }
            else:
                return {
                    "success": True,
                    "data": {
                        "ax_tree": "- window \"Simulator Workspace\"\n  - button \"Mail Box\" [ref=1]\n  - searchbox \"Search\" [ref=2]"
                    }
                }
        
        return {
            "success": True,
            "data": {
                "status": "simulated",
                "action": action,
                "arguments": kwargs
            }
        }
