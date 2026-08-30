# Explorer Report: Milestone 2 — Zod Metadata Validation Strategy

This report details the architectural plan for implementing **Milestone 2: Zod Metadata Validation** in the Kenbun dashboard application.

---

## 1. Analysis of Data Ingestion Boundaries

Based on a thorough review of the codebase, incoming lead data enters the frontend at two key boundaries:

### A. Server-Side Proxy Boundary (The Boundary of Ingestion)
- **File**: `dashboard/src/app/api_proxy/[...slug]/route.ts`
- **Location**: `handleProxy()` function
- **Role**: This is the Next.js server-side API proxy. It intercepts requests to the Python backend (e.g., `/api/backend/leads` and `/api/v1/leads`).
  - **GET**: Fetches data from the backend, reads the body as text, and forwards it to the client.
  - **POST**: Receives raw payloads from the client via `request.text()`, parses it, and forwards it.
- **Vulnerability**: Currently, the proxy does not inspect or validate payloads before forwarding them. If a tenant returns a polluted payload (like Tenant C), it is forwarded directly to the client. Similarly, the client could POST arbitrary payloads without validation.
- **Senior Recommendation**: The API proxy is the **ideal boundary** to enforce validation. Running Zod schemas here prevents malicious payloads, prototype pollution, and XSS from ever reaching the client React code or the backend database.

### B. Client-Side Parsing Boundary
- **File**: `dashboard/src/app/leads/page.tsx`
- **Location**: `loadLeads()` function (Lines 129–168)
- **Role**: Parses the JSON response received from the API using `response.json()` and sets it into the local state:
  ```typescript
  const data = await response.json();
  const leadsList = Array.isArray(data) ? data : (data.leads || []);
  setLeads(leadsList);
  ```
- **Discrepancy**: The frontend UI defines a rigid `Lead` interface (with fixed keys like `industry`, `creation_date`, `status`, `email`, etc.). However, the API backend return schema (`scripts/mock-api.js`) uses a different format, containing `id`, `name`, `tenant_id`, and a dynamic `metadata` object.
- **Senior Recommendation**: Client-side validation should run inside the React page/hook layer as a secondary guardrail, ensuring TypeScript type safety and a clean fallback experience.

---

## 2. Schema Location Strategy

To maintain a clean separation of concerns and avoid circular dependencies, we recommend the following structure:

### Location: `dashboard/src/lib/validation.ts`
- **Rationale**:
  - Centralizes all Zod schemas and validation logic.
  - Exported schemas can be imported by both server-side Next.js route handlers (`api_proxy`) and client-side React components.
  - Allows deriving TypeScript types directly from schemas via `z.infer<typeof ...>` (single source of truth).
- **Alternative considered**: `dashboard/src/types.ts`. However, mixing executable Zod validation code with pure TypeScript interfaces is a code smell that can cause issue with build-time tree-shaking and bundler configurations in React Server Components vs. Client Components.

---

## 3. Proposed Zod Schemas

Below is the proposed implementation for `dashboard/src/lib/validation.ts`. It includes schemas for both the core `Lead` structure and dynamic, safe `LeadMetadata` fields.

