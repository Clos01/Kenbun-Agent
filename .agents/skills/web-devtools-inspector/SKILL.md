---
name: web-devtools-inspector
description: Inspects live website DevTools, browser console logs, JavaScript runtime errors, network traffic, DOM state, and Chrome DevTools Protocol (CDP) telemetry. Activate this skill whenever the user wants to check the console, inspect website dev tools, debug browser errors, evaluate JavaScript expressions on a page, analyze network requests, or diagnose frontend runtime issues.
---

# 🔍 Web DevTools & Console Inspector

The **Web DevTools & Console Inspector** equips the Swarm with end-to-end browser inspection, console monitoring, Chrome DevTools Protocol (CDP) execution, and network telemetry analysis for both local development servers (`http://localhost:*`) and live remote websites.

---

## 🎯 When to Activate

Trigger this skill immediately when:
- The user asks to **check the console**, **look at dev tools**, or **inspect a website**.
- Investigating runtime errors, unhandled JavaScript exceptions, or React hydration mismatches.
- Inspecting network requests, response payloads, status codes (4xx/5xx), or CORS issues.
- Evaluating JavaScript expressions dynamically in the context of the active browser page.
- Inspecting DOM layout, computed styles, cookies, localStorage, or accessibility trees.
- Auditing site performance, Core Web Vitals, or memory bottlenecks.

---

## 🛠️ Core Tool Matrix

| Task | Primary Tool | Description |
|---|---|---|
| **Navigate to URL** | `browser_navigate(url)` | Opens the target webpage in the headless/controlled browser instance. |
| **Inspect Console** | `browser_console()` | Dumps all active console logs (`log`, `warn`, `error`, `debug`, exceptions). |
| **Evaluate In Page** | `browser_console(expression="...")` | Executes arbitrary JavaScript expressions within the page's execution context. |
| **Clear Console Buffer** | `browser_console(clear=True)` | Flushes the console buffer after reading to isolate subsequent events. |
| **Capture DOM Structure** | `browser_snapshot()` | Generates a structured snapshot with interactive element UIDs. |
| **Raw CDP Execution** | `browser_cdp(method, params)` | Calls raw Chrome DevTools Protocol domains (`Network`, `Runtime`, `Page`, `DOM`, `Performance`). |
| **Visual Screenshot** | `browser_vision()` | Captures a high-fidelity visual rendering of the active viewport. |
| **Multi-Route Audit** | `audit_console_and_network(base_url, routes)` | Automates pre-flight crawls across multiple routes to detect 500s, slow queries, and console crashes. |

---

## 📋 Standard Inspection Playbook

### Step 1: Navigate & Anchor
Open the target website or route:
```python
browser_navigate(url="https://example.com" or "http://localhost:3000/dashboard")
```

### Step 2: Read Browser Console Logs
Retrieve all active console output to identify runtime crashes or warnings:
```python
logs = browser_console()
```
*Look for:*
- `TypeError` / `ReferenceError` / unhandled promise rejections.
- React hydration mismatches (`Warning: Text content did not match...`).
- Content Security Policy (CSP) violations.
- CORS policy blocks (`has been blocked by CORS policy`).

### Step 3: Inspect Network Traffic via CDP
To monitor HTTP requests and responses:
```python
# Enable Network tracking domain
browser_cdp(method="Network.enable")

# Retrieve response body for a specific request ID
browser_cdp(method="Network.getResponseBody", params={"requestId": "<REQUEST_ID>"})

# Inspect cookies
browser_cdp(method="Network.getCookies", params={"urls": ["https://example.com"]})
```

### Step 4: Evaluate Runtime State & DOM Properties
Execute diagnostic JavaScript in the browser context:
```python
# Check global objects or state stores
browser_console(expression="window.__INITIAL_STATE__ || window.__NEXT_DATA__")

# Inspect document title and meta tags
browser_console(expression="document.title")

# Count DOM nodes and check memory metrics
browser_console(expression="({ nodes: document.querySelectorAll('*').length, memory: performance.memory ? performance.memory.usedJSHeapSize : null })")
```

### Step 5: Capture Visual Proof & Diagnostics
When reporting back to the user, capture a DOM snapshot or screenshot:
```python
snapshot = browser_snapshot()
# or
screenshot = browser_vision()
```

---

## 📚 Deep-Dive References

For specialized CDP methods, debugging patterns, and common failure signatures, consult the subdocumentation:
- [references/cdp_methods.md](references/cdp_methods.md) — Comprehensive Chrome DevTools Protocol cheat sheet (`Network`, `Runtime`, `DOM`, `Performance`, `Storage`).
- [references/console_troubleshooting.md](references/console_troubleshooting.md) — Diagnostic guide for React errors, CORS, CSP, failed fetches, and layout shifts.
