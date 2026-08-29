# Milestone 3 Exploration Report: Normalization & Component Registry

This report outlines the codebase analysis, technical architecture, security measures, and implementation strategy for **Milestone 3: Normalization & Component Registry** in the Kenbun codebase.

---

## 1. Codebase Analysis & Existing Layout
An audit of the frontend repository `~/Dev/Kenbun/dashboard` reveals the following:
* **Leads Page (`dashboard/src/app/leads/page.tsx`)**: Renders leads and their associated metadata. Currently, custom metadata fields are rendered by an inline, hardcoded `CustomMetadataBento` component (lines 129–296). This layout is static and only supports six hardcoded keys: `budget`, `request_date`, `commercial`, `location`, `recurring`, and `collections`.
* **Data Validation (`dashboard/src/lib/validation.ts`)**: Defines `LeadMetadataSchema` using Zod. Crucially, the schema ends with `.strip()`, meaning any raw custom metadata keys sent by the API backend that are not explicitly defined in the schema (e.g., `permit_num`, `expected_revenue`) are silently dropped.
* **Heritage Design System (`dashboard/DESIGN.md` & `globals.css`)**:
  - **Colors**: Primary is `#1A1C1E` (charcoal), Secondary is `#6C7278` (grey), Tertiary/Accent is `#B8422E` (Boston Clay / ochre), and Neutral is `#F7F5F2` (matte warm linen).
  - **Typography**: Space Grotesk is mapped to `font-data` for data displays and labels; Public Sans is mapped to `font-sans` and `font-heading`.
  - **Animations**: Framer Motion is used for micro-animations and interactive state transitions.
  - **Borders**: Defined via `border-primary/5` (8% opacity charcoal).

---

## 2. Normalization Layer: `MetadataTransformer`
To process raw, dynamic metadata fields from different tenants, we propose a dedicated normalization layer. It will map raw keys to human-readable labels, sanitize text values, coerce types, and order fields.

**Proposed Location**: `dashboard/src/lib/metadata.ts`

