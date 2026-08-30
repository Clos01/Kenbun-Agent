## 2026-07-06T23:48:51-04:00
You are teamwork_preview_worker.
Your task is to implement the E2E testing infrastructure for the Aura Lead OS Frontend Upgrade.

You need to create:
1. `~/Dev/Kenbun/scripts/mock-api.js`: a lightweight, zero-dependency Node.js HTTP server running on port 8001, providing `/api/health` and `/api/backend/leads` with UUID validation for `x-tenant-id` (from headers or query param `tenant_id`) and the mock datasets (Tenant A: Real Estate, Tenant B: Landscaping, Tenant C: Malicious, Tenant D: Empty).
2. `~/Dev/Kenbun/scripts/run-e2e.js`: a test runner script that spawns `mock-api.js` on port 8001 and Next.js frontend (on port 3005), wait-on health checks, runs the test suite via `node --test tests/e2e/**/*.test.js`, and ensures SIGTERM/SIGINT teardown and process cleanup.
3. `~/Dev/Kenbun/tests/e2e/leads.test.js`: containing the E2E test suite using Node's native `node:test` and `node:assert`. It must cover:
   - Tier 1: Feature Coverage (x-tenant-id header context routing, Component Registry currency/date/boolean renderers, label mapping).
   - Tier 2: Boundary/Corner (empty state display, layout overflow, Zod validation fallback, XSS sanitization, Prototype Pollution protection).
   - Tier 3: Cross-Feature (switch tenant context, theme toggle, heritage tokens).
   - Tier 4: Real-World Scenarios (Landscaping lead lifecycle, multi-tenant breach spoofing).
   Note: For UI assertions, since the frontend `/leads` page is in-progress in the Implementation Track, the test suite should check if `/leads` page is available. If it returns 404 or connection error, the tests can assert on the `/api_proxy/api/backend/leads` proxy routing and mock server functionality, and gracefully log/skip the incomplete UI parts. This ensures the test runner runs successfully and passes.
4. Update `~/Dev/Kenbun/dashboard/package.json` to include:
   `"test:e2e": "node ../scripts/run-e2e.js"`
5. Verify your implementation by running the test runner command:
   `npm run test:e2e` inside `dashboard/`
   and verify that the test runner runs and finishes.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please write a handoff report documenting the file changes, commands run, test verification results, and layout compliance.

## 2026-07-06T23:52:14-04:00
You are teamwork_preview_worker (Instance 2).
Your objective is to remediate the E2E testing infrastructure based on the critical feedback from our code reviews.

Please implement the following changes:
1. In `~/Dev/Kenbun/scripts/mock-api.js`:
   - Add a `POST /api/backend/reset` (or `POST /api/reset`) endpoint that resets the `mockLeads` database state in memory back to its initial state.
   - Print a console log when this reset occurs.
2. In `~/Dev/Kenbun/scripts/run-e2e.js`:
   - Attach `.on('exit')` and `.on('error')` event handlers to the spawned `backendProcess` and `frontendProcess` immediately after spawning them (during the startup wait phase). If either process exits or errors before the servers are verified as online, reject the startup immediately and abort with a detailed error message and exit code 1.
   - Check if port 8001 or 3005 is already in use before spawning. If they are, print an error and exit immediately rather than starting.
3. In `~/Dev/Kenbun/tests/e2e/leads.test.js`:
   - Remove the local `sanitizeHtml` helper function.
   - Refactor the XSS sanitization test (`Tier 2: Boundary/Corner - XSS sanitization check (Tenant C)`): instead of calling a local helper, fetch the `/leads` page HTML from the server and verify that the raw `<script>` tag is NOT rendered in the HTML. If the page does not render metadata yet, assert that the script tag does not leak or is not present.
   - Refactor the Coercion test (`Tier 2: Boundary/Corner - Coercion validation check (Tenant B)`): instead of asserting against the mock server directly, fetch the `/leads` page (or check proxy/rendering logic) to verify that values are coerced in the UI or processed data. If the elements aren't in the DOM yet, check that the `/api_proxy` endpoints return them and skip/warn the DOM check, but do NOT mock Zod coercion in the test file itself.
   - In a `before` or `beforeEach` hook, execute a `POST` request to `http://127.0.0.1:8001/api/backend/reset` (or `/api/reset`) to ensure the mock database state is completely reset and isolated before running tests.
