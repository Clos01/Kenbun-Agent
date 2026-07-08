const http = require("http");
const { spawn } = require("child_process");
const path = require("path");
const assert = require("assert");

const FRONTEND_PORT = 3005;
const BACKEND_PORT = 8001;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const PROXY_URL = `${FRONTEND_URL}/api_proxy/api/backend/leads`;

const TENANT_A = "4ba4e6b2-a42e-4b68-b789-f5383569c7ad";

function waitOn(url, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const interval = setInterval(() => {
      if (Date.now() - start > timeoutMs) {
        clearInterval(interval);
        reject(new Error(`Timeout waiting for server at ${url}`));
        return;
      }
      const req = http.get(url, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 500) {
          clearInterval(interval);
          resolve();
        }
      });
      req.on("error", () => {});
      req.end();
    }, 250);
  });
}

async function main() {
  console.log("=== STARTING ADVERSARIAL STRESS TESTS ===");
  
  // 1. Ensure ports are clean
  try {
    const execSync = require("child_process").execSync;
    try { execSync("lsof -t -i :8001 | xargs kill -9"); } catch (e) {}
    try { execSync("lsof -t -i :3005 | xargs kill -9"); } catch (e) {}
  } catch (e) {}

  // 2. Spawn Mock API
  const rootDir = path.resolve(__dirname, "..");
  const backendProcess = spawn("node", [path.join(rootDir, "scripts", "mock-api.js")], {
    stdio: "inherit"
  });

  // 3. Spawn Next.js Frontend
  const frontendProcess = spawn("npx", ["next", "dev", "-p", String(FRONTEND_PORT)], {
    cwd: path.join(rootDir, "dashboard"),
    env: {
      ...process.env,
      PORT: String(FRONTEND_PORT),
      INTERNAL_API_URL: BACKEND_URL
    },
    stdio: "inherit"
  });

  // Cleanup handler
  const cleanup = () => {
    console.log("🧹 Tearing down test processes...");
    try { backendProcess.kill("SIGKILL"); } catch (e) {}
    try { frontendProcess.kill("SIGKILL"); } catch (e) {}
  };

  try {
    console.log("⌛ Waiting for services to respond...");
    await Promise.all([
      waitOn(`${BACKEND_URL}/api/health`),
      waitOn(FRONTEND_URL)
    ]);
    console.log("🟢 Services are online. Commencing tests...");

    // Test Suite
    await runAdversarialTests();
    
    console.log("🏆 ALL ADVERSARIAL CHALLENGES PASSED SUCCESSFULLY!");
    cleanup();
    process.exit(0);
  } catch (err) {
    console.error("❌ Test execution failed:", err);
    cleanup();
    process.exit(1);
  }
}

