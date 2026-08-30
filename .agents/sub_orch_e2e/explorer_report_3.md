# E2E Testing Infrastructure & Test Suite Design Analysis
**Aura Lead OS Frontend Upgrade (CRG Backoffice SaaS)**
*Author: teamwork_preview_explorer (Instance 3)*
*Date: 2026-07-07T03:47:02Z*

---

## 1. Executive Summary

This report defines the End-to-End (E2E) testing architecture and test suite design for the **Aura Lead OS Frontend Upgrade**. The upgrade integrates multi-tenant context mechanisms, schema validation boundaries, and a normalized UI component registry conforming to the **Heritage Design System** style guidelines.

To ensure stability, security, and multi-tenant isolation (preventing cross-tenant data leakage), we design an **opaque-box E2E testing framework**. This framework executes automated assertions against a live-running system, mocking backend lead resources on a dedicated stub server while validating secure request propagation, payload filtering, and typography/aesthetic adherence.

---

## 2. Opaque-Box Test Runner Design (`scripts/run-e2e.js`)

The E2E test runner acts as an orchestrator that manages the lifecycle of the Next.js frontend server, the mock backend API stub, and the test suite runner, ensuring automatic resource cleanup upon completion or failure.

### 2.1 Runner Architecture & Process Flow
1. **Mock Server Spin-up**: Starts the Node.js Mock API Server on port `8001` (the default port targeted by the Next.js `api_proxy` as specified in `dashboard/src/app/api_proxy/[...slug]/route.ts`).
2. **Next.js Dashboard Spin-up**: Starts the Next.js development or production server on port `3005` (using the environment variable `PORT=3005`) to prevent port conflicts on the host system.
3. **Environment Injection**: Injects `INTERNAL_API_URL=http://127.0.0.1:8001` into the Next.js server environment so the proxy routes `/api_proxy/api/backend/leads` to the Mock Server.
4. **Liveness Probe (Health Checking)**: Pings both the mock server and the Next.js dashboard server (e.g. `/api/ping`) at `50ms` intervals with a timeout of `10` seconds, ensuring both processes are responsive before tests run.
5. **Execution**: Spawns the test runner process (e.g. Playwright or a lightweight native Node test suite using `node --test`).
6. **Orchestrated Teardown (Cleanup)**: Captures the test suite's exit code, kills the backend stub and Next.js server child processes using PGID (Process Group ID) signaling to prevent orphan zombie processes, and exits with the test suite's code.

### 2.2 Shell Integration (`dashboard/package.json`)
The script is integrated under `scripts` in the dashboard folder:
```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "eslint",
  "test:e2e": "node ../scripts/run-e2e.js"
}
```

