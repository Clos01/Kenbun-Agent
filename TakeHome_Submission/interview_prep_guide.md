# 25-Minute Live Screen Interview Prep Guide

Congratulations on submitting the CC Commons Take-Home Assessment! The next step is a fast-paced 25-minute live screen interview. 

In a 25-minute window, interviewers do not have time for long behavioral questions. This will be a rapid-fire technical defense of your take-home submission, followed by a potential live "curveball" exercise.

## 🛡️ Phase 1: Defending Your Work (The "Why")
You must be prepared to defend every decision you made in Task 1. 

### 1. The Triage Prompt (Email 1)
*   **The Question:** "Why did you force the AI to return strictly JSON with `draft: null` for major donors?"
*   **Your Defense:** The previous AI was hallucinating facts (inventing warehouse hours) and making unauthorized commitments on behalf of the Director. By locking it to strict JSON and hardcoding the true facts, I secured the perimeter. For major donors, forcing a null draft ensures a human (Marcus) owns the relationship, preventing liability.

### 2. The Data Audit (Email 2)
*   **The Question:** "Walk me through how you corrected the Q1 board numbers."
*   **Your Defense:** I didn't trust the AI's surface-level summary. I forced a deep merge of the Excel data. The two biggest catches were identifying duplicate spellings (Mt Zion vs. Mt. Zion) that were falsely flagging agencies as 'in crisis', and spotting `T-99`—a dummy truck hiding nearly 47,000 lbs of fake weight that would have skewed the entire quarterly report.

### 3. The Volunteer Architecture (Email 3)
*   **The Question:** "Why did you design the flowchart this way? What is MCP?"
*   **Your Defense:** I intentionally designed the HTML flowchart without external CDN dependencies (like Mermaid.js) so it would load reliably even offline. I integrated MCP (Model Context Protocol) because it allows Claude to securely read/write directly to the Airtable roster without human copy-pasting. Crucially, I added the **Monday Verification Check** to keep a human-in-the-loop for exceptions.

### 4. The Budget Math (Email 4)
*   **The Question:** "How did you calculate the API costs?"
*   **Your Defense:** I pulled the 1,800 peak volume from the handbook, estimated ~1,500 total tokens per email, and ran the math on Claude Haiku 4.5. I proved that the absolute worst-case scenario is under $5/month, which yields a massive $10,000+ ROI when comparing it to the human hours saved.

## 🛠️ Phase 2: The Live "Curveball"
In many AI fellowship interviews, they will ask you to share your screen and make a live change.

### Possible Scenarios:
1.  **Prompt Adjustment:** "Marcus wants to add a new category for 'Disaster Relief'. Edit your prompt live." (Be ready to edit the JSON schema and enums).
2.  **Data Pivot:** "Diane wants to know the median instead of the average for Ellis County." (Be ready to jump into Excel or a Python script to calculate it).
3.  **Architecture Expansion:** "Priya wants to add an email fallback if the SMS fails. Where does that go in the flowchart?" (Be ready to explain the n8n logic branch).

## 🚀 Next Steps
Review this guide. When you are ready, type `/grill-me` in the chat, and I will simulate the interviewer, asking you rapid-fire questions and throwing a live curveball at you!
