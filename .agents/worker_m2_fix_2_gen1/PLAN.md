# Implementation Plan - Zod Metadata Validation Security Fixes

## 1. Edit Proxy Route (`dashboard/src/app/api_proxy/[...slug]/route.ts`)
- **Fix Path Traversal bypass**: Decode `slugPath` using `decodeURIComponent` before performing blocklist and containment checks.
- **Fix Tenant ID bypass**: Restrict the bypass logic to only permit specific public routes (`api/v1/ping` and `api/v1/config`). Remove the `!isLeadsOrDataEndpoint` bypass rule so that other routes like `health` require a valid tenant UUID.

## 2. Edit Stress Test (`tests/stress_test_validation.js`)
- Modify Challenge 1 to assert that the double URL-encoded path traversal is correctly blocked with `403 Forbidden` and `{ error: "Forbidden: Path Traversal Detected" }` instead of allowing the bypass (which returned `404`).

## 3. Verification Steps
- **Step A: ESLint Audit**: Run `npm run lint` in `dashboard/` directory and ensure 0 warnings/errors.
- **Step B: Next.js Compile**: Run `npm run build` in `dashboard/` directory to ensure compilation succeeds with zero errors.
- **Step C: E2E Tests**: Run `npm run test:e2e` in `dashboard/` to ensure all 13/13 tests pass.
- **Step D: Direct Verification Test**: Run `node tests/verify_proxy_direct.js` to ensure all 3 cases (especially Case 3 returning 400 Bad Request) pass.
- **Step E: Adversarial Stress Tests**: Run `node tests/stress_test_validation.js` to verify all adversarial challenges pass (exit code 0).
- **Step F: System 2 Audit**: Call `consult_supervisor` to review the modifications.
