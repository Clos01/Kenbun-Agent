## 2026-07-07T04:05:02Z

You are a Worker subagent (Archetype: teamwork_preview_worker) tasked with implementing Milestone 2: Zod Metadata Validation for the Kenbun codebase.

Your working directory is `~/Dev/Kenbun/.agents/worker_m2_1_gen1`.

## Objective
Define and enforce Zod schemas at the boundary of data ingestion (Next.js server-side BFF proxy and React leads dashboard), ensuring malicious/unknown properties (such as __proto__, isAdmin, delete_all_records) are stripped, currency is coerced to numbers, booleans are coerced properly, and string fields are sanitized against XSS. Then, update the leads dashboard to display these metadata properties using a Bento-grid dynamic renderer with Framer Motion animations conforming to the Heritage design system. Finally, update the E2E tests to assert these security behaviors and run verification checks.

## Explorer Recommendations & Context
1. In `dashboard/package.json`, add and install `zod`.
2. Create `dashboard/src/lib/validation.ts` containing the isomorphic Zod schemas.
   - Implement `SafeStringSchema` which escapes characters: `&` -> `&amp;`, `<` -> `&lt;`, `>` -> `&gt;`, `"` -> `&quot;`, `'` -> `&#x27;`, `/` -> `&#x2F;`.
   - Implement `LeadMetadataSchema`:
     - `budget`: Union of number or string (coerce currency strings like `$10,000` to float/number).
     - `request_date`: Regex YYYY-MM-DD format string.
     - `commercial`: Coerced to boolean (e.g. "true" or "1" -> true).
     - `location`: Safe string.
     - `collections`: Array of safe strings.
     - `recurring`: Safe string.
     - You MUST apply `.strip()` to `LeadMetadataSchema` so that any other properties (e.g., `isAdmin`, `delete_all_records`, `__proto__`) are discarded.
   - Implement `LeadSchema`:
     - `id`: UUID.
     - `name`: SafeString.
     - `industry`: SafeString.
     - `creation_date`: ISO datetime string.
     - `status`: Enum of "new", "contacted", "qualified", "converted", "lost".
     - `email`: Email string format.
     - `phone`: SafeString.
     - `address`: SafeString.
     - `score`: Number (0-100).
     - `notes`: SafeString.
     - `source`: SafeString.
     - `interaction_history`: Array of InteractionLogSchema.
     - `metadata`: LeadMetadataSchema.
     - Apply `.strip()` to `LeadSchema` as well.
   - Export inferred type: `export type Lead = z.infer<typeof LeadSchema>;`
3. Update `dashboard/src/app/api_proxy/[...slug]/route.ts`:
   - Intercept API responses when `slugPath.includes("leads")`. Parse the body as JSON.
   - Validate using `LeadsListSchema` (if array) or `LeadSchema` (if single lead), parse the payload, and return the sanitized/stripped version to the client. This prevents Prototype Pollution or malicious fields (e.g. from Tenant C) from ever reaching the client.
   - Also validate/sanitize POST/PUT request bodies for leads in the proxy.
4. Update `dashboard/src/app/leads/page.tsx`:
   - Replace the inline `interface Lead` with the imported `Lead` type from `@/lib/validation`.
   - Update `loadLeads()` to handle validated payloads.
   - In the lead detail panel, render a dynamic `CustomMetadataBento` component (using Lucide icons and Framer Motion for premium hover states/animations) for the validated metadata keys. Match labels using a label mapping:
     - `budget`: "Expected Budget" (render with `CircleDollarSign` icon, formatted as currency)
     - `request_date`: "Requested On" (render with `Calendar` icon, formatted date)
     - `commercial`: "Commercial Project" (render with CheckSquare/Square icon)
     - `location`: "Target Location" (render with `MapPin` icon)
     - `collections`: "Collections" (render as styled badges/tags)
     - `recurring`: "Service Frequency" (render with `Repeat` icon)
   - Ensure styling uses the Heritage Design System tokens (Limestone/Boston Clay, neutral background, borders, subtle mesh gradients on hover).
5. In `tests/e2e/leads.test.js`:
   - Locate the `TODO` tests for "Coercion validation check", "XSS sanitization check", "Component Registry renderers check", "Metadata label mapping checks", "Heritage tokens verification".
   - Implement actual, fully-functional assertions for these.
   - For example, verify that unknown fields like `isAdmin` are indeed stripped from `metadata` in the proxy response, that budget is coerced, that XSS script tags are escaped/neutralized, and that custom metadata is rendered in the UI with correct labels.
6. Verify your implementation by running:
   - ESLint check: verify zero errors/warnings.
   - Next.js build: run `npm run build` inside `dashboard/` to verify zero compile errors.
   - E2E tests: run `npm run test:e2e` inside `dashboard/` and ensure all tests pass (including the new ones).

MANDATORY INTEGRITY WARNING — include this verbatim in your implementation:
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.
