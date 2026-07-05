---
trigger: always_on
---

## 3. THE "SYSTEM 3" PROTOCOL (Memory & Tools)
You are not alone. You have access to external tools via **MCP**.
- **Unknown Tech / Syntax?** -> Call the tool `research_official_docs(tech_key, query)`.
  * *Example:* "How do I fetch data in Next.js?" -> `research_official_docs("nextjs", "data fetching")`
- **Complex Logic / Architectural Patterns?** -> Call `ask_architect(question)` (or whatever your vector DB tool is named).
  * *Example:* "Where does the user auth logic live?" -> `ask_architect("user authentication flow")`
- **Full Code Review (Cloud AI)?** -> Call `review_code_with_gemini(code_snippet, review_context, tech_key, cross_check=True)`.
  * Runs a **4-stage pipeline**: Gemini Review → Official Docs → Supervisor Cross-Check → Consensus Report.
  * *Example:* `review_code_with_gemini("def get_user...", "Check for SQL injection", "fastapi", cross_check=True)`
  * Set `cross_check=True` to also get the local Supervisor's opinion and a consensus verdict.
- **Research with Cloud AI?** -> Call `research_with_gemini(query, tech_key)`.
  * Uses Gemini 2.0 Flash (1M token context) grounded in official docs.
  * *Example:* `research_with_gemini("How do React Server Components work?", "nextjs")`

## 4. UI & WEB MANDATE (The "UI Expert")
Whenever building or modifying a UI, you **MUST** call `mcp_stitch_generate_screen_from_text` to establish a premium aesthetic before writing code.
- **Rule:** Aesthetics are non-negotiable. Use glassmorphism, high-fidelity gradients, and premium typography.
- **Protocol:** If the UI looks "Basic" or "MVP-like," it is a failure. Consult the UI Expert via Stitch to elevate the design.