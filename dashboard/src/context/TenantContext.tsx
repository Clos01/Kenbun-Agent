"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export interface Tenant {
  id: string;
  name: string;
}

export const DEMO_TENANTS: Tenant[] = [
  { id: "00000000-0000-0000-0000-000000000000", name: "Default Tenant" },
  { id: "11111111-1111-1111-1111-111111111111", name: "Acme Corp (Test)" },
  { id: "22222222-2222-2222-2222-222222222222", name: "Initech Systems (Test)" },
  { id: "33333333-3333-3333-3333-333333333333", name: "Wayne Enterprises (Test)" },
];

interface TenantContextType {
  tenantId: string;
  setTenantId: (id: string) => void;
  tenants: Tenant[];
  currentTenant: Tenant | undefined;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

const DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000";

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const [tenantId, setTenantIdState] = useState<string>(DEFAULT_TENANT_ID);

  useEffect(() => {
    try {
      const savedTenantId = localStorage.getItem("kenbun_tenant_id");
      const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      if (savedTenantId && UUID_REGEX.test(savedTenantId)) {
        setTimeout(() => {
          setTenantIdState(savedTenantId);
        }, 0);
      } else if (savedTenantId) {
        console.warn("Invalid tenant ID format in localStorage, resetting to default");
        localStorage.setItem("kenbun_tenant_id", DEFAULT_TENANT_ID);
        setTimeout(() => {
          setTenantIdState(DEFAULT_TENANT_ID);
        }, 0);
      }
    } catch (e) {
      console.warn("localStorage not accessible during mount hydration", e);
    }
  }, []);

  const setTenantId = (id: string) => {
    const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const validatedId = id && UUID_REGEX.test(id) ? id : DEFAULT_TENANT_ID;
    setTenantIdState(validatedId);
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("kenbun_tenant_id", validatedId);
      } catch (e) {
        console.warn("localStorage failed to store tenant ID", e);
      }
    }
  };

  const currentTenant = DEMO_TENANTS.find((t) => t.id === tenantId) || {
    id: tenantId,
    name: "Custom Tenant",
  };

  return (
    <TenantContext.Provider
      value={{
        tenantId,
        setTenantId,
        tenants: DEMO_TENANTS,
        currentTenant,
      }}
    >
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
