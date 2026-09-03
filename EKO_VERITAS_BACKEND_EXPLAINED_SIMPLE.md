# 🎙️ Eko-Veritas: How the Entire System Works in Plain English

---

## 📖 The Story: From Phone Call to Fix

### 1. A Real Person Calls the Shop
* A customer calls **Stagecoach Auto Mechanics**.
* **ElevenLabs** is the AI voice that answers the phone and talks back and forth with the customer.

### 2. The Call Ends & ElevenLabs Drops off the "Receipt"
* As soon as the customer hangs up, ElevenLabs drops off a package (a webhook) on our digital doorstep.
* Inside is:
  1. The full **audio recording**.
  2. The written **word-for-word transcript** (who said what).
  3. The customer's phone number and how long the call lasted.

### 3. Eko-Veritas Automatically Grades the Call
* Eko-Veritas reads the transcript and tests it against a checklist (e.g. *Did the agent collect mileage? Did they offer towing?*).
* Did everything right? $\rightarrow$ **Green Pass**.
* Made a mistake? (e.g. told someone with a smoking engine to drive in) $\rightarrow$ **Red Flag**.

### 4. You Give Feedback (The Directive)
* You open your phone and type:
  > *"When the check engine light is flashing, warn about engine damage and call Longhorn Towing."*

### 5. Claude Performs Surgery on the Prompt (In-Place Fix)
* **The Old Bug:** The system used to just tape a messy sticky note at the very bottom of the prompt.
* **The New Fix:** Claude finds **Step 4 (Safety Check)**, erases just that one old sentence, and writes the new tow-truck rule in its exact spot.
* At the same time, it invents a **new grading test** so future calls get checked on this rule.

### 6. You Tap "Approve" $\rightarrow$ Live on ElevenLabs
* You review the before/after on your phone.
* When you hit **Approve & Deploy**, Eko-Veritas sends the update to ElevenLabs.
* The very next caller immediately gets the smarter agent.

---

<br/>

---

## 🍳 The Backend Explained Like a Restaurant Kitchen

```
[ Customer Phone Call ]
          │
          ▼
   ( ElevenLabs AI )
          │ (Hangs up & sends package)
          ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. THE FRONT DOOR & MAILBOX (/api/ingest/elevenlabs)        │
│    • Catches the package and locks the raw copy in a safe   │
│      (webhook_events) so nothing ever gets lost.            │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. THE PREP COOK (The Ingest & Normalizer)                  │
│    • Unwraps the package.                                   │
│    • Separates audio, clean transcripts, and call metadata. │
│    • Organizes into clean folders (calls, transcripts).     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. THE FIREPROOF FILING CABINET (Azure PostgreSQL with RLS) │
│    • Every business has its own locked drawer.              │
│    • Stagecoach Mechanics data is completely separate from  │
│      every other company.                                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. THE HEAD CHEF & SCRIPT DOCTOR (Claude Sonnet 3.7 / 5)    │
│    • Reads your feedback.                                   │
│    • Erases only the old sentence and rewrites in-place.    │
│    • Creates a new automated inspection test rule.          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. THE OUTGOING COURIER (The Outbox Sync Queue)             │
│    • When you tap "Approve", places the recipe in outbox.   │
│    • Calls ElevenLabs, delivers the update, and waits       │
│      15 seconds for a thumbs-up confirmation.               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Takeaways (Zero Jargon)
1. **Never Loses Data:** Even if the database blinks, every raw call package is saved first.
2. **Never Clutters Prompts:** Edits are surgical replacements inside the text, not dumped at the bottom.
3. **Always Creates a Test:** Every time you fix a rule, the system builds an automated grader to make sure the AI never forgets it.
4. **1-Click Sync:** Your phone is the remote control for your entire fleet.
