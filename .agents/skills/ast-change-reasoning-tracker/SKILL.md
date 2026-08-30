---
name: ast-change-reasoning-tracker
description: Extracts AST node modifications (functions, components, classes, server actions), binds architectural rationale, and syncs live change telemetry to Kenbun boards for complete CTO visibility.
version: 1.0.0
---

# AST Change & Reasoning Tracker Skill

## Overview
This skill provides the CTO and system owner with complete, transparent observability into what Antigravity and autonomous agents are doing to codebase AST nodes. It captures:
1. **What Changed**: Precise AST-level functions, components, classes, and types altered.
2. **Why It Changed**: The explicit architectural rationale, client quote, or bug diagnosis that prompted the change.
3. **Board Observability**: Syncs the change-rationale telemetry card directly to Kenbun boards (Planka / Kanban).
4. **Cognitive Contract Enforcement**: Enforces a strict feedback loop to reduce prompt iterations down to $\le 10$ prompts per milestone.

---

## When to Activate
Activate this skill automatically:
- At the conclusion of any major feature implementation or refactor.
- When committing changes to `main` or submitting pull requests.
- When ingesting client feedback to verify exact AST nodes mapped to the client's request.

---

## Usage via Python FastMCP Tool

```python
from tools.codebase.ast_change_tracker import track_ast_changes

result = track_ast_changes(
    repo_path="/Users/carlosrivas/Dev/Projects/eko-veritas-prod",
    reasoning="Implemented defensive ElevenLabs cross-account reconciliation and decoupled call context anchors from eval mutations.",
    target_commit_or_ref="HEAD"
)
```

---

## Output Telemetry Schema
```json
{
  "status": "SUCCESS",
  "card_title": "AST Milestone: ...",
  "repo": "eko-veritas-prod",
  "files_modified_count": 3,
  "ast_symbols_extracted": 14,
  "ast_breakdown": [
    {
      "file": "src/app/(dashboard)/voice-agents/actions.ts",
      "symbols_count": 8,
      "symbols": [
        { "name": "reconcileElevenLabsAgents", "type": "async_server_action", "lineno": 709 },
        { "name": "importElevenLabsAgent", "type": "async_server_action", "lineno": 826 }
      ]
    }
  ]
}
```
