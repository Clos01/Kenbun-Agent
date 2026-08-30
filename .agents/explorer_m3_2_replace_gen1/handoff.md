# Handoff Report: Milestone 3 - Normalization & Component Registry

## 1. Observation

During my exploration of the Kenbun repository, I directly observed the following:

1. **Dashboard Leads Page (`dashboard/src/app/leads/page.tsx`):**
   - At lines 129–296, the component `CustomMetadataBento` is defined. It expects to render specific lead metadata fields (`budget`, `request_date`, `commercial`, `location`, `recurring`, and `collections`).
   - The layout of this component hardcodes these cards. For example, the `budget` field card starts at line 160:
     ```tsx
     {/* Expected Budget Card */}
     <motion.div
       whileHover={{ scale: 1.01, translateY: -2 }}
       className="md:col-span-2 bg-card border border-primary/5 p-5 rounded-sm relative overflow-hidden group flex flex-col justify-between min-h-[120px] transition-all duration-300 shadow-sm"
     >
     ```
   - Standard css states and Framer Motion hover animations are specified, but there is no generic registry mapping types to components.

2. **Validation Schemas (`dashboard/src/lib/validation.ts`):**
   - At line 49, `LeadMetadataSchema` is declared:
     ```typescript
     export const LeadMetadataSchema = z.object({
       budget: BudgetSchema,
       request_date: RequestDateSchema,
       commercial: CommercialSchema,
       location: SafeStringSchema.optional().nullable(),
       collections: z.array(SafeStringSchema).optional().nullable(),
       recurring: SafeStringSchema.optional().nullable(),
     }).strip();
     ```
   - The trailing `.strip()` method discards any keys in metadata that are not explicitly defined in the schema.

3. **E2E Test Requirements (`tests/e2e/leads.test.js`):**
   - At line 142, the test `"Tier 2: Boundary/Corner - Prototype Pollution protection check (Tenant C)"` asserts that unknown keys (`isAdmin`, `delete_all_records`, `inject_script`, `onload_exploit`) are stripped from `metadata`:
     ```javascript
     // Verify unknown / malicious properties are stripped from metadata
     assert.strictEqual(rawLead.metadata.isAdmin, undefined);
     assert.strictEqual(rawLead.metadata.delete_all_records, undefined);
     ```
   - At line 216, the test `"Component Registry renderers check"` asserts that the layout on `/leads` includes standard text like `grid-cols-1 md:grid-cols-3`, `Expected Budget`, `Requested On`, and `Commercial Project`.

4. **Design System Specification (`dashboard/DESIGN.md`):**
   - Lines 3–24 define the Heritage token palette and formatting constraints:
     ```yaml
     name: Heritage
     colors:
       primary: "#1A1C1E"
       secondary: "#6C7278"
       tertiary: "#B8422E"
       neutral: "#F7F5F2"
     rounded:
       sm: 4px
       md: 8px
     ```

5. **Codebase Health Check Executions:**
   - Ripgrep searches did not find any existing occurrences of "ComponentRegistry" or "MetadataTransformer" in the source code directories, indicating no partial implementation is present.
   - Running `npm run lint` inside the `dashboard` directory returns clean output with zero warnings or errors.
   - Running `npm run build` inside the `dashboard` directory creates an optimized production build successfully in 3.2 seconds.
   - Running `npm run test:e2e` inside the `dashboard` directory executes node --test on the E2E test files and passes all 15 tests:
     ```
     # tests 15
     # suites 0
     # pass 15
     # fail 0
     ```

---

## 2. Logic Chain

1. **Static Coupling Limitation**: Since `CustomMetadataBento` hardcodes metadata elements directly (Observation 1), it cannot dynamically scale to show arbitrary new business metadata (e.g. `permit_num`) without code modifications.
2. **Metadata Elimination**: Because `LeadMetadataSchema` executes `.strip()` (Observation 2), any custom metadata key sent by the server that isn't statically declared in the Zod object is removed during API validation.
3. **Security Test Constraint**: Simply adding `.passthrough()` to the Zod metadata schema to preserve dynamic fields will violate the E2E security audit assertion (Observation 3). This assertion requires `isAdmin` and other un-modeled properties to be stripped.
4. **Resolution via Safe Blacklist / Transformer Configuration**:
   - To reconcile dynamic capabilities with security verification, we must intercept dynamic fields securely. We can propose either (Option A) explicit registration of allowed custom fields inside `LeadMetadataSchema`, or (Option B) an allowed-list/blacklist Zod transform that cleans security-critical properties while forwarding healthy custom metadata (e.g., `permit_num`).
   - The UI components can be generalized into separate components inside `dashboard/src/components/MetadataCards.tsx` mapped to types in `dashboard/src/components/ComponentRegistry.tsx`.
   - The metadata keys can be normalized into formatted labels and ordered using `MetadataTransformer.transform(metadata)` before rendering.

---

## 3. Caveats

- **Assumed Scope of Custom Fields**: I have assumed that the list of dynamic custom business fields (e.g., `permit_num`) is finite or can be filtered cleanly to prevent Prototype Pollution exploits. If the system must support absolutely uncontrolled user-defined metadata inputs, a nested JSON object structure (e.g. `metadata.custom`) is the safest design alternative.
- **Backend Sync**: I did not explore modifying the mock database API in `scripts/mock-api.js` beyond checking its initialization logic, as the mock server already provides sufficient coverage for testing metadata ingestion and coercion rules.

---

## 4. Conclusion

Milestone 3 should be implemented by creating:
1. `dashboard/src/lib/metadataTransformer.ts` to normalized metadata keys, types, and visual display ordering.
2. `dashboard/src/components/MetadataCards.tsx` holding dedicated React cards for `CurrencyCard`, `DateCard`, `BooleanCard`, `ListCard`, and `StringCard`.
3. `dashboard/src/components/ComponentRegistry.tsx` to register these renderers.
4. An update to `dashboard/src/lib/validation.ts` (`LeadMetadataSchema`) to safely preserve custom business fields using a blacklist-strip transform while discarding security threats to satisfy E2E security tests.
5. An integration refactor to `dashboard/src/app/leads/page.tsx` (`CustomMetadataBento`) to render mapped components dynamically.

Detailed structures and code snippets for these proposals are documented in `explorer_report.md` in this directory.

---

## 5. Verification Method

To verify the proposed implementation once it is written:
1. **ESLint Audit**:
   Execute the linting command in the dashboard directory:
   ```bash
   npm run lint
   ```
2. **Production Build Compilation**:
   Verify compilation succeeds with Next.js Turbopack:
   ```bash
   npm run build
   ```
3. **E2E Test Assertions**:
   Run the test runner script:
   ```bash
   npm run test:e2e
   ```
   *Expected outcome*: All 15 tests must pass. Specifically, the "Component Registry renderers check", "Metadata label mapping checks", and the "Prototype Pollution protection check (Tenant C)" tests must succeed.