### Implementation Code Design:
```typescript
import { SafeStringSchema } from "./validation";

export type MetadataType = "date" | "currency" | "boolean" | "list" | "string";

export interface NormalizedField {
  key: string;
  label: string;
  type: MetadataType;
  value: any;
  order: number;
}

// Map of known fields, their labels, types, and visual display ordering
export const KNOWN_FIELDS: Record<string, { label: string; type: MetadataType; order: number }> = {
  budget: { label: "Expected Budget", type: "currency", order: 10 },
  request_date: { label: "Requested On", type: "date", order: 20 },
  commercial: { label: "Commercial Project", type: "boolean", order: 30 },
  location: { label: "Target Location", type: "string", order: 40 },
  recurring: { label: "Service Frequency", type: "string", order: 50 },
  collections: { label: "Collections", type: "list", order: 60 },
  permit_num: { label: "Permit Number", type: "string", order: 70 },
  expected_revenue: { label: "Expected Revenue", type: "currency", order: 80 },
  employees: { label: "Employee Count", type: "string", order: 90 },
};

// Safe string sanitation helper to protect against XSS
export function sanitizeString(val: string): string {
  // Prevent double-escaping by first unescaping common entities
  const unescaped = val
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, "/");

  return unescaped
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;")
    .replace(/\//g, "&#x2F;");
}

export class MetadataTransformer {
  /**
   * Normalizes raw lead metadata into structured, ordered, and sanitized fields
   */
  static normalize(rawMetadata: Record<string, any> | null | undefined): NormalizedField[] {
    if (!rawMetadata || typeof rawMetadata !== "object") {
      return [];
    }

    const fields: NormalizedField[] = [];

    for (const [key, value] of Object.entries(rawMetadata)) {
      // 1. Prototype Pollution Defense
      if (key === "__proto__" || key === "constructor" || key === "prototype") {
        continue;
      }

      // Ignore null/undefined values
      if (value === null || value === undefined) {
        continue;
      }

      let label = "";
      let type: MetadataType = "string";
      let order = 1000;

      // 2. Identify known fields or dynamically infer metadata attributes
      if (KNOWN_FIELDS[key]) {
        label = KNOWN_FIELDS[key].label;
        type = KNOWN_FIELDS[key].type;
        order = KNOWN_FIELDS[key].order;
      } else {
        // Convert snake_case/camelCase to Title Case (e.g. expected_revenue -> Expected Revenue)
        label = key
          .replace(/[-_]+/g, " ")
          .replace(/([a-z])([A-Z])/g, "$1 $2")
          .split(" ")
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(" ");

        // Infer type from value structure and key strings
        if (typeof value === "boolean") {
          type = "boolean";
        } else if (Array.isArray(value)) {
          type = "list";
        } else if (typeof value === "number") {
          const lowerKey = key.toLowerCase();
          if (
            lowerKey.includes("budget") ||
            lowerKey.includes("revenue") ||
            lowerKey.includes("cost") ||
            lowerKey.includes("price") ||
            lowerKey.includes("amount")
          ) {
            type = "currency";
          } else {
            type = "string";
          }
        } else if (typeof value === "string") {
          const lowerKey = key.toLowerCase();
          const cleanValue = value.trim();

          if (
            /^\d{4}-\d{2}-\d{2}$/.test(cleanValue) ||
            (!isNaN(Date.parse(cleanValue)) &&
              (lowerKey.includes("date") || lowerKey.includes("time")))
          ) {
            type = "date";
          } else if (
            cleanValue.startsWith("$") ||
            lowerKey.includes("budget") ||
            lowerKey.includes("revenue") ||
            lowerKey.includes("cost") ||
            lowerKey.includes("price") ||
            lowerKey.includes("amount")
          ) {
            type = "currency";
          } else {
            type = "string";
          }
        }
      }

      // 3. Coerce and sanitize values securely
      let coercedValue: any = value;

      if (type === "currency") {
        if (typeof value === "number") {
          coercedValue = value;
        } else if (typeof value === "string") {
          const cleaned = value.replace(/[^0-9.]/g, "");
          const parsed = parseFloat(cleaned);
          coercedValue = isNaN(parsed) ? 0 : parsed;
        } else {
          coercedValue = 0;
        }
      } else if (type === "boolean") {
        if (typeof value === "boolean") {
          coercedValue = value;
        } else if (typeof value === "string") {
          coercedValue = value.toLowerCase() === "true" || value === "1";
        } else if (typeof value === "number") {
          coercedValue = value === 1;
        } else {
          coercedValue = false;
        }
      } else if (type === "list") {
        if (Array.isArray(value)) {
          coercedValue = value.map((item) =>
            typeof item === "string" ? sanitizeString(item) : String(item)
          );
        } else if (typeof value === "string") {
          coercedValue = value.split(",").map((s) => sanitizeString(s.trim()));
        } else {
          coercedValue = [sanitizeString(String(value))];
        }
      } else if (type === "date") {
        coercedValue = sanitizeString(String(value));
      } else {
        coercedValue = sanitizeString(String(value));
      }

      fields.push({
        key,
        label,
        type,
        value: coercedValue,
        order,
      });
    }

    // 4. Sort fields using the strict visual display order
    return fields.sort((a, b) => {
      if (a.order !== b.order) {
        return a.order - b.order;
      }
      return a.label.localeCompare(b.label);
    });
  }
}
```

---

## 3. Component Registry & Bento Cards
The Component Registry maps each normalized metadata type to a React card styled according to the Heritage Design tokens. It uses Framer Motion for premium hover states and entrance transitions.

**Proposed Location**: `dashboard/src/components/metadata/ComponentRegistry.tsx`