4. Verify your changes:
   - Run `npm run test:e2e` inside the `dashboard/` directory. Ensure all 15 tests run, pass, and processes clean up perfectly with exit code 0.
   - Run the tests multiple times in sequence to verify that the state reset endpoint has eliminated the landscaping lead test flakiness (the landscaping lead lifecycle test should never report 4 leads instead of 3 on subsequent runs).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please write a handoff report documenting the file changes, commands run, test verification results, and layout compliance.

## 2026-07-06T23:56:06-04:00
You are teamwork_preview_worker (Instance 3).
Your objective is to remediate the E2E testing infrastructure to resolve the integrity violations reported by the Forensic Auditor (facade tests and API proxy bypasses).

Please implement the following changes:
1. In `~/Dev/Kenbun/dashboard/src/app/api_proxy/[...slug]/route.ts`:
   - Modify the headers forwarding inside `handleProxy` (around line 84) to extract and forward the `x-tenant-id` header from the incoming request to the backend options. For example:
     `"x-tenant-id": request.headers.get("x-tenant-id") || ""`
2. In `~/Dev/Kenbun/tests/e2e/leads.test.js`:
   - Update the E2E tests so that they query through the Next.js API proxy (`http://127.0.0.1:3005/api_proxy/api/backend/leads`) instead of calling the mock backend directly (`http://127.0.0.1:8001/api/backend/leads`). This is a critical requirement to verify proxy behavior, security token loading, and header propagation.
   - Remove all facade/self-certifying tests. For requirements that are not yet implemented in the frontend (such as Zod validation/coercion, the Component Registry, and client-side XSS sanitization), mark the corresponding tests as `test.todo` or `test.skip` instead of using local helper stubs that pass artificially. This ensures the test suite represents honest Test-Driven Development (TDD) status.
   - Specifically:
     - Mark the Component Registry renderers test as `test.todo`.
     - Mark the Metadata label mapping checks test as `test.todo`.
     - Mark the Coercion validation check test as `test.todo`.
     - Mark the XSS sanitization check test as `test.todo` (or `test.skip`).
     - Mark the Heritage tokens verification test as `test.todo` (or `test.skip` if UI is not active/implemented).
   - Ensure active tests (Tenant isolation context routing, Proxy query param routing, switch tenant context, multi-tenant breach spoofing) execute through the Next.js API proxy and assert on the proxy responses (validating status codes, body lengths, and JSON arrays).
   - Ensure the `beforeEach` hook resets the mock API database state before each test.
3. Verify your changes:
   - Run `npm run test:e2e` inside the `dashboard/` directory. Ensure all tests run, pass (with the TODOs marked), and processes clean up perfectly with exit code 0.
   - Run the tests multiple times in sequence to verify that they are completely robust and stable.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please write a handoff report documenting the file changes, commands run, test verification results, and layout compliance.

## 2026-07-07T03:58:18Z
You are teamwork_preview_worker (Instance 4).
Your objective is to create the `~/Dev/Kenbun/TEST_READY.md` file at the project root.

The content of `TEST_READY.md` must be:
```markdown
# E2E Test Suite Ready

## Test Runner
- Command: `npm run test:e2e` (executed from the `dashboard/` directory)
- Expected: all tests pass with exit code 0

## Coverage Summary
| Tier | Count | Description |
|------|------:|-------------|
| 1. Feature Coverage | 4 | Real-time tenant context headers, API proxy, tenant context query param, data types |
| 2. Boundary & Corner | 5 | Empty lead states, layout boundaries, Zod schema type warnings (todo), XSS escapes (todo), prototype pollution |
| 3. Cross-Feature | 2 | Switch tenant context, theme toggle (todo) |
| 4. Real-World Application | 2 | Landscaping lead lifecycle, multi-tenant breach spoofing |
| **Total** | **13** | |

## Feature Checklist
| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---------|:------:|:------:|:------:|:------:|
| Tenant Context Isolation | 3 | 1 | 1 | 1 |
| Zod Metadata Validation | 1 (todo) | 2 (todo) | - | - |
| Metadata Normalization & Mapping | 1 (todo) | 1 (todo) | - | 1 |
| Component Registry rendering | 1 (todo) | - | - | 1 |
| Heritage Styling Conformance | - | - | 1 (todo) | - |
```

Verify that the file is successfully created at the project root. Write a handoff report documenting the creation.
