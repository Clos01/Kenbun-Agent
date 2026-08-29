# Handoff Report — Adversarial Verification of Milestone 2: Zod Metadata Validation

## Observation

### 1. BFF API Proxy and Validation Schemas
- The API Proxy routes are defined in `dashboard/src/app/api_proxy/[...slug]/route.ts`.
- Allowed backend routes are restricted via:
```typescript
const ALLOWED_ROUTES = ["tools", "status", "health", "metrics", "orchestrate", "brain_health", "checkpoints", "api", "kanban", "stats", "logs"];
```
- Path traversal is checked via:
```typescript
const slugPath = params.slug.join("/");
if (slugPath.includes("..")) {
  console.warn(`🚨 [PROXY] Blocked Path Traversal attempt: ${sanitizeLog(slugPath)}`);
  return NextResponse.json({ error: "Forbidden: Path Traversal Detected" }, { status: 403 });
}
```
- The Zod validation schema is defined in `dashboard/src/lib/validation.ts`. In particular:
  - `SafeStringSchema` escapes HTML characters: `&`, `<`, `>`, `"`, `'`, `/`.
  - `BudgetSchema` coerces currency strings to numbers by removing non-numeric/period characters: `val.replace(/[^0-9.]/g, "")`.
  - `CommercialSchema` coerces `string` or `number` to `boolean` (`"true"`/`"1"`/`1` -> `true`).
  - `.strip()` is called on `LeadSchema` and `LeadMetadataSchema` to remove un-modeled keys.

### 2. Custom Stress Test Script execution
- Running the custom stress test script `node tests/stress_test_validation.js` yielded:
```text
=== STARTING ADVERSARIAL STRESS TESTS ===
⌛ Waiting for services to respond...
Mock Server listening on http://127.0.0.1:8001
[MOCK API] Request: method=GET, url=/api/health, pathname=/api/health
▲ Next.js 16.2.4 (Turbopack)
- Local:         http://localhost:3005
- Network:       http://192.168.1.196:3005
- Environments: .env
✓ Ready in 280ms

🟢 Services are online. Commencing tests...

--- Challenge 1: Proxy Route Blocklists & Path Traversal ---
[PROXY] Forwarding request to: http://127.0.0.1:8001/api/2e2e/unauthorized?_cb=1783397384008
[MOCK API] Request: method=GET, url=/unauthorized?_cb=1783397384008, pathname=/unauthorized
[PROXY] Response from backend for api/2e2e/unauthorized: status=404, length=21
 GET /api_proxy/api/%252e%252e/unauthorized 404 in 598ms
Path Traversal (api/%252e%252e/unauthorized) status: 404
...
🏆 ALL ADVERSARIAL CHALLENGES PASSED SUCCESSFULLY!
```
- This shows that a request to `/api_proxy/api/%252e%252e/unauthorized` was processed by Next.js, matched the route `api_proxy/[...slug]`, decoded the `%252e` to `%2e` in the slug parameter (`slugPath` became `"api/%2e%2e/unauthorized"`), which successfully bypassed the `slugPath.includes("..")` check.
- The downstream fetch request to `http://127.0.0.1:8001/api/%2e%2e/unauthorized` was resolved by the HTTP client (undici) to `http://127.0.0.1:8001/unauthorized`, hitting the mock backend server's unauthorized route and returning a `404` status rather than being blocked with a `403` status by the proxy's route allowlist.

### 3. Build and E2E Tests
- Running `npm run build` in `dashboard/` was successful.
- Running `node --test tests/e2e/leads.test.js` passed all 13 checks (once ports 8001 and 3005 were clean and ready).

---

## Logic Chain

1. **Vulnerability in Path Traversal Check**:
   - `route.ts` joins `params.slug` to form `slugPath` and checks if it contains `..` to prevent traversal.
   - If a client requests `api/%252e%252e/unauthorized`, Next.js decodes `%252e` once to `%2e` when assigning `params.slug` (yielding `["api", "%2e%2e", "unauthorized"]`).
   - The joined `slugPath` is `"api/%2e%2e/unauthorized"`. Since this string does not contain `..`, the path traversal check passes.
   - The allowed routes check verifies that `params.slug[0]` (which is `"api"`) is in the allowed routes list. Since `"api"` is allowed, the check passes.
   - The URL is built as `http://127.0.0.1:8001/api/%2e%2e/unauthorized`.
   - Node's `fetch` (undici) resolves the URL-encoded path segments. Specifically, it decodes `%2e%2e` to `..` and normalizes the path traversal, which maps the request to `http://127.0.0.1:8001/unauthorized`.
   - **Conclusion**: The route allowlist boundary is bypassed, allowing access to unauthorized endpoints on the backend server.

