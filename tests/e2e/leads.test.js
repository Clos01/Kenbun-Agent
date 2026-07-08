const test = require("node:test");
const assert = require("node:assert");

const FRONTEND_URL = "http://127.0.0.1:3005";
const BACKEND_URL = "http://127.0.0.1:8001";
const PROXY_URL = `${FRONTEND_URL}/api_proxy/api/backend/leads`;

// Tenant UUIDs matching mock-api.js
const TENANT_A_REAL_ESTATE = "4ba4e6b2-a42e-4b68-b789-f5383569c7ad";
const TENANT_B_LANDSCAPING = "2ef1a364-e81c-4b65-bd29-c88349282fed";
const TENANT_C_MALICIOUS = "8c7f9382-749e-4c72-9cf0-e1837c73b28b";
const TENANT_D_EMPTY = "a6f02844-0b1a-45c1-90c7-2c1a85cd17e3";

// Reset the database state before each test to ensure test isolation
test.beforeEach(async () => {
  await fetch(`${BACKEND_URL}/api/backend/reset`, { method: "POST" });
});

// ----------------------------------------------------
// ACTIVE TESTS
// ----------------------------------------------------

test("Tenant isolation context routing", async (t) => {
  // Check Tenant A (Real Estate) through Next.js proxy
  const resA = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_A_REAL_ESTATE }
  });
  assert.strictEqual(resA.status, 200);
  const textA = await resA.text();
  assert.ok(textA.length > 0);
  const dataA = JSON.parse(textA);
  assert.ok(Array.isArray(dataA));
  assert.strictEqual(dataA.length, 2);
  assert.strictEqual(dataA[0].name, "Luxury Penthouse Acquisition");

  // Check Tenant B (Landscaping) through Next.js proxy
  const resB = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_B_LANDSCAPING }
  });
  assert.strictEqual(resB.status, 200);
  const textB = await resB.text();
  assert.ok(textB.length > 0);
  const dataB = JSON.parse(textB);
  assert.ok(Array.isArray(dataB));
  assert.strictEqual(dataB.length, 2);
  assert.strictEqual(dataB[0].name, "Residential Lawn Renewal");
});

test("Proxy query param routing", async (t) => {
  // Query through the Next.js API proxy using tenant_id query param
  const res = await fetch(`${PROXY_URL}?tenant_id=${TENANT_A_REAL_ESTATE}`);
  assert.strictEqual(res.status, 200);
  const text = await res.text();
  assert.ok(text.length > 0);
  const data = JSON.parse(text);
  assert.ok(Array.isArray(data));
  assert.strictEqual(data.length, 2);
  assert.strictEqual(data[0].name, "Luxury Penthouse Acquisition");
});

test("Switch tenant context", async (t) => {
  // Fetch Tenant A through Next.js proxy
  const resA = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_A_REAL_ESTATE }
  });
  assert.strictEqual(resA.status, 200);
  const textA = await resA.text();
  assert.ok(textA.length > 0);
  const dataA = JSON.parse(textA);
  assert.ok(Array.isArray(dataA));

  // Fetch Tenant B through Next.js proxy
  const resB = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_B_LANDSCAPING }
  });
  assert.strictEqual(resB.status, 200);
  const textB = await resB.text();
  assert.ok(textB.length > 0);
  const dataB = JSON.parse(textB);
  assert.ok(Array.isArray(dataB));

  // Assert separation
  assert.notDeepStrictEqual(dataA, dataB);
  assert.strictEqual(dataA[0].tenant_id, TENANT_A_REAL_ESTATE);
  assert.strictEqual(dataB[0].tenant_id, TENANT_B_LANDSCAPING);
});

test("Multi-tenant breach spoofing", async (t) => {
  // 1. Missing header and query parameter -> 400 Bad Request from proxy
  const resMissing = await fetch(PROXY_URL);
  assert.strictEqual(resMissing.status, 400);
  const textMissing = await resMissing.text();
  assert.ok(textMissing.length > 0);
  const errMissing = JSON.parse(textMissing);
  assert.ok(errMissing.error.includes("Missing x-tenant-id header"));

  // 2. Malformed tenant ID UUID -> 400 Bad Request from proxy
  const resMalformed = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": "invalid-uuid-format" }
  });
  assert.strictEqual(resMalformed.status, 400);
  const textMalformed = await resMalformed.text();
  assert.ok(textMalformed.length > 0);
  const errMalformed = JSON.parse(textMalformed);
  assert.ok(errMalformed.error.includes("Invalid x-tenant-id UUID format"));
});

