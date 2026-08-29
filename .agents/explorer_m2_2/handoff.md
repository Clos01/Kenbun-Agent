# Handoff Report: Explorer 2 (Milestone 2 - Zod Metadata Validation)

## 1. Observation
We observed the following files and code blocks in the workspace:
1. **Frontend Data Ingestion Boundary**:
   - In `dashboard/src/app/leads/page.tsx`, incoming leads are fetched and parsed from JSON directly into memory without validation on line 144:
     ```typescript
     144:         const data = await response.json();
     145:         const leadsList = Array.isArray(data) ? data : (data.leads || []);
     ```
   - Currently, the dashboard lacks any global type safety files or validation logic. The `Lead` interface is defined inline:
     ```typescript
     30: interface Lead {
     31:   id: string;
     32:   name: string;
     ...
     43: }
     ```

2. **Server-Side API Proxy Gate**:
   - In `dashboard/src/app/api_proxy/[...slug]/route.ts`, the handler forwards request data as-is on line 135:
     ```typescript
     128:     const responseData = await response.text();
     ...
     135:     return new NextResponse(responseData, {
     ```

3. **Current Dependencies**:
   - In `dashboard/package.json` (lines 12–23), the `dependencies` list does not contain `zod` or any other validation library.

4. **Pending E2E Security Tests**:
   - In `tests/e2e/leads.test.js`, there are placeholder tests explicitly checking for validation and sanitization on lines 204–205:
     ```javascript
     204: test.todo("Coercion validation check");
     205: test.todo("XSS sanitization check");
     ```

---

## 2. Logic Chain
1. Since incoming lead data is parsed from raw backend JSON directly into the client application state at `leads/page.tsx:144` and passes through `api_proxy/route.ts:135`, these boundaries are currently vulnerable to untrusted payloads.
2. Because `package.json` lacks `zod`, we must install the `zod` package to perform schema validation.
3. Defining the schemas at `dashboard/src/lib/validation.ts` allows us to import them both in client-side React code (`leads/page.tsx`) and server-side Edge/API routes (`api_proxy/[...slug]/route.ts`).
4. By using Zod's default `.strip()` behavior on the metadata object schema, any keys in the payload not explicitly matching the allowed domain definitions will be discarded, stripping malicious payload keys from the data ingestion layer.
5. In addition, using Zod's `.transform()` method with a custom string utility will sanitize incoming string values to remove HTML tags, mitigating XSS risks.
6. Auto-generating TypeScript interfaces using `z.infer<typeof LeadSchema>` allows us to replace the inline `interface Lead` in `page.tsx` with a verified schema-derived type, ensuring compile-time and run-time types are synchronized.

---

## 3. Caveats
- No code was modified during this read-only investigation.
- The structure of accepted metadata keys is based on domain context (Landscaping, Construction, HVAC, Plumbing) extracted from `PROJECT.md` and `tests/e2e/leads.test.js`.
- String sanitization proposed is a lightweight HTML-tag stripper; depending on the rendering requirements, a complete DOM-purification library (like `dompurify` or `isomorphic-dompurify`) may need to be integrated if rich text metadata rendering is allowed in the future.

---

## 4. Conclusion
To complete Milestone 2, we recommend:
1. Installing `zod` via `npm install zod`.
2. Creating `dashboard/src/lib/validation.ts` containing the `LeadSchema` and `LeadMetadataSchema` as detailed in our `explorer_report.md`.
3. Updating `dashboard/src/app/leads/page.tsx` to validate data using `LeadSchema.safeParse` (or `LeadsListSchema.safeParse` for lists).
4. Updating `dashboard/src/app/api_proxy/[...slug]/route.ts` to intercept and sanitize lead payloads at the server boundary.

---

## 5. Verification Method
- **Static Validation**: Run `npm run build` inside `dashboard/` to verify that there are no TypeScript compile-time errors after replacing inline interfaces with Zod-inferred types.
- **E2E Testing**: Run `node ../scripts/run-e2e.js` (or `npm run test:e2e` inside `dashboard/`) to verify that the validation tests are properly executed. Once the implementer integrates the schemas, the `todo("Coercion validation check")` and `todo("XSS sanitization check")` tests should be written/migrated to active assertions.
