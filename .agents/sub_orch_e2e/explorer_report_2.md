# Aura Lead OS Frontend Upgrade — E2E Testing Infrastructure & Test Suite Design Analysis

## Executive Summary
This report defines the comprehensive end-to-end (E2E) testing architecture and test suite design for the Aura Lead OS Frontend Upgrade within the CRG Backoffice SaaS. 

Since the frontend implementation (including `TenantContext`, `apiClient`, `MetadataSchema` validation, `MetadataTransformer` normalization, and the Component Registry) is scheduled for parallel implementation, this testing framework is designed as a strict **opaque-box test harness**. It treats the dashboard application as a black box, verifying all requirements through public interfaces, HTTP request interceptors, custom tenant headers, page routing, and visual/markup assertions.

By decoupling the test execution from internal state, we ensure that:
1. Multi-tenant isolation is strictly verified at the network/API boundary.
2. The Zod sanitization layer is tested against malicious inputs (XSS, prototype pollution).
3. The React Component Registry renders types (currency, dates, booleans) properly conforming to the Heritage Design System.
4. Process cleanup is completely deterministic, avoiding orphaned port bindings on mac and CI systems.

---

## 1. Opaque-Box Test Runner (`scripts/run-e2e.js`)

The opaque-box test runner acts as the orchestrator for the entire E2E test lifecycle. Its job is to spin up the mock API backend and the Next.js server, verify their readiness, execute the tests, and tear everything down gracefully.

### 1.1 Implementation Architecture (`scripts/run-e2e.js`)
The runner will be implemented in pure Node.js (with zero external dependencies for orchestration) using `child_process.spawn`. It follows this strict sequence:

```
[run-e2e.js] 
   ├── 1. Read/Assign Ports (e.g. Next.js: 3000, Mock API: 8001)
   ├── 2. Spawn Mock API Server (scripts/mock-api.js)
   ├── 3. Spawn Next.js Server (env: INTERNAL_API_URL=http://localhost:8001)
   ├── 4. Wait-On Ports (Poll localhost:8001/api/health & localhost:3000/api/ping)
   ├── 5. Spawn Test Suite (Playwright or node:test)
   └── 6. Teardown (Send SIGTERM/SIGKILL, exit with test status)
```

### 1.2 Proposed Script Design (`scripts/run-e2e.js`)
Here is the detailed design and structural code skeleton for `scripts/run-e2e.js`:

