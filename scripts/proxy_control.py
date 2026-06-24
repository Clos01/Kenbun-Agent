#!/usr/bin/env python3
"""
Kenbun Subscription Proxy Control CLI
======================================
CLI script to start, stop, check status, and list providers for the
Kenbun Subscription Proxy server.
"""

import os
import sys
import time
import signal
import socket
import argparse
import subprocess
from pathlib import Path

# Add project root and core directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "core"))

from tools.infrastructure.config import settings

PID_FILE = settings.BRAIN_HEALTH_DIR / "proxy.pid"
LOG_FILE = settings.BRAIN_HEALTH_DIR / "proxy.log"

def is_port_in_use(host: str, port: int) -> bool:
    """Checks if a port is actively listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect((host, port))
            return True
    except Exception:
        return False

def get_running_pid() -> int:
    """Reads the PID from the pidfile and returns it if the process is alive."""
    if not PID_FILE.exists():
        return 0
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is still running
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        return 0

def start_proxy(host: str, port: int):
    """Starts the proxy server in the background."""
    print(f"Checking if port {port} is already in use...")
    if is_port_in_use(host, port):
        print(f"Error: Port {port} is already in use. Cannot start proxy.")
        sys.exit(1)

    pid = get_running_pid()
    if pid:
        print(f"Proxy is already running with PID {pid}.")
        sys.exit(0)

    print(f"Starting Subscription Proxy on {host}:{port}...")
    settings.BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)

    # Prepare command and environment
    cmd = [
        sys.executable,
        "-m", "uvicorn",
        "tools.infrastructure.proxy_server:app",
        "--host", host,
        "--port", str(port)
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{root_dir / 'core'}{os.pathsep}{env.get('PYTHONPATH', '')}"

    # Open log file
    log_f = open(LOG_FILE, "a", encoding="utf-8")

    # Start the process in the background
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=log_f,
        env=env,
        cwd=str(root_dir),
        start_new_session=True  # Detach process group
    )

    # Write PID file
    PID_FILE.write_text(str(proc.pid))
    print(f"Proxy process spawned with PID {proc.pid}. Logs redirected to {LOG_FILE}.")

    # Wait and check if it successfully bound to the port
    success = False
    for _ in range(10):
        time.sleep(0.5)
        if is_port_in_use(host, port):
            success = True
            break
        if proc.poll() is not None:
            break

    if success:
        print(f"✅ Subscription Proxy successfully started and listening on http://{host}:{port}")
    else:
        print("❌ Error: Proxy server failed to start within timeout. Check logs:")
        if LOG_FILE.exists():
            try:
                print(LOG_FILE.read_text().splitlines()[-10:])
            except Exception:
                pass
        sys.exit(1)

def stop_proxy():
    """Stops the running proxy server."""
    pid = get_running_pid()
    if not pid:
        # Check if port is in use anyway
        if is_port_in_use("127.0.0.1", 8645):
            print("No PID file found, but port 8645 is active. Process might have been started externally.")
        else:
            print("Proxy is not running.")
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except Exception:
                pass
        return

    print(f"Stopping Subscription Proxy (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait up to 3 seconds for graceful shutdown
        for _ in range(6):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                print("✅ Stopped gracefully.")
                break
        else:
            # Force kill if still running
            print("Force killing process...")
            os.kill(pid, signal.SIGKILL)
            print("✅ Force killed.")
    except ProcessLookupError:
        print("Process already stopped.")
    except Exception as e:
        print(f"Error stopping process: {e}")

    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception:
            pass

def show_status():
    """Displays the status of the proxy server."""
    pid = get_running_pid()
    port = 8645 # default port
    # Check default host/port status
    port_active = is_port_in_use("127.0.0.1", port)
    
    status_info = {
        "status": "stopped",
        "pid": pid,
        "port": port,
        "host": "127.0.0.1",
        "port_active": port_active
    }

    if pid and port_active:
        status_info["status"] = "running"
        print(f"Subscription Proxy is RUNNING (PID {pid}, listening on port {port})")
    elif pid:
        status_info["status"] = "zombie"
        print(f"Subscription Proxy is in ZOMBIE state (PID {pid} exists, but port {port} is not listening)")
    elif port_active:
        status_info["status"] = "external"
        print(f"Subscription Proxy (or another service) is active on port {port}, but no local PID is tracked")
    else:
        print("Subscription Proxy is STOPPED")

    return status_info

def show_providers():
    """Prints configured upstream providers."""
    providers = []
    if settings.GEMINI_API_KEY:
        providers.append("gemini")
    if settings.DEEPSEEK_API_KEY:
        providers.append("deepseek")
    if settings.OPENAI_API_KEY:
        providers.append("openai")
    if settings.ANTHROPIC_API_KEY:
        providers.append("anthropic")
    if hasattr(settings, "XAI_API_KEY") and settings.XAI_API_KEY:
        providers.append("xai")
    if hasattr(settings, "NVIDIA_API_KEY") and settings.NVIDIA_API_KEY:
        providers.append("nvidia")
        
    print(f"Configured upstream providers: {', '.join(providers) if providers else 'None'}")
    return providers

def main():
    parser = argparse.ArgumentParser(description="Kenbun Subscription Proxy Control CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the proxy server")
    start_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    start_parser.add_argument("--port", type=int, default=8645, help="Port to bind to (default: 8645)")

    # Stop command
    subparsers.add_parser("stop", help="Stop the proxy server")

    # Status command
    subparsers.add_parser("status", help="Get proxy server status")

    # Providers command
    subparsers.add_parser("providers", help="List configured providers")

    args = parser.parse_args()

    if args.command == "start":
        start_proxy(args.host, args.port)
    elif args.command == "stop":
        stop_proxy()
    elif args.command == "status":
        show_status()
    elif args.command == "providers":
        show_providers()

if __name__ == "__main__":
    main()