test("Tier 2: Boundary/Corner - Empty state display", async (t) => {
  const res = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_D_EMPTY }
  });
  assert.strictEqual(res.status, 200);
  const text = await res.text();
  assert.ok(text.length > 0);
  const data = JSON.parse(text);
  assert.ok(Array.isArray(data));
  assert.strictEqual(data.length, 0);
});

test("Tier 2: Boundary/Corner - Layout overflow & large inputs", async (t) => {
  const largeName = "A".repeat(1000);
  const postRes = await fetch(PROXY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": TENANT_A_REAL_ESTATE
    },
    body: JSON.stringify({
      name: largeName,
      metadata: {
        budget: "$100,000",
        request_date: "2026-07-06",
        commercial: false
      }
    })
  });
  assert.strictEqual(postRes.status, 201);
  const newLead = await postRes.json();
  assert.strictEqual(newLead.name, largeName);
});

test("Tier 2: Boundary/Corner - Prototype Pollution protection check (Tenant C)", async (t) => {
  const res = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_C_MALICIOUS }
  });
  assert.strictEqual(res.status, 200);
  const data = await res.json();
  const rawLead = data[0];
  
  // Verify prototype is not polluted
  assert.strictEqual(Object.prototype.polluted, undefined);
  assert.strictEqual(({}).polluted, undefined);

  // Verify unknown / malicious properties are stripped from metadata
  assert.strictEqual(rawLead.metadata.isAdmin, undefined);
  assert.strictEqual(rawLead.metadata.delete_all_records, undefined);
  assert.strictEqual(rawLead.metadata.inject_script, undefined);
  assert.strictEqual(rawLead.metadata.onload_exploit, undefined);
});

test("Tier 4: Real-World Scenarios - Landscaping lead lifecycle", async (t) => {
  // 1. Get landscaping leads through proxy
  const getRes = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_B_LANDSCAPING }
  });
  const data = await getRes.json();
  assert.strictEqual(data.length, 2);
  
  const lawnRenewal = data.find(l => l.name === "Residential Lawn Renewal");
  assert.ok(lawnRenewal);
  assert.strictEqual(lawnRenewal.metadata.location, "Boston Suburbs");
  assert.deepStrictEqual(lawnRenewal.metadata.collections, ["residential", "sodding"]);

  // 2. Post a new landscaping lead through proxy
  const newLeadData = {
    name: "Estate Garden Renovation",
    metadata: {
      budget: "$8,500",
      request_date: "2026-07-09",
      commercial: false,
      location: "Newton Hills"
    }
  };
  const postRes = await fetch(PROXY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": TENANT_B_LANDSCAPING
    },
    body: JSON.stringify(newLeadData)
  });
  assert.strictEqual(postRes.status, 201);
  const createdLead = await postRes.json();
  assert.strictEqual(createdLead.name, "Estate Garden Renovation");
  assert.strictEqual(createdLead.tenant_id, TENANT_B_LANDSCAPING);

  // 3. Confirm persistence through proxy
  const checkRes = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_B_LANDSCAPING }
  });
  const finalData = await checkRes.json();
  assert.strictEqual(finalData.length, 3);
});

// ----------------------------------------------------
// VERIFICATION AND SECURITY COMPLIANCE TESTS
// ----------------------------------------------------

// MANDATORY INTEGRITY WARNING:
// DO NOT CHEAT. All implementations must be genuine. DO NOT
// hardcode test results, create dummy/facade implementations, or
// circumvent the intended task. A Forensic Auditor will independently
// verify your work. Integrity violations WILL be detected and your
// work WILL be rejected.

test("Component Registry renderers check", async (t) => {
  const res = await fetch(`${FRONTEND_URL}/leads`);
  assert.strictEqual(res.status, 200);
  const html = await res.text();

  // Ensure bento grid structure is present
  assert.ok(html.includes("grid-cols-1 md:grid-cols-3"));
  assert.ok(html.includes("Expected Budget"));
  assert.ok(html.includes("Requested On"));
  assert.ok(html.includes("Commercial Project"));
});

test("Metadata label mapping checks", async (t) => {
  const res = await fetch(`${FRONTEND_URL}/leads`);
  assert.strictEqual(res.status, 200);
  const html = await res.text();

  // Assert label mappings exist in the rendered page
  assert.ok(html.includes("Expected Budget"));
  assert.ok(html.includes("Requested On"));
  assert.ok(html.includes("Commercial Project"));
  assert.ok(html.includes("Target Location"));
  assert.ok(html.includes("Collections"));
});

test("Coercion validation check", async (t) => {
  const res = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": TENANT_B_LANDSCAPING }
  });
  assert.strictEqual(res.status, 200);
  const data = await res.json();

  const turfLead = data.find(l => l.name === "Commercial Office Park Turf");
  assert.ok(turfLead);
  // budget string / number coerced to number
  assert.strictEqual(typeof turfLead.metadata.budget, "number");
  assert.strictEqual(turfLead.metadata.budget, 15000);
  // commercial string "true" coerced to boolean true
  assert.strictEqual(typeof turfLead.metadata.commercial, "boolean");
  assert.strictEqual(turfLead.metadata.commercial, true);
});

