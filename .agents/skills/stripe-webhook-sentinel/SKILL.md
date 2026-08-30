---
name: stripe-webhook-sentinel
description: Enforces cryptographic HMAC signature validation, idempotent event deduplication, dead-letter retry queues, and defensive payment processing across Stripe, Paddle, and LemonSqueezy webhook handlers.
---

# 💳 Stripe & Billing Webhook Sentinel

The **Stripe Webhook Sentinel** ensures that all incoming billing, subscription, and invoice webhooks are cryptographically authenticated, processed idempotently, and insulated against double-billing or dropped events.

---

## 🎯 When to Activate

Trigger this skill immediately when:
- Creating or editing webhook API endpoints (e.g. `/api/webhooks/stripe`, `/api/v1/billing/webhook`).
- Handling subscription lifecycle events (`customer.subscription.created`, `updated`, `deleted`).
- Handling invoice payments (`invoice.payment_succeeded`, `invoice.payment_failed`).
- Implementing checkout session completion (`checkout.session.completed`).
- Diagnosing double-credit bugs, replay attacks, or unhandled 500 errors during webhook ingest.

---

## 🛡️ The 4 Cardinal Rules of Webhook Processing

### 1. Raw Body Signature Verification
Never parse JSON before verifying the signature. Stripe signatures require the exact, un-parsed raw byte string:
```typescript
// Next.js App Router / Node.js
import Stripe from "stripe";

export async function POST(req: Request) {
    const body = await req.text(); // Raw text string!
    const sig = req.headers.get("stripe-signature");

    let event: Stripe.Event;
    try {
        event = stripe.webhooks.constructEvent(body, sig!, process.env.STRIPE_WEBHOOK_SECRET!);
    } catch (err: any) {
        console.error(`🚨 Webhook signature verification failed: ${err.message}`);
        return new Response(`Webhook Error: ${err.message}`, { status: 400 });
    }

    // Process event...
    return new Response(JSON.stringify({ received: true }), { status: 200 });
}
```

### 2. Idempotency Table Deduplication
Stripe guarantees **at-least-once** delivery. Your handler WILL receive duplicate events:
```sql
CREATE TABLE IF NOT EXISTS processed_webhook_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);
```
*Before executing business logic, check if `event.id` already exists in `processed_webhook_events`.*

### 3. Immediate 200 OK & Async Processing
Stripe times out after 15-20 seconds. If fulfillment involves slow external APIs, persist the event to an event queue (e.g. Supabase queue or background worker) and return `200 OK` in <500ms.

### 4. Zero Secrets in Client Bundles
Webhook secrets (`whsec_*`) must never be prefixed with `NEXT_PUBLIC_` or committed to source control.

---

## 📚 Deep-Dive References
- [references/webhook_signature_guide.md](references/webhook_signature_guide.md) — Multi-provider signature templates (FastAPI & Next.js), Stripe CLI local testing commands, and dead-letter replay procedures.
