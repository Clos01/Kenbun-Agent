import { z } from "zod";

export const SafeStringSchema = z.string().transform((val) => {
  // Prevent double-escaping by first unescaping entities if they exist
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
});

// BudgetSchema: Union of number or string (coerce currency strings like "$10,000" to float/number)
export const BudgetSchema = z.union([z.number(), z.string()]).transform((val) => {
  if (typeof val === "number") {
    return val;
  }
  // Coerce currency strings: remove $, commas, spaces, etc.
  const cleaned = val.replace(/[^0-9.]/g, "");
  const parsed = parseFloat(cleaned);
  return isNaN(parsed) ? 0 : parsed;
});

// RequestDateSchema: Regex YYYY-MM-DD format string
export const RequestDateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Invalid date format");

// CommercialSchema: Coerced to boolean (e.g. "true" or "1" -> true)
export const CommercialSchema = z.union([z.boolean(), z.string(), z.number()]).transform((val) => {
  if (typeof val === "boolean") return val;
  if (typeof val === "string") {
    return val.toLowerCase() === "true" || val === "1";
  }
  if (typeof val === "number") {
    return val === 1;
  }
  return false;
});

// LeadMetadataSchema
export const LeadMetadataSchema = z.object({
  budget: BudgetSchema,
  request_date: RequestDateSchema,
  commercial: CommercialSchema,
  location: SafeStringSchema.optional().nullable(),
  collections: z.array(SafeStringSchema).optional().nullable(),
  recurring: SafeStringSchema.optional().nullable(),
}).strip();

// InteractionLogSchema
export const InteractionLogSchema = z.object({
  date: z.string(),
  agent: SafeStringSchema,
  action: SafeStringSchema,
  summary: SafeStringSchema,
}).strip();

// LeadSchema
export const LeadSchema = z.object({
  id: z.string().uuid(),
  name: SafeStringSchema,
  tenant_id: z.string().uuid().optional().nullable(),
  industry: SafeStringSchema.optional().default("Unknown"),
  creation_date: z.string().optional().default(() => new Date().toISOString()),
  status: z.enum(["new", "contacted", "qualified", "converted", "lost"]).optional().default("new"),
  email: z.string().optional().default(""),
  phone: SafeStringSchema.optional().default(""),
  address: SafeStringSchema.optional().default(""),
  score: z.number().min(0).max(100).optional().default(0),
  notes: SafeStringSchema.optional().default(""),
  source: SafeStringSchema.optional().default("Direct"),
  interaction_history: z.array(InteractionLogSchema).optional().default([]),
  metadata: LeadMetadataSchema,
}).strip();

export type Lead = z.infer<typeof LeadSchema>;

export const LeadsListSchema = z.array(LeadSchema);