test("XSS sanitization check", async (t) => {
  const xssPayload = {
    name: "<script>alert('XSS')</script> Safe Title",
    metadata: {
      budget: "$12,000",
      request_date: "2026-07-10",
      commercial: "1",
      location: "<img src=x onerror=alert(1)> Boston",
      collections: ["<iframe src=javascript:alert(1)>", "normal"]
    }
  };

  const postRes = await fetch(PROXY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": TENANT_A_REAL_ESTATE
    },
    body: JSON.stringify(xssPayload)
  });
  assert.strictEqual(postRes.status, 201);
  const createdLead = await postRes.json();

  // Verify that name and metadata properties are HTML escaped/sanitized
  assert.strictEqual(createdLead.name, "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;&#x2F;script&gt; Safe Title");
  assert.strictEqual(createdLead.metadata.location, "&lt;img src=x onerror=alert(1)&gt; Boston");
  assert.deepStrictEqual(createdLead.metadata.collections, ["&lt;iframe src=javascript:alert(1)&gt;", "normal"]);
  assert.strictEqual(createdLead.metadata.commercial, true);
  assert.strictEqual(createdLead.metadata.budget, 12000);
});

test("Heritage tokens verification", async (t) => {
  const res = await fetch(`${FRONTEND_URL}/leads`);
  assert.strictEqual(res.status, 200);
  const html = await res.text();

  // Verify CSS styles containing Heritage Design System tokens
  assert.ok(html.includes("text-tertiary"));
  assert.ok(html.includes("border-primary/5"));
  assert.ok(html.includes("bg-card"));
});

test("Milestone 2 Fix - Path traversal double-encoding bypass mitigation", async (t) => {
  // Test double-encoded path traversal
  const doubleEncodedUrl = `${FRONTEND_URL}/api_proxy/api/backend/%252e%252e%252fleads`;
  const resDouble = await fetch(doubleEncodedUrl, {
    headers: { "x-tenant-id": TENANT_A_REAL_ESTATE }
  });
  assert.strictEqual(resDouble.status, 403);
  const dataDouble = await resDouble.json();
  assert.strictEqual(dataDouble.error, "Forbidden: Path Traversal Detected");

  // Test backslash path traversal
  const backslashUrl = `${FRONTEND_URL}/api_proxy/api/backend/..%5cleads`;
  const resBackslash = await fetch(backslashUrl, {
    headers: { "x-tenant-id": TENANT_A_REAL_ESTATE }
  });
  assert.strictEqual(resBackslash.status, 403);
  const dataBackslash = await resBackslash.json();
  assert.strictEqual(dataBackslash.error, "Forbidden: Path Traversal Detected");
});

test("Milestone 2 Fix - Tenant ID validation on all proxy routes", async (t) => {
  // Test non-leads route (e.g. tools) without tenant ID
  const toolsUrl = `${FRONTEND_URL}/api_proxy/tools`;
  const resNoTenant = await fetch(toolsUrl);
  assert.strictEqual(resNoTenant.status, 400);
  const dataNoTenant = await resNoTenant.json();
  assert.strictEqual(dataNoTenant.error, "Bad Request: Missing x-tenant-id header");

  // Test non-leads route with invalid tenant ID format
  const resInvalidTenant = await fetch(toolsUrl, {
    headers: { "x-tenant-id": "invalid-uuid" }
  });
  assert.strictEqual(resInvalidTenant.status, 400);
  const dataInvalidTenant = await resInvalidTenant.json();
  assert.strictEqual(dataInvalidTenant.error, "Bad Request: Invalid x-tenant-id UUID format");

  // Test health route without tenant ID (must return 400 Bad Request, since health is not a bypass route)
  const healthUrl = `${FRONTEND_URL}/api_proxy/health`;
  const resNoTenantHealth = await fetch(healthUrl);
  assert.strictEqual(resNoTenantHealth.status, 400);
  const dataNoTenantHealth = await resNoTenantHealth.json();
  assert.strictEqual(dataNoTenantHealth.error, "Bad Request: Missing x-tenant-id header");

  // Test bypass route (e.g. api/v1/ping) without tenant ID
  const pingUrl = `${FRONTEND_URL}/api_proxy/api/v1/ping`;
  const resBypass = await fetch(pingUrl);
  assert.strictEqual(resBypass.status, 404); // Bypasses proxy validation (no 400) and hits mock backend (returns 404)
});
