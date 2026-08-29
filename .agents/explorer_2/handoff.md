# Handoff Report — E2E Testing Track Explorer 2

## 1. Observation
The following file contents, paths, and configurations were observed:
- **API Proxy Routing**: `dashboard/src/app/api_proxy/[...slug]/route.ts` lines 42-47:
  ```typescript
  let internalBackendUrl = process.env.INTERNAL_API_URL;
  if (!internalBackendUrl) {
    const isDocker = fs.existsSync("/.dockerenv");
    internalBackendUrl = isDocker ? "http://host.docker.internal:8001" : "http://127.0.0.1:8001";
  }
  ```
- **Dashboard Package Scripts**: `dashboard/package.json` lines 5-10:
  ```json
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint"
  }
  ```
- **Heritage CSS Variables**: `dashboard/src/app/globals.css` lines 33-37:
  ```css
  --primary: #0F2537;       /* Deep Oceanic Blue (Midnight) */
  --secondary: rgba(15, 37, 55, 0.65); /* Translucent ink instead of slate gray */
  --tertiary: #00885F;      /* Planhat Premium Emerald Green */
  --accent: #B8422E;        /* Boston Clay Interactive Accent */
  --neutral: #FFFFFF;       /* Pure white backdrop */
  ```
- **Heritage Fonts**: `dashboard/src/app/layout.tsx` lines 7-15:
  ```typescript
  const spaceGrotesk = Space_Grotesk({
    variable: "--font-space-grotesk",
    subsets: ["latin"],
  });
  const publicSans = Public_Sans({
    variable: "--font-public-sans",
    subsets: ["latin"],
  });
  ```
- **Interface Contracts**: `.agents/sub_orch_e2e/SCOPE.md` lines 15-18:
  ```markdown
  - All E2E tests must be run via `npm run test:e2e` or `node scripts/run-e2e.js`.
  - The test harness must accept a custom `x-tenant-id` header/parameter to verify multi-tenant isolation.
  ```

---

## 2. Logic Chain
1. **API Redirection Integration**:
   - The Next.js API proxy forwards all requests under `/api_proxy/*` to the address mapped by `INTERNAL_API_URL` (defaulting to port `8001`).
   - *Logic Step*: By spinning up a mock API server (`scripts/mock-api.js`) on port `8001` or configuring `INTERNAL_API_URL=http://localhost:<custom_port>` dynamically, the dashboard frontend's API calls to `/api_proxy/api/backend/leads` will automatically be routed to our mock backend without requiring code changes to the proxy or the client.
2. **Runner & Script Orchestration**:
   - There is no test runner in `scripts/` or `dashboard/package.json` for E2E tests.
   - *Logic Step*: A new script `scripts/run-e2e.js` must be implemented to spawn the mock server process, spawn the Next.js dev/prod server process, wait for both to be ready (using socket polling on ports `8001` and `3000`), execute the Playwright test suite, and ensure all child processes are killed cleanly on exit. This runner can then be integrated via `"test:e2e": "node ../scripts/run-e2e.js"` in `dashboard/package.json`.
3. **Multi-Tenant & Security Validation**:
   - The mock API must validate tenant ID headers and prevent data leakage, while Zod must sanitize malicious payloads.
   - *Logic Step*: The mock server will enforce `x-tenant-id` UUID format checks (returning `400`/`401`/`403` status codes) and partition mock data. Specifically:
     - **Tenant A (Real Estate)** and **Tenant B (Landscaping)** provide happy path data mapping different UI data types.
     - **Tenant C (Malicious)** embeds XSS script strings and prototype pollution properties.
     - **Tenant D (Empty)** returns an empty array.
   - E2E tests can verify that Tenant C's malicious fields are properly sanitized (escaped/stripped) by the frontend's Zod schema before DOM rendering, and that switching between Tenants A and B immediately updates state without data residue.
4. **Heritage Design Compliance**:
   - CSS tokens are mapped to active variables (`--primary`, `--secondary`, etc.) and font definitions.
   - *Logic Step*: The E2E tests must assert compliance by querying computed CSS styles of registry elements (e.g. verifying primary heading colors match `#0F2537`/`#1A1C1E` and fonts are `"Public Sans"`).

---

## 3. Caveats
- Since the implementation track is running in parallel, we assume the frontend code will use `/api_proxy/api/backend/leads` and conform to the specified context hook interfaces (`useTenant`).
- All designs and code snippets are presented as architectural proposals; no implementation files have been written to the codebase in accordance with the read-only constraint.

---

## 4. Conclusion
We have successfully analyzed the codebase and designed the E2E testing infrastructure. The comprehensive report has been saved to:
`~/Dev/Kenbun/.agents/sub_orch_e2e/explorer_report_2.md`

This design specifies:
- The opaque-box runner orchestration loop in `scripts/run-e2e.js`.
- The multi-tenant mock API server in `scripts/mock-api.js` validating `x-tenant-id`.
- The 4-tier test case matrix covering sanity paths, validation boundaries, cross-feature transitions, and real-world workflows.
- Styling assertions using computed styles for Heritage Design System tokens.

---

## 5. Verification Method
- Open and inspect the report file `~/Dev/Kenbun/.agents/sub_orch_e2e/explorer_report_2.md`.
- Verify the details align with the requirements and interface contracts.
