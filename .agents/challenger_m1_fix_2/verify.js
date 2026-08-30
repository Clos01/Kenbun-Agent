const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

const FRONTEND_PORT = 3089;
const BACKEND_PORT = 8089;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

let backendProcess = null;
let frontendProcess = null;

function waitOn(url, timeoutMs = 20000) {
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

function cleanup() {
  console.log("🧹 Cleaning up verification server processes...");
  if (backendProcess) {
    try { backendProcess.kill("SIGTERM"); } catch (e) {}
  }
  if (frontendProcess) {
    try { frontendProcess.kill("SIGTERM"); } catch (e) {}
  }
}

async function main() {
  const rootDir = path.resolve(__dirname, "..", "..");
  const dashboardDir = path.join(rootDir, "dashboard");

  // Ensure ports are clear
  try {
    const execSync = require("child_process").execSync;
    try { execSync(`lsof -t -i :${BACKEND_PORT} | xargs kill -9`); } catch (e) {}
    try { execSync(`lsof -t -i :${FRONTEND_PORT} | xargs kill -9`); } catch (e) {}
  } catch (e) {}

  // Write a modified mock-api.js to change the port to 8089
  const mockApiContent = fs.readFileSync(path.join(rootDir, "scripts", "mock-api.js"), "utf8");
  const modifiedMockApiContent = mockApiContent.replace("const PORT = 8001;", `const PORT = ${BACKEND_PORT};`);
  const tempMockApiFile = path.join(__dirname, "temp-mock-api.js");
  fs.writeFileSync(tempMockApiFile, modifiedMockApiContent, "utf8");

  console.log(`🚀 Starting Mock API Server on port ${BACKEND_PORT}...`);
  backendProcess = spawn("node", [tempMockApiFile], { stdio: "ignore" });

  console.log(`🚀 Starting Next.js Production Server on port ${FRONTEND_PORT}...`);
  frontendProcess = spawn("npx", ["next", "start", "-p", String(FRONTEND_PORT)], {
    cwd: dashboardDir,
    env: {
      ...process.env,
      PORT: String(FRONTEND_PORT),
      INTERNAL_API_URL: BACKEND_URL
    },
    stdio: "ignore"
  });

  console.log("⌛ Waiting for servers to start...");
  await Promise.all([
    waitOn(`${BACKEND_URL}/api/health`),
    waitOn(FRONTEND_URL)
  ]);
  console.log("🟢 Servers are ready!");

  const results = [];

  // Case 1: Missing tenant ID on a data/leads endpoint
  try {
    const res = await fetch(`${FRONTEND_URL}/api_proxy/api/backend/leads`);
    const status = res.status;
    const body = await res.json();
    results.push({
      test: "Missing Tenant ID (leads endpoint)",
      expectedStatus: 400,
      actualStatus: status,
      body,
      passed: status === 400 && body.error.includes("Missing x-tenant-id header")
    });
  } catch (e) {
    results.push({ test: "Missing Tenant ID", error: e.message, passed: false });
  }

  // Case 2: Invalid tenant ID format
  try {
    const res = await fetch(`${FRONTEND_URL}/api_proxy/api/backend/leads`, {
      headers: { "x-tenant-id": "invalid-uuid-format" }
    });
    const status = res.status;
    const body = await res.json();
    results.push({
      test: "Invalid Tenant ID Format (leads endpoint)",
      expectedStatus: 400,
      actualStatus: status,
      body,
      passed: status === 400 && body.error.includes("Invalid x-tenant-id UUID format")
    });
  } catch (e) {
    results.push({ test: "Invalid Tenant ID Format", error: e.message, passed: false });
  }

  // Case 3: Valid tenant ID correctly forwarded
  try {
    const validUuid = "4ba4e6b2-a42e-4b68-b789-f5383569c7ad";
    const res = await fetch(`${FRONTEND_URL}/api_proxy/api/backend/leads`, {
      headers: { "x-tenant-id": validUuid }
    });
    const status = res.status;
    const body = await res.json();
    results.push({
      test: "Valid Tenant ID Forwarding",
      expectedStatus: 200,
      actualStatus: status,
      leadsCount: Array.isArray(body) ? body.length : null,
      passed: status === 200 && Array.isArray(body) && body.every(lead => lead.tenant_id === validUuid)
    });
  } catch (e) {
    results.push({ test: "Valid Tenant ID Forwarding", error: e.message, passed: false });
  }

  cleanup();
  
  // Clean up temp file
  try { fs.unlinkSync(tempMockApiFile); } catch (e) {}

  console.log("\n=== CHALLENGER VERIFICATION RESULTS ===");
  console.log(JSON.stringify(results, null, 2));

  const allPassed = results.every(r => r.passed);
  console.log(`\nOverall Result: ${allPassed ? "SUCCESS" : "FAILURE"}`);
  process.exit(allPassed ? 0 : 1);
}

main().catch(err => {
  console.error("Verification failed:", err);
  cleanup();
  process.exit(1);
});
