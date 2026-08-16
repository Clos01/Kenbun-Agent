# 🎓 Fellowship Interview Spoken Cheat Sheet

This is your direct reference sheet for the interview. It is written in a natural, conversational tone so you can read it or scan it easily.

---

## 🧠 Strategic Framing: Rejecting the Lexus IT Job
**How does turning down a Lexus IT job affect your chances at the Cloud Code Fellowship?**

It is a **massive strength**, provided it is framed correctly. Here is why:
*   **Standard IT vs. AI Engineering:** The fellowship wants builders and software innovators, not helpdesk technicians. Resetting passwords at Lexus is safe; building a custom multi-system agent framework (Kenbun) to run a construction business is engineering.
*   **High-Agency & Self-Starter:** Turning down a comfortable corporate paycheck to work in physical labor by day and code by night shows incredible drive, resilience, and obsession with AI.
*   **The Narrative Shift:** You didn't turn it down out of arrogance. You turned it down because you realized your path lay in **AI engineering and building systems**, not maintaining standard corporate legacy networks.

---

## 🗣️ The Spoken Story (Natural, Conversational Tone)

> *"Honestly, my path into tech wasn't a straight line. I spent five years at CarMax doing frame inspections and sales, but I felt completely lost. I got too comfortable, so I took a risk and went to a coding bootcamp.*
>
> *After the bootcamp, the job market was really tough. I ended up joining NPower, and I am incredibly grateful for them. They put me in a cohort, took a chance on me, and helped me get my CompTIA A+ certification so I could complete what I needed to get a foothold in IT.*
> 
> *Right after getting certified, I actually got a job offer to do IT support at Lexus. It was a stable corporate route. But I chose to turn it down. I was at a crossroads—I knew I didn't want to just follow standard IT runbooks or reset passwords. I wanted to build in AI, and I wanted to do it on my own terms. I chose a completely self-directed, uncertain path, with no one over my shoulder telling me what to do or how to do it.*
>
> *So instead of the Lexus job, I focused on building the IT software and custom automation pipelines for my dad's flooring business, CRG Flooring. By day, I was doing the physical labor—carrying thousands of pounds of hardwood up stairs, organizing vans, doing herringbone layouts. But by night, I was trying to figure out how to help him grow the business and generate leads.*
>
> *When I first started building that flooring IT infrastructure, I hit a massive wall: I was getting crazy hallucinations from the LLMs. I didn't have an agentic framework yet; I was starting completely from scratch. In construction, if an LLM hallucinates a materials invoice or a scheduling dispatch, it costs the business real money.*
>
> *That’s how Kenbun started. It didn't start as some grand theoretical framework. It started because I was desperate to solve those hallucinations and automate our lead pipelines so we wouldn't miss opportunities. I bought a Small Form Factor P330 server to run our database and container stack separate from my local machine, and I designed the System 2 Validation Gate (`consult_supervisor`) to run strict test-driven checks on the AI's code before letting it execute.*
>
> *For me, this is what I fell in love with: using AI to build high-grade internal systems for small businesses at a fraction of the cost of expensive software. It's the first time I felt like what I was building actually mattered, and it proved to me that I could figure out how to solve complex engineering problems completely on my own."*

---

## 🖥️ Quick Tech Stack Reference
*   **Legion PC (lg2025):** Runs local inference using LM Studio on an RTX 5070 to host models cost-effectively.
*   **ThinkStation P330 SFF Server:** Runs Docker stacks (n8n, Planka, Gitea, Docmost) to isolate the business logic.
*   **System 1 (Execution):** Fast reactive LLM + immediate terminal/file operations.
*   **System 2 (Supervisor):** Multi-agent adversarial validation loop that checks for security (SQL/shell injection) and runs TDD tests before signing off.
*   **System 3 (Hivemind):** Long-term vector database memory (pgvector + ChromaDB) to recall past fixes.
