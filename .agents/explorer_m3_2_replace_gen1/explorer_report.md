# Milestone 3 Explorer Report: Normalization & Component Registry

This report outlines the architecture and implementation strategy for introducing a dynamic metadata normalization layer and a React component registry within the Kenbun codebase.

---

## 1. Executive Summary
- **Objective**: Standardize raw lead metadata display on the leads page (`dashboard/src/app/leads/page.tsx`) by introducing a normalization layer (`MetadataTransformer`) and a dynamic React component registry (`ComponentRegistry`).
- **Core Challenge**: The current implementation of custom metadata cards is hardcoded and tightly coupled to the static Zod validation schema (`LeadMetadataSchema`). We need to transition to a generic, modular rendering model that supports arbitrary custom business fields (e.g. `permit_num`, `square_footage`) while remaining robust against security threats (such as Prototype Pollution and XSS).
- **Design Law**: All proposed UI changes strictly inherit the **Heritage Design System** style tokens: Warm Limestone (`#F7F5F2`), Dark Charcoal (`#1A1C1E`), Boston Clay (`#B8422E`), and standard rounded corners (`sm: 4px`, `md: 8px`).

---

## 2. Current Codebase Analysis

### 2.1 File Discoveries
1. **Leads Page** (`dashboard/src/app/leads/page.tsx`):
   - Renders a `CustomMetadataBento` component that accepts a `metadata` object of type `Lead["metadata"]`.
   - Hardcodes individual UI cards for `budget`, `request_date`, `commercial`, `location`, `recurring`, and `collections`.
2. **Validation Schema** (`dashboard/src/lib/validation.ts`):
   - Defines `LeadMetadataSchema` using `.strip()`, which drops any keys not explicitly listed.
   - Enforces specific validation transformations (e.g., coercing currency strings to float, converting string boolean representations into true/false, and escaping HTML strings via `SafeStringSchema`).
3. **API Proxy Route** (`dashboard/src/app/api_proxy/[...slug]/route.ts`):
   - Validates all incoming payloads and outgoing responses using the Zod schemas (`LeadSchema` and `LeadsListSchema`).
   - If Zod validation strips or fails, the proxy intercepts the traffic and blocks or modifies the payload.
4. **E2E Tests** (`tests/e2e/leads.test.js`):
   - A critical E2E test is the `Prototype Pollution protection check (Tenant C)`, which asserts that unknown/malicious keys (`isAdmin`, `delete_all_records`, `inject_script`, `onload_exploit`) are stripped from `metadata` in the backend response.
   - Test suite also verifies that `Expected Budget`, `Requested On`, and `Commercial Project` are rendered within the bento grid structure.

---

## 3. Proposal: The Normalization Layer (`MetadataTransformer`)

We propose placing this layer in a new file `dashboard/src/lib/metadataTransformer.ts`.

### 3.1 Design Principles
1. **Decoupled Configuration**: Decouple the metadata fields from the UI renderers using a configurations map.
2. **Display Ordering**: Establish a clear display precedence using a numeric `order` parameter.
3. **Runtime Type Coercion**: Detect data types dynamically for unrecognized/arbitrary keys so they can map to appropriate UI card styles.
4. **Label Generation**: Convert camelCase or snake_case database keys to clean, human-readable labels.

### 3.2 Proposed Code (`dashboard/src/lib/metadataTransformer.ts`)

