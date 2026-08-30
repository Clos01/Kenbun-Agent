## 2026-07-07T10:00:09Z
You are a worker agent. Your working directory is ~/Dev/Kenbun/.agents/worker_m2_fix_3_gen1.
Your task is to implement the Milestone 2 Fix (path traversal double-encoding bypass and tenant ID enforcement on all routes) in the Kenbun codebase.

Here are the detailed requirements:
1. File to modify: `dashboard/src/app/api_proxy/[...slug]/route.ts`.
2. Fix the path traversal vulnerability:
   - Perform full URL decoding on the slug path recursively using `decodeURIComponent` in a loop to mitigate double-encoding bypasses (e.g. `%252e%252e` -> `%2e%2e` -> `..`).
   - Reject the request with a `403 Forbidden` JSON error if the raw or fully decoded slug path contains `".."`, backslashes `"\\"`, or any other path traversal patterns.
3. Enforce tenant ID verification on all proxy routes:
   - Currently, non-leads/non-data routes bypass the `x-tenant-id` UUID verification. You must change this so that ALL proxy routes enforce tenant ID validation, restricting the bypass to ONLY public ping/health check endpoints (like `api/v1/ping`, `api/v1/config`, `health`, `api/health`).
   - When a request is blocked due to missing `x-tenant-id`, return `400 Bad Request` with `{ error: "Bad Request: Missing x-tenant-id header" }`.
   - When a request has an invalid UUID format, return `400 Bad Request` with `{ error: "Bad Request: Invalid x-tenant-id UUID format" }`.
4. Verification:
   - Run the Next.js build using `npm run build` and linting using `npm run lint` within the `dashboard` directory.
   - Run the E2E test suite using `node scripts/run-e2e.js` from the repository root to ensure that all existing E2E tests (including isolation, spoofing, etc.) pass successfully.
   - Create a handoff.md in your working directory summarizing what you modified, why, and the build/test commands and results.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
