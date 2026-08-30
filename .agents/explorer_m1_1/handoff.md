# Handoff Report — Explorer 1 (Milestone 1)

This handoff report summarizes findings, reasoning, and the strategy to proceed with Milestone 1: "Tenant Context & Refactoring".

---

## 1. Observation

Direct observations from the repository:
1. **Next.js Frontend Location**: Located at `~/Dev/Kenbun/dashboard`.
   - Node packages and versions in `dashboard/package.json`:
     - `"next": "16.2.4"`
     - `"react": "19.2.4"`
2. **Current Layout Structure**: In `dashboard/src/app/layout.tsx` (lines 66-68), the tree is wrapped only in `ThemeProvider`:
   ```typescript
   <ThemeProvider>
     {children}
   </ThemeProvider>
   ```
3. **Data Fetching Pattern**: Done via raw `fetch` calls in individual pages. For example, in `dashboard/src/app/settings/page.tsx` (line 83):
   ```typescript
   const res = await fetch(`${API_BASE}/api/v1/config`);
   ```
4. **API Base Configuration**: Configured in `dashboard/src/lib/config.ts` (lines 10-13):
   ```typescript
   export const CONFIG = {
     get API_BASE() {
       return '/api_proxy';
     },
     ...
   };
   ```
5. **API Proxy**: Located at `dashboard/src/app/api_proxy/[...slug]/route.ts`, executing proxy requests to the backend server (lines 94-111).
6. **Leads Code Presence**: Grep searches for `lead` and `leads` as standalone words inside `~/Dev/Kenbun/dashboard/src` returned 0 hits, indicating that no lead-related views or components currently exist.
7. **Design Tokens**: Standardized styling variables are defined in `dashboard/DESIGN.md`, specifying colors (`primary: "#1A1C1E"`, `secondary: "#6C7278"`, `neutral: "#F7F5F2"`), typography font families (`Public Sans`, `Space Grotesk`), and spacing/radius constraints.

---

## 2. Logic Chain

1. **Need for Centralized Client**: Since data fetching currently relies on scattered, raw browser `fetch` calls (Observation 3), injecting a `tenant_id` header dynamically in every call is highly error-prone and risks omission. Therefore, we must introduce a unified `apiClient` wrapper in `src/lib/apiClient.ts` to automatically extract the tenant context and attach the `x-tenant-id` header.
2. **Tenant ID Propagation**: To satisfy the requirement that `tenant_id` must not be passed down as a prop, we must create a `TenantContext` provider and a corresponding `useTenant` hook in `src/context/TenantContext.tsx` (reusing the pattern seen in `ThemeContext.tsx`, Observation 2). The hook will resolve the active tenant ID under React's execution flow.
3. **Zero-Trust Proxy Gating**: Since the browser's local state or headers could be tampered with, the server-side API proxy `api_proxy/[...slug]/route.ts` must validate the incoming `x-tenant-id` header (Observation 5). By checking if it is a valid UUID using a regex, the proxy acts as a secure firewall, refusing to forward requests to the FastAPI backend unless a valid tenant ID exists.
4. **Integration of Leads View**: Because no leads-related UI exists (Observation 6), we must add a page route `src/app/leads/page.tsx` and register a "Leads" menu item inside `src/components/Sidebar.tsx` navigation items list.

---

## 3. Caveats

- **Backend Readiness**: This proposal assumes the backend FastAPI server is fully configured to intercept, authorize, and filter query results by the `x-tenant-id` header. We did not inspect backend database migrations or tables during this read-only client-side task.
- **Mock Data for Development**: Since the backend schema for `core_leads` might not be initialized, the new page `/leads` should support graceful fallback or client-side mock data representing different industries (e.g. Landscaping) for integration tests.

---

## 4. Conclusion

The strategy for implementing Milestone 1 is scoped and actionable:
1. **Create `TenantContext.tsx`**: Hold `activeTenant` state, fetch available list, and persist choices in `localStorage` and client-side cookies.
2. **Create `apiClient.ts`**: Wrap the browser `fetch` API, automatically appending the `x-tenant-id` header.
3. **Extend `api_proxy`**: Parse the `x-tenant-id` header, validate its UUID format, and forward it to the internal FastAPI backend.
4. **Create `/leads` page**: Build the dynamic leads layout adhering to the Heritage Design System styling tokens.
5. **Modify `Sidebar.tsx` and `layout.tsx`**: Wrap the root layout in `TenantProvider` and link the leads page in the navigation sidebar.

---

## 5. Verification Method

To verify the strategy once implemented:
1. **Compilation Check**:
   Run the Next.js production build command to check for syntax and type safety errors:
   ```bash
   cd dashboard && npm run build
   ```
2. **Security & Header Validation**:
   - Trigger a request via the dashboard and check the Network logs in developer tools to confirm `x-tenant-id` is included in the headers.
   - Send a manual cURL request to `/api_proxy/api/v1/leads` without an `x-tenant-id` header and confirm that the Next.js server returns a `400 Bad Request`.