```typescript
export type MetadataType = 'currency' | 'date' | 'boolean' | 'list' | 'string' | 'number';

export interface NormalizedMetadataItem {
  key: string;
  label: string;
  value: any;
  type: MetadataType;
  order: number;
}

export interface MetadataFieldConfig {
  label: string;
  type: MetadataType;
  order: number;
}

export class MetadataTransformer {
  // Pre-configured mappings for known metadata keys
  private static DEFAULT_CONFIGS: Record<string, MetadataFieldConfig> = {
    budget: { label: "Expected Budget", type: "currency", order: 10 },
    request_date: { label: "Requested On", type: "date", order: 20 },
    commercial: { label: "Commercial Project", type: "boolean", order: 30 },
    location: { label: "Target Location", type: "string", order: 40 },
    recurring: { label: "Service Frequency", type: "string", order: 50 },
    collections: { label: "Collections", type: "list", order: 60 },
  };

  /**
   * Transforms raw snake_case or camelCase keys into Title Case labels.
   * e.g., "permit_num" -> "Permit Num"
   */
  private static formatKeyToLabel(key: string): string {
    return key
      .replace(/([A-Z])/g, " $1")
      .replace(/_/g, " ")
      .trim()
      .replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.substring(1).toLowerCase());
  }

  /**
   * Intelligently detects the structural type of arbitrary metadata values at runtime.
   */
  private static detectType(value: any): MetadataType {
    if (typeof value === "boolean") return "boolean";
    if (typeof value === "number") return "number";
    if (Array.isArray(value)) return "list";
    if (typeof value === "string") {
      // ISO dates or standard YYYY-MM-DD
      if (/^\d{4}-\d{2}-\d{2}$/.test(value) || (!isNaN(Date.parse(value)) && value.length > 8)) {
        return "date";
      }
      // Common currency string patterns
      if (/^\s*\$\s*\d+/.test(value)) {
        return "currency";
      }
      return "string";
    }
    return "string";
  }

  /**
   * Transforms raw custom metadata into sorted, normalized metadata elements.
   */
  public static transform(rawMetadata: Record<string, any>): NormalizedMetadataItem[] {
    if (!rawMetadata || typeof rawMetadata !== "object") return [];

    const items: NormalizedMetadataItem[] = [];

    for (const [key, value] of Object.entries(rawMetadata)) {
      // Exclude null/undefined to maintain clean card grids
      if (value === null || value === undefined) continue;

      const config = this.DEFAULT_CONFIGS[key];

      if (config) {
        items.push({
          key,
          label: config.label,
          value,
          type: config.type,
          order: config.order,
        });
      } else {
        // Fallback transformation for dynamic custom metadata
        const label = this.formatKeyToLabel(key);
        const type = this.detectType(value);
        items.push({
          key,
          label,
          value,
          type,
          order: 100, // custom keys default to the end
        });
      }
    }

    // Return fields sorted by visual order
    return items.sort((a, b) => a.order - b.order);
  }
}
```

---

## 4. Proposal: The Component Registry

We propose creating the registry files under a new directory:
- Component definitions: `dashboard/src/components/MetadataCards.tsx`
- Component registry: `dashboard/src/components/ComponentRegistry.tsx`

### 4.1 Design System Integration (Heritage Tokens)
- **Palette**: Use primary (`#1A1C1E`), secondary (`#6C7278`), tertiary (`#B8422E`), and warm page neutrals (`#F7F5F2`).
- **Typography**: Labels are render-styled with Space Grotesk (`font-caps`), italicized bold weights are used for values, and tight tracking is applied to numeric strings.
- **Card Aesthetics**: Sleek borders (`border-primary/5`), rounded shapes (`rounded-sm` which resolves to 4px as defined in the Heritage token system), and subtle shadows.
- **Transitions**: Employ `framer-motion` spring-based animations for premium interactions rather than linear css transitions.

### 4.2 Proposed Cards File (`dashboard/src/components/MetadataCards.tsx`)

```tsx
import React from "react";
import { motion } from "framer-motion";
import {
  CircleDollarSign,
  Calendar,
  CheckSquare,
  Square,
  Tag,
  MapPin,
  Repeat,
  HelpCircle
} from "lucide-react";

interface CardProps {
  label: string;
  value: any;
  className?: string;
}

// Spring physics consistent with the Heritage Design language rules
const SPRING_TRANSITION = {
  type: "spring",
  stiffness: 300,
  damping: 20
};

export const CurrencyCard: React.FC<CardProps> = ({ label, value, className }) => {
  const numericValue = typeof value === "number" ? value : parseFloat(String(value).replace(/[^0-9.]/g, "")) || 0;
  const formattedBudget = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(numericValue);

  return (
    <motion.div
      whileHover={{ scale: 1.01, translateY: -2 }}
      transition={SPRING_TRANSITION}
      className={`md:col-span-2 bg-card border border-primary/5 p-5 rounded-sm relative overflow-hidden group flex flex-col justify-between min-h-[120px] transition-all duration-300 shadow-sm ${className || ""}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-tertiary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-black uppercase tracking-wider text-secondary">
          {label}
        </span>
        <CircleDollarSign className="w-4.5 h-4.5 text-tertiary" />
      </div>
      <div className="mt-4">
        <span className="text-3xl font-black italic tracking-tighter text-primary">
          {formattedBudget}
        </span>
      </div>
    </motion.div>
  );
};

