"use client";
import { useCallback } from "react";

import { useTenant } from "@/context/TenantContext";
import { CONFIG } from "./config";

export function useApiClient() {
  const { tenantId } = useTenant();

  const request = useCallback(async (path: string, options: RequestInit = {}) => {
    // Determine the full URL.
    // If the path is already fully qualified or absolute (starts with '/' or 'http'), use it.
    // Otherwise, prepend the API_BASE.
    let url = path;
    if (!path.startsWith("http://") && !path.startsWith("https://") && !path.startsWith("/")) {
      url = `${CONFIG.API_BASE}/${path}`;
    }

    // Clone headers or construct new ones
    const headers = new Headers(options.headers || {});
    
    // Automatically inject the active tenant ID header
    headers.set("x-tenant-id", tenantId);

    // Default Content-Type to JSON if not specified and not sending FormData
    if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    return response;
  }, [tenantId]);

  return {
    request,
    tenantId, // Exposure of tenant ID for references
  };
}
