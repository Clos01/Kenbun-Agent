---
name: weekly-review
description: "A weekly recap: what got done, what's still open, and what's coming up."
triggers:
  - "weekly review"
  - "weekly recap"
kenbun:
  mode: document
  fidelity: high
  tech_stack: [markdown]
  discovery_required: false
blueprint:
  default_schedule: "0 18 * * 0"
  inputs:
    - name: time
      type: string
      default: "18:00"
      description: "Time of day to run (e.g. 18:00)"
    - name: day
      type: string
      default: "sunday"
      description: "Day of the week (e.g. sunday)"
    - name: deliver
      type: string
      default: "origin"
      description: "Output channel (e.g. slack, discord, origin)"
  prompt_template: |
    Perform the Weekly Review. Inspect git logs for the past 7 days, parse completed issues, compile open tasks from AG_TASKS.md, and summarize next week's focus. Format as a clean markdown report.
---

# Weekly Review Skill

Weekly recap instructions:
- Parse git history for the past week.
- Scan and aggregate completed and pending tasks.
- Deliver summary report.
