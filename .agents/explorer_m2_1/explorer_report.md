# Milestone 2: Zod Metadata Validation Strategy Report

## Executive Summary
This report presents a strategy for Milestone 2: "Zod Metadata Validation" inside the Kenbun frontend dashboard. The objective is to define and enforce Zod schemas at the boundary of data ingestion, preventing cross-tenant leakage, XSS injections, and Prototype Pollution while stripping malicious payload keys from custom lead metadata.

---

## Task 1: Ingestion Points and Data Flow
After analyzing the codebase, we identified two primary ingestion boundaries:

1. **BFF Proxy Boundary (Next.js Server-Side Route Handler)**:
   - **File**: `dashboard/src/app/api_proxy/[...slug]/route.ts` (specifically in the `handleProxy` function)
   - **Mechanics**: Intercepts requests destined for the backend server (`http://127.0.0.1:8001`). It reads request bodies (POST payloads) and response bodies (GET payload lists).
   - **Role**: This is the most secure **server-side boundary**. Intercepting payloads here prevents malicious data from ever reaching the client runtime and protects the backend from invalid inputs.

2. **Client-Side Component Ingestion (Leads Page)**:
   - **File**: `dashboard/src/app/leads/page.tsx`
   - **Mechanics**: The `loadLeads()` function fetches leads from `api/v1/leads` or `api/backend/leads` and parses JSON into state:
     ```typescript
     const data = await response.json();
     const leadsList = Array.isArray(data) ? data : (data.leads || []);
     ```
   - **Role**: The parsed JSON is directly passed to component states (`setLeads`) without any verification or validation. This is the **browser runtime boundary**.

3. **API Client Helper**:
   - **File**: `dashboard/src/lib/apiClient.ts`
   - **Mechanics**: Implements the `useApiClient` custom hook. It returns the raw fetch `Response` object and does not parse JSON or enforce schemas.

---

## Task 2: Schema Definition Placement
We recommend defining the Zod schemas in a dedicated file:
`dashboard/src/lib/validation.ts` (or `dashboard/src/lib/validation/leads.ts`)

### Rationale:
1. **Shared Server/Client Execution**: Next.js allows importing files from `src/lib/` on both the client (e.g. leads page, forms) and the server (API proxy). This avoids duplicate code.
2. **Single Source of Truth**: TypeScript types can be inferred directly from the Zod schemas using `z.infer<typeof LeadSchema>`. This ensures compile-time types (`types.ts` equivalent) and runtime schemas stay perfectly synced:
   ```typescript
   export type Lead = z.infer<typeof LeadSchema>;
   export type InteractionLog = z.infer<typeof InteractionLogSchema>;
   ```
3. **Component Decoupling**: Components remain lightweight and focused on UI rendering rather than schema declarations.

---

## Task 3: Proposed Zod Schemas
Below are the proposed schemas to handle validation, coercion, XSS sanitization, and key stripping.