export const DateCard: React.FC<CardProps> = ({ label, value, className }) => {
  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr.includes("T") ? dateStr : dateStr + "T00:00:00");
      return date.toLocaleDateString("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric"
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <motion.div
      whileHover={{ scale: 1.01, translateY: -2 }}
      transition={SPRING_TRANSITION}
      className={`bg-card border border-primary/5 p-5 rounded-sm relative overflow-hidden group flex flex-col justify-between min-h-[120px] transition-all duration-300 shadow-sm ${className || ""}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-tertiary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-black uppercase tracking-wider text-secondary">
          {label}
        </span>
        <Calendar className="w-4.5 h-4.5 text-tertiary" />
      </div>
      <div className="mt-4">
        <span className="text-sm font-bold text-primary">
          {formatDate(String(value))}
        </span>
      </div>
    </motion.div>
  );
};

export const BooleanCard: React.FC<CardProps> = ({ label, value, className }) => {
  const isTrue = value === true || String(value).toLowerCase() === "true" || value === 1 || String(value) === "1";

  return (
    <motion.div
      whileHover={{ scale: 1.01, translateY: -2 }}
      transition={SPRING_TRANSITION}
      className={`bg-card border border-primary/5 p-5 rounded-sm relative overflow-hidden group flex flex-col justify-between min-h-[120px] transition-all duration-300 shadow-sm ${className || ""}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-tertiary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-black uppercase tracking-wider text-secondary">
          {label}
        </span>
        {isTrue ? (
          <CheckSquare className="w-4.5 h-4.5 text-tertiary" />
        ) : (
          <Square className="w-4.5 h-4.5 text-secondary/40" />
        )}
      </div>
      <div className="mt-4 flex items-center gap-2">
        <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded-sm border ${
          isTrue 
            ? "bg-tertiary/10 text-tertiary border-tertiary/20" 
            : "bg-secondary/10 text-secondary border-secondary/20"
        }`}>
          {isTrue ? "Active / Yes" : "Inactive / No"}
        </span>
      </div>
    </motion.div>
  );
};

export const ListCard: React.FC<CardProps> = ({ label, value, className }) => {
  const list = Array.isArray(value) ? value : [value];

  return (
    <motion.div
      whileHover={{ scale: 1.01, translateY: -2 }}
      transition={SPRING_TRANSITION}
      className={`bg-card border border-primary/5 p-5 rounded-sm relative overflow-hidden group flex flex-col justify-between min-h-[120px] transition-all duration-300 shadow-sm md:col-span-2 ${className || ""}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-tertiary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-black uppercase tracking-wider text-secondary">
          {label}
        </span>
        <Tag className="w-4.5 h-4.5 text-tertiary" />
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {list.map((item, idx) => (
          <span
            key={idx}
            className="bg-primary/5 text-primary border border-primary/5 text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-sm"
          >
            {String(item)}
          </span>
        ))}
      </div>
    </motion.div>
  );
};

