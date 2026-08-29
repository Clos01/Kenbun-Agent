# Challenger Verification Report (Milestone 1)

## Challenge Summary

**Overall risk assessment**: MEDIUM

While the core functionality of tenant context propagation, client state update, and API proxy routing works as expected under normal conditions, there is a gap between the desired safety constraints and the actual proxy implementation regarding missing tenant IDs. Specifically, a missing tenant ID header is not blocked with `400 Bad Request` by the API proxy; instead, it is defaulted to the zero-UUID and forwarded to the backend.

---

## Challenges

### [Medium] Challenge 1: Missing Tenant ID Header Bypass

- **Assumption challenged**: The API proxy (`dashboard/src/app/api_proxy/[...slug]/route.ts`) blocks missing `x-tenant-id` headers with a `400 Bad Request`.
- **Attack scenario**: A request sent to `/api_proxy/api/backend/leads` without the `x-tenant-id` header is received by the proxy. Because of the fallback logic (`const tenantId = request.headers.get("x-tenant-id") || "00000000-0000-0000-0000-000000000000"`), the proxy passes a valid zero-UUID to the backend. The backend sees a valid UUID format, matches it, and returns `200 []`. If this default tenant has default shared assets in a database, it could leak those assets instead of blocking the request as unauthorized.
- **Blast radius**: Allows un-unscoped requests to proceed to the backend with a default tenant ID, bypassing the backend's strict `401 Unauthorized` check on missing headers.
- **Mitigation**: Update the API proxy to reject requests with a `400 Bad Request` if the `x-tenant-id` header is missing, rather than applying a fallback zero-UUID.
  ```typescript
  const tenantId = request.headers.get("x-tenant-id");
  if (!tenantId) {
    return NextResponse.json({ error: "Bad Request: Missing x-tenant-id header" }, { status: 400 });
  }
  ```

### [Low] Challenge 2: Client-side LocalStorage Corruption

- **Assumption challenged**: The client-side state loads a valid tenant ID format from `localStorage`.
- **Attack scenario**: A user or extension changes the `localStorage` key `kenbun_tenant_id` to an arbitrary invalid string (e.g., `corrupted-state`). On reload, `TenantContext.tsx` initializes `tenantId` with this corrupted value because it does not validate the format of the loaded value. Consequently, all subsequent API calls made via `useApiClient` append the invalid header, which is blocked with a `400 Bad Request` by the proxy, rendering the dashboard unusable.
- **Blast radius**: Persistent denial of service (DoS) of the client dashboard until the local storage is manually cleared.
- **Mitigation**: Apply UUID regex validation during initialization in `TenantContext.tsx`:
  ```typescript
  const savedTenantId = localStorage.getItem("kenbun_tenant_id");
  const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (savedTenantId && UUID_REGEX.test(savedTenantId)) {
    return savedTenantId;
  }
  ```

---

## Stress Test Results

- **Valid UUID request to Proxy** → Expected: `200 OK` with leads → Actual: `200 OK` with leads → **PASS**
- **Invalid UUID format request to Proxy** → Expected: `400 Bad Request` → Actual: `400 Bad Request` → **PASS**
- **Missing UUID request to Proxy** → Expected: `400 Bad Request` (or blocked) → Actual: `200 []` (forwarded with zero UUID) → **FAIL**
- **Direct Backend Request with missing tenant ID** → Expected: `401 Unauthorized` → Actual: `401 Unauthorized` → **PASS**
- **Direct Backend Request with malformed tenant ID** → Expected: `400 Bad Request` → Actual: `400 Bad Request` → **PASS**
- **Change Tenant ID in UI** → Expected: `localStorage` and Client state update → Actual: Both updated correctly → **PASS**
- **API Client hook call** → Expected: Attaches active `x-tenant-id` header → Actual: Attaches header correctly → **PASS**

---

## Unchallenged Areas

- **Backend Database Partitioning**: Checked only via the mock API implementation (`scripts/mock-api.js`). Actual database RLS / multi-tenancy partitions were not verified since database interactions were stubbed by the mock server.
