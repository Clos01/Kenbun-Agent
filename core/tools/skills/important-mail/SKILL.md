---
name: important-mail
description: "Check your inbox periodically and ping you ONLY about mail that actually needs attention."
triggers:
  - "important mail"
  - "email monitor"
kenbun:
  mode: document
  fidelity: high
  tech_stack: [markdown]
  discovery_required: false
blueprint:
  default_schedule: "*/30 * * * *"
  inputs:
    - name: interval_min
      type: integer
      default: 30
      description: "Interval in minutes"
    - name: criteria
      type: string
      default: "needs a reply today, is from manager or family, or mentions a deadline"
      description: "Triage filter rules"
    - name: deliver
      type: string
      default: "origin"
      description: "Output channel (e.g. slack, discord, origin)"
  prompt_template: |
    Fetch the list of unread emails from the past {interval_min} minutes. Filter and triage them based on the criteria: '{criteria}'. If no emails match the criteria, respond with exactly [SILENT] to suppress notifications. Otherwise, write a short alert summarizing the matches.
---

# Important Mail Monitor Skill

Periodically fetch and filter emails based on custom urgency rules.
- Suppress delivery via [SILENT] if no messages match.
- Provide a concise summary of matches otherwise.
