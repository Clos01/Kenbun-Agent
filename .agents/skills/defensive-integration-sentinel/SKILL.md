---
name: defensive-integration-sentinel
description: Enforces defensive cross-account reconciliation, proactive non-blocking error envelopes, and official vendor documentation deep-linking for all external API integrations (ElevenLabs, Stripe, Twilio, etc.).
version: 1.0.0
---

# Defensive Integration Sentinel Skill

## Cognitive Origin & Purpose
This skill captures the **Carlos Defensive Integration Protocol**. 

When building software that interfaces with third-party APIs (such as ElevenLabs Conversational AI, Stripe, Twilio, OpenAI, or Resend), naive integrations assume external IDs are always valid, active, and owned by the current user. In production, this creates catastrophic blind spots:
- Cross-account entity IDs (e.g., an agent ID belonging to a different ElevenLabs workspace) cause silent ingestion drops or unhandled 401/404 crashes.
- Users and clients are left confused and unable to diagnose why entities are missing or failing.

This skill mandates that **every external integration must be architected defensively from Day 1**.

---

## When to Activate
Activate this skill automatically:
- **Planning Phase:** Whenever designing or refactoring an external API integration, webhook ingestion pipeline, or multi-tenant synchronization loop.
- **Error Remediation:** When handling third-party API 401/403/404 errors, credential mismatches, or orphan entities.
- **Code Review:** Before approving any server action or webhook handler that consumes external entity IDs.

---

## The 4 Mandates of Defensive Integration

### 1. Pre-Flight Reconciliation Envelope
Every integration must implement a defensive reconciliation server action (e.g. `reconcileElevenLabsAgents()`) that classifies entity state into three explicit buckets:
* **`matched`**: Entities verified in both the local tenant database and the remote provider account.
* **`unimportedRemote`**: Valid entities existing in the external account that have not yet been imported into the local fleet (with 1-click import capability).
* **`crossAccountErrors`**: Entities registered in the local DB whose external ID is rejected or inaccessible under the active API key (cross-account or deleted).

### 2. Proactive Non-Blocking Visibility (Zero Silent Failures)
* **Never swallow errors into silent failures.**
* **Never throw unhandled 500 crashes that break the dashboard.**
* Return a structured `ReconciliationReport` that renders accessible, non-blocking UI alert pills and luxury modal popups so users immediately understand system status.

### 3. Actionable Remediation with Official Documentation Deep-Links
Every warning or cross-account mismatch notification must include:
1. **The Exact Root Cause:** Plain-English diagnostic message.
2. **Official Vendor Documentation Link:** Direct deep-link to the provider's API docs (e.g., `https://elevenlabs.io/docs/conversational-ai/api-reference/agents/get`).
3. **1-Click Remediation Action:** (e.g., `[1-Click Import]` or `[Update API Key]`).

### 4. Strict Tenant Boundary Isolation
* Never fall back to shared global environment credentials (`process.env.API_KEY`) when a tenant integration key is required.
* Wrap all HTTP requests with strict timeouts (`AbortSignal.timeout(15000)`).
* Sanitize all error logs to prevent leaking API tokens (`xi-api-key`, `Authorization`) into logging aggregators.

---

## Reference Architecture Pattern (TypeScript / Next.js)

```typescript
export interface CrossAccountError {
  agentId: string;
  name: string;
  elevenlabsAgentId: string;
  reason: string;
  docsUrl: string;
}

export interface ReconciliationReport {
  ok: boolean;
  hasApiKey: boolean;
  totalRemote: number;
  totalLocal: number;
  matchedCount: number;
  unimportedRemote: RemoteAgentItem[];
  crossAccountErrors: CrossAccountError[];
  error?: string;
}

export async function reconcileExternalProvider(): Promise<ReconciliationReport> {
  // 1. Enforce strict tenant session boundary
  const tenantId = await getActiveTenantId();
  
  // 2. Fetch tenant-scoped API key with 15s timeout
  const apiKey = await getTenantApiKey(tenantId);
  const response = await fetch("https://api.provider.com/v1/entities", {
    headers: { "Authorization": `Bearer ${apiKey}` },
    signal: AbortSignal.timeout(15000)
  });

  // 3. Populate structured reconciliation envelope
  // ...
}
```

---

## Memory & System 3 Integration
This skill is permanently recorded in Honcho Hivemind as concept `defensive_integration_sentinel_protocol`. When initiating new project roadmaps, invoke this skill during the Implementation Plan phase.
