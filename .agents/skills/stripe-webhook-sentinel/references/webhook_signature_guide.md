# Webhook Signature Verification & Testing Guide

This guide covers production-hardened webhook verification patterns across Next.js and FastAPI, along with local Stripe CLI workflows.

---

## 1. FastAPI (Python) Webhook Handler

In FastAPI, access the raw `Request.body()` bytes directly:

```python
import stripe
from fastapi import APIRouter, Request, HTTPException, Header
import os

router = APIRouter()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/api/v1/billing/stripe-webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")
    
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Idempotency check & dispatch
    event_id = event["id"]
    event_type = event["type"]
    
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        # Fulfill customer license...
        
    return {"status": "success", "event_id": event_id}
```

---

## 2. Local Stripe CLI Testing Flow

To test webhooks against local dev servers:

```bash
# 1. Install & Login
stripe login

# 2. Forward webhooks to local server
stripe listen --forward-to localhost:3000/api/webhooks/stripe

# 3. Trigger simulated events
stripe trigger checkout.session.completed
stripe trigger invoice.payment_failed
stripe trigger customer.subscription.deleted
```
