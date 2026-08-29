# Handoff Report — Milestone 3: Normalization & Component Registry

## 1. Observation
We observed the following structure and behavior in the workspace:
* **Active Layout & Core Files**:
  - `dashboard/src/app/leads/page.tsx` contains an inline, static component `CustomMetadataBento` (lines 129-296):
    ```typescript
    const CustomMetadataBento = ({ metadata }: { metadata: Lead["metadata"] }) => {
      if (!metadata) return null;
      // ... formatBudget and formatDate helpers ...
      return (
        <div className="space-y-4">
          {/* budget card */}
          {/* request_date card */}
          {/* commercial card */}
          {/* location card */}
          {/* recurring card */}
          {/* collections card */}
        </div>
      );
    }
    ```
  - `dashboard/src/lib/validation.ts` defines `LeadMetadataSchema` (lines 49-56) with `.strip()` at the end:
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
  - `scripts/mock-api.js` contains custom, adversarial metadata fields for `Tenant C` (lines 71-81):
    ```javascript
    metadata: {
      budget: "$10,000",
      request_date: "2026-07-07",
      commercial: true,
      isAdmin: true,
      delete_all_records: "DROP TABLE leads;",
      "__proto__": { "polluted": true },
      "inject_script": "<script>alert('XSS')</script>",
      "onload_exploit": "<img src=x onerror=alert(1)>"
    }
    ```
* **Repository Health Checks**:
  - Running `npm run lint` inside `dashboard/` completed successfully.
  - Running `npm run build` inside `dashboard/` completed successfully (`Compiled successfully in 8.5s`, `Finished TypeScript in 4.5min`).
  - Running `npm run test:e2e` inside `dashboard/` completed successfully (`pass 15`, `fail 0`).

---

## 2. Logic Chain
1. **Zod Validation Override Requirement**:
   - In `dashboard/src/lib/validation.ts`, `LeadMetadataSchema` ends in `.strip()` (Observation 1).
   - This means when the client performs validation (`LeadsListSchema.parse(rawList)` in `leads/page.tsx`), all raw custom fields (such as `permit_num`, `expected_revenue`, `employees` or Tenant C's `inject_script`) are silently dropped.
   - Therefore, to process custom metadata dynamically, the validation schema must be updated from `.strip()` to `.passthrough()`.
2. **Metadata Normalization (`MetadataTransformer`)**:
   - Because raw fields can come in with arbitrary casing (camelCase, snake_case, kebab-case) and raw types, we need a normalization step (`MetadataTransformer`) to map keys to Title Case labels and coerce/infer types (currency, date, boolean, list, string) safely.
   - To guard against Prototype Pollution, we must discard keys containing `__proto__`, `constructor`, or `prototype` (as present in Tenant C, Observation 1).
   - To guard against XSS, we must run all text values through a sanitization function (`sanitizeString`) to escape HTML markup tags (such as those in `inject_script` and `onload_exploit`, Observation 1).
3. **Component Registry Mapping**:
   - The registry must map type strings (`currency`, `date`, `boolean`, `list`, `string`) to React components using Framer Motion for micro-interactions and Tailwind CSS conforming to Heritage tokens (Limestone background, charcoal primary, Slate Gray secondary, Boston Clay tertiary).
4. **Leads Page Clean Integration**:
   - Importing the newly registry-backed `CustomMetadataBento` from `@/components/metadata/ComponentRegistry` allows us to remove the local hardcoded 170-line block inside `leads/page.tsx`, rendering custom fields dynamically and securely.

---

## 3. Caveats
* The E2E tests (`scripts/run-e2e.js`) verify general path validation and tenant security checks but do not yet check the dynamic metadata grid. Dynamic component rendering tests will need to be added to the E2E test files in `tests/e2e/`.
* We assume that React 19 and Framer Motion 12 in the project dependencies remain fully compatible with our proposed component layout.

---

## 4. Conclusion
We propose:
1. Creating `dashboard/src/lib/metadata.ts` for the `MetadataTransformer` layer.
2. Creating `dashboard/src/components/metadata/ComponentRegistry.tsx` for the Component Registry and Bento cards.
3. Modifying `dashboard/src/lib/validation.ts` to use `.passthrough()` instead of `.strip()`.
4. Updating `dashboard/src/app/leads/page.tsx` to import the new `CustomMetadataBento` container.

This strategy successfully decouples metadata rendering from the leads UI, handles arbitrary custom tenant fields, and provides solid Prototype Pollution and XSS protection.

---

## 5. Verification Method
To independently verify the implementation plan:
1. Verify repository health remains pristine by running:
   ```bash
   cd dashboard
   npm run lint
   npm run build
   npm run test:e2e
   ```
2. Verify visual output matches Heritage Design guidelines (e.g. color usage, fonts, corner radii) and that dynamic fields are correctly ordered.
3. Invalidation condition: If any validation rule strips dynamic fields, or if dynamic fields in Tenant C cause errors or script execution during testing, the design must be refined.
