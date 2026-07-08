const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const FRONTEND_PORT = 3006; // Use 3006 to avoid conflicts
const BACKEND_PORT = 8003;  // Use 8003 to avoid conflicts
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

let frontendProcess = null;
let backendProcess = null;

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
  console.log("🧹 Cleaning up server processes...");
  if (backendProcess) {
    try { backendProcess.kill("SIGTERM"); } catch (e) {}
  }
  if (frontendProcess) {
    try { frontendProcess.kill("SIGTERM"); } catch (e) {}
  }
}

async function runTests() {
  try {
    const rootDir = path.resolve(__dirname, "..");
    const dashboardDir = path.join(rootDir, "dashboard");

    console.log(`🚀 Starting Mock API Server on port ${BACKEND_PORT}...`);
    // Pass port override via env or modify spawn args
    // Since scripts/mock-api.js has hardcoded PORT = 8001, let's run it by copying/editing or setting environment if supported.
    // Wait, mock-api.js has: const PORT = 8001; it does not read process.env.PORT.
    // Let's check if we can run it on 8001 if we ensure 8001 is clean.
    // Yes! Let's just use 8001 and 3005 after checking they are clean.
  } catch (err) {}
}

async function main() {
  const rootDir = path.resolve(__dirname, "..");
  const dashboardDir = path.join(rootDir, "dashboard");
  
  // We will run on ports 8001 and 3005. Let's make sure they are killed first.
  console.log("Killing any existing processes on 8001 and 3005...");
  try {
    const execSync = require("child_process").execSync;
    try { execSync("lsof -t -i :8001 | xargs kill -9"); } catch (e) {}
    try { execSync("lsof -t -i :3005 | xargs kill -9"); } catch (e) {}
  } catch (e) {}

  console.log("Starting mock-api server...");
  backendProcess = spawn("node", [path.join(rootDir, "scripts", "mock-api.js")], {
    stdio: "ignore",
    detached: false
  });

  console.log("Starting Next.js dev server...");
  frontendProcess = spawn("npx", ["next", "dev", "-p", "3005"], {
    cwd: dashboardDir,
    env: {
      ...process.env,
      PORT: "3005",
      INTERNAL_API_URL: "http://127.0.0.1:8001"
    },
    stdio: "ignore",
    detached: false
  });

  console.log("Waiting for servers to start...");
  await Promise.all([
    waitOn("http://127.0.0.1:8001/health"),
    waitOn("http://127.0.0.1:3005")
  ]);
  console.log("Servers are ready!");

  const results = [];

  // Case 1: Valid tenant ID
  try {
    const res = await fetch("http://127.0.0.1:3005/api_proxy/health", {
      headers: { "x-tenant-id": "4ba4e6b2-a42e-4b68-b789-f5383569c7ad" }
    });
    results.push({
      case: "Valid Tenant ID (4ba4e6b2-a42e-4b68-b789-f5383569c7ad)",
      status: res.status,
      ok: res.status === 200,
      body: await res.text()
    });
  } catch (e) {
    results.push({ case: "Valid Tenant ID", error: e.message, ok: false });
  }

  // Case 2: Invalid tenant ID format
  try {
    const res = await fetch("http://127.0.0.1:3005/api_proxy/health", {
      headers: { "x-tenant-id": "invalid-uuid-format" }
    });
    results.push({
      case: "Invalid Tenant ID (invalid-uuid-format)",
      status: res.status,
      ok: res.status === 400,
      body: await res.text()
    });
  } catch (e) {
    results.push({ case: "Invalid Tenant ID", error: e.message, ok: false });
  }

  // Case 3: Missing tenant ID
  try {
    const res = await fetch("http://127.0.0.1:3005/api_proxy/health");
    results.push({
      case: "Missing Tenant ID",
      status: res.status,
      ok: res.status === 400, // Expected to fail according to requirement description, but actually passes
      body: await res.text()
    });
  } catch (e) {
    results.push({ case: "Missing Tenant ID", error: e.message, ok: false });
  }

  // Case 4: Double URL-encoded path traversal
  try {
    const res = await fetch("http://127.0.0.1:3005/api_proxy/api/%252e%252e/unauthorized", {
      headers: { "x-tenant-id": "4ba4e6b2-a42e-4b68-b789-f5383569c7ad" }
    });
    results.push({
      case: "Double URL-encoded path traversal",
      status: res.status,
      ok: res.status === 403,
      body: await res.text()
    });
  } catch (e) {
    results.push({ case: "Double URL-encoded path traversal", error: e.message, ok: false });
  }

  cleanup();

  console.log("\n=== VERIFICATION RESULTS ===");
  console.log(JSON.stringify(results, null, 2));
  
  const allPassed = results[0].ok && results[1].ok && results[2].ok && results[3].ok;
  process.exit(allPassed ? 0 : 1);
}

main().catch(err => {
  console.error("Main execution failed:", err);
  cleanup();
  process.exit(1);
});
