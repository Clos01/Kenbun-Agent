# Kenbun Skill Protocol (PROTOCOL.md)

This protocol defines how **Skills** are authored and registered within the Kenbun ecosystem. A Skill is a self-contained intelligence module that teaches the Swarm how to produce a specific artifact (e.g., a SaaS landing page, a technical report, or a 3D shader).

## 1. Directory Structure
Every skill must live in `tools/skills/<skill-name>/` and contain:
- `SKILL.md`: The primary directive and frontmatter.
- `assets/`: Static templates, CSS, or images.
- `references/`: Supporting documentation or design specs.

## 2. The `SKILL.md` Convention
We adopt the Claude Code standard with an extended `kenbun:` frontmatter.

```markdown
---
kenbun:
  mode: prototype | deck | document
  fidelity: high | wireframe
  tech_stack: [nextjs, tailwind, framer-motion]
  discovery_required: true
---

# [Skill Name]
Directives for the AI on how to execute this specific skill.
```

## 3. Discovery Integration
If `discovery_required: true` is set, the **System 5 Discovery Agent** will automatically parse the `SKILL.md` to generate custom questions for the user before execution.

## 4. Artifact Output
Skills MUST produce a single, self-contained HTML `<artifact>` block. 
- **Sandboxed**: No external scripts except whitelisted CDNs (Tailwind, Framer Motion, Lucide).
- **Responsive**: Must use the device frames provided by the `Visual Observatory`.

## 5. Examples of Implemented Skills
- `web-prototype`: The default skill for responsive landing pages.
- `pitch-deck`: Editorial-grade presentations with WebGL backgrounds.
- `pm-spec`: High-fidelity technical documentation.
