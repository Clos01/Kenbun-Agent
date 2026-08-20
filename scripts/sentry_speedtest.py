#!/usr/bin/env python3
"""Sentry Speed & Latency Watchdog.

Autonomous network connection health benchmark engine using Ookla CLI.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
from typing import Any, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sentry-speedtest")

SPEEDTEST_BIN: str = os.getenv("SPEEDTEST_BIN", "/usr/local/bin/speedtest")
LOG_DIR: str = os.getenv("SENTRY_LOG_DIR", "/var/log/sentry")
LOG_FILE: str = os.path.join(LOG_DIR, "speedtest.json")
LATEST_FILE: str = os.path.join(LOG_DIR, "speedtest_latest.json")


def safe_write_json(file_path: str, data: Dict[str, Any], append: bool = False) -> None:
    """Write JSON data to disk atomically with explicit 0o640 permissions."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    fd = os.open(file_path, flags, 0o640)
    try:
        with open(fd, "w", encoding="utf-8", closefd=True) as f:
            if append:
                f.write(json.dumps(data) + "\n")
            else:
                json.dump(data, f, indent=2)
    except Exception as err:
        logger.error("Failed writing to %s: %s", file_path, err)


def run_speedtest() -> Dict[str, Any] | None:
    """Execute Ookla Speedtest binary and parse JSON output safely."""
    cmd = [SPEEDTEST_BIN, "--format=json", "--accept-license", "--accept-gdpr"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
        if res.returncode != 0:
            logger.warning("Speedtest binary returned non-zero code: %d. Error: %s", res.returncode, res.stderr.strip())
            return None
        parsed = json.loads(res.stdout)
        if isinstance(parsed, dict):
            return parsed
        logger.error("Unexpected non-dict payload from speedtest binary.")
        return None
    except subprocess.TimeoutExpired:
        logger.error("Speedtest execution timed out after 90 seconds.")
        return None
    except json.JSONDecodeError as err:
        logger.error("Failed to decode speedtest JSON output: %s", err)
        return None
    except OSError as err:
        logger.error("Operating system error during speedtest execution: %s", err)
        return None


def main() -> None:
    """Run benchmark and write structured telemetry metrics."""
    os.makedirs(LOG_DIR, mode=0o750, exist_ok=True)
    logger.info("Executing Ookla Speedtest benchmark on connection...")

    data = run_speedtest()
    if not data:
        logger.error("Aborting telemetry update due to speedtest failure.")
        return

    ping_obj = data.get("ping", {}) if isinstance(data.get("ping"), dict) else {}
    download_obj = data.get("download", {}) if isinstance(data.get("download"), dict) else {}
    upload_obj = data.get("upload", {}) if isinstance(data.get("upload"), dict) else {}
    server_obj = data.get("server", {}) if isinstance(data.get("server"), dict) else {}
    interface_obj = data.get("interface", {}) if isinstance(data.get("interface"), dict) else {}

    ping_latency: float = round(float(ping_obj.get("latency", 0)), 2)
    ping_jitter: float = round(float(ping_obj.get("jitter", 0)), 2)
    packet_loss: float = round(float(data.get("packetLoss", 0)), 2)

    dl_bytes = float(download_obj.get("bandwidth", 0))
    ul_bytes = float(upload_obj.get("bandwidth", 0))

    download_mbps: float = round((dl_bytes * 8) / 1_000_000, 2)
    upload_mbps: float = round((ul_bytes * 8) / 1_000_000, 2)

    isp: str = str(data.get("isp", "Unknown ISP"))
    client_ip: str = str(interface_obj.get("externalIp", "Unknown IP"))
    server_name: str = str(server_obj.get("name", "Local Server"))
    server_loc: str = str(server_obj.get("location", "Unknown Location"))
    result_url: str = str(data.get("result", {}).get("url", "") if isinstance(data.get("result"), dict) else "")

    now_iso: str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    summary: Dict[str, Any] = {
        "timestamp": now_iso,
        "isp": isp,
        "external_ip": client_ip,
        "download_mbps": download_mbps,
        "upload_mbps": upload_mbps,
        "ping_ms": ping_latency,
        "jitter_ms": ping_jitter,
        "packet_loss_pct": packet_loss,
        "server": f"{server_name} ({server_loc})",
        "result_url": result_url,
    }

    safe_write_json(LATEST_FILE, summary, append=False)
    safe_write_json(LOG_FILE, summary, append=True)

    print("")
    print("=" * 60)
    print("  ⚡ OOKLA BENCHMARK RESULTS")
    print("=" * 60)
    print(f"  🌐 ISP:           {isp} ({client_ip})")
    print(f"  🎯 Server:        {server_name} ({server_loc})")
    print(f"  ⏱️  Ping Latency:  {ping_latency} ms (Jitter: {ping_jitter} ms)")
    print(f"  📦 Packet Loss:   {packet_loss}%")
    print(f"  ⬇️  Download:      {download_mbps} Mbps")
    print(f"  ⬆️  Upload:        {upload_mbps} Mbps")
    if result_url:
        print(f"  🔗 Verified Link: {result_url}")
    print("=" * 60)
    print("")


if __name__ == "__main__":
    main()