async function runAdversarialTests() {
  // Reset backend DB state
  await fetch(`${BACKEND_URL}/api/backend/reset`, { method: "POST" });

  // Challenge 1: SSRF / Path Traversal attempts
  console.log("\n--- Challenge 1: Proxy Route Blocklists & Path Traversal ---");
  
  // Traversal path using double URL-encoding (%252e%252e) to bypass next.js routing normalization
  const traversalRes = await fetch(`${FRONTEND_URL}/api_proxy/api/%252e%252e/unauthorized`, {
    headers: { "x-tenant-id": TENANT_A }
  });
  console.log(`Path Traversal (api/%252e%252e/unauthorized) status: ${traversalRes.status}`);
  // The path traversal must be blocked by the proxy and return 403 Forbidden
  assert.strictEqual(traversalRes.status, 403); 
  const traversalBody = await traversalRes.json();
  assert.strictEqual(traversalBody.error, "Forbidden: Path Traversal Detected");

  // Route not in allowlist
  const unauthorizedRes = await fetch(`${FRONTEND_URL}/api_proxy/unauthorized_endpoint`, {
    headers: { "x-tenant-id": TENANT_A }
  });
  console.log(`Unauthorized route status: ${unauthorizedRes.status}`);
  assert.strictEqual(unauthorizedRes.status, 403);
  const unauthorizedBody = await unauthorizedRes.json();
  assert.strictEqual(unauthorizedBody.error, "Forbidden: Unauthorized API Route");

  // Challenge 2: Malformed UUID validation
  console.log("\n--- Challenge 2: Malformed Tenant ID Validation ---");
  
  const badUuidRes = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": "4ba4e6b2-a42e-4b68-b789-f5383569c7ad; DROP TABLE leads;" }
  });
  console.log(`SQL Injection Tenant ID status: ${badUuidRes.status}`);
  assert.strictEqual(badUuidRes.status, 400);

  const hexBypassRes = await fetch(PROXY_URL, {
    headers: { "x-tenant-id": "%34ba4e6b2-a42e-4b68-b789-f5383569c7ad" }
  });
  console.log(`URL Encoded Tenant ID status: ${hexBypassRes.status}`);
  assert.strictEqual(hexBypassRes.status, 400);

  // Challenge 3: Payload validation - stripping malicious properties
  console.log("\n--- Challenge 3: Stripping Malicious Payload Keys ---");
  
  const maliciousPayload = {
    name: "Regular Lead",
    isAdmin: true,
    delete_all_records: "DROP TABLE users;",
    extra_unknown_key: "some_data",
    metadata: {
      budget: "$5,000",
      request_date: "2026-07-07",
      commercial: false,
      isAdmin: "yes",
      "__proto__": {
        "polluted": "yes"
      }
    }
  };

  const postRes = await fetch(PROXY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": TENANT_A
    },
    body: JSON.stringify(maliciousPayload)
  });
  
  assert.strictEqual(postRes.status, 201);
  const responseData = await postRes.json();
  console.log("Response data:", JSON.stringify(responseData, null, 2));

  // Assert top level fields stripped
  assert.strictEqual(responseData.isAdmin, undefined);
  assert.strictEqual(responseData.delete_all_records, undefined);
  assert.strictEqual(responseData.extra_unknown_key, undefined);
  // Assert metadata fields stripped
  assert.strictEqual(responseData.metadata.isAdmin, undefined);
  assert.strictEqual(Object.prototype.hasOwnProperty.call(responseData.metadata, "__proto__"), false);
  assert.strictEqual(({}).polluted, undefined); // Prototype not polluted
  
  // Challenge 4: XSS HTML escaping
  console.log("\n--- Challenge 4: XSS HTML Escaping ---");
  const xssPayload = {
    name: "<script>alert('XSS')</script> Lead Name",
    metadata: {
      budget: 1000,
      request_date: "2026-07-07",
      commercial: true,
      location: "<img src=x onerror=alert('location')>",
      collections: ["<svg onload=alert(1)>", "normal-tag"]
    }
  };

  const xssPostRes = await fetch(PROXY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": TENANT_A
    },
    body: JSON.stringify(xssPayload)
  });

  assert.strictEqual(xssPostRes.status, 201);
  const xssData = await xssPostRes.json();
  console.log("XSS Sanitized Response Data:", JSON.stringify(xssData, null, 2));

  assert.strictEqual(xssData.name, "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;&#x2F;script&gt; Lead Name");
  assert.strictEqual(xssData.metadata.location, "&lt;img src=x onerror=alert(&#x27;location&#x27;)&gt;");
  assert.deepStrictEqual(xssData.metadata.collections, ["&lt;svg onload=alert(1)&gt;", "normal-tag"]);

  // Challenge 5: Coercion edge cases
  console.log("\n--- Challenge 5: Coercion Robustness ---");
  
  const coercionPayload = {
    name: "Coercion Test Lead",
    metadata: {
      budget: "  $  10,230.50  ", // Weird spaces, commas, signs
      request_date: "2026-07-07",
      commercial: "1", // string representation of 1 (true)
    }
  };

  const coercionRes = await fetch(PROXY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": TENANT_A
    },
    body: JSON.stringify(coercionPayload)
  });

  assert.strictEqual(coercionRes.status, 201);
  const coercionData = await coercionRes.json();
  console.log("Coercion Response Data:", JSON.stringify(coercionData, null, 2));
  assert.strictEqual(coercionData.metadata.budget, 10230.5);
  assert.strictEqual(coercionData.metadata.commercial, true);

  // Weirder coercion cases
  const weirdCoercionPayload = {
    name: "Weirder Coercion Test Lead",
    metadata: {
      budget: "not a number at all", 
      request_date: "2026-07-07",
      commercial: "TRUE", // uppercase string true
    }
  };

  const weirdCoercionRes = await fetch(PROXY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": TENANT_A
    },
    body: JSON.stringify(weirdCoercionPayload)
  });

  assert.strictEqual(weirdCoercionRes.status, 201);
  const weirdCoercionData = await weirdCoercionRes.json();
  console.log("Weird Coercion Response Data:", JSON.stringify(weirdCoercionData, null, 2));
  assert.strictEqual(weirdCoercionData.metadata.budget, 0); // fallback is 0
  assert.strictEqual(weirdCoercionData.metadata.commercial, true);

  // Challenge 6: Invalid payloads (Bad date format)
  console.log("\n--- Challenge 6: Invalid Payloads Rejecting ---");
  
  const badDatePayload = {
    name: "Bad Date Lead",
    metadata: {
      budget: 100,
      request_date: "07-07-2026", // Incorrect date format (not YYYY-MM-DD)
      commercial: false
    }
  };

  const badDateRes = await fetch(PROXY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-tenant-id": TENANT_A
    },
    body: JSON.stringify(badDatePayload)
  });
  console.log(`Bad Date Response Status: ${badDateRes.status}`);
  assert.strictEqual(badDateRes.status, 400);
}

main();
