const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");
const net = require("net");

const FRONTEND_PORT = 3005;
const BACKEND_PORT = 8001;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

function checkPort(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", (err) => {
      if (err.code === "EADDRINUSE") {
        resolve(true);
      } else {
        resolve(false);
      }
    });
    server.once("listening", () => {
      server.close(() => {
        resolve(false);
      });
    });
    server.listen(port, "127.0.0.1");
  });
}

let frontendProcess = null;
let backendProcess = null;
let isExiting = false;

function waitOn(url, timeoutMs = 120000) {
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
      req.on("error", () => {
        // Suppress error and wait
      });
      req.end();
    }, 250);
  });
}

function findTestFiles(dir) {
  let results = [];
  if (!fs.existsSync(dir)) return results;
  const list = fs.readdirSync(dir);
  list.forEach((file) => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    if (stat && stat.isDirectory()) {
      results = results.concat(findTestFiles(filePath));
    } else if (file.endsWith(".test.js")) {
      results.push(filePath);
    }
  });
  return results;
}

function cleanup(exitCode) {
  if (isExiting) return;
  isExiting = true;
  console.log("\n🧹 Tearing down E2E server processes...");

  if (backendProcess) {
    try {
      console.log(`Killing Mock Server (PID: ${backendProcess.pid})...`);
      process.kill(-backendProcess.pid, "SIGTERM");
    } catch (e) {
      try {
        backendProcess.kill("SIGTERM");
      } catch (err) {}
    }
  }

  if (frontendProcess) {
    try {
      console.log(`Killing Next.js Frontend (PID: ${frontendProcess.pid})...`);
      process.kill(-frontendProcess.pid, "SIGTERM");
    } catch (e) {
      try {
        frontendProcess.kill("SIGTERM");
      } catch (err) {}
    }
  }

  console.log(`Exit with code: ${exitCode}`);
  process.exit(exitCode);
}

process.on("SIGINT", () => cleanup(130));
process.on("SIGTERM", () => cleanup(143));
process.on("exit", () => cleanup(0));

async function main() {
  try {
    const rootDir = path.resolve(__dirname, "..");
    const dashboardDir = path.join(rootDir, "dashboard");

    // Check if ports are already in use
    const backendInUse = await checkPort(BACKEND_PORT);
    const frontendInUse = await checkPort(FRONTEND_PORT);
    if (backendInUse || frontendInUse) {
      if (backendInUse) {
        console.warn(`⚠️ Port ${BACKEND_PORT} may be in TIME_WAIT or in use.`);
      }
      if (frontendInUse) {
        console.warn(`⚠️ Port ${FRONTEND_PORT} may be in TIME_WAIT or in use.`);
      }
    }

    let serversOnline = false;

    console.log("🚀 Starting E2E Mock API Server on port 8001...");
    backendProcess = spawn("node", [path.join(__dirname, "mock-api.js")], {
      stdio: "inherit",
      detached: true
    });

    backendProcess.on("exit", (code, signal) => {
      if (!serversOnline) {
        console.error(`❌ Mock API Server (backendProcess) exited early with code ${code} (signal: ${signal}) during startup.`);
        cleanup(1);
      }
    });

    backendProcess.on("error", (err) => {
      if (!serversOnline) {
        console.error(`❌ Mock API Server (backendProcess) process errored during startup:`, err);
        cleanup(1);
      }
    });

    console.log("🚀 Starting Next.js Frontend on port 3005...");
    frontendProcess = spawn("npx", ["next", "dev", "-p", String(FRONTEND_PORT), "-H", "127.0.0.1"], {
      cwd: dashboardDir,
      env: {
        ...process.env,
        PORT: String(FRONTEND_PORT),
        INTERNAL_API_URL: BACKEND_URL
      },
      stdio: "inherit",
      detached: true
    });

    frontendProcess.on("exit", (code, signal) => {
      if (!serversOnline) {
        console.error(`❌ Next.js Frontend (frontendProcess) exited early with code ${code} (signal: ${signal}) during startup.`);
        cleanup(1);
      }
    });

    frontendProcess.on("error", (err) => {
      if (!serversOnline) {
        console.error(`❌ Next.js Frontend (frontendProcess) process errored during startup:`, err);
        cleanup(1);
      }
    });

    console.log("⌛ Waiting for services to respond...");
    await Promise.all([
      waitOn(`${BACKEND_URL}/api/health`),
      waitOn(FRONTEND_URL)
    ]);
    serversOnline = true;
    console.log("🟢 All services online. Resolving test files...");

    const testDir = path.join(rootDir, "tests", "e2e");
    const testFiles = findTestFiles(testDir);
    console.log(`Found test files: ${JSON.stringify(testFiles)}`);

    if (testFiles.length === 0) {
      throw new Error(`No test files found in ${testDir}`);
    }

    console.log("🏃 Running E2E Test Suite via node --test...");
    const testRunner = spawn("node", ["--test", ...testFiles], {
      cwd: rootDir,
      stdio: "inherit"
    });

    testRunner.on("close", (code) => {
      cleanup(code === null ? 1 : code);
    });

    testRunner.on("error", (err) => {
      console.error("Test Runner Process Error:", err);
      cleanup(1);
    });

  } catch (error) {
    console.error("❌ E2E Runner Setup Failed:", error.message);
    cleanup(1);
  }
}

main();