### Implementation Code Design:
```typescript
import React from "react";
import { motion } from "framer-motion";
import {
  CircleDollarSign,
  Calendar,
  CheckSquare,
  Square,
  Tag,
  Repeat,
  Database,
  Briefcase,
  Layers,
  HelpCircle
} from "lucide-react";
import { NormalizedField, MetadataTransformer } from "@/lib/metadata";

// Formatter helpers
const formatBudget = (value: number) => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(value);
};

const formatDate = (dateStr: string) => {
  try {
    const date = new Date(dateStr + "T00:00:00");
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric"
    });
  } catch {
    return dateStr;
  }
};

// Common motion transition parameters for entrance and premium hover interactions
const getMotionProps = (index: number) => ({
  initial: { opacity: 0, y: 15 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] },
  whileHover: { scale: 1.01, translateY: -2 }
});

// Card Base Structure with Heritage Design System tokens
interface CardProps {
  field: NormalizedField;
  index: number;
  colSpan?: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

const BaseCard: React.FC<CardProps> = ({ field, index, colSpan = "md:col-span-1", icon, children }) => {
  return (
    <motion.div
      {...getMotionProps(index)}
      className={`${colSpan} bg-card border border-primary/5 p-5 rounded-sm relative overflow-hidden group flex flex-col justify-between min-h-[120px] transition-all duration-300 shadow-sm`}
    >
      {/* Premium Glassmorphic Mesh Hover Effect */}
      <div className="absolute inset-0 bg-gradient-to-br from-tertiary/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-black uppercase tracking-wider text-secondary font-data">
          {field.label}
        </span>
        <div className="text-secondary group-hover:text-tertiary transition-colors duration-300">
          {icon}
        </div>
      </div>
      
      <div className="mt-4 flex-1 flex flex-col justify-end">
        {children}
      </div>
    </motion.div>
  );
};

// 1. Currency Card Component (spans 2 columns)
export const CurrencyCard: React.FC<{ field: NormalizedField; index: number }> = ({ field, index }) => (
  <BaseCard
    field={field}
    index={index}
    colSpan="md:col-span-2"
    icon={<CircleDollarSign className="w-4.5 h-4.5" />}
  >
    <span className="text-3xl font-black italic tracking-tighter text-primary font-sans leading-none">
      {formatBudget(field.value)}
    </span>
  </BaseCard>
);

// 2. Date Card Component
export const DateCard: React.FC<{ field: NormalizedField; index: number }> = ({ field, index }) => (
  <BaseCard
    field={field}
    index={index}
    icon={<Calendar className="w-4.5 h-4.5" />}
  >
    <span className="text-sm font-bold text-primary font-data">
      {formatDate(field.value)}
    </span>
  </BaseCard>
);

// 3. Boolean Card Component
export const BooleanCard: React.FC<{ field: NormalizedField; index: number }> = ({ field, index }) => {
  const isTrue = field.value === true;
  return (
    <BaseCard
      field={field}
      index={index}
      icon={isTrue ? <CheckSquare className="w-4.5 h-4.5" /> : <Square className="w-4.5 h-4.5" />}
    >
      <div className="flex items-center gap-2">
        <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded-sm border font-data ${
          isTrue 
            ? "bg-tertiary/10 text-tertiary border-tertiary/20" 
            : "bg-secondary/10 text-secondary border-secondary/20"
        }`}>
          {isTrue ? "Commercial" : "Residential"}
        </span>
      </div>
    </BaseCard>
  );
};

// 4. List Card Component (spans 2 columns if length > 2)
export const ListCard: React.FC<{ field: NormalizedField; index: number }> = ({ field, index }) => {
  const items = Array.isArray(field.value) ? field.value : [];
  const colSpan = items.length > 2 ? "md:col-span-2" : "md:col-span-1";
  
  return (
    <BaseCard
      field={field}
      index={index}
      colSpan={colSpan}
      icon={<Tag className="w-4.5 h-4.5" />}
    >
      <div className="flex flex-wrap gap-1.5 mt-2">
        {items.map((item: string, idx: number) => (
          <span
            key={idx}
            className="bg-primary/5 text-primary border border-primary/5 text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-sm hover:border-tertiary/20 hover:bg-tertiary/5 transition-all duration-200"
          >
            {item}
          </span>
        ))}
      </div>
    </BaseCard>
  );
};

// 5. String Card Component (with dynamic icon mapping)
export const StringCard: React.FC<{ field: NormalizedField; index: number }> = ({ field, index }) => {
  let icon = <Database className="w-4.5 h-4.5" />;
  const lowerKey = field.key.toLowerCase();
  
  if (lowerKey.includes("location") || lowerKey.includes("address")) {
    icon = <Database className="w-4.5 h-4.5" />; // maps to data/location database icon
  } else if (lowerKey.includes("recurring") || lowerKey.includes("frequency")) {
    icon = <Repeat className="w-4.5 h-4.5" />;
  } else if (lowerKey.includes("permit")) {
    icon = <Layers className="w-4.5 h-4.5" />;
  } else if (lowerKey.includes("employee")) {
    icon = <Briefcase className="w-4.5 h-4.5" />;
  }
  
  return (
    <BaseCard field={field} index={index} icon={icon}>
      <span className="text-sm font-bold text-primary font-data break-words">
        {field.value}
      </span>
    </BaseCard>
  );
};

