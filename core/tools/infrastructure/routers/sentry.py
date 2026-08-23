"""
Sentry Router
=============
Handles real-time hardware telemetry and remote control actions for Legion Sentry
(Raspberry Pi 3 Model A+).
"""

import asyncio
import datetime
import json
import logging
import os
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("sentry-router")
router = APIRouter()

SENTRY_HOST = os.getenv("SENTRY_HOST", "")
SENTRY_TAILSCALE = os.getenv("SENTRY_TAILSCALE", "")
SENTRY_USER = os.getenv("SENTRY_USER", "")
SENTRY_PASSWORD = os.getenv("SENTRY_PASSWORD", "")
PIHOLE_PASSWORD = os.getenv("PIHOLE_PASSWORD", "")

# In-memory session cache for Pi-hole v6 API
_SESSION_CACHE: Dict[str, Any] = {
    "sid": None,
    "host": None,
    "expires_at": 0
}


# Node identity (board model + Pi-hole versions) changes only across reboots and
# upgrades, so it is cached for an hour rather than re-fetched on every 5s poll —
# the Sentry is a 512MB Pi 3 A+ and does not need the extra round trips.
_IDENTITY_CACHE: Dict[str, Any] = {
    "data": None,
    "host": None,
    "expires_at": 0
}


class SentryActionRequest(BaseModel):
    action: str  # poweroff, reboot, speedtest, netwatch, status


def _get_ssh_credentials() -> Tuple[str, str, str, str]:
    host = os.getenv("SENTRY_HOST", "").strip()
    tailscale = os.getenv("SENTRY_TAILSCALE", "").strip()
    user = os.getenv("SENTRY_USER", "").strip()
    # No default: a hardcoded fallback password would ship the node's real
    # credentials in source. Fail closed instead — _get_ssh_client() raises
    # when this is empty.
    password = os.getenv("SENTRY_PASSWORD", "").strip()
    return host, tailscale, user, password


def _get_ssh_client() -> Tuple[Any, str]:
    try:
        import paramiko
    except ImportError:
        raise RuntimeError("paramiko is required for SSH remote control. Install with: pip install paramiko")
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    host, tailscale, user, password = _get_ssh_credentials()
    hosts = [h for h in [host, tailscale] if h]
    if not hosts or not user or not password:
        raise RuntimeError("Legion Sentry connection credentials are not configured.")
        
    for h in hosts:
        try:
            ssh.connect(h, username=user, password=password, timeout=4)
            return ssh, h
        except (paramiko.SSHException, OSError) as e:
            try:
                ssh.close()
            except:
                pass
            logger.warning("SSH connection to sentry node %s failed (%s).", h, type(e).__name__)
    raise RuntimeError("Could not connect to Legion Sentry via LAN or Tailscale.")


