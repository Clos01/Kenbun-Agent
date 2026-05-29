import { NextRequest, NextResponse } from "next/server";

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
    const slugPath = params.slug.join("/");
    const internalBackendUrl = process.env.INTERNAL_API_URL || "http://fastmcp_server:8001";
    
    // We append the exact search params (like ?page=1) to the backend URL
    const searchParams = request.nextUrl.search;
    const backendUrl = `${internalBackendUrl}/${slugPath}${searchParams}`;

    console.log(`[PROXY] Forwarding request to: ${backendUrl}`);

    const options: RequestInit = {
      method: request.method,
      headers: {
        "Content-Type": request.headers.get("Content-Type") || "application/json",
      },
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      options.body = await request.text();
    }

    const response = await fetch(backendUrl, options);
    
    // Read response body as text to pass it cleanly
    const responseData = await response.text();
    
    return new NextResponse(responseData, {
      status: response.status,
      statusText: response.statusText,
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });

  } catch (error: any) {
    console.error(`[PROXY ERROR]: ${error.message}`);
    return NextResponse.json(
      { error: "Proxy Failed", details: error.message },
      { status: 502 }
    );
  }
}
