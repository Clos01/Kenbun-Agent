# Explorer Report: Milestone 1 - Tenant Context & Refactoring

## Summary
The current Next.js frontend has decentralized data fetching using direct `fetch()` calls inside page components and lacks tenant boundary protection. This report proposes establishing a secure React `TenantContext` wrapped at the root layout, implementing a hook-based `useApiClient` that automatically injects tenant headers, and modifying the Next.js API proxy to prevent header truncation.

---

## 1. Current State Assessment & Findings

### Frontend Data Fetching and State Management
- **Raw Fetch Calls**: Data fetching is scattered across client pages (e.g. `board/page.tsx`, `chat/page.tsx`, `telemetry/page.tsx`) using manual `fetch(`${API_BASE}/...`)` requests. There is no unified API client or hook wrapper.
- **State Management**: State is localized inside components using standard React `useState` and `useEffect` hooks. There are no external global state managers (like Zustand or Redux).
- **Endpoint Configuration**: Base pathing is managed via `CONFIG.API_BASE` (pointing to `/api_proxy`) in `dashboard/src/lib/config.ts`.

### Proxy Guardrail Vulnerability (Critical Finding)
The Next.js API proxy in `dashboard/src/app/api_proxy/[...slug]/route.ts` intercepts requests and forwards them to the backend server. However, it currently strips all incoming client headers except `Content-Type` and `Authorization`.
```typescript
// Line 84 in dashboard/src/app/api_proxy/[...slug]/route.ts
const options: RequestInit = {
  method: request.method,
  cache: "no-store",
  headers: {
    "Content-Type": request.headers.get("Content-Type") || "application/json",
    "Authorization": configToken ? `Bearer ${configToken}` : "",
  },
};
```
If the frontend sends an `x-tenant-id` header to the `/api_proxy` routes, the proxy will **silently discard** it before forwarding to the backend, breaking tenant isolation.

### Lead-Related Views
- No lead-related routes or views exist in the current Next.js application.
- A new route `dashboard/src/app/leads/page.tsx` must be created to hold the Aura Lead OS client interface.
- The sidebar (`dashboard/src/components/Sidebar.tsx`) must be modified to register a "Leads" tab.

---

## 2. Recommended Strategy & Code Architecture

### A. Tenant Context (`TenantContext`)
We propose creating `TenantContext.tsx` to serve as the single source of truth for the active tenant, ensuring that components always query data in the scope of the selected tenant.

**Proposed File**: `dashboard/src/context/TenantContext.tsx`
```typescript
"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

interface TenantContextType {
  tenantId: string;
  setTenantId: (id: string) => void;
  tenantName: string;
  isLoading: boolean;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

// Standard mock tenant UUID for fallback/demo
const DEFAULT_TENANT_ID = "de305d54-75b4-431b-adb2-eb6b9e546013";

export const TenantProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [tenantId, setTenantIdState] = useState<string>("");
  const [tenantName, setTenantName] = useState<string>("Demolition Corp");
  const [isLoading, setIsLoading] = useState(true);

  const setTenantId = (id: string) => {
    // Enforce strict UUID validation at the client state level
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    if (id && uuidRegex.test(id)) {
      setTenantIdState(id);
      localStorage.setItem("x-tenant-id", id);
      // Optional: Update name based on mock list or backend mapping
      if (id === DEFAULT_TENANT_ID) {
        setTenantName("Demolition Corp");
      } else {
        setTenantName(`Tenant (${id.substring(0, 8)})`);
      }
    } else {
      console.warn("Rejected setting invalid tenant ID format. UUID required.");
    }
  };

  useEffect(() => {
    // 1. Inspect URL parameters (e.g. ?tenant_id=...)
    const params = new URLSearchParams(window.location.search);
    const urlTenantId = params.get("tenant_id");

    // 2. Fallback to localStorage
    const storedTenantId = localStorage.getItem("x-tenant-id");

    const activeId = urlTenantId || storedTenantId || DEFAULT_TENANT_ID;
    setTenantId(activeId);
    setIsLoading(false);
  }, []);

  return (
    <TenantContext.Provider value={{ tenantId, setTenantId, tenantName, isLoading }}>
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = () => {
  const context = useContext(TenantContext);
  if (context === undefined) {
    throw new Error("useTenant must be used within a TenantProvider");
  }
  return context;
};
```

### B. Secure API Client (`useApiClient`)
To satisfy the requirement that components consuming tenant-scoped APIs must not receive `tenant_id` as a prop (preventing accidental leakage), we propose a custom React hook `useApiClient` that encapsulates request construction and header injection.

