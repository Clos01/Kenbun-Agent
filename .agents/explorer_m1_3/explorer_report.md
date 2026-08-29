# 🕵️ EXPLORER REPORT: Tenant Context & Refactoring Strategy (Milestone 1)

**Date**: 2026-07-07  
**Status**: Completed Read-only Analysis  
**Working Directory**: `~/Dev/Kenbun/.agents/explorer_m1_3/`  
**Milestone**: Milestone 1 (Tenant Context & Refactoring)

---

## 1. Executive Summary
This report outlines the strategy for implementing **Milestone 1: Tenant Context & Refactoring** for the Aura Lead OS Next.js frontend, preparing it to integrate with the multi-tenant SaaS architecture. The codebase is currently a client-side heavy Next.js App Router project which relies on raw, distributed `fetch` requests without a central client, and contains no lead-related modules. 

Our strategy introduces:
1. A secure client-side `TenantContext` and `useTenant` hook to track the active tenant UUID.
2. A custom `useApiClient` hook to centralize fetching and inject the `x-tenant-id` header securely on all outgoing backend requests.
3. Crucial modifications to the Next.js API Proxy (`api_proxy`) to forward custom headers.
4. A new route (`/leads`) and Sidebar registration for lead management.

---

## 2. Current Codebase Analysis

### 2.1 Data Fetching Code
Existing frontend data fetching is executed inline inside React components via native `fetch` wrappers:
- **Location**: Scattered throughout files like `dashboard/src/app/board/page.tsx`, `dashboard/src/app/chat/page.tsx`, `dashboard/src/app/telemetry/page.tsx`, and `dashboard/src/components/GalaxyMap.tsx`.
- **Pattern**: Most endpoints call `${API_BASE}/api/v1/...` (where `API_BASE` resolves to the Next.js local rewrite proxy path `/api_proxy`).
- **Shortcoming**: There is no centralized API client or unified headers configuration, meaning headers like `x-tenant-id` cannot be injected globally without touching dozens of files.

### 2.2 State Management
- **Pattern**: Completely decentralized, utilizing standard React hooks (`useState`, `useReducer`, `useEffect`, `useCallback`, `useMemo`).
- **Dependencies**: Analysis of `package.json` confirms no global state manager is installed (no Redux, Zustand, etc.).
- **Strategy**: Leverage the native React Context API (`TenantContext`) since it fits the project's zero-external-dependency state design.

### 2.3 Lead-Related Views
- **Current State**: There are currently **no** files, directories, or routes related to "leads" in the dashboard application.
- **Integration Proposal**:
  1. Add a new route directory: `dashboard/src/app/leads/page.tsx` for the Leads dashboard.
  2. Implement list views and detail panels in `dashboard/src/components/leads/` for granular lead item visualization.
  3. Register the Leads interface in `dashboard/src/components/Sidebar.tsx` under the navigation item `{ name: "Leads", href: "/leads", icon: ClipboardList }` conforming to the Heritage design system structure.

---

## 3. Proposal: Tenant Context & `useTenant` Hook

### 3.1 Design Intentions
The context provider must:
- Detect the active `tenant_id` UUID safely.
- Avoid passing it down as component props to prevent cross-tenant leakage.
- Enforce strict validation: if `tenantId` is invalid, restrict component rendering or show an error state.
- Resolve the `tenantId` in a prioritized order: URL parameter (`?tenant_id=...`), `localStorage` (saved state), and a fallback sandbox UUID.

### 3.2 Implementation Draft (`dashboard/src/context/TenantContext.tsx`)
```typescript
"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

interface Tenant {
  id: string; // UUID
  name: string;
  industry: string;
}

interface TenantContextType {
  tenantId: string | null;
  tenant: Tenant | null;
  isLoading: boolean;
  error: string | null;
  setTenantId: (id: string) => void;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const [tenantId, setTenantIdState] = useState<string | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initializeTenant = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // 1. Resolve from URL Query String (for quick developer swapping/testing)
        const params = new URLSearchParams(window.location.search);
        let activeId = params.get("tenant_id");

        // 2. Resolve from LocalStorage
        if (!activeId) {
          activeId = localStorage.getItem("crg_tenant_id");
        }

        // 3. Resolve from Environment Variable Fallback
        if (!activeId) {
          activeId = process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID || "00000000-0000-0000-0000-000000000000";
        }

        // Validate UUID formatting at the client-side boundary
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(activeId)) {
          throw new Error("Invalid Tenant UUID format");
        }

        setTenantIdState(activeId);
        localStorage.setItem("crg_tenant_id", activeId);

        // Fetch Tenant Verification from backend to confirm database record
        const res = await fetch(`/api_proxy/api/v1/tenants/${activeId}`);
        if (res.ok) {
          const data = await res.json();
          setTenant(data);
        } else {
          throw new Error(`Failed to fetch tenant configuration (Status ${res.status})`);
        }
      } catch (err: any) {
        console.error("❌ [Tenant Context Init Failed]:", err.message);
        setError(err.message || "Unknown error occurred initializing tenant.");
      } finally {
        setIsLoading(false);
      }
    };

    initializeTenant();
  }, []);

  const setTenantId = (id: string) => {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(id)) {
      console.error("Invalid tenant UUID format");
      return;
    }
    setTenantIdState(id);
    localStorage.setItem("crg_tenant_id", id);
    // Reload dynamically
    window.location.search = `?tenant_id=${id}`;
  };

  return (
    <TenantContext.Provider value={{ tenantId, tenant, isLoading, error, setTenantId }}>
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  const context = useContext(TenantContext);
  if (context === undefined) {
    throw new Error("useTenant must be used within a TenantProvider");
  }
  return context;
}
```

