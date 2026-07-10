"use client";

const DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000";
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Drop-in replacement for fetch() against /api_proxy that always attaches the
// x-tenant-id the proxy requires. Reads the active tenant from localStorage —
// the same key TenantProvider persists — so it works outside React context and
// needs no hook/dependency plumbing at the ~36 legacy call sites.
export function tenantFetch(input: string, init: RequestInit = {}): Promise<Response> {
  let tenantId = DEFAULT_TENANT_ID;
  try {
    const saved = typeof window !== "undefined" ? localStorage.getItem("kenbun_tenant_id") : null;
    if (saved && UUID_REGEX.test(saved)) tenantId = saved;
  } catch {
    // localStorage unavailable — fall back to default tenant
  }
  return fetch(input, {
    ...init,
    headers: {
      ...((init.headers as Record<string, string>) || {}),
      "x-tenant-id": tenantId,
    },
  });
}
