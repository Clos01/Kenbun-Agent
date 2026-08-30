# Explorer Report — Milestone 1: Tenant Context & Refactoring

This report provides the analysis and strategy for implementing Tenant Context and Refactoring for Milestone 1 in the Next.js Dashboard.

---

## 1. Executive Summary

Milestone 1 introduces secure multi-tenant data isolation and refactors the frontend to consume data scoped by UUIDs. The dashboard will utilize a React Context (`TenantContext`) to manage the current active tenant state, which is consumed via the `useTenant` hook. 

A centralized `apiClient` wrapper around `fetch` will automatically inject the active tenant ID into the headers of all outgoing requests to the backend via the Next.js API Proxy (`api_proxy`). The proxy will act as a security gate, validating UUID formats and appending the verified tenant ID to the internal FastAPI backend request.

---

## 2. Current State Analysis

### 2.1. Data Fetching
- **Observation**: Page components currently make raw browser `fetch` requests directly to endpoint paths using `CONFIG.API_BASE` (e.g. `src/app/board/page.tsx`, `src/app/chat/page.tsx`, `src/app/fleet/page.tsx`).
- **State Management**: State is localized inside individual view components using React `useState` hooks. There is no central API client, caching library (like SWR or React Query), or global state manager for general API requests.
- **Tenant Context**: No tenant context or state exists currently.

### 2.2. Lead-Related Views
- **Observation**: No lead-related views, routes, components, or API calls exist in the current Next.js code directory.
- **Recommendation**: Integrate lead views via a new route at `src/app/leads/page.tsx`. Include a navigation link in the `src/components/Sidebar.tsx` navigation configuration (`navItems`).

---

## 3. Recommended Strategy & Design

### 3.1. Tenant Context & Hook (`TenantContext.tsx`)
Create a client-side context provider at `src/context/TenantContext.tsx` to encapsulate tenant state.

#### Interface Design
```typescript
export interface Tenant {
  id: string; // Must be a valid UUIDv4
  name: string;
}

interface TenantContextType {
  activeTenant: Tenant | null;
  tenants: Tenant[];
  isLoading: boolean;
  setActiveTenant: (tenant: Tenant) => void;
  setTenants: (tenants: Tenant[]) => void;
}
```

#### Initialization & Persistence
- **Storage**: Maintain the current active tenant in `localStorage` (`kb_active_tenant`) for client persistence.
- **Session/Cookie**: Sync the active tenant ID to a strict client cookie (`kb_tenant_id`) on selection.
- **Hook Gating**: Define the `useTenant()` custom hook which throws a developer-facing runtime exception if consumed outside the context provider.

---

### 3.2. Secure API Client (`apiClient.ts`)
Create a custom fetch wrapper `src/lib/apiClient.ts` to enforce tenant injection and unify requests.

```typescript
import { CONFIG } from "./config";

interface ApiOptions extends RequestInit {
  tenantId?: string;
}

export async function apiClient(path: string, options: ApiOptions = {}) {
  const { tenantId, headers = {}, ...restOptions } = options;

  let resolvedTenantId = tenantId;
  if (!resolvedTenantId && typeof window !== "undefined") {
    try {
      const savedTenant = localStorage.getItem("kb_active_tenant");
      if (savedTenant) {
        resolvedTenantId = JSON.parse(savedTenant)?.id;
      }
    } catch (e) {
      console.error("apiClient: Failed to resolve tenant from storage", e);
    }
  }

  const mergedHeaders = new Headers(headers);
  mergedHeaders.set("Content-Type", "application/json");
  
  if (resolvedTenantId) {
    mergedHeaders.set("x-tenant-id", resolvedTenantId);
  }

  const url = `${CONFIG.API_BASE}${path}`;
  const response = await fetch(url, {
    ...restOptions,
    headers: mergedHeaders,
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    throw new Error(`API Error: ${response.status} ${response.statusText} - ${errorBody}`);
  }

  return response.json();
}
```

---

### 3.3. Secure Next.js API Proxy Gate
Modify the Next.js API Proxy (`src/app/api_proxy/[...slug]/route.ts`) to intercept, validate, and inject the tenant header before forwarding requests to the internal API server:

1. **Extract**: Retrieve `x-tenant-id` from incoming request headers.
2. **Validate**: Match against standard UUIDv4 regex (`/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i`).
3. **Gate**: Block requests targeting tenant-specific backend routes (like `/api/v1/leads`) if the header is missing or malformed (returning `400 Bad Request`).
4. **Inject**: Forward the validated header to the backend FastAPI server as `x-tenant-id`.

---

## 4. Component Modification Matrix

| File Action | Path | Description / Changes |
| :--- | :--- | :--- |
| **CREATE** | `dashboard/src/context/TenantContext.tsx` | Implements the React Context provider and the custom `useTenant` hook. |
| **CREATE** | `dashboard/src/lib/apiClient.ts` | Unified HTTP fetch wrapper with automatic tenant header injection. |
| **CREATE** | `dashboard/src/app/leads/page.tsx` | Core view demonstrating the layout-agnostic Lead UI, populated using tenant ID. |
| **MODIFY** | `dashboard/src/app/layout.tsx` | Wrap the children hierarchy inside `<TenantProvider>` inside `RootLayout`. |
| **MODIFY** | `dashboard/src/app/api_proxy/[...slug]/route.ts` | Extends proxy logic to validate and forward `x-tenant-id` securely. |
| **MODIFY** | `dashboard/src/components/Sidebar.tsx` | Adds a "Leads" dashboard link to the main navigation menu using Heritage style. |

---

## 5. Heritage Design System Compliance

All new generated UI components inside `/leads` page must strictly adhere to `dashboard/DESIGN.md`:
- **Colors**: Use variables mapping to primary (`#1A1C1E`), secondary (`#6C7278`), and neutral (`#F7F5F2`) colors.
- **Typography**: Space Grotesk font family for labels (`label-caps`) and Public Sans for structural headers (`h1`) and body (`body-md`).
- **Radii / Spacing**: Rounding of elements to `rounded-sm` (4px) or `rounded-md` (8px), with standard increments of `8px` (`sm`) or `16px` (`md`).