```javascript
/**
 * scripts/run-e2e.js
 * Opaque-Box Test Orchestration Runner
 */
const { spawn } = require("child_process");
const net = require("net");
const path = require("path");

const FRONTEND_PORT = process.env.PORT || 3000;
const MOCK_API_PORT = process.env.MOCK_API_PORT || 8001;

const children = [];

// Helper: Check if a port is open and listening
function checkPort(port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    const onError = () => {
      socket.destroy();
      resolve(false);
    };
    socket.setTimeout(1000);
    socket.once("error", onError);
    socket.once("timeout", onError);
    socket.connect(port, "127.0.0.1", () => {
      socket.end();
      resolve(true);
    });
  });
}

// Helper: Polling wait-on for servers
async function waitOnPort(port, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const isOpen = await checkPort(port);
    if (isOpen) return true;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`Timeout waiting for port ${port}`);
}

// Graceful Teardown Handler
function cleanupAndExit(exitCode = 0) {
  console.log("\n🧹 [TEARDOWN] Cleaning up spawned processes...");
  for (const child of children) {
    if (child && !child.killed) {
      try {
        console.log(`Sending SIGTERM to PID ${child.pid}`);
        child.kill("SIGTERM");
      } catch (err) {
        console.error(`Failed to kill process ${child.pid}:`, err);
      }
    }
  }
  process.exit(exitCode);
}

// Register exit hook listeners to prevent orphaned processes
process.on("SIGINT", () => cleanupAndExit(130));
process.on("SIGTERM", () => cleanupAndExit(143));
process.on("uncaughtException", (err) => {
  console.error("🔥 Uncaught exception in runner:", err);
  cleanupAndExit(1);
});

async function main() {
  try {
    console.log("🚀 [RUNNER] Initializing E2E Test Suite Environment...");

    // 1. Spawn Mock API Server
    console.log(`[RUNNER] Spawning Mock API on port ${MOCK_API_PORT}...`);
    const mockApi = spawn("node", [path.resolve(__dirname, "mock-api.js")], {
      env: { ...process.env, PORT: MOCK_API_PORT },
      stdio: "inherit",
    });
    children.push(mockApi);

    // 2. Wait for Mock API to be ready
    await waitOnPort(MOCK_API_PORT);
    console.log("✅ [RUNNER] Mock API is ready.");

    // 3. Spawn Next.js Server
    console.log(`[RUNNER] Spawning Next.js frontend on port ${FRONTEND_PORT}...`);
    const nextServer = spawn("npm", ["run", "dev", "--", "-p", FRONTEND_PORT], {
      cwd: path.resolve(__dirname, "../dashboard"),
      env: {
        ...process.env,
        PORT: FRONTEND_PORT,
        INTERNAL_API_URL: `http://127.0.0.1:${MOCK_API_PORT}`,
      },
      stdio: "inherit",
    });
    children.push(nextServer);

    // 4. Wait for Next.js to be ready
    await waitOnPort(FRONTEND_PORT);
    console.log("✅ [RUNNER] Next.js frontend server is ready.");

    // 5. Execute E2E Tests (using Playwright)
    console.log("🧪 [RUNNER] Running Playwright E2E tests...");
    const testProcess = spawn("npx", ["playwright", "test"], {
      cwd: path.resolve(__dirname, "../dashboard"),
      stdio: "inherit",
      env: { ...process.env, BASE_URL: `http://localhost:${FRONTEND_PORT}` }
    });

    testProcess.on("exit", (code) => {
      console.log(`🧪 [RUNNER] E2E test run complete with exit code: ${code}`);
      cleanupAndExit(code);
    });

  } catch (error) {
    console.error("❌ [RUNNER ERROR]:", error.message);
    cleanupAndExit(1);
  }
}

main();
```

### 1.3 Integration in `dashboard/package.json`
To make E2E execution a first-class citizen in the frontend module, the `dashboard/package.json` must be updated to export a clean `npm run test:e2e` hook:

```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "eslint",
  "test:e2e": "node ../scripts/run-e2e.js"
}
```

---

## 2. Mock API Server (`scripts/mock-api.js`)

The mock server simulates the actual API Gateway behavior. It performs validation on incoming request contexts and headers, specifically testing tenant isolation boundaries.

### 2.1 Design of the Mock Server
- **Zero Dependencies**: Created using Node’s built-in `http` and `url` modules.
- **Route Handlers**:
  - `GET /api/health`: Light check returning `{ status: "ok" }` for the test runner's wait-on check.
  - `GET /api/backend/leads`: Core API endpoint.
- **Tenant Context Verification**:
  - Checks for the presence of the `x-tenant-id` header.
  - Validates that the tenant ID is in UUIDv4 format (`/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i`).
  - Returns `400 Bad Request` if missing, or `401 Unauthorized` if invalid format.
  - Performs data filtering based on the tenant context to ensure no data leaks between tenants.

### 2.2 Mock Dataset Schema
The mock dataset includes several tenants designed to trigger distinct code paths:

1. **Tenant A (UUID: `d3b07384-d113-49cd-a5d6-80bd00d11111`) — Happy Path Real Estate**:
   Contains clean metadata containing formatting variants: currency, dates, booleans, and nested structures.
2. **Tenant B (UUID: `e4c07384-e224-49cd-b6e7-90be00e22222`) — Happy Path Landscaping**:
   Contains normal landscaping attributes to test theme styling and component layouts under a different schema.
3. **Tenant C (UUID: `f5d07384-f335-49cd-c7f8-a0bf00f33333`) — Validation & Sanitization Boundary**:
   Injects malicious elements to test the frontend's Zod parsing layer, including:
   - XSS vectors (e.g. `<script>alert('XSS')</script>`).
   - Prototype pollution payload properties (e.g., `__proto__`, `constructor`, `prototype`).
   - Malformed data types (e.g., non-numeric strings in currency fields).
4. **Tenant D (UUID: `a1b07384-a111-49cd-a111-a0af00a11111`) — Empty State**:
   Returns an empty list `[]` to verify empty state display rendering.

### 2.3 Proposed Mock Server Script (`scripts/mock-api.js`)
```javascript
/**
 * scripts/mock-api.js
 * Lightweight, zero-dependency multi-tenant mock backend server
 */
