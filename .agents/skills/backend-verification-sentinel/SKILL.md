---
name: "backend-verification-sentinel"
description: "Enforces strict backend pre-flight verification and surgical self-healing before code or prompt modifications are ever surfaced to the user. Strictly prohibits relying on superficial frontend warnings."
version: "1.0.0"
license: "MIT"
---

# Backend Verification Sentinel

Strict Pre-Flight Code & Business Logic Integrity Verification Protocol.

Version: 1.0.0  
License: MIT

## Purpose

This sentinel guarantees that **all code changes, prompt revisions, and database mutations are verified and self-healed on the backend BEFORE being presented to the human user**.

### 🚫 Strictly Prohibited:
- Showing a cosmetic warning on the frontend to cover up a backend hallucination.
- Saving truncated or destructive AI outputs into the database.
- Allowing AI to delete core business logic without automated backend interception.

---

## 🛡️ The 5-Point Backend Pre-Flight Pipeline

1. **AST & Syntax Check**: Verify that code parses into a valid Abstract Syntax Tree.
2. **Type & Compilation Check**: Ensure TypeScript/Python compiler reports 0 errors.
3. **Franchise & Business Logic Invariant Check**: Verify no standard operating procedures (intake, callbacks, routing) were truncated.
4. **Autonomous Surgical Self-Healing**: If the AI returned an isolated excerpt or dropped lines, reconstruct the full prompt in-place before database insertion.
5. **Signed Verification Seal**: Only verified artifacts are marked `status: 'verified'` and rendered on the client.
