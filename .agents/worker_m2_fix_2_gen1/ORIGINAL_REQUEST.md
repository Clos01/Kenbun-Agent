## 2026-07-07T10:00:08Z
You are a Worker subagent (Archetype: teamwork_preview_worker) tasked with applying security fixes for Milestone 2: Zod Metadata Validation for the Kenbun codebase.

Your working directory is `~/Dev/Kenbun/.agents/worker_m2_fix_2_gen1`.

## Objective
Fix two security/contract issues in the Next.js API BFF proxy (`dashboard/src/app/api_proxy/[...slug]/route.ts`):
1. **Double URL-Encoded Path Traversal Bypass**:
   Attackers can bypass the directory traversal check using double URL-encoded dots (`%252e%252e`), which Next.js parses as `%2e%2e` in the slug parameter but the backend resolver maps to `..`.
   **Fix**: Completely decode the joined `slugPath` using `decodeURIComponent` before performing containment or blocklist checks:
   ```typescript
   const decodedPath = decodeURIComponent(slugPath);
   if (decodedPath.includes("..") || slugPath.includes("..")) {
     console.warn(`🚨 [PROXY] Blocked Path Traversal attempt: ${sanitizeLog(slugPath)}`);
     return NextResponse.json({ error: "Forbidden: Path Traversal Detected" }, { status: 403 });
   }
   ```
2. **Missing Tenant ID Contract Bypass**:
   The proxy currently bypasses tenant ID validation for any endpoint that is not a leads or data endpoint (e.g. `health`). This causes the direct proxy verification test (`tests/verify_proxy_direct.js`) to fail on Case 3, because it expects a missing tenant ID on `/api_proxy/health` to return `400 Bad Request`.
   **Fix**: Restrict the bypass logic to only permit specific public bypass routes (e.g. `api/v1/ping` and `api/v1/config`). Remove the `!isLeadsOrDataEndpoint` bypass rule so that other routes like `health` require a valid tenant UUID.
   ```typescript
   const isBypass = slugPath === "api/v1/ping" || slugPath === "api/v1/config";
   ```

## Verification Requirements
1. Run ESLint: verify zero warnings or errors.
2. Compile the Next.js app: `npm run build` in `dashboard/` must pass with zero errors.
3. Run the E2E tests: `npm run test:e2e` in `dashboard/` must pass with 13/13 successes.
4. Run the direct verification test:
   ```bash
   node tests/verify_proxy_direct.js
   ```
   This must pass with Case 3 returning 400 Bad Request (exit code 0).
5. Run the adversarial stress tests:
   ```bash
   node tests/stress_test_validation.js
   ```
   This must pass with exit code 0.

MANDATORY INTEGRITY WARNING:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.
