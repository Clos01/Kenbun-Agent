import sys
from pathlib import Path

sys.path.insert(0, str(Path("core").resolve()))

from tools.infrastructure.server import consult_supervisor

proposal = "Implement dynamic metadata transformer and component registry for the bento grid display of project proposal metadata. Ensure strict typescript validation without 'any' type, and correct formatting of currency, dates, booleans, arrays, and standard strings, conforming to the Heritage design system."

snippet = r"""
// --- dashboard/src/lib/metadataTransformer.ts ---
export type MetadataType = "currency" | "date" | "boolean" | "list" | "string";

export interface NormalizedMetadataField {
  key: string;
  label: string;
  type: MetadataType;
  value: unknown;
  order: number;
}

interface FieldConfiguration {
  label: string;
  type: MetadataType;
  order: number;
}

const FIELD_REGISTRY: Record<string, FieldConfiguration> = {
  budget: { label: "Expected Budget", type: "currency", order: 10 },
  request_date: { label: "Requested On", type: "date", order: 20 },
  commercial: { label: "Commercial Project", type: "boolean", order: 30 },
  location: { label: "Target Location", type: "string", order: 40 },
  collections: { label: "Collections", type: "list", order: 50 },
  recurring: { label: "Service Frequency", type: "string", order: 60 },
  permit_num: { label: "Permit Number", type: "string", order: 70 },
  expected_revenue: { label: "Expected Revenue", type: "currency", order: 80 },
  completion_date: { label: "Completion Date", type: "date", order: 90 },
};

export class MetadataTransformer {
  static transform(rawMetadata: Record<string, unknown> | undefined | null): NormalizedMetadataField[] {
    if (!rawMetadata || typeof rawMetadata !== "object") return [];
    const fields: NormalizedMetadataField[] = [];
    for (const [key, value] of Object.entries(rawMetadata)) {
      if (value === null || value === undefined) continue;
      const registered = FIELD_REGISTRY[key];
      const label = registered?.label || this.beautifyKey(key);
      const type = registered?.type || this.inferType(key, value);
      const order = registered?.order !== undefined ? registered.order : 999;
      fields.push({ key, label, type, value, order });
    }
    return fields.sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return a.key.localeCompare(b.key);
    });
  }

  private static beautifyKey(key: string): string {
    return key
      .replace(/_/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  private static inferType(key: string, value: unknown): MetadataType {
    if (typeof value === "boolean") return "boolean";
    if (Array.isArray(value)) return "list";
    if (typeof value === "string" && /^\\d{4}-\\d{2}-\\d{2}$/.test(value)) return "date";
    const lowercaseKey = key.toLowerCase();
    if (
      typeof value === "number" &&
      (lowercaseKey.includes("budget") ||
       lowercaseKey.includes("revenue") ||
       lowercaseKey.includes("price") ||
       lowercaseKey.includes("cost") ||
       lowercaseKey.includes("amount") ||
       lowercaseKey.includes("value"))
    ) {
      return "currency";
    }
    return "string";
  }
}
"""

try:
    print(consult_supervisor(proposal, snippet, False))
except Exception as e:
    print(f"Error: {e}")
