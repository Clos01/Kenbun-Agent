# E2E Infrastructure Review Report

**Verdict**: REQUEST_CHANGES

## Review Summary
While the E2E test runner (`run-e2e.js`) and mock API server (`mock-api.js`) successfully orchestrate execution, and the tests successfully pass on clean runs, a critical integrity violation has been identified. Specifically, the XSS sanitization check is self-certifying (using a helper function defined inside the test file itself to sanitize data, rather than invoking actual application code or proxy-level validation). Additionally, the mock database lacks reset endpoints, leading to state leakage between test executions.

---

## Findings

### 🔴 [Critical] Finding 1: INTEGRITY VIOLATION - Self-Certifying Test Implementation for XSS Sanitization
- **What**: The E2E test `"Tier 2: Boundary/Corner - XSS sanitization check (Tenant C)"` defines a local helper function `sanitizeHtml` directly inside `tests/e2e/leads.test.js` (lines 27-35) and verifies its output, rather than testing the application code or API gateway proxy's sanitization layer.
- **Where**: `~/Dev/Kenbun/tests/e2e/leads.test.js` (lines 27-35, 164-177)
- **Why**: This is a facade test. It creates a green test result for XSS protection while bypassing the actual application under test. The application's actual Zod validation and front-end rendering layers do not currently implement or enforce XSS sanitization (Milestone 2 is PLANNED).
- **Suggestion**: Refactor the test to assert on the actual page output, or mark it as a `TODO` / skip it until Milestone 2 is completed. Do not use local mock sanitization helpers inside the test runner to self-certify compliance.

### 🟡 [Major] Finding 2: Lack of Mock API State Isolation/Reset
- **What**: The mock API server `mock-api.js` keeps an in-memory dataset that gets mutated by POST requests during tests. There is no mechanism to reset this state between test runs or individual test cases.
- **Where**: `~/Dev/Kenbun/scripts/mock-api.js` (lines 10-85, 137-160) and `~/Dev/Kenbun/tests/e2e/leads.test.js` (lines 254-296)
- **Why**: In our initial run, the landscaping lead lifecycle test failed with an assertion error `4 !== 3` because a previous test run had mutated the mock state and left extra leads in memory.
- **Suggestion**: Add an endpoint to reset the mock database state (e.g., `POST /api/backend/reset`) and call it in `before/beforeEach` blocks in the test suite.

### 🟡 [Major] Finding 3: Robustness Gap in run-e2e.js Startup Handlers
- **What**: `run-e2e.js` uses `waitOn` to wait for 30 seconds for Next.js and the mock server to start. However, it does not attach `exit` or `error` listeners to the spawned child processes during this startup phase.
- **Where**: `~/Dev/Kenbun/scripts/run-e2e.js` (lines 89-116)
- **Why**: If a server process fails immediately (e.g., due to port collision or execution crash), the runner remains stuck in the 30-second wait loop before reporting a generic timeout error.
- **Suggestion**: Attach `.on('exit')` and `.on('error')` listeners immediately upon spawning so the runner can abort the wait loop and clean up instantly if either process dies.

---

## Verified Claims

- **Command `npm run test:e2e` inside `dashboard/` runs the test suite**  
  *Verified via `run_command` in `dashboard/`* → **PASS** (all tests pass when run cleanly, but transient failures occur if database is mutated)
- **Mock API supports `x-tenant-id` header/parameter and UUID validation**  
  *Verified via `view_file` on `mock-api.js` and `leads.test.js`* → **PASS**
- **Subtests conform to Tiers 1-4 methodology in SCOPE.md**  
  *Verified via analysis of `leads.test.js`* → **PASS** (structure conforms, though Tier 2 XSS and coercion checks are simulated/local stubs)

---

## Coverage Gaps

- **Direct UI Interaction**: The tests verify Next.js page compilation and simple HTML text inclusion of CSS/font styles, but do not interact with the frontend dynamically (e.g., checking that selecting a different tenant from the dropdown actually issues the API request with the new tenant ID). This poses a medium risk.  
  *Recommendation*: Once browser automation libraries are available or during later integration milestones, add interactive UI assertions.

## Unverified Items

- None. All claimed infrastructure scripts were inspected and executed.