const http = require("http");
const url = require("url");

const PORT = process.env.PORT || 8001;

// Regex to validate UUID format
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const MOCK_LEADS = {
  // Tenant A: Happy Path Real Estate leads
  "d3b07384-d113-49cd-a5d6-80bd00d11111": [
    {
      id: "7a2b9c3e-4f5a-6b7c-8d9e-0f1a2b3c4d5e",
      name: "Arthur Pendragon",
      email: "arthur@camelot.org",
      created_at: "2026-07-01T10:00:00Z",
      metadata: {
        lead_value: 450000.00,        // Currency mapping target
        closing_date: "2026-10-31",   // Date mapping target
        is_pre_approved: true,         // Boolean mapping target
        buyer_notes: "Looking for property with historic gravitas.", // Text mapping target
      }
    }
  ],
  // Tenant B: Landscaping lead
  "e4c07384-e224-49cd-b6e7-90be00e22222": [
    {
      id: "8c3d9e4f-5a6b-7c8d-9e0f-1a2b3c4d5e6f",
      name: "Guinevere Green",
      email: "guinevere@gardens.net",
      created_at: "2026-07-06T15:30:00Z",
      metadata: {
        quote_amount: 2500.50,         // Currency mapping target
        scheduled_date: "2026-07-15",  // Date mapping target
        has_lawn_care: true,           // Boolean mapping target
        urgency_rating: "high",        // Text mapping target
      }
    }
  ],
  // Tenant C: Malicious/Malformed Inputs to test sanitization & Zod boundaries
  "f5d07384-f335-49cd-c7f8-a0bf00f33333": [
    {
      id: "9d4e0f5a-6b7c-8d9e-0f1a-2b3c4d5e6f7a",
      name: "Malicious Actor",
      email: "attacker@exploit.net",
      created_at: "2026-07-06T23:59:59Z",
      metadata: {
        lead_value: "invalid_currency_100_abc", // Should trigger currency parser fallback or fail validation gracefully
        closing_date: "99-99-9999",             // Malformed date
        is_pre_approved: "not-a-boolean",      // Malformed boolean type
        xss_payload: "<script>alert(document.cookie)</script>", // XSS Target
        pollution_attempt: {
          __proto__: { polluted: "exploit_success" },
          constructor: { prototype: { hijacked: true } }
        }
      }
    }
  ],
  // Tenant D: Empty State
  "a1b07384-a111-49cd-a111-a0af00a11111": []
};

