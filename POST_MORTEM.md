# Post Mortems

## 2026-06-18: Next.js HMR Tailscale Isolation Bug

### Symptoms
When the Next.js Dashboard was deployed inside a Tailscale sidecar container network (NetworkMode: `container:tailscale`) on the Legion PC, the dashboard landing page would load, but the "Launch" button (which routes to `/observatory`) was completely unresponsive. The browser console showed errors related to blocked WebSocket connections.

### Root Cause
Next.js 16 (and newer versions) has strict cross-origin security for its development server. It will block the `/_next/webpack-hmr` WebSocket connection if the request origin does not match `localhost`. Because the user was accessing the dashboard via the Tailscale sidecar IP (`100.120.241.65`) and the host Tailscale IP (`100.104.211.61`), Next.js intercepted and blocked the HMR connection, which cascaded into a client-side routing freeze.

### Fix
Added explicit Tailscale IP whitelists to `dashboard/next.config.ts`:
```typescript
const nextConfig: NextConfig = {
  // @ts-ignore
  allowedDevOrigins: [
    "100.120.241.65", 
    "100.104.211.61", 
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

## 2026-07-12: Flexbox Centering Container Modal Squishing Bug

### Symptoms
When clicking the "New Project" or "New Board" button inside the Kanban page, the modal popup dialog card would appear squished to a narrow vertical strip (~30px width), wrapping text vertically and overlapping elements.

### Root Cause
The outer backdrop element used a centering flexbox (`flex items-center justify-center`). The inner modal card had `w-full max-w-md` but was missing a `min-w` boundary. Inside a flex container with centering alignment, children shrink to their contents' absolute minimum width if no minimum width boundary is defined, causing the card layout to collapse.

### Fix
Added explicit minimum width classes (`min-w-[320px] sm:min-w-[400px]`) to the modal card container class lists across the local `Kenbun` and remote `crg-backoffice` repositories.

## 2026-07-12: n8n Docker OAuth Redirect URL Mismatch

### Symptoms
When setting up Google OAuth credentials in an n8n instance hosted behind a Cloudflare Tunnel (`n8n.rivasautomations.com`), the n8n UI generated an internal Tailscale IP callback URL (`http://100.100.199.127:5678/rest/oauth2-credential/callback`) instead of the public domain. This caused a "Redirect URI mismatch" error in Google Cloud because n8n ignored the browser's Host header.

### Root Cause
In the `docker-compose.yml` used to deploy the n8n container, the `WEBHOOK_URL` environment variable was hardcoded to the internal Tailscale IP (`http://100.100.199.127:5678`). When this variable is set, n8n forces all webhook and OAuth endpoints to use it exclusively, regardless of how the user accesses the dashboard.

### Fix
SSH'd into the host machine, updated the `docker-compose.yml` to set `WEBHOOK_URL=https://n8n.rivasautomations.com`, and recreated the container (`docker compose up -d`). This allowed n8n to generate the correct public callback URL to supply to Google Cloud.

## 2026-07-12: n8n CLI User Management Reset

### Symptoms
The user forgot their n8n dashboard login credentials and was locked out of their `n8n.rivasautomations.com` workspace. Because n8n stores credentials as secure cryptographic hashes (bcrypt), password retrieval is mathematically impossible.

### Root Cause
Forgotten credentials on a self-hosted instance without an SMTP server configured for password resets.


## 2026-07-21: Periodic 60-Second Polling vs Event-Driven Push Architecture

### Symptoms
Mobile email replies sent from phone in Gmail were not triggering n8n automatically unless periodic polling loops were enabled.

### Root Cause
Periodic polling loops (e.g. 60-second intervals) consume CPU, hit API quotas unnecessarily, and create visual node clutter ("visual spaghetti"). Without Google Cloud Pub/Sub push notifications, Gmail holds email replies in Google's inbox server without notifying external webhooks.

### Fix
Implemented zero-polling event-driven push architecture (`Google Cloud Pub/Sub` -> `https://n8n.rivasautomations.com/webhook/gmail-reply-push`). The system consumes 0.0% compute when idle and processes mobile email replies in <500ms upon receiving incoming push events.

## 2026-07-21: n8n SQLite `versionId` & Webhook Route Registration

### Symptoms
Updating n8n workflows directly via SQLite resulted in `"Active version not found for workflow"` or `"Cannot POST /webhook/..."` 404 errors.

### Root Cause
n8n v1+ requires non-null UUIDs in `versionId` and `activeVersionId` in `workflow_entity`, as well as corresponding path mappings in `webhook_entity`.

### Fix
Scripted node updates to populate `versionId`, `activeVersionId`, and `webhook_entity` records simultaneously, followed by n8n container restart to re-bind production webhooks into n8n process memory.

## 2026-07-21: Smart Contractor Greeting & Trade Persona Safeguards

### Symptoms
Default outreach copy contained informal phrasing ("without needing to be babysat") and greeted corporate permit filings awkwardly ("Hi TWP Garner Retail").

### Root Cause
Static template strings lacked business entity regex filtering and trade tone enforcement.

### Fix
Purged informal slang from all templates. Implemented smart corporate regex filtering to fallback to `"Hi Estimating Team,"` or `"Hi Dash-In Team,"` when corporate names (LLC, Inc, Retail, Corp) are detected. Stored tone rules in Honcho Hivemind memory.
## 2026-08-29: Antigravity 2.0 Remote Control Daemon & Protobuf Deserializer Fix

### Symptoms
`https://antigravity.google.com/` remained stuck on the "Connect your first instance" onboarding shell despite the daemon and Desktop IDE running locally. DevTools console displayed `Failed to attach portal to header bar: Error: X` and `TypeError: Failed to fetch` in `m=base:13`. Network tab showed `ListInstances` returning 200 OK with an empty 22-byte payload.

### Root Cause
1. **Protobuf JSON Schema Syntax Error**: `~/.gemini/config/config.json` had unbalanced curly braces (4 open, 3 closed). Google's Go language server (`user_config_io.go:38`) failed with `proto: unexpected EOF`, silently defaulting `RemoteControlEnabled` to `false` (`Staying disconnected: Remote Control user setting is off`).
2. **Google Multi-Account Index Mismatch**: The active browser tab queried `x-goog-authuser: 0` (`carlos123939@gmail.com`) or `x-goog-authuser: 3` (`velocitybaskets00@gmail.com`), whereas the daemon had authenticated to `cjrivas00@gmail.com`.
3. **PWA Service Worker Cache Corruption**: Chrome's service worker (`m=base`) was serving a stale offline onboarding shell and rejecting fetch promises.

### Fix
1. Repaired `~/.gemini/config/config.json` structure, validated syntax with `json.loads`, and explicitly set `"remoteControlEnabled": true` and `"cliRemoteControlHostname": "Kenbun-Swarm-Node"`.
2. Bounced the daemon via `bash agy-daemon.sh restart`, establishing a live V2 WebChannel tunnel to `jetski-webchannel.googleapis.com:443`.
3. Unregistered the corrupted Service Worker in DevTools -> Application -> Storage -> Clear Site Data.
4. Aligned the Google account session in the browser to `cjrivas00@gmail.com`. Both instances (`Kenbun-Swarm-Node` daemon and Desktop IDE) immediately turned `🟢 Online`.
