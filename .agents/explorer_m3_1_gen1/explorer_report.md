# Explorer Report: Milestone 3 - Normalization Layer & Component Registry

## Executive Summary
This report outlines the proposed strategy for implementing the metadata normalization layer (`MetadataTransformer`) and the dynamic UI component mapping (`Component Registry`) for Milestone 3 of the Kenbun dashboard application. The proposed design transitions the leads page metadata grid from a static, hardcoded rendering system into an extensible, type-safe, dynamic visual engine. It strictly adheres to the Heritage Design System styling tokens (Limestone, Boston Clay, Space Grotesk) and introduces a "Senior Version" dynamic fallback type inference mechanism to prevent regressions or styling debt when processing unregistered custom metadata keys.

---

## 1. Codebase Baseline & Observations
We analyzed the codebase structure and existing frontend layouts:
- **Filespace Layout**: 
  - The React app is stored in the `dashboard/` directory.
  - The leads list and detail inspector are defined in `dashboard/src/app/leads/page.tsx`.
  - The Zod validation schema is located in `dashboard/src/lib/validation.ts`.
- **Target Page**: `leads/page.tsx` contains the `CustomMetadataBento` component (lines 129–296), which currently processes and renders a fixed set of fields (`budget`, `request_date`, `commercial`, `location`, `recurring`, `collections`) by duplicating Framer Motion containers and icon elements.
- **Design Tokens (`dashboard/DESIGN.md` & `globals.css`)**:
  - `primary` color: `#1A1C1E` (Dark Charcoal)
  - `secondary` color: `#6C7278` (Slate Gray)
  - `tertiary` (interactive accent): `#B8422E` (Boston Clay)
  - `neutral` background: `#F7F5F2` (Matte paper/Limestone)
  - Rounded corners: `sm: 4px`, `md: 8px`
  - Font families: Public Sans (general/headings), Space Grotesk (label-caps/data fields, styled as `font-data`), Space Mono (monospaced data tags/values).
- **Linter & Tests Check**:
  - ESLint ran with 0 errors.
  - Next.js production build succeeded completely.
  - All 15 E2E tests (`npm run test:e2e`) passed successfully.

---

## 2. Proposed Architectural Strategy

### A. The Normalization Layer (`MetadataTransformer`)
We propose creating `MetadataTransformer` inside `dashboard/src/lib/metadataTransformer.ts`.
- **Goal**: Standardize incoming metadata keys (both registered and dynamic) into a common shape containing:
  - `key`: The raw identifier (e.g. `budget`).
  - `label`: Human-readable label (e.g. "Expected Budget").
  - `type`: Discovered type matching a supported component (e.g. `"currency"`, `"date"`, `"boolean"`, `"list"`, `"string"`).
  - `value`: Sanitized value.
  - `order`: Integer defining layout precedence.
- **Registry & Ordering**: We establish a static registry `FIELD_REGISTRY` mapping expected fields to their labels, types, and visual ordering.
- **Dynamic Fallbacks**: Unregistered fields undergo name-beautification (translating snake_case to Title Case) and type inference (identifying dates, lists, booleans, and matching key suffixes for financial values like "cost", "revenue", or "budget" to map to `"currency"`).

### B. The Component Registry (`MetadataRegistry.tsx`)
We propose creating the Component Registry in `dashboard/src/components/MetadataRegistry.tsx`.
- **Goal**: Establish a React dictionary (`METADATA_COMPONENTS`) mapping `MetadataType` to styling-compliant React components.
- **Visual Design**: Uses a shared, interactive card wrapper `MetadataCardContainer` implementing:
  - Framer Motion micro-interactions: hover scaling (`scale: 1.01`, translation `translateY: -2`), and fade-in entries.
  - A premium mesh-gradient color wash (`from-tertiary/[0.02] to-transparent`) activated on hover.
  - Heritage design borders (`border-primary/5`), matte finish backgrounds (`bg-card`), Space Grotesk fonts (`font-data`), and small border-radii (`rounded-sm`).
- **Dynamic Grid Layout Context**: The `ListCard` evaluates sibling context (e.g. checks if a `recurring` field is rendered elsewhere) to dynamically swap column spans (`md:col-span-1` vs `md:col-span-2`), keeping the Bento grid balanced and aligned.

---

## 3. Recommended Directory & Class Structure

### File 1: `dashboard/src/lib/metadataTransformer.ts`
```typescript
export type MetadataType = "currency" | "date" | "boolean" | "list" | "string";

export interface NormalizedMetadataField {
  key: string;
  label: string;
  type: MetadataType;
  value: any;
  order: number;
}

export class MetadataTransformer {
  static transform(rawMetadata: Record<string, any> | undefined | null): NormalizedMetadataField[];
  private static beautifyKey(key: string): string;
  private static inferType(key: string, value: any): MetadataType;
}
```

### File 2: `dashboard/src/components/MetadataRegistry.tsx`
```typescript
import React from "react";

export const MetadataCardContainer: React.FC<{
  label: string;
  icon: React.ReactNode;
  colSpan?: string;
  children: React.ReactNode;
}>;

export const CurrencyCard: React.FC<{ field: NormalizedMetadataField }>;
export const DateCard: React.FC<{ field: NormalizedMetadataField }>;
export const BooleanCard: React.FC<{ field: NormalizedMetadataField }>;
export const ListCard: React.FC<{ field: NormalizedMetadataField; hasRecurring?: boolean }>;
export const StringCard: React.FC<{ field: NormalizedMetadataField }>;

export const METADATA_COMPONENTS: Record<
  MetadataType,
  React.ComponentType<{ field: NormalizedMetadataField }>
>;
```

### Integration in `dashboard/src/app/leads/page.tsx`
Replace the static rendering tree of `CustomMetadataBento` with:
```typescript
const CustomMetadataBento = ({ metadata }: { metadata: Lead["metadata"] }) => {
  if (!metadata) return null;
  const fields = MetadataTransformer.transform(metadata);
  const hasRecurring = fields.some((f) => f.key === "recurring");

  return (
    <div className="space-y-4">
      <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-tertiary">
        Project Proposal Metadata
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-data">
        <AnimatePresence mode="popLayout">
          {fields.map((field) => {
            const Component = METADATA_COMPONENTS[field.type];
            if (!Component) return null;
            if (field.type === "list") {
              return <ListCard key={field.key} field={field} hasRecurring={hasRecurring} />;
            }
            return <Component key={field.key} field={field} />;
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};
```

---

## 4. Verification & Testing Strategy
Independent verification must ensure both visual precision and programmatic robustness:
1. **Linter & Compiler Verification**:
   - Run `npm run lint` and `npm run build` to guarantee compilation and clean imports.
2. **E2E Compatibility Test Suite**:
   - Run `npm run test:e2e` to verify that all 15 tests pass. The dynamic components must output labels and formatting matching the assertions in `leads.test.js` exactly (specifically "Expected Budget", "Requested On", "Commercial Project", "Target Location", and "Collections").
3. **Dynamic Field Rendering Audit**:
   - Inject a custom test lead in `mock-api.js` (or post via mock endpoint) containing unexpected fields (e.g. `permit_num: "PM-98101"`, `expected_revenue: 145000`) and visually verify they render as Title Case labels in the expected sort layout order with appropriate icons.
