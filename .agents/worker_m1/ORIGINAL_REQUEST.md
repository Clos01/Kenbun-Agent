## 2026-07-07T03:49:04Z

Worker 1 request for Milestone 1: "Tenant Context & Refactoring".

Objective & Tasks:
1. Implement `TenantContext` & `useTenant` in `dashboard/src/context/TenantContext.tsx`. The context should store the active `tenant_id` (defaulting to a valid UUID format, e.g. `00000000-0000-0000-0000-000000000000`). It should also allow selecting/switching the active tenant for testing.
2. Update `dashboard/src/app/layout.tsx` to wrap the app tree inside `TenantProvider`.
3. Implement `apiClient` / `useApiClient` custom hook in `dashboard/src/lib/apiClient.ts` (or similar helper) that automatically injects the `x-tenant-id` header from the Tenant Context into all API requests.
4. Modify `dashboard/src/app/api_proxy/[...slug]/route.ts` to extract `x-tenant-id` from incoming request headers, validate that it is a valid UUID, and forward it in the proxy request headers to the backend.
5. Create the Leads dashboard page at `dashboard/src/app/leads/page.tsx` using the Heritage design language from `dashboard/DESIGN.md`. The page should show a list of leads (UUIDs, name, industry, creation date, status) and their detailed metadata. Use `useApiClient` to attempt fetching from `${API_BASE}/api/v1/leads` or `/api/backend/leads`. To ensure the frontend remains robust, include high-fidelity fallback mock data inside the page if the backend request fails or if the endpoint doesn't exist, showing realistic lead records (e.g., Landscaping lead).
6. Register the Leads page (`/leads`) under `navItems` in `dashboard/src/components/Sidebar.tsx` using an appropriate icon (like `Database` or `Layers`).
7. Verify that Next.js builds successfully by running the build command in the `dashboard` directory: `npm run build` or `npx next build`. Fix any TypeScript or Next.js build errors.
