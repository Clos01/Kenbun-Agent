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