### 2.3 Proposed Test Runner Script (`scripts/run-e2e.js`)
```javascript
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const FRONTEND_PORT = process.env.PORT || 3005;
const BACKEND_PORT = 8001;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

let frontendProcess = null;
let backendProcess = null;

// Helper to check server readiness
function waitOn(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const interval = setInterval(() => {
      if (Date.now() - start > timeoutMs) {
        clearInterval(interval);
        reject(new Error(`Timeout waiting for server at ${url}`));
        return;
      }
      http.get(url, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 400) {
          clearInterval(interval);
          resolve();
        }
      }).on("error", () => {
        // Suppress and wait
      });
    }, 100);
  });
}

async function main() {
  try {
    console.log("🚀 Starting E2E Mock API Server...");
    backendProcess = spawn("node", [path.resolve(__dirname, "mock-server.js")], {
      stdio: "inherit",
      detached: true
    });

    console.log("🚀 Starting Next.js Frontend...");
    frontendProcess = spawn("npm", ["run", "dev"], {
      cwd: path.resolve(__dirname, "../dashboard"),
      env: {
        ...process.env,
        PORT: FRONTEND_PORT,
        INTERNAL_API_URL: BACKEND_URL
      },
      stdio: "inherit",
      detached: true
    });

    console.log("⌛ Waiting for services to become healthy...");
    await Promise.all([
      waitOn(`${BACKEND_URL}/health`),
      waitOn(`${FRONTEND_URL}/api/ping`)
    ]);
    console.log("🟢 All services online. Running E2E Test Suite...");

    const testRunner = spawn("npx", ["playwright", "test"], {
      cwd: path.resolve(__dirname, "../dashboard"),
      env: { ...process.env, E2E_BASE_URL: FRONTEND_URL },
      stdio: "inherit"
    });

    testRunner.on("close", (code) => {
      cleanup(code);
    });

  } catch (error) {
    console.error("❌ E2E Runner Setup Failed:", error.message);
    cleanup(1);
  }
}

function cleanup(exitCode) {
  console.log("🧹 Tearing down E2E server processes...");
  
  if (backendProcess) {
    try {
      process.kill(-backendProcess.pid, "SIGTERM");
    } catch (e) {}
  }
  if (frontendProcess) {
    try {
      process.kill(-frontendProcess.pid, "SIGTERM");
    } catch (e) {}
  }
  
  process.exit(exitCode);
}

// Handle termination signals
process.on("SIGINT", () => cleanup(130));
process.on("SIGTERM", () => cleanup(143));

main();
```

---

## 3. Mock Server / API Stub Design

The mock server acts as the backend instance of the CRG Backoffice, intercepting API requests, isolating responses based on headers, and exposing security boundary vulnerabilities (such as custom malicious payloads) to test the frontend's sanitation layer.

### 3.1 Tenant Verification & Isolation Rules
- **Header Required**: Every request to `/api/backend/leads` must contain the `x-tenant-id` header.
- **UUID Schema Enforcement**: The `x-tenant-id` must conform to the standard UUIDv4 regex: `/^[0-9a-f]{8}-[0-9a-f]{4}-[40-9a-f]{3}-[89ab0-9a-f]{3}-[0-9a-f]{12}$/i`.
- **Response Matrix**:
  - Valid UUID with leads: Returns `200 OK` with JSON array.
  - Valid UUID with no leads: Returns `200 OK` with empty array `[]`.
  - Malformed UUID format: Returns `400 Bad Request` with an explicit JSON error.
  - Missing header: Returns `401 Unauthorized`.
  - Non-existent tenant lookup: Returns `200 OK` with empty array `[]` (prevents enumerative leaks).

### 3.2 Security Validation & Payload Models
To test the frontend's boundary scrubbing (Zod validation in `MetadataSchema`), the mock server must serve different styles of payloads:

1. **Standard Lead (Tenant A)**:
   - Valid metadata components (`budget`, `request_date`, `commercial`).
2. **Exploit Injection Lead (Tenant A)**:
   - Contains malicious/privileged attributes inside `metadata` (`isAdmin: true`, `delete_all_records: "DROP TABLE"`) and Prototype Pollution properties (`__proto__: { "polluted": true }`). The E2E tests will verify these keys are stripped and not rendered in the frontend's DOM.
3. **Coercion Edge Lead (Tenant B)**:
   - Contains raw representations (e.g. `budget: 5000` as a number, `commercial: "true"` as a string) to test that the Zod schema coerces them safely to the standard string/boolean structures before transformation.