```typescript
import { z } from "zod";

/**
 * XSS Sanitization Helper
 * Escapes characters to prevent script tags and HTML injection attacks.
 */
const htmlEscape = (str: string): string => {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;")
    .replace(/\//g, "&#x2F;");
};

// Safe string parser that trims whitespace and escapes HTML entities
export const SafeStringSchema = z.string().transform((val) => htmlEscape(val.trim()));

// Strict Safe String that throws a validation error if HTML is present
export const StrictSafeStringSchema = z.string()
  .refine((val) => !/[<>]/g.test(val), {
    message: "HTML tags are not allowed"
  })
  .transform((val) => htmlEscape(val.trim()));

// Interaction History Timeline item schema
export const InteractionLogSchema = z.object({
  date: z.string().datetime({ message: "Invalid ISO date-time format" }).or(z.string()),
  agent: SafeStringSchema,
  action: SafeStringSchema,
  summary: SafeStringSchema
}).strip();

// Lead Metadata Schema (Validates known properties, strips out any other keys)
export const LeadMetadataSchema = z.object({
  budget: z.union([
    z.number(),
    z.string().transform((val) => {
      // Coerce budget strings (e.g., "$15,000" or "15000" -> 15000)
      const cleanVal = val.replace(/[$,]/g, "");
      const parsed = parseFloat(cleanVal);
      return isNaN(parsed) ? val : parsed;
    })
  ]).optional(),
  request_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Must be in YYYY-MM-DD format").optional(),
  commercial: z.union([
    z.boolean(),
    z.string().transform((val) => val.toLowerCase() === "true" || val === "1")
  ]).transform(Boolean).optional(),
  location: SafeStringSchema.optional(),
  collections: z.array(SafeStringSchema).optional(),
  recurring: SafeStringSchema.optional(),
}).strip(); // Default behavior: discard any properties not explicitly defined above

// Core Lead Schema
export const LeadSchema = z.object({
  id: z.string().uuid("Invalid UUID format"),
  name: SafeStringSchema.min(1, "Lead name is required"),
  industry: SafeStringSchema,
  creation_date: z.string().datetime({ message: "Invalid creation ISO timestamp" }),
  status: z.enum(["new", "contacted", "qualified", "converted", "lost"]),
  email: z.string().email("Invalid email address format"),
  phone: SafeStringSchema,
  address: SafeStringSchema,
  score: z.number().min(0).max(100).default(0),
  notes: SafeStringSchema.default(""),
  source: SafeStringSchema,
  interaction_history: z.array(InteractionLogSchema).default([]),
  metadata: LeadMetadataSchema.default({})
}).strip();

// Lead Collection Schema
export const LeadsListSchema = z.array(LeadSchema);
```

---

## Task 4: Key Stripping and Mitigation Strategy

### 1. Stripping Malicious / Unknown Keys
Using `.strip()` on `z.object()` forces Zod to ignore and omit all undeclared properties from the output object.
- **Prototype Pollution Prevention**: If an attacker submits a payload containing `"__proto__": { "polluted": true }`, Zod will intercept this and strip the `__proto__` property completely before parsing.
- **Privilege Escalation**: Keys like `isAdmin: true` will be silently discarded from `metadata`.
- **SQL Injection/RCE Parameters**: Keys like `delete_all_records: "DROP TABLE leads;"` will be discarded.

### 2. The Dynamic / Extensible Strategy (Senior Version)
If we want to allow arbitrary custom fields instead of restricting them to a hardcoded list, we can design a **Dynamic Safe Schema** that uses an denylist for sensitive keys and enforces type checks + XSS escaping:
```typescript
const SENSITIVE_KEYS = ["__proto__", "constructor", "prototype", "isAdmin", "role", "delete_all_records"];

export const DynamicMetadataSchema = z.record(
  z.string().refine(key => !SENSITIVE_KEYS.includes(key), "Forbidden metadata key"),
  z.union([
    z.number(),
    z.boolean(),
    z.array(z.string().transform(htmlEscape)),
    z.string().transform(htmlEscape)
  ])
).transform((obj) => {
  // Strip blocked keys
  const cleanObj: Record<string, any> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (!SENSITIVE_KEYS.includes(key)) {
      cleanObj[key] = value;
    }
  }
  return cleanObj;
});
```

### 3. Coercion
Zod's `.transform()` and `z.union()` are utilized to cleanly coerce strings like `"true"` to `true`, and string currency formats like `"$10,000"` to numbers (or leave them safe if they fail numeric coercion).

### 4. XSS Sanitization
The schema escapes `<`, `>`, `&`, `"`, `'`, `/` in all strings, converting them to HTML entities, neutralizing browser execution.

---

## Task 5: Required NPM Packages
To implement this strategy, the following packages should be added to the dashboard dependencies:
- **`zod`**: Essential validation library.
```bash
npm install zod
```

