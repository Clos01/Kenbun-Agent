# Chrome DevTools Protocol (CDP) Methods Reference

This reference catalogs the most effective Chrome DevTools Protocol (CDP) methods supported via the `browser_cdp` tool.

---

## 1. Network Domain (`Network.*`)

Used for capturing HTTP/HTTPS traffic, inspecting request/response headers, analyzing payload sizes, and debugging failed API calls.

| Method | Parameters | Description |
|---|---|---|
| `Network.enable` | `{}` | Enables network tracking events. Always call this first before network inspections. |
| `Network.disable` | `{}` | Disables network tracking. |
| `Network.getResponseBody` | `{"requestId": "123.4"}` | Returns the decoded text/JSON body of an HTTP response. |
| `Network.getRequestPostData` | `{"requestId": "123.4"}` | Returns the request payload sent by the browser. |
| `Network.getCookies` | `{"urls": ["https://example.com"]}` | Retrieves all cookies visible to the specified URL. |
| `Network.clearBrowserCookies` | `{}` | Clears all active browser cookies. |
| `Network.setExtraHTTPHeaders` | `{"headers": {"Authorization": "Bearer ..."}}` | Injects custom request headers into all outgoing requests. |
| `Network.emulateNetworkConditions` | `{"offline": false, "latency": 100, "downloadThroughput": 1000000, "uploadThroughput": 500000}` | Throttles network speed to simulate slow 3G/4G. |

---

## 2. Runtime & Console Domain (`Runtime.*` & `Console.*`)

Used to evaluate scripts, inspect object graphs, and monitor uncaught exceptions.

| Method | Parameters | Description |
|---|---|---|
| `Console.enable` | `{}` | Enables reporting of console API messages and exceptions. |
| `Console.clearMessages` | `{}` | Clears the recorded console message log buffer. |
| `Runtime.evaluate` | `{"expression": "document.title", "returnByValue": true}` | Evaluates a JavaScript expression and returns the primitive or JSON result. |
| `Runtime.getProperties` | `{"objectId": "..."}` | Inspects object properties and prototypes on a remote heap reference. |
| `Runtime.compileScript` | `{"expression": "...", "sourceURL": "test.js", "persistScript": false}` | Validates JavaScript syntax before execution. |

---

## 3. DOM & CSS Domain (`DOM.*` & `CSS.*`)

Used for inspecting node trees, box models, computed styles, and layout geometry.

| Method | Parameters | Description |
|---|---|---|
| `DOM.getDocument` | `{"depth": 2, "pierce": true}` | Retrieves the root DOM node and immediate descendants. |
| `DOM.querySelector` | `{"nodeId": 1, "selector": "button#submit"}` | Finds a specific node ID matching a CSS selector. |
| `DOM.getBoxModel` | `{"nodeId": 12}` | Returns border, padding, content, and margin coordinates for layout auditing. |
| `CSS.getComputedStyleForNode` | `{"nodeId": 12}` | Returns resolved CSS properties (e.g. `font-size`, `color`, `display`). |

---

## 4. Performance & Metrics Domain (`Performance.*`)

Used to evaluate Largest Contentful Paint (LCP), Cumulative Layout Shift (CLS), DOM node counts, and JS heap sizes.

| Method | Parameters | Description |
|---|---|---|
| `Performance.enable` | `{}` | Enables performance metrics collection. |
| `Performance.getMetrics` | `{}` | Dumps key metrics: `Timestamp`, `Documents`, `Nodes`, `JSHeapUsedSize`, `JSHeapTotalSize`, `LayoutCount`, `RecalcStyleCount`. |

### Example Metrics Output:
```json
{
  "metrics": [
    { "name": "Documents", "value": 3 },
    { "name": "Nodes", "value": 842 },
    { "name": "JSHeapUsedSize", "value": 18452104 },
    { "name": "JSHeapTotalSize", "value": 32505856 },
    { "name": "LayoutCount", "value": 14 }
  ]
}
```

---

## 5. Storage Domain (`Storage.*`)

Used to audit cookies, LocalStorage, IndexedDB, and CacheStorage.

| Method | Parameters | Description |
|---|---|---|
| `Storage.getStorageKeyForFrame` | `{"frameId": "..."}` | Resolves the storage key partition for the target frame. |
| `Storage.clearDataForOrigin` | `{"origin": "https://example.com", "storageTypes": "all"}` | Purges localStorage, sessionStorage, service workers, and cookies. |