### 3.3 Proposed Mock Server (`scripts/mock-server.js`)
```javascript
const http = require("http");
const url = require("url");

const PORT = 8001;
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

// Mock database partitioned by tenant_id
const mockLeads = {
  // Tenant A: Landscaping LLC (Valid UUIDv4)
  "4ba4e6b2-a42e-4b68-b789-f5383569c7ad": [
    {
      id: "90a9b836-e82a-4a6c-b3a1-2d7c5b61e27a",
      name: "Residential Lawn Renewal",
      tenant_id: "4ba4e6b2-a42e-4b68-b789-f5383569c7ad",
      metadata: {
        budget: "$4,200",
        request_date: "2026-07-06",
        commercial: false,
        location: "Boston Suburbs",
        collections: ["residential", "sodding"]
      }
    },
    {
      id: "5c80efc2-7ba4-4fe1-ba76-d1883be71e29",
      name: "Industrial Turf Exploit Attempt",
      tenant_id: "4ba4e6b2-a42e-4b68-b789-f5383569c7ad",
      metadata: {
        budget: "$45,000",
        request_date: "2026-07-07",
        commercial: true,
        location: "Corporate HQ",
        // Malicious keys & injection attempts
        isAdmin: true, 
        delete_all_records: "DROP TABLE leads;",
        "__proto__": { "pollute": "compromised" },
        "inject_script": "<script>alert('XSS')</script>"
      }
    }
  ],
  // Tenant B: CleanCorp Services (Valid UUIDv4)
  "2ef1a364-e81c-4b65-bd29-c88349282fed": [
    {
      id: "8c7f9382-749e-4c72-9cf0-e1837c73b28b",
      name: "Commercial Office Janitorial",
      tenant_id: "2ef1a364-e81c-4b65-bd29-c88349282fed",
      metadata: {
        budget: 1500, // Intended coercion testing (number to formatted string)
        request_date: "2026-07-08",
        commercial: "true", // Intended coercion testing (string to boolean)
        recurring: "weekly"
      }
    }
  ]
};

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;

  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "x-tenant-id, Content-Type, Authorization");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // Health endpoint for liveness checking
  if (pathname === "/health" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "healthy" }));
    return;
  }

  // Leads endpoint
  if (pathname === "/api/backend/leads") {
    const tenantId = req.headers["x-tenant-id"] || parsedUrl.query.tenant_id;

    if (!tenantId) {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Unauthorized: Missing x-tenant-id header" }));
      return;
    }

    if (!UUID_REGEX.test(tenantId)) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Bad Request: Invalid UUID tenant context" }));
      return;
    }

    if (req.method === "GET") {
      const responseData = mockLeads[tenantId] || [];
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(responseData));
      return;
    }

    if (req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => { body += chunk; });
      req.on("end", () => {
        try {
          const newLead = JSON.parse(body);
          // Auto-inject tenant context into mock database record
          newLead.id = require("crypto").randomUUID();
          newLead.tenant_id = tenantId;
          
          if (!mockLeads[tenantId]) {
            mockLeads[tenantId] = [];
          }
          mockLeads[tenantId].push(newLead);
          
          res.writeHead(201, { "Content-Type": "application/json" });
          res.end(JSON.stringify(newLead));
        } catch (err) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "Bad Request: Malformed payload JSON" }));
        }
      });
      return;
    }
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not Found" }));
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`🟢 Mock Server listening on http://127.0.0.1:${PORT}`);
});
```

---

## 4. Feature Inventory & E2E Test Suite Design

The E2E Test Suite is structured into 4 logical tiers, testing components progressively from fundamental functionality to complex real-world workloads and security failure scenarios.

### 4.1 Feature Inventory
1. **Tenant Context (`TenantContext` & `useTenant`)**: Evaluates global React Context bindings.
2. **Secure Client Fetching (`apiClient`)**: Monitors header insertion and cross-tenant network isolation.
3. **Boundary Schema Sanitizer (`MetadataSchema`)**: Inspects validation, error states, and stripping rules.
4. **Metadata Normalization (`MetadataTransformer`)**: Validates logical ordering and mapping of labels.
5. **Component Registry rendering**: Checks rendering visual component mappings (dates, currency, booleans).

---

### 4.2 Test Suite Matrix (Tiers 1-4)

#### Tier 1: Feature Coverage (>= 5 cases per feature)
*Goal: Ensure baseline functionality is covered.*

*   **Tenant Context**
    1. Verify context initializes without throwing if a valid UUID is provided.
    2. Confirm standard UI components display the tenant workspace name based on context.
    3. Assert context changes when selecting an alternate workspace from the sidebar list.
    4. Assert context is stored in memory and doesn't pollute local storage keys (privacy compliance).
    5. Verify UI displays a descriptive "No Active Workspace" card if the context is uninitialized.
*   **Secure API client**
    1. Verify `apiClient` includes the `x-tenant-id` header on standard API requests.
    2. Confirm requests include a valid header key-value structure under `headers: { 'x-tenant-id': '...' }`.
    3. Verify that requests fail on client side if the API client detects an invalid UUID format.
    4. Ensure the client does not send the tenant context to external API endpoints.
    5. Verify that token refreshing logic preserves the active `x-tenant-id` context parameter.
*   **Boundary Schema Sanitizer**
    1. Verify normal metadata objects pass validation without modifications.
    2. Ensure validation handles a clean empty object `{}` gracefully.
    3. Confirm nested elements conforming to the structure are validated successfully.
    4. Verify malformed structures (e.g. array instead of object) are rejected.
    5. Ensure validation errors do not crash the React component tree (handled via error boundary).
*   **Metadata Normalization**
    1. Verify mapping `request_date` returns "Request Date" as a label in the lead inspector.
    2. Verify key ordering matches: `budget` first, `request_date` second, and `commercial` third.
    3. Confirm optional attributes are skipped entirely instead of rendering empty placeholders.
    4. Verify custom list values (like `collections`) render as discrete badges.
    5. Confirm safe but unlisted keys are compiled at the end in an "Additional Info" group.
*   **Component Registry**
    1. Verify that `budget: "$4,200"` triggers the rendering of the custom Currency element.
    2. Confirm `request_date` metadata renders with the Date element incorporating a Calendar icon.
    3. Assert `commercial` boolean metadata renders as an styled Yes/No Toggle or Badge.
    4. Ensure long descriptions render inside a readable text block.
    5. Verify standard text elements use the default string component.

#### Tier 2: Boundary & Corner Cases (>= 5 cases per feature)
*Goal: Verify error handling, negative validations, and adversarial inputs.*

*   **Tenant Context Boundaries**
    1. Request data with a missing `x-tenant-id` header; confirm client UI blocks view with an Authorization Error boundary.
    2. Pass an invalid tenant format (e.g., `4ba4e6b2-a42e`) and assert that the client validation layer cancels the query.
    3. Inject SQL queries in the workspace selector (e.g. `' OR '1'='1`) and ensure client filters parameters.
    4. Test cross-tenant hijack: manually inject tenant ID B in query params while context is tenant A, verifying client-side client ignores query parameters and enforces context-level header.
    5. Ensure Unicode and special characters injected in tenant headers are encoded safely (prevents header injection).
*   **Sanitization Boundaries (Malicious Payload Injection)**
    1. Confirm that `isAdmin: true` is stripped and is not present in the rendered HTML.
    2. Confirm that SQL phrases (e.g. `DROP TABLE leads`) inside metadata text are sanitized.
    3. Confirm that Prototype Pollution keys (like `__proto__` and `constructor`) are dropped during schema parsing.
    4. Assert that XSS tags (e.g. `<script>alert(1)</script>`) are escaped and do not execute.
    5. Verify that huge strings (e.g. >10,000 characters) are rejected or truncated by the validator.
*   **Data Transformation Boundaries**
    1. Pass cyclic references and verify the transformer escapes without causing browser stack overflow.
    2. Supply completely corrupted metadata (such as binary text) and confirm it defaults to an empty layout.
    3. Verify duplicate metadata keys are merged safely or filtered according to schema specifications.
    4. Confirm that numerical float values (e.g., `NaN`, `Infinity`) default to a safe fallback (e.g. `$--`).
    5. Confirm that injected inline styling or Tailwind classes are neutralized before binding to the layout.
*   **Registry Boundaries**
    1. Input extreme currencies (e.g., `$999,999,999` and negative numbers) and verify proper layout container behavior.
    2. Verify invalid date arguments (e.g., `2026-02-30`, `null`) render placeholder text rather than crashing.
    3. Verify boolean coercion for inputs like `"yes"`, `1`, or `true` maps to correct true states.
    4. Assert that failed component assets activate local component fallback strategies without breaking layout.
    5. Render lists with 200+ metadata fields to ensure performance meets frame-rate constraints.

#### Tier 3: Cross-Feature Combinations
*Goal: Test integration flow between context, client, validation, mapping, and components.*

1. **Successful Pipeline Cycle**: Select Tenant A -> Load Leads -> Sanitize -> Transform Metadata -> Render Currency & Date elements in the Kanban view with Heritage styling.
2. **Tenant Transition Reflushing**: Swap active workspace from Tenant A to Tenant B. Confirm Tenant A's cached state is instantly flushed, and Tenant B's leads are loaded, validated, and displayed with distinct metadata schemas.
3. **Partial Exploit Scrapping**: Load a lead containing normal records (`budget`) alongside invalid records (`isAdmin`). Verify Zod cleanses the exploit, the registry displays the budget with the Heritage colors, and the exploit is completely blocked from entering the DOM.
4. **Race Condition Prevention**: Trigger parallel requests under Tenant A and Tenant B. Assert that the client-side fetches isolate responses without leaking Tenant A data into Tenant B's active layout.
5. **Empty State Component Path**: Trigger lookup for Tenant C with zero leads. Verify the network client completes, metadata registry maps an empty list configuration, and the UI displays an empty board conforming to visual spacing tokens.

#### Tier 4: Real-World Scenarios
*Goal: E2E scenario workflows testing true user behavior.*

1. **The Landscaping Lead (Residential Workflow)**:
   - Select workspace "Landscaping LLC" (`4ba4e6b2-a42e-4b68-b789-f5383569c7ad`).
   - Query leads. Assert page loads "Residential Lawn Renewal" card.
   - Click card to open sidebar details.
   - Assert "Budget" is displayed as `$4,200` with the custom Currency component (rendered in bold green text).
   - Assert "Request Date" is formatted as `2026-07-06` alongside the calendar icon.
   - Assert "Commercial" is rendered as a light grey "Residential" badge (neutral tone).
   - Assert "Collections" tags render as separate pills: "residential", "sodding".
   - Confirm all text styles inherit the **Public Sans** font family.
2. **The Landscaping Lead (Exploit Remediation Workflow)**:
   - Select workspace "Landscaping LLC".
   - Click "Industrial Turf Exploit Attempt" card.
   - Verify sidebar details panel renders the budget `$45,000` and the location `Corporate HQ`.
   - Perform DOM assertions: verify that `isAdmin`, `delete_all_records`, `__proto__`, and `inject_script` tags are completely absent from the page HTML.
   - Verify no javascript alerts are triggered during the lead load cycle.
3. **The Multi-Tenant Workspace Swap Scenario**:
   - Log in. Select "Landscaping LLC" -> Verify 2 leads display.
   - Click workspace dropdown -> Switch to "CleanCorp Services" (`2ef1a364-e81c-4b65-bd29-c88349282fed`).
   - Verify active leads count becomes 1 ("Commercial Office Janitorial").
   - Click lead -> Assert budget `1500` is parsed and formatted as `$1,500.00`.
   - Assert "Commercial" is rendered as a green "Commercial" badge (coerced from `"true"`).
   - Verify no leftover context or tokens from Landscaping LLC remain in client state.

---

## 5. Heritage Design System Conformance & Audit

A critical part of E2E verification is ensuring visual compliance with the Heritage Design System. E2E tests should systematically audit styling elements to prevent "AI-Slop" layouts from leaking into production.

### 5.1 Token Specifications (`dashboard/DESIGN.md` vs `globals.css`)
There is a current mismatch between the layout specification in `dashboard/DESIGN.md` and the active code variables inside `dashboard/src/app/globals.css`.

| Token Category | DESIGN.md Specification | globals.css Implementation | Reconciled Solution for M4 Upgrade |
|---|---|---|---|
| **Primary Color** | `#1A1C1E` (Limestone Charcoal) | `#0F2537` (Midnight Oceanic Blue) | Use `--primary: #1A1C1E` |
| **Secondary Color**| `#6C7278` (Slate Gray) | `rgba(15, 37, 55, 0.65)` | Use `--secondary: #6C7278` |
| **Tertiary Color** | `#B8422E` (Boston Clay) | `#00885F` (Planhat Emerald) | Use `--tertiary: #B8422E` |
| **Neutral Color**  | `#F7F5F2` (Matte Limestone) | `#FFFFFF` (Pure white backdrop) | Use `--neutral: #F7F5F2` |
| **Accent Color**   | (Inherit from Tertiary) | `#B8422E` (Boston Clay) | Standardize accent variable to `--accent` |
| **Border Radius**  | `sm: 4px`, `md: 8px` | `sm: 4px`, `md: 8px` | Match values exactly |
| **Spacing**        | `sm: 8px`, `md: 16px` | `sm: 8px`, `md: 16px` | Match values exactly |

