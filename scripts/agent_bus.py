#!/usr/bin/env python3
"""
🌸 Kenbun Agent Bus — Sub-Agent Coordination Layer
Manages background sub-agents spawned from the Termchat shell.
Agents communicate via a brain_health/agent_bus.json message queue.
"""
import os
import sys
import json
import time
import uuid
import threading
import subprocess
from pathlib import Path
from datetime import datetime

# ── Resolve bus file path ──────────────────────────────────────────────────────
def _get_bus_path() -> Path:
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    bus_dir = project_root / "brain_health"
    bus_dir.mkdir(parents=True, exist_ok=True)
    return bus_dir / "agent_bus.json"

_bus_lock = threading.Lock()

# ── Low-level bus read/write ───────────────────────────────────────────────────
def _read_bus() -> dict:
    path = _get_bus_path()
    if not path.exists():
        return {"agents": {}}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {"agents": {}}

def _write_bus(data: dict) -> None:
    path = _get_bus_path()
    with _bus_lock:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

def _update_agent(agent_id: str, fields: dict) -> None:
    data = _read_bus()
    if agent_id in data["agents"]:
        data["agents"][agent_id].update(fields)
        _write_bus(data)

# ── Spawn a background sub-agent ──────────────────────────────────────────────
def spawn_agent(task_name: str, command: str, cwd: str | None = None) -> str:
    """
    Spawns a background subprocess and registers it in the agent bus.
    Returns the agent_id string.
    """
    agent_id = f"agent-{str(uuid.uuid4())[:8]}"
    started_at = datetime.utcnow().isoformat()

    # Register the agent in the bus immediately
    data = _read_bus()
    data["agents"][agent_id] = {
        "id": agent_id,
        "task": task_name,
        "command": command,
        "status": "RUNNING",
        "started_at": started_at,
        "finished_at": None,
        "exit_code": None,
        "output": "",
        "error": "",
    }
    _write_bus(data)

    # Run in a background thread so we don't block the caller
    def _run():
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=600,
            )
            _update_agent(agent_id, {
                "status": "DONE" if result.returncode == 0 else "ERROR",
                "finished_at": datetime.utcnow().isoformat(),
                "exit_code": result.returncode,
                "output": result.stdout[-4000:] if result.stdout else "",
                "error": result.stderr[-2000:] if result.stderr else "",
            })
        except subprocess.TimeoutExpired:
            _update_agent(agent_id, {
                "status": "TIMEOUT",
                "finished_at": datetime.utcnow().isoformat(),
                "exit_code": -1,
                "error": "Agent timed out after 600 seconds.",
            })
        except Exception as e:
            _update_agent(agent_id, {
                "status": "ERROR",
                "finished_at": datetime.utcnow().isoformat(),
                "exit_code": -1,
                "error": str(e),
            })

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return agent_id

# ── List all agents ────────────────────────────────────────────────────────────
def list_agents() -> list[dict]:
    data = _read_bus()
    return list(data["agents"].values())

# ── Get a single agent's status ───────────────────────────────────────────────
def get_agent(agent_id: str) -> dict | None:
    data = _read_bus()
    return data["agents"].get(agent_id)

# ── Kill a running agent (best-effort) ────────────────────────────────────────
def kill_agent(agent_id: str) -> bool:
    """Mark agent as killed in bus (subprocess already daemonized, OS will GC it)."""
    data = _read_bus()
    if agent_id in data["agents"]:
        data["agents"][agent_id]["status"] = "KILLED"
        data["agents"][agent_id]["finished_at"] = datetime.utcnow().isoformat()
        _write_bus(data)
        return True
    return False

# ── Purge finished/old agents ─────────────────────────────────────────────────
def purge_agents() -> int:
    data = _read_bus()
    original = len(data["agents"])
    data["agents"] = {
        k: v for k, v in data["agents"].items()
        if v["status"] == "RUNNING"
    }
    _write_bus(data)
    return original - len(data["agents"])

# ── Poll for any new status updates (for main loop status line) ───────────────
def poll_status_lines() -> list[str]:
    """
    Returns a list of one-line status strings for any active or recently
    completed agents. Call this on every prompt cycle.
    """
    agents = list_agents()
    if not agents:
        return []
    lines = []
    for a in agents:
        status = a["status"]
        icon = {"RUNNING": "🟡", "DONE": "✅", "ERROR": "❌", "TIMEOUT": "⏰", "KILLED": "🛑"}.get(status, "⚪")
        elapsed = ""
        if a.get("started_at") and a.get("finished_at"):
            try:
                s = datetime.fromisoformat(a["started_at"])
                e = datetime.fromisoformat(a["finished_at"])
                secs = int((e - s).total_seconds())
                elapsed = f"  ({secs}s)"
            except Exception:
                pass
        lines.append(f"  {icon} [{a['id']}] {a['task']}{elapsed}")
    return lines


if __name__ == "__main__":
    # Quick CLI test
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "list":
            for a in list_agents():
                print(f"[{a['status']}] {a['id']} — {a['task']}")
        elif cmd == "spawn" and len(sys.argv) > 3:
            aid = spawn_agent(sys.argv[2], sys.argv[3])
            print(f"Spawned: {aid}")
        elif cmd == "kill" and len(sys.argv) > 2:
            print("Killed:", kill_agent(sys.argv[2]))
        elif cmd == "purge":
            print(f"Purged {purge_agents()} agents.")
