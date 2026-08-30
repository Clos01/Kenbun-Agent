# Handoff Report: Milestone 2 — Zod Metadata Validation

## 1. Observation
We observed the following files and code snippets in the repository `~/Dev/Kenbun`:

- **File**: `dashboard/package.json`
  - In `dependencies`, Zod is currently missing:
    ```json
    "dependencies": {
      "@gsap/react": "^2.1.2",
      "clsx": "^2.1.1",
      "framer-motion": "^12.38.0",
      "gsap": "^3.15.0",
      "lucide-react": "^1.14.0",
      "next": "16.2.4",
      "postcss": "^8.5.14",
      "react": "19.2.4",
      "react-dom": "19.2.4",
      "tailwind-merge": "^3.5.0"
    }
    ```
- **File**: `dashboard/src/app/leads/page.tsx`
  - Ingestion occurs via the `loadLeads` function:
    ```typescript
    console.log(`[LEADS] Fetching api/v1/leads with tenant: ${tenantId}`);
    let response = await request("api/v1/leads");
    ...
    if (response.ok) {
      const data = await response.json();
      const leadsList = Array.isArray(data) ? data : (data.leads || []);
    ```
  - It expects a hardcoded type `Lead` that currently does not support backend dynamic `metadata` keys.
- **File**: `dashboard/src/app/api_proxy/[...slug]/route.ts`
  - Incoming requests are proxied via `handleProxy`:
    ```typescript
    const response = await fetch(backendUrl, options);
    const responseData = await response.text();
    ...
    return new NextResponse(responseData, { ... });
    ```
- **File**: `scripts/mock-api.js`
  - In Tenant C, malicious inputs are injected into lead metadata to simulate attacks:
    ```javascript
    "metadata": {
      budget: "$10,000",
      request_date: "2026-07-07",
      commercial: true,
      isAdmin: true,
      delete_all_records: "DROP TABLE leads;",
      "__proto__": { "polluted": true },
      "inject_script": "<script>alert('XSS')</script>",
      "onload_exploit": "<img src=x onerror=alert(1)>"
    }
    ```
- **File**: `tests/e2e/leads.test.js`
  - Unimplemented features are listed as pending tests:
    ```javascript
    test.todo("Component Registry renderers check");
    test.todo("Metadata label mapping checks");
    test.todo("Coercion validation check");
    test.todo("XSS sanitization check");
    test.todo("Heritage tokens verification");
    ```

---

## 2. Logic Chain

1. **Vulnerability Point**: Since `dashboard/src/app/api_proxy/[...slug]/route.ts` forwards response text directly to the client without validation, the browser client receives malicious raw properties like `__proto__`, `isAdmin`, and XSS injection vectors (e.g. `<script>alert('XSS')</script>`).
2. **Stripping Vector**: Defining a Zod schema using `.strip()` at the object level filters out any undeclared payload keys (e.g., `isAdmin: true` or SQL injection payloads on root fields).
3. **Dynamic Safeguard**: Using `z.record(keySchema, valueSchema)` for dynamic metadata allows for validating dynamic custom keys. To prevent prototype pollution, the key schema must reject `__proto__`, `constructor`, and `prototype`.
4. **Sanitization Vector**: Applying custom string transforms to escape HTML tags (`sanitizeHtml`) blocks XSS strings from executing when rendered in the DOM.
5. **Coercion Vector**: Standard `z.coerce.boolean()` evaluates `"false"` as `true`, so we need custom union/transform logic for safe boolean/numeric coercion of incoming string representations.
6. **Execution Point**: Creating `dashboard/src/lib/validation.ts` enables sharing the validation logic between client pages and server-side routes, preserving a single source of truth.

---

## 3. Caveats
- Since this was a read-only investigation, we did not verify how the frontend renders custom fields inside `leads/page.tsx`. Currently, the frontend UI has no logic to display dynamic key-value properties from `metadata`.
- We assumed the Python backend relies on Next.js to do boundary cleaning. If the database itself is vulnerable, backend-side validation (in Python FastAPIs / Pydantic) would also be required in subsequent milestones.

---

## 4. Conclusion
We recommend:
1. Installing `zod` inside the `dashboard/` workspace.
2. Creating `dashboard/src/lib/validation.ts` to define schema definitions (e.g., `leadIngestionSchema` with `.strip()`, dynamic `leadMetadataSchema` with prototype pollution guards, custom XSS string sanitizers, and safe boolean/number coercion helpers).
3. Modifying `dashboard/src/app/api_proxy/[...slug]/route.ts` to parse, validate, and sanitize the outgoing lead responses before returning them to the React frontend client.

---

## 5. Verification Method

To verify the implementation once coded:
1. **Command**: Run the e2e test suite:
   ```bash
   npm run test:e2e --prefix dashboard
   ```
2. **Inspection**:
   - Verify that the active E2E test `Multi-tenant breach spoofing` and `Prototype Pollution protection check (Tenant C)` still pass.
   - Verify that the todo tests `Coercion validation check` and `XSS sanitization check` are completed and pass.
3. **Invalidation conditions**:
   - If `Object.prototype.polluted` is modified, the prototype pollution check has failed.
   - If string values in Tenant C's metadata output retain the `<script>` tag, the XSS sanitization check has failed.

---

## 6. Remaining Work
1. Install `zod` inside `dashboard/package.json` (`npm install zod`).
2. Create the `dashboard/src/lib/validation.ts` file containing the schemas proposed in `explorer_report.md`.
3. Integrate the schema validation in `dashboard/src/app/api_proxy/[...slug]/route.ts` inside the `handleProxy` handler.
4. Update the E2E tests in `tests/e2e/leads.test.js` to implement the `Coercion validation check` and `XSS sanitization check` tests.
