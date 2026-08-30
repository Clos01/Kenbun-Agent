# E2E Infrastructure Adversarial Challenge Report

**Overall Risk Assessment**: LOW

This report stress-tests the remediated E2E testing infrastructure, analyzes implicit assumptions, and evaluates failure modes under different runtime conditions.

---

## Challenges

### 🔴 [Medium] Challenge 1: Cross-Platform Process Teardown Failure (Windows Support)
- **Assumption challenged**: The test runner assumes it is running on a Unix-like system (macOS/Linux) where process group termination is supported via negative PIDs.
- **Attack scenario**: If a developer or CI pipeline runs `npm run test:e2e` on a Windows host, the command `process.kill(-backendProcess.pid)` will throw an exception (`EINVAL`) because Windows does not support negative PID group signals. This will prevent clean cleanup of the Next.js and mock API servers, leaving ports 3005 and 8001 occupied on subsequent runs.
- **Blast radius**: Subsequent test runs will fail immediately due to port collision (`EADDRINUSE`) because the previous servers are still running as orphaned background processes.
- **Mitigation**: Update the runner to detect the platform (`process.platform === 'win32'`) and use a utility like `taskkill` or helper packages to clean up the process tree on Windows, falling back to standard `process.kill(-pid)` on macOS/Linux.

### 🟡 [Low] Challenge 2: Next.js Slow Compilation Timeout
- **Assumption challenged**: The dev server will always respond and compile within the `timeoutMs = 30000` (30 seconds) limit in `waitOn`.
- **Attack scenario**: In resource-constrained CI environments (e.g. single-core virtual machines) or during clean runs where Next.js `.next` cache is missing and must compile pages from scratch, page generation might take longer than 30 seconds.
- **Blast radius**: The runner will timeout, throw a startup error, kill the processes, and exit with code 1, causing flaky CI builds.
- **Mitigation**: Allow the timeout to be overridden via an environment variable (e.g., `E2E_TIMEOUT_MS`), defaulting to 30000.

### 🟡 [Low] Challenge 3: Loopback Binding Port Race Condition
- **Assumption challenged**: The port check and server binding are atomic.
- **Attack scenario**: The runner checks if ports 3005 and 8001 are free, closes the temp server, and then spawns the child processes. In a highly concurrent host running multiple builds or processes, another process might bind to the port in the tiny window between the check closing and the child process starting.
- **Blast radius**: The child process will crash on startup with `EADDRINUSE`.
- **Mitigation**: The runner's early crash detection will successfully catch this, abort, and clean up, preventing a hung run, which is already a solid defense.

---

## Stress Test Results

- **Port Collision Check** → Start a process on port 8001 and run `npm run test:e2e` → Runner aborts immediately with port error and exits with code 1 → **PASS**
- **Startup Crash Handling** → Put a syntax error in `mock-api.js` and run the runner → Runner aborts immediately without hanging for 30s → **PASS**
- **SIGINT / SIGTERM Interrupt** → Press Ctrl+C during tests → Both servers killed instantly and ports released → **PASS**