const server = http.createServer((req, res) => {
  // CORS Headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, x-tenant-id");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  const parsedUrl = url.parse(req.url, true);

  // Health check endpoint
  if (parsedUrl.pathname === "/api/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  // Leads endpoint
  if (parsedUrl.pathname === "/api/backend/leads") {
    // 1. Authenticate and extract x-tenant-id from header or query param context
    const tenantId = req.headers["x-tenant-id"] || parsedUrl.query["tenant_id"];

    if (!tenantId) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Bad Request: Missing x-tenant-id context header or parameter." }));
      return;
    }

    // 2. Validate tenant ID format
    if (!UUID_REGEX.test(tenantId)) {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Unauthorized: Invalid Tenant ID format (UUID required)." }));
      return;
    }

    // 3. Fetch data or empty array fallback
    const tenantLeads = MOCK_LEADS[tenantId];
    if (tenantLeads === undefined) {
      // Forbidden: Trying to access an unrecognized or unauthorized tenant
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Forbidden: Tenant context not authorized." }));
      return;
    }

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(tenantLeads));
    return;
  }

  // Fallback 404
  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not Found" }));
});

server.listen(PORT, () => {
  console.log(`[MOCK API] Mock server running on port ${PORT}`);
});
```

---

## 3. Feature Inventory & Test Cases (Tiers 1-4)

The test suite must exhaustively cover features, boundary conditions, cross-feature interactions, and real-world workloads using the four-tier methodology.

### 3.1 Feature Inventory
The Leads Dashboard upgrade consists of five core integrated components:
1. **Tenant Context & Hook (`useTenant`)**: React hook mapping layout fetches to active tenant context.
2. **Secure Fetch Layer (`apiClient`)**: Injects `x-tenant-id` securely from context headers.
3. **Zod Validation boundary (`leadSchema`)**: Sanitizes API response payloads, ensuring proper data formatting.
4. **Metadata Normalization (`MetadataTransformer`)**: Normalizes raw keys (e.g. `lead_value` ➔ "Lead Value") and orders them dynamically.
5. **Component Registry**: Renders types (`currency`, `date`, `boolean`, `string`) using customized Heritage styling.

---

### 3.2 Tier 1: Feature Coverage (Sanity & Happy Paths)
*Asserts baseline requirement fulfillment. >=5 tests required.*

- **Test 1.1: Tenant ID Context Routing Verification**
  - **Objective**: Verify that the application initializes a Tenant Context and includes the `x-tenant-id` header in the API fetch request.
  - **Action**: Load `/leads` (or select Tenant A via context UI selector). Intercept the `/api/backend/leads` call.
  - **Assertion**: Verify the request has header `x-tenant-id: d3b07384-d113-49cd-a5d6-80bd00d11111` and returns `200 OK`.
  
- **Test 1.2: Component Registry - Currency Renderer**
  - **Objective**: Verify currency data type is caught and formatted inside a custom visual badge.
  - **Action**: Select Tenant A. Verify lead listing.
  - **Assertion**: Element for `lead_value` (value `450000.00`) should render formatted text (e.g., `$450,000.00`) and use the `Accent` or `Tertiary` typography block.

- **Test 1.3: Component Registry - Date Renderer**
  - **Objective**: Verify date data type renders formatted using a calendar-style display card.
  - **Action**: Select Tenant A. Locate `closing_date`.
  - **Assertion**: Raw text `2026-10-31` is converted into a formatted local string (e.g. "Oct 31, 2026").

- **Test 1.4: Component Registry - Boolean Toggle Badge**
  - **Objective**: Verify boolean state is mapped to visual indicators instead of printing raw "true"/"false".
  - **Action**: Select Tenant A. Locate `is_pre_approved` status element.
  - **Assertion**: Renders as a styled checkmark badge or green toggle with readable text indicator.

- **Test 1.5: Metadata Normalization Label Mapping**
  - **Objective**: Verify `MetadataTransformer` maps raw keys to readable keys.
  - **Action**: Load Tenant A leads.
  - **Assertion**: Label for `lead_value` is printed as "Lead Value", and `is_pre_approved` is printed as "Pre Approved" (or mapping specified in transformer configuration).

---

### 3.3 Tier 2: Boundary & Corner Cases (Fuzzing, Empty States, Security)
*Asserts system resilience under pressure and validation strictness. >=5 tests required.*

- **Test 2.1: Empty State Handling**
  - **Objective**: Verify the UI handles empty lead responses gracefully.
  - **Action**: Select Tenant D (UUID: `a1b07384-a111-49cd-a111-a0af00a11111`).
  - **Assertion**: Intercepted response is `[]`. The UI displays a clean placeholder card (e.g. "No active leads found for this tenant") instead of breaking or spinner hanging.

- **Test 2.2: Extreme Layout / Overflow Boundary**
  - **Objective**: Verify text strings in metadata do not break layouts.
  - **Action**: Seed lead with metadata description containing 2000 characters.
  - **Assertion**: Layout remains grid-aligned. Description element applies css line-clamp or text truncation (`truncate`/`overflow-hidden`) with "Read more" trigger.

- **Test 2.3: Zod Type Validation Fallback**
  - **Objective**: Verify validation failure of individual keys degrades gracefully.
  - **Action**: Select Tenant C (malformed payload values).
  - **Assertion**: `lead_value` with value `"invalid_currency_100_abc"` fails numeric parsing. The UI falls back to standard text renderer safely or displays validation warnings next to the entry without crashing the panel.

- **Test 2.4: XSS Payload Sanitization**
  - **Objective**: Verify html tag escaping preventing Client-Side Script Injection.
  - **Action**: Select Tenant C. Open lead detail inspector containing `xss_payload` `<script>alert(document.cookie)</script>`.
  - **Assertion**: The script tag is rendered as literal text (escaped) or stripped. Assert that no alert popups are triggered and the page context remains clean.

- **Test 2.5: Prototype Pollution Prevention (Security Boundary)**
  - **Objective**: Ensure prototype pollution keys in metadata are stripped at the Zod layer and do not mutate JavaScript Object prototypes.
  - **Action**: Select Tenant C. Fetch lead containing `pollution_attempt` dictionary.
  - **Assertion**: Verify via browser test console that `Object.prototype.polluted` is `undefined` (not polluted) and the keys `__proto__` are omitted or stripped.

---

### 3.4 Tier 3: Cross-Feature Combinations (Feature Interactions)
*Asserts multi-feature interactions, ensuring no state leakage.*

- **Test 3.1: Switch Tenant Context + Request Isolation Lifecycle**
  - **Objective**: Verify switching active tenant updates the context and correctly fetches new isolated resources.
  - **Action**: Load Tenant A leads. Verify Camelot data exists. Switch tenant selector UI to Tenant B.
  - **Assertion**: 
    1. UI immediately triggers loading state and updates `useTenant()` context.
    2. New fetch request is dispatched to `/api/backend/leads` with `x-tenant-id` header set to Tenant B's UUID.
    3. UI renders Tenant B leads (Guinevere Green) and Camelot details are fully cleaned/removed from DOM, verifying **zero cross-tenant data leakage**.

- **Test 3.2: Theme Toggle + Heritage Design Tokens Compliance**
  - **Objective**: Verify that toggling between Light and Dark mode renders correct CSS variables on the custom components without breaking layouts.
  - **Action**: Load leads view. Click theme toggle button in Sidebar.
  - **Assertion**: 
    1. `document.documentElement` toggles the `.light` class.
    2. Color values of background and text match variables: `--background` is updated (e.g. from Dark-theme default to `#FFFFFF` neutral).
    3. Computed colors on component borders match the specified `rgba(15, 37, 55, 0.08)` line boundary color.

