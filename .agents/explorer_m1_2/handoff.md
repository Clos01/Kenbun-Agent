# Soft Handoff: Explorer 2 (Milestone 1 - Tenant Context & Refactoring)

## 1. Observation

- **Project Structure**: Next.js App Router root is at `dashboard/`. We located client routes and components under `dashboard/src/app/` and `dashboard/src/components/`.
- **API Proxy Routing**: In `dashboard/src/app/api_proxy/[...slug]/route.ts` (lines 81-88), the proxy request configuration only extracts and forwards two headers to the backend:
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
- **Data Fetching Patterns**: Direct, decentralized `fetch` calls are used inside page files. For example, in `dashboard/src/app/board/page.tsx` (line 171):
  ```typescript
  const res = await fetch(`${API_BASE}/api/v1/planka/structure`, { cache: "no-store" });
  ```
- **Navigation Menu**: In `dashboard/src/components/Sidebar.tsx` (lines 29-39), there is no entry for leads or tenant metrics.
- **Theme Variables**: Heritage colors and styling tokens are defined as CSS custom properties under `:root` in `dashboard/src/app/globals.css` (lines 32-50):
  - `--primary`: `#0F2537` (Midnight)
  - `--secondary`: `rgba(15, 37, 55, 0.65)` (Ink)
  - `--tertiary`: `#00885F` (Emerald)
  - `--accent`: `#B8422E` (Boston Clay)
  - `--neutral`: `#FFFFFF` (Limestone)

---

## 2. Logic Chain

- **Context Boundary**: Because the Next.js API proxy does not forward custom headers, any `x-tenant-id` header sent by the client would be stripped before hitting the backend server. Thus, modifying the proxy route handler is required.
- **Context Injection**: To fulfill the security requirement that components must not receive `tenant_id` as props, we need a root-level `TenantProvider` in `layout.tsx` that exposes a `useTenant` hook.
- **Unified Fetching**: To automate tenant header attachment, we should expose a hook `useApiClient` that wraps `fetch`, reads the tenant ID from context, and appends the `x-tenant-id` header, removing manual request configuration in future pages.
- **Route Creation**: Since there is currently no page or sidebar navigation for leads, we must add a `/leads` page in `dashboard/src/app/leads/page.tsx` and update the navigation item list in `Sidebar.tsx`.

---

## 3. Caveats

- **No Backend Validation**: We assumed the backend leads service will correctly parse the `x-tenant-id` header and filter queries. Database-level RLS or schema validation is out of scope for the frontend explorer role.
- **Auth Separation**: There is no active user auth context. In production, tenant switching should be gated by authenticated session permissions. For the current scope, we proposed a dropdown selector allowing manual toggling of the active tenant ID for verification.

---

## 4. Conclusion

The recommended strategy involves:
1. Creating `TenantContext.tsx` to handle the active tenant state with localStorage persistence and UUID validation.
2. Creating `apiClient.ts` as a React hook wrapper for `fetch` that attaches `x-tenant-id`.
3. Creating the Aura Lead OS client landing page at `dashboard/src/app/leads/page.tsx`.
4. Registering the new view in `Sidebar.tsx` and wrapping the App sub-tree in `TenantProvider` inside `layout.tsx`.
5. Modifying `/api_proxy/[...slug]/route.ts` to forward `x-tenant-id`.

---

## 5. Verification Method

- **Build Check**: Navigate to `dashboard/` and run `npm run build`. The compilation must pass without TypeScript or ESLint warnings.
- **Header Check**: Inspect requests to `/api_proxy` routes in Chrome DevTools to confirm the `x-tenant-id` header contains a valid UUID format and is sent on every API request.
- **Proxy Forwarding Check**: Log or trace header forwarding in the API Proxy to guarantee the `x-tenant-id` header value reaches the backend server.

---

## 6. Remaining Work (Implementation Steps)

- [ ] Create `dashboard/src/context/TenantContext.tsx` with `useTenant` and default UUID.
- [ ] Create `dashboard/src/lib/apiClient.ts` to export the `useApiClient` custom hook.
- [ ] Create `dashboard/src/app/leads/page.tsx` with the list/detail template using Heritage typography and layout.
- [ ] Wrap `children` in `TenantProvider` inside `dashboard/src/app/layout.tsx`.
- [ ] Modify `dashboard/src/components/Sidebar.tsx` to include the leads navigation item.
- [ ] Modify `dashboard/src/app/api_proxy/[...slug]/route.ts` to extract and forward `x-tenant-id`.
- [ ] Run `npm run build` to confirm compilation.