### 3.3 Inserting into Layout (`dashboard/src/app/layout.tsx`)
Inject the context globally wrapping `{children}` directly beneath `ThemeProvider`:
```typescript
// Add: import { TenantProvider } from "@/context/TenantContext";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="...">
      <body suppressHydrationWarning className="...">
        <ThemeProvider>
          <TenantProvider>
            {children}
          </TenantProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

---

## 4. Proposal: Secure API Client (`useApiClient`)

### 4.1 Custom Hook Design
Since all client pages use client-side React (`"use client"`), we can build a custom `useApiClient` hook which internally consumes `useTenant`. This guarantees the `x-tenant-id` is automatically and securely attached to headers without developer oversight.

### 4.2 Implementation Draft (`dashboard/src/lib/apiClient.ts`)
```typescript
import { useTenant } from "@/context/TenantContext";
import { CONFIG } from "./config";

export function useApiClient() {
  const { tenantId } = useTenant();

  const request = async (path: string, options: RequestInit = {}) => {
    const headers = new Headers(options.headers);

    // Enforce Tenant Injection
    if (tenantId) {
      headers.set("x-tenant-id", tenantId);
    } else {
      console.warn("⚠️ [API Client] Request made without active tenant ID context!");
    }

    if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }

    const url = `${CONFIG.API_BASE}${path}`;

    const res = await fetch(url, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const errorText = await res.text();
      let errorData;
      try {
        errorData = JSON.parse(errorText);
      } catch {
        errorData = { error: errorText };
      }
      throw new Error(errorData.error || errorData.message || `Request failed with status ${res.status}`);
    }

    return res.json();
  };

  return {
    get: (path: string, options?: Omit<RequestInit, "method">) => 
      request(path, { ...options, method: "GET" }),
    post: (path: string, body?: any, options?: Omit<RequestInit, "method" | "body">) => 
      request(path, { ...options, method: "POST", body: JSON.stringify(body) }),
    put: (path: string, body?: any, options?: Omit<RequestInit, "method" | "body">) => 
      request(path, { ...options, method: "PUT", body: JSON.stringify(body) }),
    delete: (path: string, options?: Omit<RequestInit, "method">) => 
      request(path, { ...options, method: "DELETE" }),
  };
}
```

### 4.3 Proxy Security Gateway Adjustment (`dashboard/src/app/api_proxy/[...slug]/route.ts`)
**Critical Catch**: The server-side API proxy currently strips out custom headers, forwarding only `Content-Type` and `Authorization`. We must adjust `handleProxy` to forward `x-tenant-id`:
```typescript
    // Inside handleProxy in dashboard/src/app/api_proxy/[...slug]/route.ts
    const options: RequestInit = {
      method: request.method,
      cache: "no-store",
      headers: {
        "Content-Type": request.headers.get("Content-Type") || "application/json",
        "Authorization": configToken ? `Bearer ${configToken}` : "",
        "x-tenant-id": request.headers.get("x-tenant-id") || "", // Forward the tenant isolation key!
      },
    };
```

---

## 5. Files to Create or Modify

| File Action | Relative File Path | Purpose |
|---|---|---|
| **Create** | `dashboard/src/context/TenantContext.tsx` | Provides multi-tenant state and context verification (`useTenant`). |
| **Create** | `dashboard/src/lib/apiClient.ts` | Centralized secure fetcher hook `useApiClient` which auto-injects `x-tenant-id`. |
| **Create** | `dashboard/src/app/leads/page.tsx` | Leads dashboard page containing lead records list and mock component tests. |
| **Modify** | `dashboard/src/app/layout.tsx` | Wraps application tree in `TenantProvider`. |
| **Modify** | `dashboard/src/app/api_proxy/[...slug]/route.ts` | Configures the Next.js gateway to forward the `x-tenant-id` header securely to the Python backend API. |
| **Modify** | `dashboard/src/components/Sidebar.tsx` | Appends a "Leads" dashboard option under navigation array. |
| **Modify** | `dashboard/package.json` | Installs `zod` as a project dependency for the validation layer planned in M2. |

---

## 6. Verification and Quality Strategy
1. **Infra Verification**: Verify that the Next.js build (`npm run build`) completes with zero errors once context wrapper and types are set.
2. **Security Verification**: Capture raw HTTP requests made from Next.js server proxy (`api_proxy`) and verify the `x-tenant-id` header is attached and populated on the outgoing call to the backend container.
3. **Boundary Verification**: Pass E2E simulation cases demonstrating that an attempt to access a resource with a spoofed UUID format gets intercepted at the context initialization layer.
