---
name: morning-brief
description: "A short daily briefing: today's calendar, weather, and anything urgent waiting on you."
triggers:
  - "morning brief"
  - "daily brief"
kenbun:
  mode: document
  fidelity: high
  tech_stack: [markdown]
  discovery_required: false
blueprint:
  default_schedule: "0 8 * * *"
  inputs:
    - name: time
      type: string
      default: "08:00"
      description: "Time of day to run (e.g. 08:00)"
    - name: deliver
      type: string
      default: "origin"
      description: "Output channel (e.g. slack, discord, origin)"
  prompt_template: |
    Perform the Morning Briefing. Query my calendar for today's schedule, fetch the local weather forecast, and list the top 3 highest priority tasks on my desk. Format as a clean dashboard summary.
---

# Morning Briefing Skill

Produce a clean daily briefing summary.
- Query calendars or agendas.
- Query local weather.
- Compile urgent task status.