**Proposed File**: `dashboard/src/lib/apiClient.ts`
```typescript
import { useTenant } from "@/context/TenantContext";
import { CONFIG } from "@/lib/config";

export function useApiClient() {
  const { tenantId } = useTenant();

  const request = async (path: string, options: RequestInit = {}) => {
    // Securely inject tenant context headers at request time
    const headers = new Headers(options.headers);
    headers.set("x-tenant-id", tenantId);
    
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${CONFIG.API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error ${response.status}: ${errorText || response.statusText}`);
    }

    return response.json();
  };

  return {
    get: (path: string, options?: RequestInit) => 
      request(path, { ...options, method: "GET" }),
    post: (path: string, body: any, options?: RequestInit) => 
      request(path, { ...options, method: "POST", body: JSON.stringify(body) }),
    put: (path: string, body: any, options?: RequestInit) => 
      request(path, { ...options, method: "PUT", body: JSON.stringify(body) }),
    patch: (path: string, body: any, options?: RequestInit) => 
      request(path, { ...options, method: "PATCH", body: JSON.stringify(body) }),
    delete: (path: string, options?: RequestInit) => 
      request(path, { ...options, method: "DELETE" }),
  };
}
```

### C. Integrating Tenant Provider in Root Layout
The `TenantProvider` must wrap the sub-tree inside the `ThemeProvider` to make the tenant context universally accessible.

**Modified File**: `dashboard/src/app/layout.tsx`
```typescript
import { ThemeProvider } from "@/context/ThemeContext";
import { TenantProvider } from "@/context/TenantContext";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
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

## 3. Lead Interface Component Proposal

We will create a new route handler `/leads` that represents the main panel of the Aura Lead OS, integrating with the sidebar navigation.

**Proposed File**: `dashboard/src/app/leads/page.tsx`
```typescript
"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import { useTenant } from "@/context/TenantContext";
import { useApiClient } from "@/lib/apiClient";
import { Shield, RefreshCw, UserCheck } from "lucide-react";

interface Lead {
  id: string; // Enforce UUID
  name: string;
  email: string;
  phone?: string;
  status: string;
  metadata: Record<string, any>;
  created_at: string;
}

export default function LeadsPage() {
  const { tenantId, tenantName, setTenantId } = useTenant();
  const api = useApiClient();

  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLeads = async () => {
    try {
      setLoading(true);
      setError(null);
      // Fetch from backend (automatically includes x-tenant-id in request headers)
      const data = await api.get("/api/v1/leads");
      setLeads(data.items || data || []);
    } catch (err: any) {
      setError(err.message || "Failed to fetch leads");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [tenantId]); // Re-fetch when tenant context changes

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      
      <main className="flex-1 overflow-y-auto p-8 space-y-6">
        {/* Header Block with Heritage Radii & Spacing */}
        <div className="flex justify-between items-center border-b border-border pb-6">
          <div>
            <h1 className="text-3xl font-bold uppercase tracking-tight text-primary font-sans">
              Aura Lead OS
            </h1>
            <p className="text-sm text-secondary font-mono">
              Active Tenant: <span className="text-accent font-bold">{tenantName}</span> ({tenantId})
            </p>
          </div>
          
          {/* Tenant Selector Dropdown for Demo Validation */}
          <div className="flex items-center gap-3">
            <span className="text-xs uppercase tracking-wider font-mono text-secondary">Demo Tenant Switcher:</span>
            <select
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className="bg-card border border-border p-2 rounded-sm text-xs font-mono text-primary outline-none"
            >
              <option value="de305d54-75b4-431b-adb2-eb6b9e546013">Demolition Corp (UUID-1)</option>
              <option value="f18c6422-9477-49d6-b09e-4e78dbf8c422">Landscaping Co (UUID-2)</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="p-4 bg-accent/10 border border-accent text-accent text-xs font-mono rounded-sm flex items-center gap-2">
            <Shield className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center items-center h-64">
            <RefreshCw className="w-6 h-6 text-tertiary animate-spin" />
          </div>
        ) : (
          <div className="border border-border bg-card rounded-md divide-y divide-border">
            {leads.length === 0 ? (
              <div className="p-8 text-center text-secondary text-sm">
                No active leads found for this tenant scope.
              </div>
            ) : (
              leads.map((lead) => (
                <div key={lead.id} className="p-4 flex justify-between items-center hover:bg-sand transition-colors duration-150">
                  <div>
                    <h3 className="font-bold text-primary text-sm flex items-center gap-2">
                      <UserCheck className="w-4 h-4 text-tertiary" /> {lead.name}
                    </h3>
                    <p className="text-xs text-secondary mt-0.5">{lead.email}</p>
                  </div>
                  <div className="text-right">
                    <span className="px-2 py-0.5 border border-border rounded-sm text-[10px] uppercase font-mono bg-neutral text-primary">
                      {lead.status}
                    </span>
                    <p className="text-[10px] text-secondary mt-1">{new Date(lead.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </main>
    </div>
  );
}
```

---

## 4. Proposed File Changes

Here are the precise files that will need to be created or modified for Milestone 1:

| File Action | Path | Purpose |
|---|---|---|
| **Create** | `dashboard/src/context/TenantContext.tsx` | Secure React context for managing active tenant selection/UUID and preventing prop drilling. |
| **Create** | `dashboard/src/lib/apiClient.ts` | Unified api fetch wrapper hook that automatically pulls context `tenantId` and attaches the `x-tenant-id` header. |
| **Create** | `dashboard/src/app/leads/page.tsx` | Aura Lead OS dashboard view to view, switch, and query leads list scoped to the current tenant. |
| **Modify** | `dashboard/src/app/layout.tsx` | Wrap the layout body in the newly designed `TenantProvider`. |
| **Modify** | `dashboard/src/components/Sidebar.tsx` | Add the new `/leads` path to the desktop/mobile navigation list. |
| **Modify** | `dashboard/src/app/api_proxy/[...slug]/route.ts` | Update header options in `handleProxy` to forward the `x-tenant-id` header from Next.js server to FastAPI backend server. |
