---
name: kenbun-teacher
description: >-
  Use this skill to randomly select a teaching moment about Kenbun architecture, workflows, or tools and present it to the user with a visual diagram. Invoke this when completing a major milestone or when the user asks to be taught about Kenbun.
---

# Kenbun Algorithmic Teaching Engine

The `kenbun-teacher` skill helps the agent progressively teach the user about the underlying Kenbun architecture, tool workflows, and best practices.

## How it works (The Algorithm)

1. Read the JSON dictionary at `./dictionary.json`.
2. Select a `teaching_moment` dynamically (e.g., based on the current context, or randomly via the timestamp / step index).
3. Append a dedicated "Teaching Moment" section to the bottom of your response.
4. Format the section strictly using the `visual_mermaid` diagram and the `explanation` text.

## Output Format Example

```markdown
---
### 🎓 Kenbun Teaching Moment: [Title]
**Concept**: [Concept]

[Explanation]

```mermaid
[visual_mermaid block]
```
---
```

## Mandate for Carlos Persona
When operating as the CTO / Architect (Carlos), use this skill frequently to ensure the user is constantly upskilling and understanding the "why" behind the Swarm's asynchronous and resilient decisions.
