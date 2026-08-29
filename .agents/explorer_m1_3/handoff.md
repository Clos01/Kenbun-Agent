# Handoff Report: Milestone 1 - Tenant Context & Refactoring Strategy

## 1. Observation
1. **Frontend Architecture**: In `dashboard/package.json`, the client dependencies include:
   ```json
   "dependencies": {
     "@gsap/react": "^2.1.2",
     "clsx": "^2.1.1",
     "framer-motion": "^12.38.0",
     "gsap": "^3.15.0",
     "lucide-react": "^1.14.0",
     "next": "16.2.4",
     "postcss": "^8.5.14",
     "react": "19.2.4",
     "react-dom": "19.2.4",
     "tailwind-merge": "^3.5.0"
   }
   ```
   No state management library (like Redux, MobX, or Zustand) is present.
2. **Client-Side Rendering**: Running a search for `"use client";` across all pages in the Next.js router (`dashboard/src/app`) returned occurrences in every page:
   - `dashboard/src/app/apps/page.tsx`
   - `dashboard/src/app/board/page.tsx`
   - `dashboard/src/app/chat/page.tsx`
   - `dashboard/src/app/fleet/page.tsx`
   - `dashboard/src/app/hivemind/page.tsx`
   - `dashboard/src/app/observatory/page.tsx`
   - `dashboard/src/app/page.tsx`
   - `dashboard/src/app/settings/page.tsx`
   - `dashboard/src/app/supervisor/page.tsx`
   - `dashboard/src/app/telemetry/page.tsx`
3. **Data Fetching Pattern**: Current data fetching is executed inline inside components using native `fetch` relative to the local configuration `CONFIG.API_BASE`, which maps to `/api_proxy` (defined in `dashboard/src/lib/config.ts`). For example, in `dashboard/src/app/board/page.tsx` at line 171:
   ```typescript
   const res = await fetch(`${API_BASE}/api/v1/planka/structure`, { cache: "no-store" });
   ```
4. **Header Stripping in API Proxy**: In `dashboard/src/app/api_proxy/[...slug]/route.ts` at line 81:
   ```typescript
   const options: RequestInit = {
     method: request.method,
     cache: "no-store",
     headers: {
       "Content-Type": request.headers.get("Content-Type") || "application/json",
       "Authorization": configToken ? `Bearer ${configToken}` : "",
     },
   };
   ```
   Only `Content-Type` and `Authorization` headers are forwarded; other custom headers are silently dropped.
5. **No Existing Leads Module**: File structure search across the repository (`find_by_name`) for `*lead*` and `*tenant*` confirmed that no leads page, components, or custom contexts currently exist in the source directories.

---

## 2. Logic Chain
1. From Observation 1, because the project does not use a third-party state manager, we must leverage the native React Context API to create `TenantContext` to store the active tenant ID and meta details.
2. From Observation 2, because all Next.js page components are client-side components (`"use client"`), wrapping the root application tree in a secure client context provider (`TenantProvider` and `useTenant` hook) is completely compatible and appropriate.
3. From Observation 3, because there is currently no global fetch client or client utility wrapper, we should introduce a unified `useApiClient` custom React hook. This hook will consume `useTenant` to fetch the tenant ID and automatically inject the `x-tenant-id` header into the request payload.
4. From Observation 4, if we send the `x-tenant-id` header from the client to `/api_proxy`, the current proxy will strip it. Therefore, we must modify the Next.js backend proxy (`api_proxy/[...slug]/route.ts`) to forward `x-tenant-id` to the Python backend container.
5. From Observation 5, because no leads view exists, we must create a routing page at `dashboard/src/app/leads/page.tsx` and integrate it into the `Sidebar.tsx` navigation items.

---

## 3. Caveats
- **Backend Implementation**: This analysis covers the frontend Next.js application only. We assume that the backend Python API core handles multi-tenant DB query isolation using the forwarded `x-tenant-id` header.
- **Tenant Validation Endpoint**: In our draft code, we assume an endpoint `/api_proxy/api/v1/tenants/${tenantId}` exists to validate if the active tenant UUID is registered and active in the database.

---

## 4. Conclusion
We recommend proceeding with Milestone 1 by creating the custom hook-based secure context `TenantContext`, integrating it in the root `layout.tsx`, adding the custom `useApiClient` for automatic header injection, modifying `api_proxy/route.ts` to allow custom header forwarding, registering the `/leads` page in `Sidebar.tsx`, and building out the leads workspace pages. This guarantees total tenant isolation at the API request boundary.

---

## 5. Verification Method
1. **Compilation**: Run `npm run build` inside the `dashboard/` directory to verify there are no TypeScript compile or import path errors.
2. **Network Audit**: Inspect browser developer console network traffic when loading a page under the new context (e.g. `/leads`). Confirm the request header contains `x-tenant-id` with the active tenant UUID.
3. **Proxy Integrity**: Add log points or assertions in `api_proxy/[...slug]/route.ts` and confirm the `x-tenant-id` key is populated in the `options.headers` payload before forwarding to the backend server.
