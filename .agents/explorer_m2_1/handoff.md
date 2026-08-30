# Handoff Report: Milestone 2 Zod Metadata Validation Strategy

## 1. Observation
I directly observed the following files, layouts, and lines of code:

- **Dashboard Ingestion/State**: In `dashboard/src/app/leads/page.tsx` (lines 120-125), lead state is defined as `Lead[]`:
  ```typescript
  const [leads, setLeads] = useState<Lead[]>([]);
  ```
  And in `loadLeads()` (lines 144-145), the API response JSON is ingested without validation:
  ```typescript
  const data = await response.json();
  const leadsList = Array.isArray(data) ? data : (data.leads || []);
  ```
  The inline `interface Lead` (lines 30-43) completely lacks a definition for `metadata`.

- **API BFF Proxy**: In `dashboard/src/app/api_proxy/[...slug]/route.ts` (lines 125-135), the server-side proxy forwards requests and reads response data as text without any validation before returning it:
  ```typescript
  const response = await fetch(backendUrl, options);
  const responseData = await response.text();
  ...
  return new NextResponse(responseData, { ... });
  ```

- **Mock API Payload Structures**: In `scripts/mock-api.js` (lines 66-83), Tenant C (Malicious) contains adversarial parameters inside `metadata`:
  ```javascript
  metadata: {
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

- **Unimplemented E2E Test Hooks**: In `tests/e2e/leads.test.js` (lines 198-207), the following TODO test hooks are present:
  ```javascript
  test.todo("Component Registry renderers check");
  test.todo("Metadata label mapping checks");
  test.todo("Coercion validation check");
  test.todo("XSS sanitization check");
  test.todo("Heritage tokens verification");
  ```

---

## 2. Logic Chain
1. **Malicious Keys Detection**: Based on `scripts/mock-api.js` line 66-83, the incoming data from `Tenant C` contains malicious keys (`isAdmin`, `delete_all_records`, `__proto__`, script tags) designed to exploit the frontend dashboard or backend.
2. **Lack of Validation**: Since the BFF API proxy `route.ts` forwards text and `leads/page.tsx` calls `await response.json()` directly without validation or sanitization, these malicious properties are currently ingested into the React client memory.
3. **Zod Boundary Enforcement**: Defining a Zod schema with `.strip()` allows Next.js server/client runtimes to automatically discard any object properties not explicitly declared.
4. **Coercion & Sanitization Requirements**: The TODO tests in `leads.test.js` dictate that the solution must handle value coercion (e.g. string to number/boolean) and string XSS sanitization. Zod's `.transform()` pipeline is the ideal mechanism for running both inline coercion logic and HTML escaping on string properties.
5. **Component Registry Mapping**: In order to render validated metadata keys dynamically in the UI while satisfying the "Component Registry renderers check" and "Heritage tokens verification" TODO tests, the dashboard needs a registry mapping metadata keys to dedicated Lucide-icon-based components adhering to the Limestone/Boston Clay palettes.

---

## 3. Caveats
- No changes to source code were implemented as per the read-only boundary constraints.
- Real-time E2E tests were not run because doing so requires launching server processes (violating the read-only and no active execution limits of this task phase).
- Package installation (`npm install zod`) must be executed before writing code, as Zod is not listed in `dashboard/package.json`.

---

## 4. Conclusion
We recommend defining standard Zod schemas in a new file `dashboard/src/lib/validation.ts`. This file will act as a single source of truth for both runtime validation (via `.parse()`) and compile-time types (via `z.infer`). 

Ingestion validation must be enforced at the server-side BFF boundary `dashboard/src/app/api_proxy/[...slug]/route.ts` to filter payloads before they reach the browser, and in the UI using a Bento-grid dynamic renderer inside `dashboard/src/app/leads/page.tsx` utilizing Framer Motion for micro-interactions to comply with design regulations.

---

## 5. Verification Method
To independently verify the implementation:
1. Run the E2E test command inside the `dashboard` folder:
   ```bash
   npm run test:e2e
   ```
2. The tests should successfully run, and the unimplemented `test.todo` blocks in `tests/e2e/leads.test.js` should be replaced with assertions confirming that:
   - Unknown keys (e.g. `isAdmin`) are stripped from `metadata` objects.
   - String numbers and booleans are coerced.
   - HTML injection scripts are neutralized.
   - Dynamic renderers display mapped labels instead of raw property names.

---

## 6. Remaining Work (For Implementer)
1. Add `zod` dependency to `dashboard/package.json` and install.
2. Create `dashboard/src/lib/validation.ts` containing the proposed schemas.
3. Integrate schema validation into the `handleProxy` method of `dashboard/src/app/api_proxy/[...slug]/route.ts` for both GET and POST requests.
4. Update `dashboard/src/app/leads/page.tsx` to display custom metadata via `CustomMetadataBento` component with framer-motion animations.
5. Convert `leads.test.js` TODO hooks to active test cases and run the E2E test suite to verify success.
