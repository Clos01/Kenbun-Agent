import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { LeadSchema, LeadsListSchema } from "@/lib/validation";

// Disabled Edge Runtime to support Node.js fs filesystem operations securely
// export const runtime = 'edge';
export const dynamic = 'force-dynamic';
export const fetchCache = 'force-no-store';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  return handleProxy(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  return handleProxy(request, await params);
}

function sanitizeLog(str: string): string {
  return str.replace(/[^a-zA-Z0-9_\-\/]/g, "");
}

function sanitizeLogUrl(str: string): string {
  return str.replace(/[^a-zA-Z0-9_\-\/\:\.\?\&\=]/g, "");
}

async function handleProxy(request: NextRequest, params: { slug: string[] }) {
  try {
    // SSRF Security Guardrail: Explicitly allowlist permitted API routes
    const ALLOWED_ROUTES = ["tools", "status", "health", "metrics", "orchestrate", "brain_health", "checkpoints", "api", "kanban", "stats", "logs"];
    const baseRoute = params.slug[0];
    
    if (!ALLOWED_ROUTES.includes(baseRoute)) {
      console.warn(`🚨 [PROXY] Blocked unauthorized route access: ${sanitizeLog(baseRoute)}`);
      return NextResponse.json({ error: "Forbidden: Unauthorized API Route" }, { status: 403 });
    }
    
    // SSRF Security Guardrail: Prevent Path Traversal
    const slugPath = params.slug.join("/");
    let decodedSlugPath = slugPath;
    let prevPath = "";
    let iterations = 0;
    while (decodedSlugPath !== prevPath && iterations < 10) {
      prevPath = decodedSlugPath;
      try {
        decodedSlugPath = decodeURIComponent(decodedSlugPath);
      } catch {
        break;
      }
      iterations++;
    }

    if (
      slugPath.includes("..") ||
      slugPath.includes("\\") ||
      decodedSlugPath.includes("..") ||
      decodedSlugPath.includes("\\")
    ) {
      console.warn(`🚨 [PROXY] Blocked Path Traversal attempt: ${sanitizeLog(slugPath)} (decoded: ${sanitizeLog(decodedSlugPath)})`);
      return NextResponse.json({ error: "Forbidden: Path Traversal Detected" }, { status: 403 });
    }

    // Smart backend URL resolution: fallback to host.docker.internal inside Docker container, otherwise 127.0.0.1
    let internalBackendUrl = process.env.INTERNAL_API_URL;
    if (!internalBackendUrl) {
      const isDocker = fs.existsSync("/.dockerenv");
      internalBackendUrl = isDocker ? "http://host.docker.internal:8001" : "http://127.0.0.1:8001";
    }
    
    // We append the exact search params (like ?page=1) to the backend URL, plus a cache buster
    const searchParams = new URLSearchParams(request.nextUrl.search);
    searchParams.set('_cb', Date.now().toString());
    const backendUrl = `${internalBackendUrl}/${slugPath}?${searchParams.toString()}`;

    console.log(`[PROXY] Forwarding request to: ${sanitizeLogUrl(backendUrl)}`);

    // Secure shared secret token retrieval for System 2 & 4 lock compliance
    let configToken = process.env.CONFIG_TOKEN || "";
    if (!configToken) {
      try {
        const pathsToTry = [
          "/app/brain_health/config_token.secret",
          path.join(path.dirname(process.cwd()), "brain_health", "config_token.secret"),
          path.join(process.cwd(), "brain_health", "config_token.secret"),
        ];
        if (process.env.PROJECT_ROOT) {
          pathsToTry.push(path.resolve(process.env.PROJECT_ROOT, "brain_health/config_token.secret"));
        }
        
        for (const tokenPath of pathsToTry) {
          if (fs.existsSync(tokenPath)) {
            configToken = fs.readFileSync(tokenPath, "utf8").trim();
            console.log(`[PROXY] Cryptographic config token loaded successfully from ${sanitizeLog(tokenPath)}`);
            break;
          }
        }
      } catch (err) {
        console.error("[PROXY] Shared config token retrieval failed:", err);
      }
    }

    // Extract and validate x-tenant-id header
    const tenantIdHeader = request.headers.get("x-tenant-id") || request.nextUrl.searchParams.get("tenant_id");
    const bypassRoutes = new Set([
      "api/v1/ping",
      "api/v1/config",
      "api/health",
    ]);
    const isBypass = bypassRoutes.has(slugPath) || bypassRoutes.has(decodedSlugPath);

    let tenantId = tenantIdHeader;
    if (!tenantId) {
      if (isBypass) {
        tenantId = "00000000-0000-0000-0000-000000000000";
      } else {
        console.warn(`🚨 [PROXY] Blocked request with missing x-tenant-id header for path: ${sanitizeLog(slugPath)}`);
        return NextResponse.json({ error: "Bad Request: Missing x-tenant-id header" }, { status: 400 });
      }
    }

    const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!UUID_REGEX.test(tenantId)) {
      const sanitizedTenantId = tenantId.replace(/[^0-9a-fA-F\-]/g, "");
      console.warn(`🚨 [PROXY] Blocked invalid x-tenant-id UUID: ${sanitizeLog(sanitizedTenantId)}`);
      return NextResponse.json({ error: "Bad Request: Invalid x-tenant-id UUID format" }, { status: 400 });
    }

    const options: RequestInit = {
      method: request.method,
      cache: "no-store",
      headers: {
        "Content-Type": request.headers.get("Content-Type") || "application/json",
        "Authorization": configToken ? `Bearer ${configToken}` : "",
        "x-tenant-id": tenantId,
      },
    };

    if (slugPath.includes("leads") && (request.method === "POST" || request.method === "PUT")) {
      try {
        const bodyText = await request.text();
        if (bodyText.trim()) {
          const json = JSON.parse(bodyText);
          const validated = LeadSchema.partial().parse(json);
          options.body = JSON.stringify(validated);
        }
      } catch (err) {
        console.error("[PROXY] Validation/Sanitization failed for request body:", err);
        return NextResponse.json(
          { error: "Bad Request: Payload validation failed", details: String(err) },
          { status: 400 }
        );
      }
    } else if (request.method !== "GET" && request.method !== "HEAD") {
      options.body = await request.text();
    }

    const response = await fetch(backendUrl, options);
    
    // Read response body as text to pass it cleanly
    const responseData = await response.text();
    
    console.log(`[PROXY] Response from backend for ${sanitizeLog(slugPath)}: status=${response.status}, length=${responseData.length}`);
    if (responseData === "[]") {
      console.log(`[PROXY] WARNING: Backend returned literally "[]" for ${sanitizeLog(slugPath)}`);
    }

    let finalResponseData = responseData;
    if (slugPath.includes("leads") && response.ok && responseData.trim()) {
      try {
        const json = JSON.parse(responseData);
        if (Array.isArray(json)) {
          const validated = LeadsListSchema.parse(json);
          finalResponseData = JSON.stringify(validated);
        } else {
          const validated = LeadSchema.parse(json);
          finalResponseData = JSON.stringify(validated);
        }
      } catch (err) {
        console.error("[PROXY] Validation/Sanitization failed for response:", err);
        return NextResponse.json(
          { error: "Internal Server Error: Response validation failed", details: String(err) },
          { status: 500 }
        );
      }
    }

    return new NextResponse(finalResponseData, {
      status: response.status,
      statusText: response.statusText,
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });

  } catch (error: unknown) {
    const err = error as { message?: string; cause?: { message?: string } };
    const message = err.message || String(error);
    const causeMessage = err.cause?.message || "unknown";
    console.error(`[PROXY ERROR]: ${message} (cause: ${causeMessage})`);
    return NextResponse.json(
      { error: "Proxy Failed", details: message, cause: err.cause?.message || null },
      { status: 502 }
    );
  }
}
