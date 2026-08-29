# Browser Console Troubleshooting & Error Signatures

This guide provides diagnostic patterns and fixes for common browser console errors, warnings, and network failures.

---

## 1. React Hydration Failures

### Symptom
Console logs:
```log
Warning: Text content did not match. Server: "1:33 AM" Client: "1:34 AM"
Warning: Expected server HTML to contain a matching <div> in <div>.
Uncaught Error: Hydration failed because the initial UI does not match what was rendered on the server.
```

### Diagnosis
- The server (SSR) rendered HTML containing dynamic data (timestamps, `window.innerWidth`, `Math.random()`, or `localStorage` values) that changed before client hydration executed.
- Invalid HTML nesting (e.g. `<p>` wrapping `<div>`, or `<tr>` without `<tbody>`).

### Quick Fix Pattern
1. Wrap client-only code in `useEffect` or `useState(false)` with a mounted flag:
```tsx
const [mounted, setMounted] = useState(false);
useEffect(() => setMounted(true), []);
if (!mounted) return <Skeleton />;
return <div>{new Date().toLocaleTimeString()}</div>;
```
2. Or use Next.js dynamic import with `{ ssr: false }`.

---

## 2. CORS Policy Violations

### Symptom
Console logs:
```log
Access to fetch at 'https://api.domain.com/v1/data' from origin 'http://localhost:3000' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

### Diagnosis
The backend API server did not return the required `Access-Control-Allow-Origin` response header matching the frontend origin.

### Verification via CDP:
```python
browser_cdp(method="Network.getResponseBody", params={"requestId": "<REQ_ID>"})
```

### Fix Patterns
- **FastAPI / Python:**
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:3000", "https://app.domain.com"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Next.js API Rewrite (Proxy):** Route external requests through `next.config.ts` rewrites to bypass browser CORS checks during local development.

---

## 3. Unhandled Promise Rejections & TypeErrors

### Symptom
Console logs:
```log
Uncaught (in promise) TypeError: Cannot read properties of undefined (reading 'map')
```

### Diagnosis
An asynchronous API call returned `undefined`, `null`, or an error object instead of an expected array or dictionary, and the UI component attempted to map over it directly without optional chaining or default fallbacks.

### Fix Pattern
```tsx
// Defensive data binding:
const items = data?.items ?? [];
return items.map((item) => <Card key={item.id} {...item} />);
```

---

## 4. Content Security Policy (CSP) Violations

### Symptom
Console logs:
```log
Refused to load the script 'https://cdn.external.com/script.js' because it violates the following Content Security Policy directive: "script-src 'self'".
```

### Diagnosis
The application has strict CSP headers (e.g., in Next.js `middleware.ts` or `<meta http-equiv="Content-Security-Policy">`) blocking external scripts, fonts, styles, or WebSocket connections.

### Fix Pattern
Add the external domain or nonce to the appropriate CSP directive (`script-src`, `connect-src`, `img-src`).
