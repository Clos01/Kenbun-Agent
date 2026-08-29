# Milestone 1 Code Review Report (Tenant Context & Refactoring)

## Review Summary

**Verdict**: REQUEST_CHANGES

The implementation of Milestone 1 provides a functional, modular React context for tenant management and header propagation. However, the Next.js linting check fails on a modified file (`dashboard/src/app/api_proxy/[...slug]/route.ts`), and we identified log injection vulnerability vectors in the proxy routing error/warning logs. The client-side context also lacks basic validation for corrupted localStorage values.

---

## Findings

### Major Finding 1: Lint Error in Modified File
- **What**: Lint check failed due to `Unexpected any. Specify a different type` (`@typescript-eslint/no-explicit-any`).
- **Where**: `dashboard/src/app/api_proxy/[...slug]/route.ts` (Line 123)
- **Why**: TypeScript compiler/lint rules forbid `any` types. Since the project specifications require TypeScript compile and lint checks to be 100% successful, this is a blocker.
- **Suggestion**: Change the catch block parameter to `unknown` or disable the specific ESLint rule on that line:
  ```typescript
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    // ...
  }
  ```

### Major Finding 2: Log Injection (CWE-117) in Warn/Error Logs
- **What**: Warning logs output raw unvalidated user input.
- **Where**: `dashboard/src/app/api_proxy/[...slug]/route.ts` (Lines 31, 38)
- **Why**: While `tenantId` is sanitized before logging, the proxy route logs `baseRoute` and `slugPath` raw:
  - `console.warn(`🚨 [PROXY] Blocked unauthorized route access: ${baseRoute}`);`
  - `console.warn(`🚨 [PROXY] Blocked Path Traversal attempt: ${slugPath}`);`
  An attacker can send newlines (`%0D%0A`) in the URL request path to inject fake log entries into the server logs.
- **Suggestion**: Strip control characters/newlines from `baseRoute` and `slugPath` before logging:
  ```typescript
  const sanitizedBaseRoute = baseRoute.replace(/[^a-zA-Z0-9_\-]/g, "");
  console.warn(`🚨 [PROXY] Blocked unauthorized route access: ${sanitizedBaseRoute}`);
  ```

### Minor Finding 3: Lack of Client-Side Tenant ID Validation
- **What**: `localStorage` retrieval doesn't validate UUID formatting.
- **Where**: `dashboard/src/context/TenantContext.tsx` (Lines 31-43)
- **Why**: If `localStorage` is tampered with or corrupted, the invalid tenant value will persist and trigger recurrent 400 Bad Request responses from the API proxy, with no automatic fallback.
- **Suggestion**: Add a regex check to validate UUID format on load, falling back to `DEFAULT_TENANT_ID` if invalid.

---

## Verified Claims

- **Tenant Provider Integration** → Verified that `<TenantProvider>` wraps layout body in `layout.tsx` → **PASS**
- **API Client Propagation** → Verified that `useApiClient` fetches with `x-tenant-id` header set to the active context value → **PASS**
- **Next.js Production Build Success** → Checked Next.js compilation via `npm run build` → **PASS**
- **Heritage Design System Compliance** → Verified that colors, fonts, margins, and borders in the Leads page align with `DESIGN.md` guidelines → **PASS**
- **Log Injection Defense on tenantId** → Verified that `tenantId` is validated via Regex and sanitized before logging in proxy route → **PASS**

---

## Coverage Gaps

- **E2E Integration** — Risk Level: Medium — The current scope only verifies static build. The actual backend routes (`api/v1/leads`) were mock-checked. We recommend full E2E testing in subsequent milestones.

---

## Unverified Items

- **Real backend data integration** — Reason: The local backend is not currently running/active, so Leads Page fallback mode was active during build and manual inspect. This is acceptable for Milestone 1 as per design.

---

# Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: MEDIUM

## Challenges

### Medium Challenge 1: Log Injection via Route Parameters
- **Assumption challenged**: That only the `x-tenant-id` header is vulnerable to log injection in the proxy.
- **Attack scenario**: Sending newlines in the API route parameters (e.g. `/api_proxy/invalid_route%0d%0a[INFO]%20Data%20compromised`) will result in log injection because `baseRoute` is logged raw in warning handlers.
- **Blast radius**: Spurious log entries, log poisoning, evasion of audit controls.
- **Mitigation**: Clean all route slug segments before printing them in warning logs.

### Low Challenge 2: Persistent Client Denial of Service via LocalStorage Corruption
- **Assumption challenged**: That users will always have valid UUIDs in `localStorage`.
- **Attack scenario**: A user clicks a malicious link or executes a console command that writes an invalid value to `kenbun_tenant_id` in localStorage. Every subsequent request yields 400 Bad Request.
- **Blast radius**: Localized denial of service for the client until manual storage clearance.
- **Mitigation**: Perform pattern validation on state initialization.
