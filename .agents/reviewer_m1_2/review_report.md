# Review Report — Milestone 1 (Tenant Context & Refactoring)

## Review Summary

**Verdict**: REQUEST_CHANGES (FAIL)

The implementation successfully establishes tenant context isolation, API proxy forwarding with x-tenant-id verification, and integration with the Leads page. All 15 E2E tests in `tests/e2e/leads.test.js` pass. However, the review fails due to the following critical and major issues:
1. **Lint Check Failures**: The project has 52 lint/typescript errors and warnings when running `npm run lint`. This includes a TypeScript strict lint failure in the reviewed file `api_proxy/[...slug]/route.ts`.
2. **Heritage Design System Non-Conformance**: The colors defined in `dashboard/src/app/globals.css` deviate significantly from the Heritage specifications in `dashboard/DESIGN.md`. It implements a Midnight/Emerald/White palette instead of the Charcoal/Slate/Boston Clay/Limestone palette.
3. **React Hydration Mismatch Risk**: The lazy initialization of `tenantId` in `TenantContext.tsx` from `localStorage` will trigger React hydration mismatches on client render when a non-default tenant is stored.

---

## Findings

### [Critical] Finding 1: Strict Lint Failure in Proxy Route
- **What**: The ESLint verification fails with an error for unexpected use of `any` in a catch block.
- **Where**: `dashboard/src/app/api_proxy/[...slug]/route.ts` (Line 123)
- **Why**: Strict TypeScript configurations in the repository prohibit the use of `any`. The catch variable is typed as `any`: `catch (error: any)`.
- **Suggestion**: Change to `catch (error: unknown)` and cast it or extract the message safely (e.g. `const message = error instanceof Error ? error.message : String(error)`).

### [Critical] Finding 2: Project-Wide Lint Failures
- **What**: Running `npm run lint` yields 52 problems (35 errors, 17 warnings).
- **Where**: Various files in the dashboard (e.g., `settings/page.tsx`, `supervisor/page.tsx`, `board/page.tsx`).
- **Why**: Several files call `setState` synchronously within a `useEffect` effect body, which is flagged by the custom `react-hooks/set-state-in-effect` ESLint rule.
- **Suggestion**: Ensure that the codebase is lint-clean before marking the milestone complete. Sync state or wrap the updates inside macrotasks/microtasks or use proper state synchronization.

### [Major] Finding 3: Heritage Design System Color Mismatch
- **What**: Non-conformance to Heritage Design System color tokens.
- **Where**: `dashboard/src/app/globals.css` vs `dashboard/DESIGN.md`
- **Why**: The Heritage Design System defines:
  - `primary`: `#1A1C1E` (Charcoal)
  - `secondary`: `#6C7278` (Gray)
  - `tertiary`: `#B8422E` (Boston Clay)
  - `neutral`: `#F7F5F2` (Limestone)
  But `globals.css` configures:
  - `--primary`: `#0F2537` (Midnight)
  - `--secondary`: `rgba(15, 37, 55, 0.65)` (Translucent Ink)
  - `--tertiary`: `#00885F` (Emerald Green)
  - `--accent`: `#B8422E` (Boston Clay)
  - `--neutral`: `#FFFFFF` (White)
  This causes the Leads page and navigation to display Midnight/Emerald/White, directly violating the Heritage Design System mandate.
- **Suggestion**: Re-align CSS custom properties in `globals.css` to match the exact hex codes of the Heritage Design System specified in `dashboard/DESIGN.md`.

### [Major] Finding 4: Hydration Mismatch Vulnerability in TenantContext
- **What**: React hydration mismatch when using lazy state initialization from client-only storage.
- **Where**: `dashboard/src/context/TenantContext.tsx` (Lines 31-43)
- **Why**: Next.js performs server-side rendering (SSR). During SSR, `typeof window` is `undefined`, so the server renders using `DEFAULT_TENANT_ID`. On the client, during hydration, `typeof window !== "undefined"` causes the lazy state initializer to read `localStorage` (which might contain a different tenant ID like `11111111-1111-1111-1111-111111111111`). React will detect a mismatch between the server-rendered HTML and client-hydrated HTML.
- **Suggestion**: Initialize state with `DEFAULT_TENANT_ID` and synchronize with `localStorage` inside a `useEffect` hook on mount (which only runs on the client-side post-hydration), or guard page rendering with a `mounted` flag.

