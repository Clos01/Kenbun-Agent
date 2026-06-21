---
kenbun:
  mode: document
  fidelity: wireframe
  tech_stack: []
  discovery_required: false
---

# Quick Recap

Make completion state obvious at the end of every response.

## Status Block

Every response that completes a unit of work must end with:

```md
🟢 Actual concise status sentence
```

Rules:

- Keep the status line under 100 characters.
- Use `🟢` when the requested work is finished.
- Use `🟡` when non-routine follow-up remains; name the pending item.
- Use `🔴` only when blocked on user input.
- Put the status line at the very end of the response.
- Do not add `---`, spacer lines, or any content after the status line.

## Examples

Finished work:

```md
🟢 Updated quick recap docs with output examples
```

Non-routine follow-up remains:

```md
🟡 Code updated, set PROVIDER_WEBHOOK_SECRET before testing webhooks
```

Blocked on user input:

```md
🔴 Need the production API key to continue
```
