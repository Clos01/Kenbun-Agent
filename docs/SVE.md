# Sovereign Verification Engine (SVE)

The **Sovereign Verification Engine (SVE)**, located in `core/tools/autonomic/`, is Kenbun's System 5.1 capability. It acts as the ultimate architectural immune system, designed to enforce codebase laws, prevent architectural drift, and automatically heal broken logic.

## 📡 The SVE Pulse

The heartbeat of this system is the `sve_pulse.py` background daemon. 

### Periodic Scanning
- `sve_pulse.py` periodically scans the entire `core/` directory hierarchy (e.g., `tools/infrastructure`, `tools/strategy`, `tools/audit`, `tools/autonomic`, etc.).
- It extracts the Abstract Syntax Tree (AST) of every `.py` file and passes it through the `audit_code()` engine (`tools.infrastructure.sovereign_verifier`).
- The engine checks for hardcoded secrets, disallowed imports, non-twelve-factor configuration usage, and deviations from Kenbun's architectural design patterns.

### The Sovereign Registry
- The results of every scan (Total Files, Clean Files, and specific structural breaches) are aggregated and saved into `sovereign_registry.json` inside the `brain_health` directory.
- This JSON file acts as the source of truth for the health score of the entire repository.
- If architectural breaches are detected, the pulse daemon broadcasts high-priority alerts via `log_reflection()`.

## 🛠️ Interactive Autonomic Fixes

The SVE isn't just a static linter; it is intrinsically tied to the **Observatory Dashboard**. 

1. **Inspector Panel**: The `sovereign_registry.json` data is streamed directly to the Observatory UI (`dashboard/src/components/galaxy-map/InspectorPanel.tsx`).
2. **Interactive Audits**: From the dashboard, an operator can click on any breached node to manually trigger an interactive SVE code audit on that specific file.
3. **Autonomic Corrector**: When an operator clicks **"Autofix Bugs"**, a payload is dispatched to the backend orchestrator (`orchestrator.py`). The Orchestrator routes this to the deterministic `bug_fix.py` pipeline, which:
   - Uses the `autonomic_corrector.py` tools to diagnose the AST failure.
   - Leverages the Ensemble-Based Auditing architecture (System 2) to draft a fix.
   - Pushes the fix back to the codebase.

## 🎯 Goal
By combining continuous background polling (`sve_pulse.py`), real-time visual telemetry (The Observatory), and deterministic LLM patch pipelines (`bug_fix.py`), the SVE ensures **infinite system stability and total architectural grounding**.