To ensure conformance in the M4 milestone, components should use CSS classes derived from the reconciled Heritage theme variables, ensuring the background is mapped to `--neutral` (`#F7F5F2`), text and headings to `--primary` (`#1A1C1E`), and interactive items to `--tertiary` (`#B8422E`).

### 5.2 Programmatic Verification in E2E Tests
To automate this audit, the Playwright tests must run script evaluations verifying computed CSS values of key layout components:

```javascript
// Example Playwright test snippet verifying Heritage tokens
test("Verify Heritage Design System Token Conformance", async ({ page }) => {
  await page.goto("/board");

  // 1. Verify Neutral Background color
  const bodyBg = await page.evaluate(() => 
    window.getComputedStyle(document.body).backgroundColor
  );
  // Hex #F7F5F2 translates to RGB rgb(247, 245, 242)
  expect(bodyBg).toBe("rgb(247, 245, 242)");

  // 2. Verify Primary Typography Font and Color
  const heading = page.locator("h1").first();
  const headingFont = await heading.evaluate(el => window.getComputedStyle(el).fontFamily);
  const headingColor = await heading.evaluate(el => window.getComputedStyle(el).color);
  expect(headingFont).toContain("Public Sans");
  expect(headingColor).toBe("rgb(26, 28, 30)"); // Hex #1A1C1E

  // 3. Verify Card Border Radius md (8px)
  const leadCard = page.locator("[data-testid='lead-card']").first();
  const borderRadius = await leadCard.evaluate(el => window.getComputedStyle(el).borderRadius);
  expect(borderRadius).toBe("8px");

  // 4. Verify Spacing and padding alignment (multiples of 8px grid)
  const paddingLeft = await leadCard.evaluate(el => parseInt(window.getComputedStyle(el).paddingLeft));
  expect(paddingLeft % 8).toBe(0); // Verifies compliance with 8px linear grid layout

  // 5. Anti-Slop Audit: Confirm NO flat generic white backgrounds for panels
  const detailPanel = page.locator("[data-testid='details-panel']");
  if (await detailPanel.isVisible()) {
    const panelBg = await detailPanel.evaluate(el => window.getComputedStyle(el).backgroundColor);
    expect(panelBg).not.toBe("rgb(255, 255, 255)"); // Reject generic white background
  }
});
```

Using these checks ensures that any UI code that deviates from the design system tokens is automatically caught and blocked before deployment.