---

### 3.5 Tier 4: Real-World Scenarios (Customer Workloads & Spinoffs)
*Simulates high-fidelity client workflows.*

- **Test 4.1: Landscaping Lead Lifecycle Workflow**
  - **Objective**: Simulate a complete backoffice operator reviewing a new Landscaping lead.
  - **Action/Steps**:
    1. Operator loads dashboard. Selects Tenant B (Landscaping).
    2. Interceptor checks request includes header `x-tenant-id: e4c07384-e224-49cd-b6e7-90be00e22222`.
    3. Grid renders. Operator clicks on "Guinevere Green" lead card.
    4. SVE Inspector right-side panel slides in.
    5. Verifies component registry displays details: "Quote Amount" rendered with currency badge (`$2,500.50`), "Scheduled Date" rendered with calendar badge ("Jul 15, 2026"), and "Urgency Rating" shows colored warning tag ("high").
    6. Operator toggles lead status.

- **Test 4.2: Malicious Multi-Tenant Breach Spoofing**
  - **Objective**: Simulate a malicious operator trying to force a context hijack or request resource leakage.
  - **Action/Steps**:
    1. Operator logs in as Tenant A.
    2. Operator executes a script or forces client routing query injection: `/leads?tenant_id=e4c07384-e224-49cd-b6e7-90be00e22222` (Tenant B's UUID).
    3. Intercept `apiClient` call: `apiClient` must reject using URL-injected parameters or cross-check it against the authenticated tenant context stored in the application's root state provider.
    4. If the client attempts to forge the header `x-tenant-id: e4c07384-e224-49cd-b6e7-90be00e22222` manually, the mock API server returns `403 Forbidden` since the authenticated operator token does not map to Tenant B.
    5. The dashboard UI catches the error and renders an "Access Denied / Forbidden" security warning banner in conformance with the Heritage styling.

---

## 4. Heritage Design System Compliance Checklist

Every component rendered by the registry must strictly conform to the Heritage Design tokens defined in `dashboard/DESIGN.md` and `dashboard/src/app/globals.css`. The E2E tests should verify styling via DOM and CSS computed assertions:

| Token Category | Token Target Value | E2E CSS Assertion Selector & Value |
|---|---|---|
| **Primary Color** | `#0F2537` / `#1A1C1E` | `color` of text headers (`h1, h2, h3`) / `background-color` of active buttons. |
| **Secondary Color**| `rgba(15, 37, 55, 0.65)` | `color` of secondary meta text (`.label-caps`). |
| **Tertiary Color** | `#00885F` (Planhat Emerald) | `color` or `background-color` of positive status indicators. |
| **Accent Color** | `#B8422E` (Boston Clay) | `color` or border highlight of interactive accents or hover states. |
| **Neutral Color** | `#FFFFFF` / `#F7F5F2` | `background-color` of main container body. |
| **Borders** | `rgba(15, 37, 55, 0.08)` | `border-color` of cards and list items. |
| **Border Radius sm**| `4px` | `border-radius` of small buttons/badges. |
| **Border Radius md**| `8px` | `border-radius` of cards and containers. |
| **Spacing sm** | `8px` | `padding` or `margin` offsets for small groupings. |
| **Spacing md** | `16px` | Grid gap and block spacing layout components. |
| **Typography Sans**| `"Public Sans", ...` | `font-family` of body text. |
| **Typography Data**| `"Space Grotesk", ...` | `font-family` of uppercase labels (`.label-caps`). |

---

## 5. Verification Method

Once implemented, the E2E infrastructure and tests can be run and verified using the following steps:

1. **Build and Run Test Runner**:
   ```bash
   cd dashboard
   npm run test:e2e
   ```
   This will spin up `mock-api.js` on port `8001` and Next.js on port `3000`, wait for their startup cycles, execute Playwright scripts, output the results, and automatically clean up all processes.

2. **Verify Process Cleanup**:
   After the tests complete (pass or fail), run the following command to ensure no orphan processes are lingering on ports `3000` or `8001`:
   ```bash
   lsof -i :3000
   lsof -i :8001
   ```
   *Expected result: No output (ports are free).*

3. **Validation of Malicious Payloads**:
   Inspecting test execution output logs should confirm that Test 2.4 and Test 2.5 successfully triggered sanitization assertions, reporting `0 script executions` and `0 prototype mutations`.