```typescript
import { z } from "zod";

// ==========================================
// 1. Sanitization & Coercion Helpers
// ==========================================

/**
 * XSS Sanitizer: Strips HTML tags and escapes special characters.
 */
export const sanitizeHtml = (val: string): string => {
  return val
    .replace(/<[^>]*>/g, "") // Strip all HTML tags (e.g. <script>, <img>)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
};

/**
 * Safe Boolean Coercion: Standard z.coerce.boolean() evaluates any non-empty
 * string as true, which is dangerous (e.g. "false" becomes true).
 */
export const coercedBoolean = z.union([
  z.boolean(),
  z.enum(["true", "false"]).transform((val) => val === "true"),
]);

/**
 * Safe Number Coercion: Strips currency/formatting symbols and parses safely.
 */
export const coercedNumber = z.union([
  z.number(),
  z.string().transform((val) => {
    const parsed = Number(val.replace(/[^0-9.-]/g, ""));
    return isNaN(parsed) ? 0 : parsed;
  }),
]);

// ==========================================
// 2. Lead Metadata Validation Schema
// ==========================================

// Safe key schema to prevent Prototype Pollution & SQL injection targets
const safeKeySchema = z.string()
  .min(1, "Metadata key cannot be empty")
  .max(100, "Metadata key too long")
  .refine(
    (key) => !["__proto__", "constructor", "prototype"].includes(key),
    { message: "Forbidden: Prototype pollution key detected" }
  )
  .refine(
    (key) => !["isAdmin", "role", "permissions"].includes(key),
    { message: "Forbidden: Unauthorized privilege key" }
  );

// Safe value schema supporting strings, numbers, booleans, arrays of strings, and null
const safeValueSchema = z.union([
  z.string().max(1000).transform(sanitizeHtml),
  coercedNumber,
  coercedBoolean,
  z.array(z.string().max(255).transform(sanitizeHtml)).max(50),
  z.null(),
]);

/**
 * Validates dynamic lead metadata objects.
 */
export const leadMetadataSchema = z.record(safeKeySchema, safeValueSchema)
  .refine(
    (record) => {
      // Secondary safeguard against runtime prototype pollution
      return !("__proto__" in record || "constructor" in record || "prototype" in record);
    },
    { message: "Prototype pollution attempt detected" }
  );

// ==========================================
// 3. Core Lead Validation Schema
// ==========================================

/**
 * Interaction Log Schema for tracking activities.
 */
export const interactionLogSchema = z.object({
  date: z.string().datetime({ message: "Invalid ISO 8601 date format" }),
  agent: z.string().min(1).max(100).transform(sanitizeHtml),
  action: z.string().min(1).max(100).transform(sanitizeHtml),
  summary: z.string().max(1000).transform(sanitizeHtml),
}).strict(); // Reject extra keys in interaction logs

/**
 * Unified Lead Ingestion Schema
 * 
 * Enforces strong type safety and uses .strip() to automatically remove
 * unknown or malicious fields.
 */
export const leadIngestionSchema = z.object({
  id: z.string().uuid("Invalid Lead ID UUID format"),
  name: z.string().min(1, "Name is required").max(255, "Name exceeds limit").trim().transform(sanitizeHtml),
  tenant_id: z.string().uuid("Invalid Tenant ID UUID format"),
  // Support both legacy core fields (optional) and structured metadata
  industry: z.string().max(100).trim().transform(sanitizeHtml).optional(),
  creation_date: z.string().datetime().optional(),
  status: z.enum(["new", "contacted", "qualified", "converted", "lost"]).default("new"),
  email: z.string().email("Invalid email format").or(z.literal("")).optional(),
  phone: z.string().max(30).trim().transform(sanitizeHtml).optional(),
  address: z.string().max(500).trim().transform(sanitizeHtml).optional(),
  score: z.number().min(0).max(100).default(0),
  notes: z.string().max(5000).transform(sanitizeHtml).optional(),
  source: z.string().max(100).transform(sanitizeHtml).optional(),
  interaction_history: z.array(interactionLogSchema).default([]),
  
  // Dynamic custom metadata fields
  metadata: leadMetadataSchema.default({}),
}).strip(); // Strips out malicious top-level keys like isAdmin, drop table commands, etc.

// ==========================================
// 4. Inferred TypeScript Types
// ==========================================
export type LeadMetadata = z.infer<typeof leadMetadataSchema>;
export type Lead = z.infer<typeof leadIngestionSchema>;
export type InteractionLog = z.infer<typeof interactionLogSchema>;
```

---

## 4. Key Stripping and Safety Enforcement Strategy

### A. Preventing Privilege Escalation & Extra Key Injection
By using `.strip()` on the root level schema (`leadIngestionSchema`), Zod will strip out any keys not defined in the object. If an adversary attempts to inject `isAdmin: true` or a payload like `{ "delete_all_records": "DROP TABLE leads;" }` at the root of the lead object, Zod will silently exclude it from the validated object.

### B. Defending against Prototype Pollution
For dynamic metadata properties (which are validated using `z.record(...)`), Zod cannot use `.strip()` because it is designed to map any dynamic string keys. We prevent prototype pollution by:
1. Validating keys with `safeKeySchema`, which restricts keys from matching `__proto__`, `constructor`, or `prototype`.
2. Refining the record object itself to ensure none of the restricted runtime keys exist on the validated object.

### C. Mitigating XSS (Cross-Site Scripting)
String values are automatically passed through the `sanitizeHtml` transformer during Zod parsing. Any HTML tags are stripped out and special characters are escaped, ensuring the frontend is fully insulated from script injection when displaying custom fields.

### D. Integration with the Next.js API Proxy (`api_proxy/[...slug]/route.ts`)
To apply these rules, update the `api_proxy` handler to parse payloads before responding:

```typescript
// Inside handleProxy (route.ts):
const responseData = await response.text();
if (slugPath.includes("leads") && response.ok) {
  try {
    const rawJson = JSON.parse(responseData);
    if (Array.isArray(rawJson)) {
      // Validate and strip malicious payload keys from lists of leads
      const validatedLeads = rawJson.map(lead => leadIngestionSchema.parse(lead));
      return NextResponse.json(validatedLeads);
    } else {
      const validatedLead = leadIngestionSchema.parse(rawJson);
      return NextResponse.json(validatedLead);
    }
  } catch (err) {
    console.error("🚨 [PROXY] Lead data validation failed:", err);
    return NextResponse.json({ error: "Data Validation Failed" }, { status: 422 });
  }
}
```

---

## 5. Required NPM Packages

To implement this strategy, the following dependency must be added:

1. **`zod`** (Core validation library)
   - **Installation**: Run `npm install zod` in the `dashboard` directory.
   - **Target File**: `dashboard/package.json` under `dependencies`.

No other third-party dependencies are strictly necessary. A custom lightweight string sanitizer is proposed to keep runtime sizes low and avoid dependency bloat.
