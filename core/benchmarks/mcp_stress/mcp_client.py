"""Minimal MCP stdio client: speaks JSON-RPC to `python -m tools.infrastructure.server`.

Kept dependency-free on purpose so the stress driver talks to the server exactly
the way a real MCP client does — same transport, same framing, same schemas.
"""
import json
import subprocess
import threading
import time


class MCPClient:
    def __init__(self, cmd, cwd="/app/core", timeout=120):
        self.timeout = timeout
        self.proc = subprocess.Popen(
            cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self._id = 0
        self._lock = threading.Lock()

    def _rpc(self, method, params=None, timeout=None):
        with self._lock:
            self._id += 1
            msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
            if params is not None:
                msg["params"] = params
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()

            deadline = time.time() + (timeout or self.timeout)
            while time.time() < deadline:
                line = self.proc.stdout.readline()
                if not line:
                    raise RuntimeError("MCP server closed the connection")
                line = line.strip()
                if not line or not line.startswith("{"):
                    # Anything non-JSON on stdout is itself a protocol defect.
                    raise RuntimeError(f"NON-JSON ON STDOUT: {line[:200]!r}")
                data = json.loads(line)
                if data.get("id") == self._id:
                    return data
            raise TimeoutError(f"{method} timed out after {timeout or self.timeout}s")

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def initialize(self):
        r = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "kenbun-stress", "version": "1"},
        })
        self.notify("notifications/initialized")
        return r

    def list_tools(self):
        return self._rpc("tools/list").get("result", {}).get("tools", [])

    def call_tool(self, name, arguments, timeout=None):
        return self._rpc("tools/call", {"name": name, "arguments": arguments},
                         timeout=timeout)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