2. **Zod Validation and HTML Escaping**:
   - The `SafeStringSchema` transforms input strings by unescaping and then escaping standard HTML tags/characters.
   - The Zod schema `LeadSchema` and `LeadMetadataSchema` utilize `.strip()`, meaning any keys not defined in the schema (like `isAdmin`, `delete_all_records`, `__proto__`) are removed.
   - The React client renders parameters dynamically within JSX text braces (`{selectedLead.name}`, `{metadata.location}`), which natively prevents browser HTML interpretation (XSS). No `dangerouslySetInnerHTML` is used for dynamic user parameters.
   - **Conclusion**: Zod validation, prototype pollution filtering, and XSS sanitization are robustly implemented and cannot be bypassed.

---

## Caveats

- The path traversal bypass works only if the target backend server accepts the normalized path. If the backend server itself checks for `%2e%2e` or doesn't support path normalization, it will return an error, but the proxy itself has still failed to block it.
- This test suite was executed against the node-based mock backend (`mock-api.js`). The production Python FastAPI backend might handle path normalization or path parameters differently.

---

## Conclusion

The validation boundaries implemented in Milestone 2 are robust against prototype pollution, malformed input type coercion, and XSS script execution.
However, **there is a verified High-risk security vulnerability in the Next.js API BFF proxy (`route.ts`) allowing Route Allowlist / Path Traversal bypass via double URL-encoding (`%252e%252e`)**.

---

## Verification Method

To verify the vulnerability and validation rules:
1. Ensure both the mock-api server and Next.js frontend are running (or run `tests/stress_test_validation.js` directly, which handles startup/cleanup automatically).
2. Execute the stress test script:
   ```bash
   node tests/stress_test_validation.js
   ```
3. Observe output:
   - Challenge 1 confirms the bypass of path traversal / route blocklist.
   - Challenges 2-6 verify prototype pollution stripping, XSS escaping, and type coercion.

---

## Challenge Report (Adversarial Review)

### Challenge Summary
- **Overall risk assessment**: **HIGH** (due to proxy allowlist bypass vulnerability)

### Challenges

#### [High] Challenge 1: Route Allowlist/SSRF Bypass via Double URL-Encoded Traversal
- **Assumption challenged**: That checking `slugPath.includes("..")` is sufficient to prevent path traversal to unauthorized routes.
- **Attack scenario**: Sending `%252e%252e` in the URL segment. Next.js decodes it once to `%2e%2e`, bypassing the proxy's `..` check. The HTTP client decodes it again to `..` and normalizes the path traversal, hitting arbitrary backend routes.
- **Blast radius**: Allows an attacker to hit any backend server endpoints (including administrative or system utilities) that are not on the proxy's allowlist, potentially breaching tenant isolation or running unauthorized commands.
- **Mitigation**: Perform a decode of the `slugPath` before checking for traversal, or block `%2e` specifically:
  ```typescript
  const decodedPath = decodeURIComponent(slugPath);
  if (decodedPath.includes("..") || slugPath.includes("%2e") || slugPath.includes("%2E")) {
    // block request
  }
  ```

### Stress Test Results
- **SSRF Allowlist Traversal Bypass** → Block traversal (`403`) → Bypassed Proxy and reached Backend (`404`) → **FAIL** (Vulnerability confirmed)
- **Tenant ID Format SQLi/Malformed** → Reject request (`400`) → Rejected (`400`) → **PASS**
- **Prototype Pollution / Unknown Keys Stripping** → Stripped from payload → Stripped successfully → **PASS**
- **XSS HTML Escaping** → Escaped strings returned in response → Escaped (`&lt;script&gt;` etc.) → **PASS**
- **Coercion Robustness** → Malformed budget / commercial string coerced to float / bool → Coerced successfully (`10230.5`, `true`) → **PASS**
- **Invalid payloads rejection** → Reject malformed request_date format (`400`) → Rejected (`400`) → **PASS**

### Unchallenged Areas
- None.
