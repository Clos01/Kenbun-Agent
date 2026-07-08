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

// Registry defining static mappings for expected fields
const FIELD_REGISTRY: Record<string, FieldConfiguration> = {
  budget: { label: "Expected Budget", type: "currency", order: 10 },
  request_date: { label: "Requested On", type: "date", order: 20 },
  commercial: { label: "Commercial Project", type: "boolean", order: 30 },
  location: { label: "Target Location", type: "string", order: 40 },
  collections: { label: "Collections", type: "list", order: 50 },
  recurring: { label: "Service Frequency", type: "string", order: 60 },
  
  // Future predicted/registered fields for scalability
  permit_num: { label: "Permit Number", type: "string", order: 70 },
  expected_revenue: { label: "Expected Revenue", type: "currency", order: 80 },
  completion_date: { label: "Completion Date", type: "date", order: 90 },
};

export class MetadataTransformer {
  /**
   * Transforms a raw metadata object from the API into a sorted, normalized list of fields.
   * Strips null and undefined values. For unregistered keys, generates labels dynamically
   * and infers the data type based on values.
   */
  static transform(rawMetadata: Record<string, unknown> | undefined | null): NormalizedMetadataField[] {
    if (!rawMetadata || typeof rawMetadata !== "object") return [];

    const fields: NormalizedMetadataField[] = [];

    for (const [key, value] of Object.entries(rawMetadata)) {
      // Ignore nullish values
      if (value === null || value === undefined) continue;

      const registered = FIELD_REGISTRY[key];
      
      const label = registered?.label || this.beautifyKey(key);
      const type = registered?.type || this.inferType(key, value);
      const order = registered?.order !== undefined ? registered.order : 999;

      fields.push({
        key,
        label,
        type,
        value,
        order,
      });
    }

    // Sort primarily by order weight, and secondarily alphabetically by key
    return fields.sort((a, b) => {
      if (a.order !== b.order) {
        return a.order - b.order;
      }
      return a.key.localeCompare(b.key);
    });
  }

  /**
   * Dynamically formats a camelCase or snake_case key into space-separated Title Case words.
   * E.g. "permit_num" -> "Permit Num", "expectedRevenue" -> "Expected Revenue"
   */
  private static beautifyKey(key: string): string {
    return key
      .replace(/_/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  /**
   * Dynamically infers the type of an unregistered metadata field.
   */
  private static inferType(key: string, value: unknown): MetadataType {
    if (typeof value === "boolean") return "boolean";
    if (Array.isArray(value)) return "list";

    // Date inference: check if string matches YYYY-MM-DD pattern
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
      return "date";
    }

    // Currency inference: check if value is a number and key suggests financial context
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
