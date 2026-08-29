# Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: LOW

The overall security risk of the validated code is very low. The BFF proxy and Zod validations have successfully closed the targeted attack surfaces (XSS injection, path traversal via encoding, prototype pollution, and tenant spoofing).

---

## Challenges

### Low Challenge 1: Recursion Limit on double URL decoding
- **Assumption challenged**: Assumes that recursive URL decoding up to 10 iterations is sufficient to catch all nested URL-encoded characters.
- **Attack scenario**: A highly nested URL-encoded traversal pattern (e.g. 11 levels of encoding) could bypass the check if the decoder stops before resolving it, and the backend is configured to resolve the remaining encoding levels recursively.
- **Blast radius**: The backend might decode the eleventh layer and process a traversal route.
- **Mitigation**: While 11-level encoding is extremely rare, the current check is robust. To make it bulletproof, the loop could decode until no change is detected (without a low iteration cap) or block the request if the recursion limit is hit.

### Low Challenge 2: Tenant Spoofing through Frontend Bypass
- **Assumption challenged**: Assumes client requests cannot query the backend directly, bypassing the BFF proxy.
- **Attack scenario**: If the backend port (e.g. 8001) is exposed to the outside network or other tenants, attackers could bypass the proxy and make direct calls to the backend without the tenant ID verification, cryptographic token, or XSS validation.
- **Blast radius**: Full access to all tenant records, injection of malicious scripts, and bypassing of database constraints.
- **Mitigation**: Ensure the backend network interface is bound only to localhost (`127.0.0.1`) and not exposed externally, or require signature verification (using the cryptographic config token) for all backend incoming traffic. The codebase currently loads `/app/brain_health/config_token.secret` to verify this signature, mitigating this risk.

---

## Stress Test Results

- **Recursive decode traversal (`%252e%252e`)** → Expected 403 Forbidden → Received 403 Forbidden → **PASS**
- **Backslash path traversal (`..%5c`)** → Expected 403 Forbidden → Received 403 Forbidden → **PASS**
- **Tenant ID SQL injection spoofing** → Expected 400 Bad Request → Received 400 Bad Request → **PASS**
- **Malicious Payload Key injection (`__proto__`, `isAdmin`)** → Expected keys to be stripped → Checked returned JSON, keys were stripped → **PASS**
- **Lead name XSS tags (`<script>`)** → Expected HTML characters to be escaped → Received `&lt;script&gt;` → **PASS**
- **Location field XSS tags (`<img onerror=...`)** → Expected HTML characters to be escaped → Received `&lt;img src=x onerror=...&gt;` → **PASS**
- **Collections array XSS tags (`<iframe src=...`)** → Expected HTML characters to be escaped → Received `&lt;iframe src=...&gt;` → **PASS**
- **Budget coercion (`$10,230.50`)** → Expected coercion to number `10230.5` → Coerced to `10230.5` → **PASS**
- **Commercial coercion ("1", "TRUE")** → Expected coercion to boolean `true` → Coerced to `true` → **PASS**
- **Invalid Date format (`07-07-2026`)** → Expected reject with 400 Bad Request → Rejected with 400 Bad Request → **PASS**

---

## Unchallenged Areas

- **Backend Database queries and Row-Level Security** — Not challenged as the backend source code is outside the scope of this review. We assume the backend behaves correctly given a validated tenant ID and config token.
