import sys
import os
from pathlib import Path

# Load .env manually
env_path = Path(".env")
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                val = val.strip().strip("'\"")
                os.environ[key.strip()] = val

sys.path.insert(0, str(Path("core").resolve()))

from tools.strategy.planka_workflow import sync_pipeline_start, sync_pipeline_step
from tools.infrastructure.planka import planka_get_board

# Steps for E2E Testing
e2e_steps = [
    {"id": "T1", "label": "E2E Test Infra Setup"},
    {"id": "T2", "label": "Tier 1 & 2 Test Suite"},
    {"id": "T3", "label": "Tier 3 & 4 Test Suite"}
]

# Steps for Implementation
impl_steps = [
    {"id": "M1", "label": "Tenant Context & Refactoring"},
    {"id": "M2", "label": "Zod Metadata Validation"},
    {"id": "M3", "label": "Normalization & Component Registry"},
    {"id": "M4", "label": "Heritage Styling Enforcement"},
    {"id": "M5", "label": "Final E2E Integration & Verification"}
]

print("Initializing Planka sync for E2E Testing Track...")
e2e_ctx = sync_pipeline_start(
    workflow="E2E Testing Track",
    task="Implement the 4-tier E2E test suite for the Aura Lead OS Next.js frontend update.",
    steps=e2e_steps,
    board_id="1803497714239931407"
)
print("E2E Context:", e2e_ctx)

print("\nInitializing Planka sync for Implementation Track...")
impl_ctx = sync_pipeline_start(
    workflow="Implementation Track",
    task="Update frontend data fetching/state to use UUIDs, inject tenant_id via Context, add Zod schema, implement Normalization & Component Registry, and enforce Heritage design tokens.",
    steps=impl_steps,
    board_id="1803497714239931407"
)
print("Implementation Context:", impl_ctx)

# Let's save the context to a file so we can update them later
import json
with open(".agents/orchestrator/planka_context.json", "w") as f:
    json.dump({
        "e2e": e2e_ctx,
        "impl": impl_ctx
    }, f, indent=2)
print("Context saved to .agents/orchestrator/planka_context.json")
