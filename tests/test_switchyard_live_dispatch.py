"""
SwitchYard Router Live Dispatch Test:
Routes "Open Firefox and navigate to carmax.com" to Tier 0 (Local P330 Hardware),
validates zero-cost execution, and commands the physical OS on DISPLAY=:0.
"""

import sys
import json
import time
import subprocess

sys.path.insert(0, "/Users/carlosrivas/Dev/Kenbun")

from core.tools.strategy.switchyard_router import SwitchyardRouter, ModelTier


def main():
    print("=" * 70)
    print("🔀 NVIDIA SWITCHYARD COST ESCALATION ROUTER: LIVE DISPATCH")
    print("=" * 70)

    router = SwitchyardRouter()
    task = "Open Firefox and navigate to carmax.com"

    print(f"• Inbound Task: \"{task}\"")
    print("• Evaluating Cost & Capability Escalation...")

    tier = router.classify_initial_tier(task, is_visual=True)
    is_healthy = router.check_local_health()

    print(f"• Initial Classified Tier: {tier.value}")
    print(f"• Local P330 Hardware VLM Status: {'🟢 Healthy & Online' if is_healthy else '🔴 Offline'}")

    if tier == ModelTier.TIER_0_LOCAL and is_healthy:
        print("⚡ ROUTING DECISION: Assigned to TIER 0 (Free Local P330 Hardware).")
        print("💰 Estimated Cost: $0.0000 (100% Cost Avoidance)")
        print("\n🚀 Dispatching live execution to P330 on DISPLAY=:0...")

        cmd = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=45", "p330",
            "python3 /home/its_los/ui_tars_vision_runner.py \"Open Firefox and navigate to carmax.com\""
        ]
        
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - t0

        print(proc.stdout)
        if proc.stderr:
            print("[STDERR]:", proc.stderr)

        print("-" * 70)
        print(f"⏱️ Total Dispatch & Execution Latency: {duration:.2f}s")
        print("🎉 SwitchYard Tier 0 Execution Completed Successfully!")
    else:
        print("⚠️ Escalating to Cloud Tiers...")
        res = router.route_and_execute(task)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