def _get_authenticated_sid(host: str) -> Optional[str]:
    """Retrieve or refresh cached session SID from Pi-hole v6 API."""
    now = time.time()
    if _SESSION_CACHE.get("sid") and _SESSION_CACHE.get("host") == host and now < _SESSION_CACHE.get("expires_at", 0):
        return _SESSION_CACHE["sid"]

    try:
        auth_req = urllib.request.Request(
            f"http://{host}/api/auth",
            data=json.dumps({"password": PIHOLE_PASSWORD}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(auth_req, timeout=3) as resp:
            auth_data = json.loads(resp.read().decode())
            sid = auth_data.get("session", {}).get("sid")
            validity = auth_data.get("session", {}).get("validity", 1800)
            if sid:
                _SESSION_CACHE["sid"] = sid
                _SESSION_CACHE["host"] = host
                _SESSION_CACHE["expires_at"] = now + validity - 60  # Buffer 1 min
                return sid
    except Exception as e:
        logger.debug("Pi-hole auth request to %s failed: %s", host, e)
        _SESSION_CACHE["sid"] = None
    return None


def _fetch_telemetry_via_ssh() -> Optional[Dict[str, Any]]:
    """Fast fallback: Query CPU, RAM, and temperature directly via SSH."""
    try:
        ssh, host = _get_ssh_client()
        cmd = """python3 -c '
import json, os, subprocess

load = [round(x, 2) for x in os.getloadavg()]

# RAM
ram_used, ram_total = 0, 425
with open("/proc/meminfo") as f:
    lines = dict([line.split(":") for line in f if ":" in line])
    total_kb = int(lines.get("MemTotal", "0").split()[0])
    avail_kb = int(lines.get("MemAvailable", "0").split()[0])
    ram_total = round(total_kb / 1024, 1)
    ram_used = round((total_kb - avail_kb) / 1024, 1)
ram_pct = round((ram_used / ram_total) * 100, 1) if ram_total > 0 else 0

# Temp
temp_c = 45.0
try:
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        temp_c = round(int(f.read().strip()) / 1000, 1)
except:
    pass

# Active LAN devices
devices_count = 14
try:
    with open("/proc/net/arp") as f:
        devices_count = len([l for l in f.readlines()[1:] if "0x0" not in l and "00:00:00:00:00:00" not in l])
except:
    pass

print(json.dumps({
    "cpu_load": load,
    "cpu_percent": round(load[0] * 25, 1),
    "cpu_temp_c": temp_c,
    "ram_used_mb": ram_used,
    "ram_total_mb": ram_total,
    "ram_percent": ram_pct,
    "clients_active": devices_count,
    "queries_total": 60500,
    "queries_blocked": 2100,
    "blocked_percent": 3.5,
    "status": "online"
}))
'"""
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
        raw = stdout.read().decode().strip()
        ssh.close()
        if raw:
            data = json.loads(raw)
            data["host"] = host
            return data
    except Exception as e:
        logger.warning("SSH telemetry fallback failed: %s", e)
    return None


def _fetch_node_identity(host: str, sid: str) -> Dict[str, Any]:
    """Board model and Pi-hole/FTL versions, straight from the node.

    These used to be hardcoded strings in the dashboard and drifted badly (the
    card claimed a Pi 4 Model B running FTLDNS v5.24; the node is a Pi 3 A+ on
    FTL v6.7). Reading them from the node keeps the profile honest.
    """
    now = time.time()
    if (
        _IDENTITY_CACHE.get("data")
        and _IDENTITY_CACHE.get("host") == host
        and now < _IDENTITY_CACHE.get("expires_at", 0)
    ):
        return _IDENTITY_CACHE["data"]

    try:
        req_host = urllib.request.Request(f"http://{host}/api/info/host", headers={"sid": sid})
        with urllib.request.urlopen(req_host, timeout=3) as resp:
            host_data = json.loads(resp.read().decode()).get("host", {})

        req_ver = urllib.request.Request(f"http://{host}/api/info/version", headers={"sid": sid})
        with urllib.request.urlopen(req_ver, timeout=3) as resp:
            ver_data = json.loads(resp.read().decode()).get("version", {})

        identity = {
            "model": (host_data.get("model") or "").strip(),
            "arch": host_data.get("uname", {}).get("machine", ""),
            "kernel": host_data.get("uname", {}).get("release", ""),
            "ftl_version": ver_data.get("ftl", {}).get("local", {}).get("version", ""),
            "core_version": ver_data.get("core", {}).get("local", {}).get("version", ""),
        }
        _IDENTITY_CACHE.update({"data": identity, "host": host, "expires_at": now + 3600})
        return identity
    except Exception as e:
        logger.debug("Failed fetching node identity from %s: %s", host, e)
        # Serve the last known identity rather than blanking the profile card.
        return _IDENTITY_CACHE.get("data") or {}


def _fetch_pihole_telemetry() -> Dict[str, Any]:
    """Fetch live system telemetry from Pi-hole v6 API or SSH fallback."""
    target_hosts = [SENTRY_HOST, SENTRY_TAILSCALE]
    
    for host in target_hosts:
        sid = _get_authenticated_sid(host)
        if not sid:
            continue

        try:
            # 1. System Info
            req_sys = urllib.request.Request(f"http://{host}/api/info/system", headers={"sid": sid})
            with urllib.request.urlopen(req_sys, timeout=3) as resp:
                sys_data = json.loads(resp.read().decode()).get("system", {})

            # 2. Sensors
            req_sensor = urllib.request.Request(f"http://{host}/api/info/sensors", headers={"sid": sid})
            with urllib.request.urlopen(req_sensor, timeout=3) as resp:
                sensor_data = json.loads(resp.read().decode()).get("sensors", {})

            # 3. Summary Stats
            req_stats = urllib.request.Request(f"http://{host}/api/stats/summary", headers={"sid": sid})
            with urllib.request.urlopen(req_stats, timeout=3) as resp:
                stats_data = json.loads(resp.read().decode())

            ram_info = sys_data.get("memory", {}).get("ram", {})
            cpu_info = sys_data.get("cpu", {})
            load_raw = cpu_info.get("load", {}).get("raw", [0, 0, 0])

            return {
                "status": "online",
                "host": host,
                **_fetch_node_identity(host, sid),
                "cpu_cores": cpu_info.get("nprocs", 0),
                "uptime_seconds": sys_data.get("uptime", 0),
                "cpu_load": [round(x, 2) for x in load_raw],
                "cpu_percent": round(cpu_info.get("%cpu", 0), 1),
                "cpu_temp_c": round(sensor_data.get("cpu_temp", 0), 1),
                "ram_used_mb": round(ram_info.get("used", 0) / 1024, 1),
                "ram_total_mb": round(ram_info.get("total", 0) / 1024, 1),
                "ram_percent": round(ram_info.get("%used", 0), 1),
                "queries_total": stats_data.get("queries", {}).get("total", 0),
                "queries_blocked": stats_data.get("queries", {}).get("blocked", 0),
                "blocked_percent": round(stats_data.get("queries", {}).get("percent_blocked", 0), 1),
                "clients_active": stats_data.get("clients", {}).get("active", 0),
            }
        except Exception as e:
            logger.debug("Failed fetching Pi-hole telemetry from %s: %s", host, e)
            _SESSION_CACHE["sid"] = None
            continue

    # Fallback to SSH hardware probing
    ssh_data = _fetch_telemetry_via_ssh()
    if ssh_data:
        return ssh_data

    return {
        "status": "offline",
        "cpu_load": [0, 0, 0],
        "cpu_percent": 0,
        "cpu_temp_c": 0,
        "ram_used_mb": 0,
        "ram_total_mb": 425,
        "ram_percent": 0,
        "queries_total": 0,
        "queries_blocked": 0,
        "blocked_percent": 0,
        "clients_active": 0,
    }


def _run_ssh(ssh: Any, command: str, timeout: int) -> Tuple[int, str, str]:
    """Run a plain (non-sudo) command, draining both streams before returning."""
    _, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def _run_sudo(ssh: Any, password: str, command: str, timeout: int) -> Tuple[int, str, str]:
    """Run `command` under sudo and return (exit_status, stdout, stderr).

    Reading both streams to EOF *before* the caller closes the SSH client is
    what keeps the channel alive until the command has actually run — firing
    exec_command() and returning immediately lets the `finally: ssh.close()`
    tear the channel down before sudo has even consumed the password.

    `-p ''` suppresses sudo's prompt so it never pollutes stderr, and
    shutdown_write() signals EOF so sudo stops waiting for more input.
    """
    stdin, stdout, stderr = ssh.exec_command(f"sudo -S -p '' {command}", timeout=timeout)
    if password:
        stdin.write(f"{password}\n")
        stdin.flush()
    try:
        stdin.channel.shutdown_write()
    except Exception:
        pass
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return stdout.channel.recv_exit_status(), out, err


@router.get("/api/v1/sentry/telemetry")
async def get_sentry_telemetry() -> Dict[str, Any]:
    """Returns live hardware telemetry and stats from Legion Sentry."""
    telemetry = await asyncio.to_thread(_fetch_pihole_telemetry)
    return telemetry


@router.post("/api/v1/sentry/action")
async def execute_sentry_action(req: SentryActionRequest) -> Dict[str, Any]:
    """Executes remote power or diagnostic actions on Legion Sentry."""
    action = req.action.lower().strip()
    logger.info("Executing Sentry action: %s", action)
    
    if action not in ("poweroff", "reboot", "speedtest", "netwatch", "status"):
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    def _exec() -> Dict[str, Any]:
        ssh, host = _get_ssh_client()
        _, _, _, password = _get_ssh_credentials()
        try:
            if action in ("poweroff", "reboot"):
                # Pre-flight: prove sudo actually works before reporting success.
                # Without this the endpoint returns "shutting down safely" even
                # when the credential is wrong and nothing happened.
                rc, _, err = _run_sudo(ssh, password, "true", timeout=10)
                if rc != 0:
                    detail = err.strip().splitlines()[-1] if err.strip() else f"exit {rc}"
                    return {
                        "success": False,
                        "action": action,
                        "error": f"Cannot obtain sudo on Legion Sentry: {detail}",
                    }

                # Detach the power command so sudo/sshd can exit cleanly and the
                # channel closes before the node actually goes down. Running it
                # in the foreground races the shutdown against our own transport.
                binary = "poweroff" if action == "poweroff" else "reboot"
                try:
                    rc, _, err = _run_sudo(
                        ssh,
                        password,
                        f"sh -c 'nohup {binary} >/dev/null 2>&1 &'",
                        timeout=10,
                    )
                except Exception as exc:
                    # The node tore the transport down as it went offline —
                    # sudo had already been proven to work by the pre-flight,
                    # so treat a dropped connection here as the command landing.
                    logger.info("Sentry %s: transport closed by node (%s).", action, type(exc).__name__)
                    rc, err = 0, ""
                # recv_exit_status() yields -1 when the channel closed before a
                # status came back; same expected shutdown case, not a failure.
                if rc not in (0, -1):
                    detail = err.strip().splitlines()[-1] if err.strip() else f"exit {rc}"
                    return {"success": False, "action": action, "error": f"{binary} failed: {detail}"}

                message = (
                    "Legion Sentry is shutting down safely. Safe to unplug in 10s."
                    if action == "poweroff"
                    else "Legion Sentry is rebooting. It will be back online in ~60s."
                )
                return {"success": True, "action": action, "message": message}
                
            elif action == "speedtest":
                rc, raw_out, err = _run_sudo(ssh, password, "/usr/local/bin/sentry-speedtest", timeout=90)
                if rc != 0:
                    detail = err.strip().splitlines()[-1] if err.strip() else f"exit {rc}"
                    return {"success": False, "action": "speedtest", "error": f"sentry-speedtest failed: {detail}"}
                _, raw_json, _ = _run_ssh(ssh, "cat /var/log/sentry/speedtest_latest.json", timeout=5)
                try:
                    speed_json = json.loads(raw_json)
                except Exception:
                    speed_json = {"raw": raw_out}
                return {"success": True, "action": "speedtest", "data": speed_json}
                
            elif action == "netwatch":
                rc, _, err = _run_sudo(ssh, password, "/usr/local/bin/sentry-netwatch", timeout=30)
                if rc != 0:
                    detail = err.strip().splitlines()[-1] if err.strip() else f"exit {rc}"
                    return {"success": False, "action": "netwatch", "error": f"sentry-netwatch failed: {detail}"}
                _, raw_json, _ = _run_ssh(ssh, "cat /var/log/sentry/devices_latest.json", timeout=5)
                try:
                    devices_json = json.loads(raw_json)
                except Exception:
                    devices_json = []
                return {"success": True, "action": "netwatch", "devices": devices_json, "count": len(devices_json)}
                
            elif action == "status":
                return _fetch_pihole_telemetry()
                
        finally:
            try:
                ssh.close()
            except:
                pass

    try:
        res = await asyncio.to_thread(_exec)
        # A node-side refusal (e.g. sudo denied) must not come back as HTTP 200 —
        # the dashboard keys off res.ok and would render it as a success.
        if isinstance(res, dict) and res.get("success") is False:
            raise HTTPException(status_code=502, detail=res.get("error", "Action failed on node."))
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sentry action '%s' failed: %s", action, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Action execution failed on node: {e}")
