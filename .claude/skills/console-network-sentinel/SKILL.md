---
name: "console-network-sentinel"
description: "Autonomously catches, diagnoses, and fixes runtime crashes, browser console errors, React hydration failures, slow network requests, database statement timeouts, and SSR error overlays before users ever see them."
version: "1.0.0"
license: "MIT"
---

# 🛡️ Console & Network Sentinel

Autonomous pre-flight runtime auditor, browser console listener, and network/database latency monitor for sovereign agentic engineering.

**Version:** 1.0.0  
**License:** MIT

---

## 🎯 Purpose & Mission

To guarantee that **zero runtime bugs, console crashes, or network timeouts reach the user**.

This skill autonomously:
1. **Intercepts Browser & SSR Console Errors:** Detects `console.error`, unhandled runtime exceptions, `Runtime ReferenceError`, and React hydration mismatches before deployment.
2. **Monitors Network & Endpoint Latency:** Audits all Next.js / FastAPI HTTP routes, checking for `500 Internal Server Errors`, `504 Gateway Timeouts`, and slow responses (>1500ms).
3. **Identifies Database Statement Timeouts:** Proactively profiles PostgreSQL / Supabase queries, catching statement timeouts (`canceling statement due to statement timeout`) caused by un-indexed subqueries, N+1 loops, or missing CTE pre-aggregations.
4. **Executes Pre-Flight Crawls:** Probes every application route (`/`, `/fleet-overview`, `/voice-agents`, `/call-telemetry`, `/feedback`, `/settings`) with zero human intervention.

---

## ⚡ When to Activate

Trigger this skill:
- **Mandatory Pre-Flight Check:** Immediately before marking any feature, bug fix, or UI redesign complete.
- **After Any Database / Query Change:** Whenever modifying SQL queries, table schemas, or API endpoints.
- **When Investigating Runtime Errors:** Whenever a `canceling statement due to statement timeout` or `ReferenceError` occurs.
- **Continuous Background Watchdog:** During active local dev server operation (`bin/console-sentinel watch`).

---

## 🛠️ Tool & CLI Suite

### 1. Standalone CLI Utility (`bin/console-sentinel`)
```bash
# Pre-flight probe all core application routes
bin/console-sentinel probe http://localhost:3000

# Probe specific routes with custom timeout
bin/console-sentinel probe http://localhost:3000 --routes "/voice-agents,/fleet-overview" --timeout 15.0

# JSON output for automated CI/CD gating
bin/console-sentinel probe http://localhost:3000 --json

# Continuous real-time route & console monitor
bin/console-sentinel watch http://localhost:3000
```

### 2. Kenbun Sovereign MCP Tools
```python
# 1. Audit all routes for console and network errors
result = audit_console_and_network(
    base_url="http://localhost:3000",
    routes=["/voice-agents", "/fleet-overview", "/call-telemetry", "/feedback", "/settings"],
    timeout_sec=12.0
)

# 2. Profile a slow SQL query and get CTE optimization recommendations
profile = profile_database_performance(
    query_description="getRecentCalls with 150 limit",
    raw_query_sql="SELECT ... FROM calls LEFT JOIN eval_results ...",
    execution_time_ms=15564.0
)
```

---

## 🧩 The 4 Core Sentinel Anti-Patterns & Protocols

### 1. Database Statement Timeout Prevention (`canceling statement due to statement timeout`)
* **Root Cause:** Correlated subqueries in `SELECT` projections or Cartesian products across un-aggregated child tables (e.g. `eval_results` joined directly with `calls`).
* **Sentinel Rule:**
  - ❌ **Forbidden:** `(SELECT raw_text FROM transcripts WHERE call_id = c.id LIMIT 1)` repeated 150 times.
  - ✅ **Mandatory Pattern:** Use `DISTINCT ON` in an isolated CTE:
    ```sql
    WITH top_transcripts AS (
      SELECT DISTINCT ON (call_id) call_id, raw_text
      FROM transcripts
      WHERE call_id IN (SELECT id FROM top_calls)
      ORDER BY call_id, created_at DESC
    )
    ```
  - **Timeout Safeguard:** Set `statement_timeout = '30s'` in transaction GUC parameters to absorb transient network latency.

### 2. Runtime ReferenceError & Undefined Symbol Prevention
* **Root Cause:** Importing components on the server without client guards or referencing variables outside closure scope.
* **Sentinel Rule:**
  - Verify all Lucide icons and UI atoms are explicitly imported.
  - Apply null-coalescing guards (`(obj?.text || "").slice(0, 30)`) on optional nullable database columns.

### 3. React Hydration Mismatch Prevention
* **Root Cause:** `Date.now()`, `localStorage`, or random UUIDs rendered directly during SSR without `useEffect` or `suppressHydrationWarning`.
* **Sentinel Rule:**
  - Gate client-only storage/timers inside `useEffect` or mount flags (`const [mounted, setMounted] = useState(false)`).

### 4. Zero Blocking Fullscreen Overlays
* **Root Cause:** Intro splashes or modal overlays rendering without dismissal persistence or outside-click listeners.
* **Sentinel Rule:**
  - Always bind `handleClickOutside` and `Escape` key listeners on floating popovers.
  - Keep dashboard root layouts free of blocking un-dismissible overlays.
