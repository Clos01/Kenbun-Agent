#!/usr/bin/env python3
"""
🩺 PC Brain Health Check
─────────────────────────
One command to answer "is my AI on the PC actually working?"

Usage:
    python3 scripts/check_pc_brain.py

What each test means in plain English:
    [1] Network — can the Mac even SEE the PC on the LAN?
    [2] Ollama  — is the Ollama service running on the PC?
    [3] Models  — what AIs are loaded and ready?
    [4] Brain   — can it actually answer a question?
    [5] Speed   — how fast is the GPU?

If ANY test fails, the script tells you EXACTLY what to do next.
"""
from __future__ import annotations
import os
import socket
import sys
import time

try:
    import requests
except ImportError:
    print("❌ Missing dependency: pip install requests")
    sys.exit(1)

# Setup paths to import core tools
from tools.infrastructure.config import settings

# Read from Sovereign Settings
PC_IP = settings.SWARM_PC_IP
PORT = settings.workers.p330_ollama_port
MODEL = settings.SWARM_MODEL

BASE = f"http://{PC_IP}:{PORT}"
SEP = "─" * 64


def header(text: str) -> None:
    print(f"\n{SEP}\n  {text}\n{SEP}")


def step(n: int, total: int, label: str) -> None:
    print(f"\n[{n}/{total}] {label}")


def ok(msg: str) -> None:
    print(f"      ✅ {msg}")


def bad(msg: str, hint: str = "") -> None:
    print(f"      ❌ {msg}")
    if hint:
        print(f"      💡 {hint}")


# ── Tests ─────────────────────────────────────────────────────────────
def test_network() -> bool:
    step(1, 5, f"Can the Mac reach the PC at {PC_IP}:{PORT}?")
    try:
        with socket.create_connection((PC_IP, PORT), timeout=3):
            ok(f"TCP connection to {PC_IP}:{PORT} succeeded")
            return True
    except socket.timeout:
        bad(
            "Connection timed out.",
            "PC is off, on a different network, or Windows Firewall is blocking port "
            f"{PORT}. On the PC (PowerShell as admin), run:\n"
            f"         netsh advfirewall firewall add rule name=\"Ollama Bridge\" "
            f"dir=in action=allow protocol=TCP localport={PORT}",
        )
    except Exception as exc:
        bad(f"{type(exc).__name__}: {exc}",
            "Check both machines are on the same Wi-Fi/LAN.")
    return False


def test_ollama_alive() -> bool:
    step(2, 5, "Is the Ollama service running?")
    try:
        r = requests.get(f"{BASE}/", timeout=4)
        if "Ollama is running" in r.text:
            ok(f"Ollama responded: '{r.text.strip()}'")
            return True
        bad(f"Got unexpected response: {r.text[:120]}")
    except Exception as exc:
        bad(
            f"{type(exc).__name__}: {exc}",
            "On the PC, run:  docker ps   — you should see a container named "
            "'ollama'. If not:  docker start ollama",
        )
    return False


def test_models() -> list[str]:
    step(3, 5, "What models are loaded?")
    try:
        r = requests.get(f"{BASE}/api/tags", timeout=5)
        models = r.json().get("models", [])
        if not models:
            bad(
                "Zero models loaded.",
                "On the PC: docker exec -it ollama ollama list  — if empty, you need "
                "to (re)create your custom model with `ollama create antigrav -f Modefile`.",
            )
            return []
        ok(f"Found {len(models)} model(s):")
        names = []
        for m in models:
            sz = m.get("size", 0) / 1e9
            print(f"         • {m['name']:30s} {sz:5.2f} GB")
            names.append(m["name"])
        return names
    except Exception as exc:
        bad(f"{type(exc).__name__}: {exc}")
        return []


def test_brain(model_name: str) -> bool:
    step(4, 5, f"Can '{model_name}' actually answer a question?")
    try:
        t0 = time.time()
        r = requests.post(
            f"{BASE}/api/chat",
            timeout=120,
            json={
                "model": model_name,
                "messages": [
                    {"role": "user", "content": "Reply with exactly: PONG"},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 20,
                    "repeat_penalty": 1.1,
                },
            },
        )
        dt = time.time() - t0
        if not r.ok:
            bad(f"HTTP {r.status_code}: {r.text[:200]}")
            return False
        answer = r.json()["message"]["content"].strip()
        ok(f"Replied in {dt:.1f}s: \"{answer[:120]}\"")
        return True
    except Exception as exc:
        bad(f"{type(exc).__name__}: {exc}")
        return False


def test_speed(model_name: str) -> None:
    step(5, 5, "Speed test (tokens per second)...")
    try:
        t0 = time.time()
        r = requests.post(
            f"{BASE}/api/generate",
            timeout=120,
            json={
                "model": model_name,
                "prompt": "Count from 1 to 30, one number per line.",
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 200},
            },
        )
        dt = time.time() - t0
        data = r.json()
        tokens = data.get("eval_count", 0)
        tps = tokens / dt if dt else 0
        verdict = "🚀 GPU is doing its job" if tps > 20 else "🐢 looks like CPU mode — check `docker exec ollama nvidia-smi`"
        ok(f"{tokens} tokens in {dt:.1f}s = {tps:.1f} tok/s   {verdict}")
    except Exception as exc:
        bad(f"{type(exc).__name__}: {exc}")


# ── Main ──────────────────────────────────────────────────────────────
def main() -> int:
    header(f"PC BRAIN HEALTH CHECK  →  {BASE}")
    print(f"  Target model: {MODEL}")

    if not test_network():
        return 1
    if not test_ollama_alive():
        return 2

    models = test_models()
    if not models:
        return 3

    target = MODEL if MODEL in models else models[0]
    if target != MODEL:
        print(f"      ⚠️  '{MODEL}' not found, falling back to '{target}'")

    if not test_brain(target):
        return 4

    test_speed(target)

    header("ALL SYSTEMS GO ✅")
    print(f"""
  Your local AI stack is fully operational:

      Mac  ──[LAN]──>  Windows ──[WSL2]──>  Docker ──[GPU]──>  Ollama
                       {PC_IP}:{PORT}                     {target}

  In your Sovereign Settings (core/tools/infrastructure/config.py), verify:
      PC_IP_ADDRESS={PC_IP}
      P330_OLLAMA_PORT={PORT}
      SWARM_MODEL={target}
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())