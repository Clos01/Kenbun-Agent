import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

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

async function handleProxy(request: NextRequest, params: { slug: string[] }) {
  try {
    // SSRF Security Guardrail: Explicitly allowlist permitted API routes
    const ALLOWED_ROUTES = ["tools", "status", "health", "metrics", "orchestrate", "brain_health", "checkpoints", "api", "kanban", "stats", "logs"];
    const baseRoute = params.slug[0];
    
    if (!ALLOWED_ROUTES.includes(baseRoute)) {
      console.warn(`🚨 [PROXY] Blocked unauthorized route access: ${baseRoute}`);
      return NextResponse.json({ error: "Forbidden: Unauthorized API Route" }, { status: 403 });
    }
    
    // SSRF Security Guardrail: Prevent Path Traversal
    const slugPath = params.slug.join("/");
    if (slugPath.includes("..")) {
      console.warn(`🚨 [PROXY] Blocked Path Traversal attempt: ${slugPath}`);
      return NextResponse.json({ error: "Forbidden: Path Traversal Detected" }, { status: 403 });
    }

    // If running outside docker (e.g. npm run dev on Mac), fallback to 127.0.0.1
    const internalBackendUrl = process.env.INTERNAL_API_URL || "http://127.0.0.1:8001";
    
    // We append the exact search params (like ?page=1) to the backend URL, plus a cache buster
    const searchParams = new URLSearchParams(request.nextUrl.search);
    searchParams.set('_cb', Date.now().toString());
    const backendUrl = `${internalBackendUrl}/${slugPath}?${searchParams.toString()}`;

    console.log(`[PROXY] Forwarding request to: ${backendUrl}`);

    // Secure shared secret token retrieval for System 2 & 4 lock compliance
    let configToken = process.env.CONFIG_TOKEN || "";
    if (!configToken) {
      try {
        const tokenPath = "/app/brain_health/config_token.secret";
        if (fs.existsSync(tokenPath)) {
          configToken = fs.readFileSync(tokenPath, "utf8").trim();
        }
      } catch (err) {
        console.error("[PROXY] Shared config token retrieval failed:", err);
      }
    }

    const options: RequestInit = {
      method: request.method,
      cache: "no-store",
      headers: {
        "Content-Type": request.headers.get("Content-Type") || "application/json",
        "Authorization": configToken ? `Bearer ${configToken}` : "",
      },
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      options.body = await request.text();
    }

    const response = await fetch(backendUrl, options);
    
    // Read response body as text to pass it cleanly
    const responseData = await response.text();
    
    console.log(`[PROXY] Response from backend for ${slugPath}: status=${response.status}, length=${responseData.length}`);
    if (responseData === "[]") {
      console.log(`[PROXY] WARNING: Backend returned literally "[]" for ${slugPath}`);
    }

    return new NextResponse(responseData, {
      status: response.status,
      statusText: response.statusText,
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });

  } catch (error: any) {
    console.error(`[PROXY ERROR]: ${error.message} (cause: ${error.cause ? error.cause.message : 'unknown'})`);
    return NextResponse.json(
      { error: "Proxy Failed", details: error.message, cause: error.cause ? error.cause.message : null },
      { status: 502 }
    );
  }
}
