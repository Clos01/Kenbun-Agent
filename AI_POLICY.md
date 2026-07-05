# 🏛️ Augmented CTO: Personal AI Policy

*This document outlines the official standards and boundaries for AI collaboration in personal and professional software architecture contexts.*

## 1. Core Philosophy
Artificial Intelligence acts as a rapid prototyping and execution partner, not the final decision-maker. As the Augmented CTO, I maintain absolute strategic responsibility for the architecture, scalability, and security of all deployed systems. AI is used to amplify engineering throughput, not to replace architectural judgment.

## 2. Standards for Engagement (The 4Ds)
*   **Delegation:** AI is delegated boilerplate generation, initial code drafts, and large-scale data parsing. Humans retain architecture design, security boundaries, and final code reviews.
*   **Description:** All AI interactions must use strict structural prompts (e.g., the Hermes Blueprint) to prevent hallucinations.
*   **Discernment:** AI outputs are assumed flawed until mathematically or programmatically proven otherwise.
*   **Diligence:** All AI usage is transparently disclosed in project documentation.

## 3. Data Boundaries and Security (Zero-Secret Hardening)
*   **No Secrets in Prompts:** Under no circumstances will API keys, `.env` file contents, or unencrypted database credentials be passed into a public or local LLM. 
*   **PII Protection:** No Personally Identifiable Information (PII) or sensitive customer data will be used to train or prompt AI models.
*   **Local Sandboxing:** Whenever testing AI execution, it must be run inside a non-root Jailed Sandbox with dropped capabilities to prevent host-system compromise.

## 4. Quality Control (System 2 Sign-Off Mandate)
No AI-generated code will be merged into a production repository without passing a strict System 2 audit. This includes:
1. Passing automated linting and formatting.
2. Generating passing unit tests.
3. Passing a security review for regressions (e.g., SQL injection, context bleeding).

## 5. Transparency and Attribution
In all major professional or open-source projects, an `AI_DILIGENCE.md` file will be included in the repository. This file will explicitly state which AI models were used (e.g., Claude, Gemini) and what specific tasks they were delegated, ensuring full transparency with the open-source community, clients, and end-users.
