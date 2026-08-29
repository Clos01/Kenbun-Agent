# Challenger Report — Milestone 1 Verification

## Challenge Summary

**Overall risk assessment**: MEDIUM

While the client-side state preservation, API client header propagation, and invalid tenant UUID blocking work exactly as designed, a critical security vulnerability exists in the API proxy logic: **missing `x-tenant-id` headers are not blocked, but are instead silently allowed to bypass security validation by falling back to a default system UUID.**

---

## Challenges

### [High] Challenge 1: Fail-Open Behavior on Missing `x-tenant-id` Headers

- **Assumption challenged**: The API proxy (`dashboard/src/app/api_proxy/[...slug]/route.ts`) assumes that missing headers are secure by assigning them to a default tenant UUID, expecting downstream or proxy validation to block unauthorized requests.
- **Attack scenario**: An attacker (or a buggy client component) sends requests to proxy endpoints (e.g., `/api_proxy/api/backend/leads`) without providing an `x-tenant-id` header. Instead of being rejected with a `400 Bad Request` at the proxy boundary, the request is transparently mapped to the default tenant (`00000000-0000-0000-0000-000000000000`) and successfully forwarded.
- **Blast radius**: High. Downstream APIs receive a valid UUID and may expose default/system-wide tenant data, bypassing front-line security controls.
- **Mitigation**: Update the API proxy handler to strictly require the `x-tenant-id` header. If it is missing or empty, immediately reject the request with `400 Bad Request` or `401 Unauthorized` without falling back to a default UUID:
  ```typescript
  const tenantId = request.headers.get("x-tenant-id");
  if (!tenantId) {
    return NextResponse.json({ error: "Bad Request: Missing x-tenant-id header" }, { status: 400 });
  }
  ```

### [Medium] Challenge 2: Coercion and Sanitization Relies on Frontend Correctness

- **Assumption challenged**: The backend and frontend are assumed to have perfectly aligned types, but the backend is loose (storing mixed types like string `"true"` for boolean and number `15000` for budget string).
- **Attack scenario**: Raw data in the database does not conform to the expected UI registry models (e.g., currency must be a string starting with `$`, booleans must be actual booleans). The UI relies on the React Component Registry or client-side transformers to clean up payloads. If a client fetches data outside of the React UI (e.g., direct API consumer), it receives unsanitized and uncoerced payloads.
- **Blast radius**: Medium. Can cause runtime errors or visual inconsistencies if the component registry fails to coerce elements.
- **Mitigation**: Enforce the Zod schema validation layer at the backend API gateway or in the Next.js API proxy boundary for both inbound and outbound responses.

---

## Stress Test Results

- **Valid UUID Format** (`4ba4e6b2-a42e-4b68-b789-f5383569c7ad`) → Expected: `200 OK` (Forwarded) → Actual: `200 OK` (Forwarded) → **PASS**
- **Invalid UUID Format** (`invalid-uuid-format`) → Expected: `400 Bad Request` (Blocked) → Actual: `400 Bad Request` (Blocked) → **PASS**
- **Missing UUID Header** → Expected: `400 Bad Request` (Blocked) → Actual: `200 OK` (Forwarded with default UUID) → **FAIL**
- **Empty UUID Header** (`-H "x-tenant-id: "`) → Expected: `400 Bad Request` (Blocked) → Actual: `200 OK` (Forwarded with default UUID) → **FAIL**

---

## Unchallenged Areas

- **UI Browser Interactions**: Dynamic state updates inside the browser window (such as simulating a user clicking the select dropdown and checking the visual re-render of components) were not verified using an automated browser driver (e.g., Playwright/Puppeteer) as those libraries are not available in the project's dependencies.
- **Verification Method**: Verified via React component unit structure inspections, direct Next.js router execution testing, and server-side state evaluation.