Optional libraries (if advanced sanitization or validation is requested later):
- **`xss`** or **`isomorphic-dompurify`** (if we want to parse HTML safely instead of escaping all characters).
- **`validator`** (for rich string format checkers, e.g. international phone formats).

---

## Senior UX/UI Component Registry Design (Rule 7 Mandate)
To support the custom metadata layout, we propose integrating a dynamic component registry conforming to the Heritage Design System tokens and Magic UI/Aceternity style.

### Component Design (in `leads/page.tsx` or a custom component):
```typescript
import { motion } from "framer-motion";
import { Calendar, CircleDollarSign, CheckSquare, Square, MapPin, Tags, Repeat } from "lucide-react";

export const METADATA_LABEL_MAP: Record<string, string> = {
  budget: "Expected Budget",
  request_date: "Requested On",
  commercial: "Commercial Project",
  location: "Target Location",
  collections: "Collections",
  recurring: "Service Frequency"
};

export const MetadataRenderers: Record<string, (val: any) => React.ReactNode> = {
  budget: (val) => (
    <div className="flex items-center gap-1.5 font-mono text-tertiary">
      <CircleDollarSign className="w-3.5 h-3.5" />
      <span>{typeof val === 'number' ? `$${val.toLocaleString()}` : val}</span>
    </div>
  ),
  request_date: (val) => (
    <div className="flex items-center gap-1.5 text-primary">
      <Calendar className="w-3.5 h-3.5 text-secondary/40" />
      <span>{new Date(val).toLocaleDateString()}</span>
    </div>
  ),
  commercial: (val) => (
    <div className="flex items-center gap-1.5 text-primary">
      {val ? (
        <>
          <CheckSquare className="w-3.5 h-3.5 text-emerald-500" />
          <span className="text-emerald-500 text-[10px] font-black uppercase tracking-wider">Yes</span>
        </>
      ) : (
        <>
          <Square className="w-3.5 h-3.5 text-secondary/40" />
          <span className="text-secondary/60 text-[10px] font-black uppercase tracking-wider">No</span>
        </>
      )}
    </div>
  ),
  location: (val) => (
    <div className="flex items-center gap-1.5 text-primary">
      <MapPin className="w-3.5 h-3.5 text-secondary/40" />
      <span>{val}</span>
    </div>
  ),
  collections: (val) => (
    <div className="flex flex-wrap gap-1">
      {Array.isArray(val) && val.map((tag, idx) => (
        <span key={idx} className="text-[9px] font-black uppercase tracking-widest bg-primary/5 border border-primary/10 px-1.5 py-0.5 rounded-sm text-secondary">
          {tag}
        </span>
      ))}
    </div>
  ),
  recurring: (val) => (
    <div className="flex items-center gap-1.5 text-primary">
      <Repeat className="w-3.5 h-3.5 text-secondary/40" />
      <span>{val}</span>
    </div>
  )
};

export function CustomMetadataBento({ lead }: { lead: Lead }) {
  if (!lead.metadata || Object.keys(lead.metadata).length === 0) return null;

  return (
    <div className="space-y-4 mt-6">
      <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-secondary">
        Enforced Custom Metadata
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3.5">
        {Object.entries(lead.metadata).map(([key, value], index) => {
          const label = METADATA_LABEL_MAP[key] || key;
          const renderer = MetadataRenderers[key];
          return (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              whileHover={{ scale: 1.02 }}
              className="relative overflow-hidden bg-white/[0.02] backdrop-blur-md border border-white/[0.05] p-3 rounded-md flex flex-col justify-between hover:border-tertiary/30 transition-all duration-300 group"
            >
              {/* Mesh Gradient Glow */}
              <div className="absolute inset-0 bg-gradient-to-br from-tertiary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
              
              <span className="text-[8px] font-black uppercase tracking-widest text-secondary/50 block mb-1">
                {label}
              </span>
              <div className="text-xs mt-1.5 font-semibold">
                {renderer ? renderer(value) : <span className="text-primary">{String(value)}</span>}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
```
