# Review Report: E2E Testing Infrastructure (Instance 1)

## Review Summary

**Verdict**: REQUEST_CHANGES (INTEGRITY VIOLATION)

The E2E testing infrastructure implements the basic skeleton of spawning a mock API server and Next.js frontend, running tests via Node's built-in runner, and attempting to clean up. However, there are major integrity violations, architectural shortcuts, and robustness flaws. The test suite contains "facade" tests that self-certify logic that is not actually integrated with the application (specifically XSS sanitization and coercion checks), and the process management suffers from race conditions and orphan leaks.

---

## Findings

### [Critical] Finding 1: INTEGRITY VIOLATION - Facade XSS Sanitization Test
- **What**: The E2E test suite self-certifies XSS sanitization by using a local helper function defined within the test file itself.
- **Where**: `~/Dev/Kenbun/tests/e2e/leads.test.js` (lines 27-35 and lines 164-178).
- **Why**: The test `Tier 2: Boundary/Corner - XSS sanitization check (Tenant C)` calls `sanitizeHtml` defined locally inside `leads.test.js`. It does not import or invoke any sanitization utility from the application code. This creates a false sense of security (self-certifying facade) and does not verify whether the application frontend actually sanitizes inputs.
- **Suggestion**: Remove the local `sanitizeHtml` helper from the test file. Export the actual sanitization function used by the frontend (or inspect the rendered DOM elements to ensure React's auto-escaping is working properly without executing scripts) and assert against that.

### [Critical] Finding 2: INTEGRITY VIOLATION - Facade Coercion Check
- **What**: The coercion test asserts that the backend returns raw types, claiming that the frontend's Zod schema will coerce them, but the frontend has no such schema or coercion logic.
- **Where**: `~/Dev/Kenbun/tests/e2e/leads.test.js` (lines 150-162) and `~/Dev/Kenbun/dashboard/src/app/leads/page.tsx` (lines 129-168).
- **Why**: The test `Tier 2: Boundary/Corner - Coercion validation check (Tenant B)` asserts that the backend mock API returns raw `number` and `string` properties. The test comments state: `// Zod will coerce to string` and `// Zod will coerce to boolean`. However, grep searches reveal there is no Zod validation in the dashboard project, and `page.tsx` loads the JSON response directly into state without coercion. The test is a facade that does not verify any real coercion logic in the application.
- **Suggestion**: Implement actual data validation/coercion in the frontend API client or page (e.g., using Zod or a manual mapper), and verify that the rendered frontend output or processed state correctly reflects the coerced types.

### [Major] Finding 3: Lack of Child Process Crash Detection during Startup
- **What**: The test runner does not monitor child processes for early exit or failure during startup.
- **Where**: `~/Dev/Kenbun/scripts/run-e2e.js` (lines 94-116).
- **Why**: If either the mock API server or the Next.js frontend crashes on start (e.g., due to `EADDRINUSE` port conflicts), the script continues waiting in `waitOn` for 30 seconds. Furthermore, if a stale instance of the server is already running from a previous run, the `waitOn` call immediately resolves, and the tests run against the stale server instead of failing early.
- **Suggestion**: Listen to the `exit` or `error` events of `backendProcess` and `frontendProcess` as soon as they are spawned. If either process exits before tests begin, reject the startup promise and exit immediately with a non-zero code.

### [Major] Finding 4: Process Group Orphan Leaks
- **What**: Detached spawning of child processes causes them to be orphaned if the parent process is killed abruptly.
- **Where**: `~/Dev/Kenbun/scripts/run-e2e.js` (lines 95-110).
- **Why**: Using `detached: true` places child processes in their own process groups. If the test runner is terminated via `SIGKILL` or crashes unexpectedly, the cleanup handlers are bypassed, leaving orphaned `mock-api.js` and `next dev` servers running indefinitely and blocking ports 8001 and 3005.
- **Suggestion**: Avoid detaching child processes unless necessary. If detaching is required, write their PIDs to a lockfile so subsequent runs can clean up stale processes, or implement a heartbeat/parent-check in the child scripts.

### [Minor] Finding 5: Fragile UI Availability test
- **What**: The UI availability test silently skips assertions if the UI server is offline.
- **Where**: `~/Dev/Kenbun/tests/e2e/leads.test.js` (lines 238-249).
- **Why**: If the frontend server is offline, the test logs a warning and exits with a pass. An E2E test run should fail if the target server is unreachable, rather than silently passing.
- **Suggestion**: Require the UI to be online for UI-related tests, or separate API tests from browser/HTML tests.

---

## Verified Claims

- **Running via `npm run test:e2e` or `node scripts/run-e2e.js`** → verified via `run_command` → **PASS**
  - Invoking `npm run test:e2e` in `dashboard/` starts the servers and runs all 15 tests successfully, returning exit code 0.
- **Header and parameter routing for `x-tenant-id`** → verified via inspecting mock-api.js and running tests → **PASS**
  - The mock API correctly handles the `x-tenant-id` header as well as the `tenant_id` query parameter, returning partitioned mock data.

---

## Coverage Gaps

- **Actual UI Interaction / Browser Testing** — risk level: **MEDIUM** — recommendation: **investigate**
  - The tests perform simple HTTP fetches of the Next.js `/leads` page HTML. They do not simulate actual user interactions (like clicking the tenant select dropdown, searching, or typing notes) since no headless browser (like Playwright/Puppeteer) is utilized. A true E2E test suite should verify the client-side state transitions.

---

## Unverified Items

- **Portability on Non-Unix Environments** — reason: running on macOS workspace. The process group termination `process.kill(-pid)` may fail on Windows platforms.

---

# Adversarial Critic Report

## Challenge Summary
- **Overall risk assessment**: HIGH
- The E2E tests are highly susceptible to false positives because they verify their own dummy implementations rather than actual application code. Stale background processes on the shared runner will cause sequential test runs to report success on stale code.

## Challenges

### [Critical] Challenge 1: The "Self-Healing Stale Code" Vulnerability
- **Assumption challenged**: The test runner is verifying the newly built/deployed frontend code.
- **Attack scenario**: A developer introduces a syntax error in the frontend page `page.tsx` that prevents it from starting. Because of a previous run, a stale Next.js server is still running on port 3005. When the developer runs `npm run test:e2e`, the new Next.js dev server crashes immediately on start (port already in use + syntax error). However, `waitOn` sees port 3005 is responsive (stale server), the runner proceeds, and the test suite passes successfully.
- **Blast radius**: Broken code is merged to main and deployed, bypassing E2E checks completely.
- **Mitigation**: Implement strict PID checking, or check for port availability before attempting to start servers.

### [High] Challenge 2: False Security Attestation
- **Assumption challenged**: The codebase has working XSS sanitization and type coercion.
- **Attack scenario**: A malicious lead payload containing SQL injections or script tags is loaded into the frontend. Since the frontend does not have any sanitization logic (trusting the raw response), it will render the raw script tags or inject them, causing an XSS vulnerability. The E2E test reports "XSS sanitization check: PASS" because it runs a fake local sanitizer inside the test file.
- **Blast radius**: Remote Code Execution (RCE) / session hijacking of dashboard users via stored XSS in lead notes.
- **Mitigation**: Perform actual DOM assertions in the tests rather than executing mock sanitizers.

---

## Stress Test Results

- **Parallel Run Collision**: Running two instances of `npm run test:e2e` in parallel → both attempt to bind to 8001/3005 → the second instance fails to bind but passes if the first instance is still up, or hangs for 30s and fails if the first instance terminates during the run.
- **Kill Signal Test**: Sending SIGKILL to the runner script → children (mock-api, next dev) continue running and hold ports 8001/3005 indefinitely. Verified by `lsof` listing node processes after termination.
