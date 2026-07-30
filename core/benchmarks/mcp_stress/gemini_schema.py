"""Sanitize MCP/Pydantic JSON Schema into Gemini function-declaration schema.

Gemini's Schema type accepts only a small OpenAPI-ish subset: type, format,
description, nullable, enum, items, properties, required, min/maxItems. Pydantic
emits `title`, `default`, `anyOf` (for Optional[...]), and `$defs` — all of which
make generateContent reject the whole request with a bare 400.
"""
ALLOWED = {"type", "format", "description", "nullable", "enum", "items",
           "properties", "required", "minItems", "maxItems"}
VALID_TYPES = {"string", "number", "integer", "boolean", "array", "object"}


def sanitize(node):
    if not isinstance(node, dict):
        return {"type": "string"}

    # Optional[X] becomes anyOf:[{X}, {null}] -> take the first real type and
    # mark it nullable, which is how Gemini expresses the same thing.
    if "anyOf" in node or "oneOf" in node:
        variants = node.get("anyOf") or node.get("oneOf") or []
        real = [v for v in variants
                if isinstance(v, dict) and v.get("type") != "null"]
        base = sanitize(real[0]) if real else {"type": "string"}
        if len(real) < len(variants):
            base["nullable"] = True
        if node.get("description"):
            base["description"] = node["description"]
        return base

    out = {}
    for k, v in node.items():
        if k not in ALLOWED:
            continue          # drops title, default, $defs, additionalProperties…
        if k == "properties" and isinstance(v, dict):
            out[k] = {pk: sanitize(pv) for pk, pv in v.items()}
        elif k == "items":
            out[k] = sanitize(v)
        elif k == "type":
            t = v[0] if isinstance(v, list) and v else v
            out[k] = t if t in VALID_TYPES else "string"
        else:
            out[k] = v

    if out.get("type") == "object" and "properties" not in out:
        out["properties"] = {}
    if "type" not in out:
        out["type"] = "object" if "properties" in out else "string"
    # Gemini rejects required entries that name a property that isn't declared.
    if "required" in out:
        props = out.get("properties", {})
        req = [r for r in out["required"] if r in props]
        if req:
            out["required"] = req
        else:
            out.pop("required")
    return out


def to_declaration(tool):
    schema = sanitize(tool.get("inputSchema") or {})
    if schema.get("type") != "object":
        schema = {"type": "object", "properties": {}}
    return {"name": tool["name"],
            "description": (tool.get("description") or tool["name"])[:600],
            "parameters": schema}