---

## Verified Claims

- **Tenant Isolation** → verified via E2E test run and direct inspection of `apiClient.ts` and `route.ts`. Header `x-tenant-id` is correctly appended and validated → **PASS**
- **UUID Format Enforced** → verified via `UUID_REGEX` validation in API proxy router (`[...slug]/route.ts`) returning 400 for malformed IDs → **PASS**
- **Production Build Successful** → verified by running `npm run build` in `dashboard/`, which completed successfully in 2.3s → **PASS**
- **E2E Test Success** → verified by running `npm run test:e2e` in `dashboard/`, which executes `tests/e2e/leads.test.js` successfully (15/15 tests passed) → **PASS**

---

## Coverage Gaps
- **E2E Test Coverage on Hydration Warning** — E2E tests run in a headless environment and do not assert on console warnings (such as React hydration mismatches) → **medium risk** → *recommendation: implement assertions to capture browser logs/errors during E2E runs.*
- **CSS Color Enforcement** — E2E test `Tier 3: Heritage tokens verification` passed because it matched `#B8422E` inside `globals.css` (which is mapped to `--accent`), but it overlooked that `--primary`, `--secondary`, `--tertiary`, and `--neutral` did not match the Heritage theme → **medium risk** → *recommendation: expand design system E2E assertions to verify all key CSS custom property mappings.*

---

## Unverified Items
- **None** — All key capabilities (context propagation, proxy routing, build compilation, E2E tests, and style layout) were successfully verified.

---
---

# Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: MEDIUM

The core isolation mechanism (context + proxy validation) is logically sound and successfully prevents cross-tenant data leaks. However, the system is vulnerable to state synchronization bugs (hydration mismatches) and style regressions (theme mismatch).

---

## Challenges

### [High] Challenge 1: Client Hydration Mismatch
- **Assumption challenged**: Lazy state initialization in React context is safe for Next.js SSR apps.
- **Attack scenario**: A user switches their tenant to "Acme Corp" (Tenant B). The page is reloaded. The server renders the default tenant dashboard. The client's React runtime hydrates with Tenant B's state from `localStorage`, causing mismatched elements. This leads to DOM nodes getting misaligned or event listeners failing.
- **Blast radius**: Broken navigation, flickering UI, or incorrect tenant data displays during page load.
- **Mitigation**: Fetch `localStorage` asynchronously inside `useEffect` after mount, keeping the initial state matching the server's default.

### [Medium] Challenge 2: E2E Test Verification Bypass
- **Assumption challenged**: The E2E tests guarantee Heritage styling is properly applied.
- **Attack scenario**: The styling has completely drifted to a green-and-midnight theme instead of red-and-limestone, yet the E2E test `Heritage tokens verification` passes because it searches for any matching substrings across files rather than asserting actual property computed values.
- **Blast radius**: Undetected visual drift and complete violation of Heritage Design System guidelines.
- **Mitigation**: Update tests to perform strict checks on actual computed style properties (e.g. reading `--primary` and `--neutral` variables).

---

## Stress Test Results

- **Invalid Tenant UUID spoofing** → Client sends requests with invalid header values → Proxy route blocks it with 400 Bad Request → **PASS (Secure)**
- **Path Traversal attempt** → Client sends request to `api_proxy/api/../secret` → Proxy blocks with 403 Forbidden → **PASS (Secure)**
- **Route Injection attempt** → Client requests unlisted base route `api_proxy/unauthorized_path` → Proxy blocks with 403 Forbidden → **PASS (Secure)**
