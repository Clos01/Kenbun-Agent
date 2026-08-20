import { z } from "zod";

export interface KenbunMetadata {
  location?: string;
  recurring?: "none" | "daily" | "weekly" | "monthly";
  collections?: string[];
  dependencies?: string[];
  layout?: { x: number; y: number };
  shape?: "process" | "decision" | "terminal";
  linkLabels?: Record<string, string>;
}

const KenbunMetadataSchema = z.object({
  location: z.string().max(100).regex(/^[a-zA-Z0-9_\-\s]+$/).optional(),
  recurring: z.enum(["none", "daily", "weekly", "monthly"]).optional(),
  collections: z.array(z.string().max(50).regex(/^[a-zA-Z0-9_\-\s]+$/)).max(30).optional(),
  dependencies: z.array(z.string().max(50).regex(/^[a-zA-Z0-9_\-]+$/)).max(100).optional(),
  layout: z.object({
    x: z.number(),
    y: z.number()
  }).strict().optional(),
  shape: z.enum(["process", "decision", "terminal"]).optional(),
  linkLabels: z.record(z.string().max(50).regex(/^[a-zA-Z0-9_\-]+$/), z.string().max(100)).optional(),
}).strict();

const DescriptionInputSchema = z.string().max(50000).catch("");

function sanitizeText(input: string): string {
  if (typeof input !== "string") return "";
  return input
    .replace(/<[^>]*>?/gm, "")
    .replace(/javascript:/gi, "")
    .replace(/&#039;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

export function parseCardMetadata(description: string): { cleanDescription: string; metadata: KenbunMetadata } {
  if (typeof description !== "string") {
    return { cleanDescription: "", metadata: {} };
  }
  const inputStr = DescriptionInputSchema.parse(description);
  if (!inputStr) {
    return { cleanDescription: "", metadata: {} };
  }

  const regex = /<!--\s*kenbun_metadata:\s*({[\s\S]*?})\s*-->/;
  const match = inputStr.match(regex);
  
  if (match) {
    try {
      const jsonStr = match[1].trim();
      
      if (jsonStr.length > 5000) {
        throw new Error("Metadata exceeds length limit.");
      }
      if (!jsonStr.startsWith("{") || !jsonStr.endsWith("}")) {
        throw new Error("Metadata is not a valid JSON object.");
      }

      const keysRegex = /"([^"]+)"\s*:/g;
      let keyMatch;
      const allowedKeys = ["location", "recurring", "collections", "dependencies", "layout", "shape", "x", "y", "linkLabels"];
      while ((keyMatch = keysRegex.exec(jsonStr)) !== null) {
        const key = keyMatch[1];
        if (!allowedKeys.includes(key)) {
          throw new Error(`Unauthorized key detected before parsing: ${key}`);
        }
      }
      
      const rawParsed = JSON.parse(jsonStr);
      
      if (!rawParsed || typeof rawParsed !== "object" || Array.isArray(rawParsed)) {
        throw new Error("Parsed metadata is not an object.");
      }
      if (Object.getPrototypeOf(rawParsed) !== Object.prototype) {
        throw new Error("Malformed prototype chain detected.");
      }
      if (
        Object.prototype.hasOwnProperty.call(rawParsed, "__proto__") ||
        Object.prototype.hasOwnProperty.call(rawParsed, "constructor") ||
        Object.prototype.hasOwnProperty.call(rawParsed, "prototype")
      ) {
        throw new Error("Malicious prototype attributes present.");
      }

      const safeParsed = Object.create(null);
      
      if (rawParsed.location !== undefined) {
        if (typeof rawParsed.location !== "string" || rawParsed.location.length > 100) {
          throw new Error("Invalid location field length.");
        }
        safeParsed.location = rawParsed.location;
      }
      
      if (rawParsed.recurring !== undefined) {
        safeParsed.recurring = rawParsed.recurring;
      }
      
      if (rawParsed.collections !== undefined) {
        if (!Array.isArray(rawParsed.collections) || rawParsed.collections.length > 30) {
          throw new Error("Collections exceeds array size boundary.");
        }
        for (let i = 0; i < rawParsed.collections.length; i++) {
          const item = rawParsed.collections[i];
          if (typeof item !== "string" || item.length > 50) {
            throw new Error("Collection item size exceeds safe limit.");
          }
        }
        safeParsed.collections = rawParsed.collections;
      }
      
      if (rawParsed.dependencies !== undefined) {
        if (!Array.isArray(rawParsed.dependencies) || rawParsed.dependencies.length > 100) {
          throw new Error("Dependencies exceeds array size boundary.");
        }
        for (let i = 0; i < rawParsed.dependencies.length; i++) {
          const item = rawParsed.dependencies[i];
          if (typeof item !== "string" || item.length > 50) {
            throw new Error("Dependency item size exceeds safe limit.");
          }
        }
        safeParsed.dependencies = rawParsed.dependencies;
      }

      if (rawParsed.layout !== undefined) {
        if (rawParsed.layout === null || typeof rawParsed.layout !== "object" || Array.isArray(rawParsed.layout)) {
          throw new Error("Invalid layout field type.");
        }
        if (typeof rawParsed.layout.x !== "number" || typeof rawParsed.layout.y !== "number") {
          throw new Error("Layout coordinates must be numbers.");
        }
        safeParsed.layout = {
          x: rawParsed.layout.x,
          y: rawParsed.layout.y
        };
      }

      if (rawParsed.shape !== undefined) {
        if (typeof rawParsed.shape !== "string" || !["process", "decision", "terminal"].includes(rawParsed.shape)) {
          throw new Error("Invalid shape field value.");
        }
        safeParsed.shape = rawParsed.shape;
      }

      if (rawParsed.linkLabels !== undefined) {
        if (typeof rawParsed.linkLabels !== "object" || Array.isArray(rawParsed.linkLabels) || rawParsed.linkLabels === null) {
          throw new Error("Invalid linkLabels field type.");
        }
        const safeLabels: Record<string, string> = {};
        for (const key in rawParsed.linkLabels) {
          if (Object.prototype.hasOwnProperty.call(rawParsed.linkLabels, key)) {
            const val = rawParsed.linkLabels[key];
            if (typeof key !== "string" || key.length > 50 || typeof val !== "string" || val.length > 100) {
              throw new Error("Invalid linkLabel key or value size.");
            }
            safeLabels[key] = val;
          }
        }
        safeParsed.linkLabels = safeLabels;
      }

      const parsed = KenbunMetadataSchema.parse(safeParsed);
      
      const metadata: KenbunMetadata = {
        location: parsed.location ? sanitizeText(parsed.location) : undefined,
        recurring: parsed.recurring,
        collections: parsed.collections ? parsed.collections.map(sanitizeText) : undefined,
        dependencies: parsed.dependencies ? parsed.dependencies.map(sanitizeText) : undefined,
        layout: parsed.layout,
        shape: parsed.shape,
        linkLabels: parsed.linkLabels
      };
      
      const rawClean = inputStr.replace(regex, "");
      const cleanDescription = sanitizeText(rawClean);
      
      return { cleanDescription, metadata };
    } catch (e) {
      console.error("Failed to parse kenbun_metadata:", e);
    }
  }
  
  return { cleanDescription: sanitizeText(inputStr), metadata: {} };
}

export function injectCardMetadata(description: string, metadata: KenbunMetadata): string {
  const { cleanDescription } = parseCardMetadata(description);
  const jsonStr = JSON.stringify(metadata);
  const metadataComment = `\n\n<!-- kenbun_metadata: ${jsonStr} -->`;
  return cleanDescription + metadataComment;
}