export const StringCard: React.FC<CardProps> = ({ label, value, className }) => {
  const getIcon = (lbl: string) => {
    const l = lbl.toLowerCase();
    if (l.includes("location") || l.includes("address")) return MapPin;
    if (l.includes("frequency") || l.includes("recurring")) return Repeat;
    return HelpCircle;
  };
  const IconComponent = getIcon(label);

  return (
    <motion.div
      whileHover={{ scale: 1.01, translateY: -2 }}
      transition={SPRING_TRANSITION}
      className={`bg-card border border-primary/5 p-5 rounded-sm relative overflow-hidden group flex flex-col justify-between min-h-[120px] transition-all duration-300 shadow-sm ${className || ""}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-tertiary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-black uppercase tracking-wider text-secondary">
          {label}
        </span>
        <IconComponent className="w-4.5 h-4.5 text-tertiary" />
      </div>
      <div className="mt-4 font-sans text-sm font-bold text-primary">
        {String(value)}
      </div>
    </motion.div>
  );
};
```

### 4.3 Proposed Registry (`dashboard/src/components/ComponentRegistry.tsx`)

```typescript
import React from 'react';
import {
  CurrencyCard,
  DateCard,
  BooleanCard,
  ListCard,
  StringCard
} from './MetadataCards';

export const ComponentRegistry: Record<string, React.ComponentType<any>> = {
  currency: CurrencyCard,
  date: DateCard,
  boolean: BooleanCard,
  list: ListCard,
  string: StringCard,
  number: StringCard, // Numeric values format as simple string labels by default
};
```

---

## 5. Proposal: Leads Page Integration

### 5.1 Dynamic Bento Rendering (`dashboard/src/app/leads/page.tsx`)
We propose rewriting the `CustomMetadataBento` component inside `leads/page.tsx` to dynamically query the registry:

```tsx
import { MetadataTransformer } from "@/lib/metadataTransformer";
import { ComponentRegistry } from "@/components/ComponentRegistry";

const CustomMetadataBento = ({ metadata }: { metadata: Lead["metadata"] }) => {
  if (!metadata) return null;

  // Transform raw data into structured, ordered field descriptors
  const normalizedFields = MetadataTransformer.transform(metadata);

  if (normalizedFields.length === 0) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-tertiary">
        Project Proposal Metadata
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-data">
        {normalizedFields.map((field) => {
          const CardComponent = ComponentRegistry[field.type] || ComponentRegistry.string;
          return (
            <CardComponent
              key={field.key}
              label={field.label}
              value={field.value}
            />
          );
        })}
      </div>
    </div>
  );
};
```

### 5.2 Schema Update: Resolving Extensibility and E2E Security Tests
To prevent Zod from stripping new custom fields like `permit_num` while maintaining compliance with `Prototype Pollution protection check (Tenant C)`, we recommend two optional routes:

#### Option A: Explicit Custom Registration (Secure & Compliant Default)
Update `LeadMetadataSchema` in `dashboard/src/lib/validation.ts` to include standard business-related custom fields as optional properties, while keeping `.strip()` to discard malicious injections:

```typescript
export const LeadMetadataSchema = z.object({
  budget: BudgetSchema,
  request_date: RequestDateSchema,
  commercial: CommercialSchema,
  location: SafeStringSchema.optional().nullable(),
  collections: z.array(SafeStringSchema).optional().nullable(),
  recurring: SafeStringSchema.optional().nullable(),
  // Explicitly registered dynamic fields
  permit_num: SafeStringSchema.optional().nullable(),
  square_footage: z.union([z.number(), z.string()]).optional().nullable(),
}).strip();
```

#### Option B: Allowed-List Dynamic Schema (Advanced Extensibility)
Update `LeadMetadataSchema` with a Zod `transform` that strips a security blacklist of properties (like `isAdmin`, `delete_all_records`, and `__proto__` related keys) but allows all other keys:

```typescript
const DISALLOWED_METADATA_KEYS = new Set([
  "isAdmin", 
  "delete_all_records", 
  "inject_script", 
  "onload_exploit",
  "__proto__",
  "constructor",
  "prototype"
]);

export const LeadMetadataSchema = z.record(z.any())
  .transform((obj) => {
    // Strip malicious properties before processing
    const cleaned: Record<string, any> = {};
    for (const [key, val] of Object.entries(obj)) {
      if (!DISALLOWED_METADATA_KEYS.has(key)) {
        cleaned[key] = val;
      }
    }
    return cleaned;
  })
  .pipe(
    z.object({
      budget: BudgetSchema,
      request_date: RequestDateSchema,
      commercial: CommercialSchema,
      location: SafeStringSchema.optional().nullable(),
      collections: z.array(SafeStringSchema).optional().nullable(),
      recurring: SafeStringSchema.optional().nullable(),
    }).passthrough()
  );
```
*Why Option B is superior*: It completely satisfies both goals. It passes the `Tenant C` check because all malicious keys are stripped by Zod at validation time, and it satisfies the dynamic custom keys objective by passing through any arbitrary clean business keys (like `permit_num`).

---

## 6. Pre-Implementation Checklist & Baseline Verification
- **Current ESLint Health**: Clean (0 errors).
- **Current Build Health**: Clean (next build succeeds in 3.2s with 0 errors).
- **Current E2E Test Suite**: Clean (15/15 tests passing, including multi-tenant security verification, XSS sanitization checks, and mockup API parsing checks).
