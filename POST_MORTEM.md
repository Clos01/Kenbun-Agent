# Post Mortems

## 2026-06-18: Next.js HMR Tailscale Isolation Bug

### Symptoms
When the Next.js Dashboard was deployed inside a Tailscale sidecar container network (NetworkMode: `container:tailscale`) on the Legion PC, the dashboard landing page would load, but the "Launch" button (which routes to `/observatory`) was completely unresponsive. The browser console showed errors related to blocked WebSocket connections.

### Root Cause
Next.js 16 (and newer versions) has strict cross-origin security for its development server. It will block the `/_next/webpack-hmr` WebSocket connection if the request origin does not match `localhost`. Because the user was accessing the dashboard via the Tailscale sidecar IP (`127.0.0.1`) and the host Tailscale IP (`127.0.0.1`), Next.js intercepted and blocked the HMR connection, which cascaded into a client-side routing freeze.

### Fix
Added explicit Tailscale IP whitelists to `dashboard/next.config.ts`:
```typescript
const nextConfig: NextConfig = {
  // @ts-ignore
  allowedDevOrigins: [
    "127.0.0.1", 
    "127.0.0.1", 
    "localhost"
  ],
};
```
Restarting the `portable_dashboard` container fully resolved the issue and restored full routing capabilities. This concept was also successfully ingested into the Hivemind (`save_to_hivemind`).

## 2026-06-24: Pipeline vs Tool Signature Ghost Bug

### Symptoms
The `analyze_review_request` step in `pipelines/code_review.py` was silently failing or crashing without breaking the whole process when `skip_if` was not triggered.

### Root Cause
There was a parameter mismatch between the orchestration pipeline lambda and the underlying registry function. `pipelines/code_review.py:56` passed `tech_key=` into the `analyze_bug` slot, but the registry mapped `analyze_bug` to `_analyze_bug(...)` which did not accept `tech_key`. This caused Python `TypeError` signature drifts that only fired under specific conditions.

### Fix
The Orchestrator pipeline was updated to use a unified `_analyze_review_request` wrapper that safely consumed `tech_key` and delegated correctly to the bug-fix analyzer. This enforces stricter contract boundaries between the dynamic pipeline lambdas and the target tool implementations.

## 2026-06-24: System 3 Dual-Write Memory Drift (Honcho vs ChromaDB)

### Symptoms
Agent memory retrieval (`knowledge_manager.py`) was sporadically missing critical architectural context that had been recently saved by the System 5 Reflection Agent.

### Root Cause
A partial migration left Kenbun in a state of "Dual-write / dual-read drift". `knowledge_manager.py` was reading from both Honcho and a legacy local ChromaDB instance, but writes were only going to one backend. This caused a divergence in the vector spaces.

### Fix
ChromaDB was formally deprecated and bypassed. A strict PostgreSQL/Honcho adapter was implemented as the sole source of truth for System 3. All writes and reads now flow exclusively through Honcho, eliminating the split-brain scenario.
