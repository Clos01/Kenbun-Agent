import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * GET /api/ping?url=http://...
 *
 * Server-side health check relay. The browser calls this endpoint instead of
 * pinging the target service directly, which would be blocked by CORS/mixed-content
 * policies. The Next.js server performs the actual HEAD request and returns a
 * simple { online: boolean } payload to the client.
 */
export async function GET(request: NextRequest) {
  const rawUrl = request.nextUrl.searchParams.get("url");
  if (!rawUrl) {
    return NextResponse.json({ online: false, error: "Missing url param" }, { status: 400 });
  }

  // Allowlist only http/https schemes (block file://, javascript:, etc.)
  let target: URL;
  try {
    target = new URL(rawUrl);
    if (target.protocol !== "http:" && target.protocol !== "https:") {
      return NextResponse.json({ online: false, error: "Forbidden scheme" }, { status: 400 });
    }
  } catch {
    return NextResponse.json({ online: false, error: "Invalid URL" }, { status: 400 });
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    const res = await fetch(target.toString(), {
      method: "HEAD",
      cache: "no-store",
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    return NextResponse.json({ online: res.ok || res.status < 500 });
  } catch {
    return NextResponse.json({ online: false });
  }
}