// Registry Mapping Types to Components
export const ComponentRegistry: Record<
  NormalizedField["type"],
  React.ComponentType<{ field: NormalizedField; index: number }>
> = {
  currency: CurrencyCard,
  date: DateCard,
  boolean: BooleanCard,
  list: ListCard,
  string: StringCard
};

// Dynamic Bento Container Component
interface CustomMetadataBentoProps {
  metadata: Record<string, any> | null | undefined;
}

export const CustomMetadataBento: React.FC<CustomMetadataBentoProps> = ({ metadata }) => {
  if (!metadata) return null;
  
  const normalizedFields = MetadataTransformer.normalize(metadata);
  
  if (normalizedFields.length === 0) return null;
  
  return (
    <div className="space-y-4">
      <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-tertiary font-data">
        Project Proposal Metadata
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-data">
        {normalizedFields.map((field: NormalizedField, index: number) => {
          const CardComponent = ComponentRegistry[field.type] || StringCard;
          return <CardComponent key={field.key} field={field} index={index} />;
        })}
      </div>
    </div>
  );
};
```

---

## 4. Integration Blueprint

### Step A: Update `dashboard/src/lib/validation.ts`
Modify the `LeadMetadataSchema` to change `.strip()` to `.passthrough()`. This lets raw, custom metadata fields pass validation so they can be processed dynamically by the normalization layer.

```typescript
// Replace lines 49-56 in dashboard/src/lib/validation.ts:
export const LeadMetadataSchema = z.object({
  budget: BudgetSchema,
  request_date: RequestDateSchema,
  commercial: CommercialSchema,
  location: SafeStringSchema.optional().nullable(),
  collections: z.array(SafeStringSchema).optional().nullable(),
  recurring: SafeStringSchema.optional().nullable(),
}).passthrough(); // Changed from .strip() to retain dynamic custom fields
```

### Step B: Integrate with `dashboard/src/app/leads/page.tsx`
Remove the inline definition of `CustomMetadataBento` (lines 129–296) and import the registry version:

```typescript
// Add import at the top of leads/page.tsx:
import { CustomMetadataBento } from "@/components/metadata/ComponentRegistry";

// Remove the local definition of:
// const CustomMetadataBento = ({ metadata }: { metadata: Lead["metadata"] }) => { ... };
```

---

## 5. Security & Safety Guidelines

Because we are processing arbitrary user-provided metadata, the implementation must prevent the following vulnerabilities:

1. **Prototype Pollution**:
   - Attackers might inject metadata with keys like `__proto__` or `constructor` to pollute JavaScript objects.
   - **Defense**: The `MetadataTransformer` uses an explicit guard:
     ```typescript
     if (key === "__proto__" || key === "constructor" || key === "prototype") {
       continue;
     }
     ```
2. **Cross-Site Scripting (XSS)**:
   - Attackers might submit script strings (e.g., `<script>alert('XSS')</script>` or SVG image exploits).
   - **Defense**: All string values are sanitized before display using `sanitizeString()`, replacing active HTML tokens with their escaped entity equivalents (`&` -> `&amp;`, `<` -> `&lt;`, etc.). Additionally, React renders value content using safe elements (`<span>`, `<div>`) instead of using raw HTML injectors.

---

## 6. Pre-Implementation Health Check & Verification Plan

To verify this implementation is clean and does not break existing flows:

1. **Run Pre-Checks**:
   Verify the dashboard builds, lints, and E2E tests pass before changes:
   ```bash
   npm run lint
   npm run build
   npm run test:e2e
   ```
   *Current status: All checks successfully passed.*

2. **Validate Mock Integration**:
   - Check `scripts/mock-api.js` under Tenant C. Verify it includes adversarial custom fields such as `inject_script`, `onload_exploit`, and `__proto__`.
   - Start the development server and inspect the dynamic bento layout for Tenant C.
   - Confirm that `inject_script` is rendered as plain escaped text (`&lt;script&gt;...`) and is not executed.
   - Confirm that the `__proto__` properties did not pollute the runtime objects.
