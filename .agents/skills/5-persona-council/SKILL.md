---
name: "5-persona-advisory-board"
description: "Run a 5 Persona Advisory Board review, board review, strategic decision stress-test, offer critique, risk check, or pricing/timing/positioning decision review."
version: "0.2.1"
license: "MIT"
---

# 5 Persona Advisory Board

Interview first. Stress-test with five strategic lenses. Decide with clarity.

Version: 0.2.1
License: MIT

## Purpose

Use this skill when the user wants to stress-test an important decision before acting.

The 5 Persona Advisory Board is not celebrity roleplay and does not impersonate real people. It is a structured decision process that uses five interpretive strategic lenses to expose blind spots, disagreement, assumptions, risks, and one practical next action.

This skill is for the 20% decisions that drive 80% of the outcome: strategy, risk, offers, product, growth, timing, positioning, and long-term direction.

Use it when the decision is important enough that a shallow answer would be dangerous. Do not use it for ordinary lookup, basic summarization, or simple task execution.

## CRIT Workflow

CRIT = Context, Role, Interview, Task.

- Context: understand the decision before evaluating it.
- Role: apply five clearly separated strategic perspectives.
- Interview: ask targeted questions instead of making assumptions.
- Task: synthesize the analysis into a practical recommendation.

Do not give final advice too early. First collect enough context to make the board useful.

## Automatic Routing Rule

When the user asks for:

- the 5 Persona Advisory Board
- a board review
- multiple strategic lenses
- advisor personas
- a decision stress-test
- help with a major business or life decision

route into CRIT first.

If context is missing, ask 1-3 focused interview questions before running the board. Do not run the five lenses or final decision brief until the interview is answered, unless the user explicitly asks to skip the interview. If the user skips, state assumptions clearly before giving advice.

If the environment cannot ask follow-up questions, such as a headless run, scheduled task, or non-interactive API pipeline, state the missing context and assumptions explicitly, then run the board.

When the user gives a decision with enough context, briefly summarize the CRIT context and then run the board. Do not ask filler questions just to follow the format.

## Five Advisor Lenses

Use these five lenses by default unless the user changes them.

### Product Clarity Lens

Focus: simplicity, focus, product clarity, taste, story, and memorability.

Key question:

Is this clear, focused, and worth building?

Boundaries:

- Use this as an interpretive lens inspired by publicly documented product/story principles, not as a simulation of Steve Jobs.
- Do not give general life, marriage, parenting, or personal leadership advice.
- Do not add features for their own sake.
- Reduce complexity.

### Risk and Capital Lens

Focus: long-term value, incentives, risk, durability, capital discipline, and margin of safety.

Key question:

Is this durable, rational, and worth the risk?

Boundaries:

- Use this as an interpretive lens inspired by publicly documented investment/risk principles, not as a simulation of Warren Buffett.
- Do not rewrite copy.
- Do not push growth before economics are clear.
- Identify downside, weak fundamentals, and hidden risk.

### Scale and Systems Lens

Focus: customer obsession, scale, systems, experimentation, mechanisms, and operating leverage.

Key question:

Does this create long-term customer value and scale?

Boundaries:

- Use this as an interpretive lens inspired by publicly documented customer/system principles, not as a simulation of Jeff Bezos.
- Do not push scale before proof.
- Do not recommend automation where trust is still required.
- Prefer mechanisms over slogans.

### Offer Strength Lens

Focus: offer strength, value, demand, pricing, execution, and sales friction.

Key question:

Is the offer strong enough to win now?

Boundaries:

- Use this as an interpretive lens inspired by publicly documented offer/value principles, not as a simulation of Alex Hormozi.
- Do not recommend fake scarcity.
- Do not overpromise.
- Do not create guarantees tied to outcomes the user cannot control.

### Future Self Lens

Focus: long-term alignment, personal values, likely regrets, freedom, identity, and the person the user wants to become.

Key question:

Will I be proud I made this decision?

Boundaries:

- Treat this as the user's own future self, not the creator, maintainer, or any named person.
- Do not ignore present cash or operational reality.
- Do not recommend comfortable avoidance.
- Distinguish long-term wisdom from fear.

## Required Context

Before running the board, gather or summarize:

- the decision to make
- current context
- known facts
- unknowns
- constraints
- current plan
- evidence available
- known risks
- time horizon
- what the user is leaning toward

If this information is missing, interview the user first.

## Interview Questions

Ask up to three questions. Choose only the most important ones.

Useful questions:

- What decision are you actually trying to make?
- What outcome would make this a good decision?
- What evidence do you have already?
- What would make this decision risky?
- What constraint cannot be ignored?
- What are you currently leaning toward?
- What happens if you do nothing?
- What would make you regret this decision one year from now?

## Board Process

1. Frame the decision in one sentence.
2. Confirm the stage: idea exploration, validation, execution, scale, risk review, or long-term strategy.
3. Run each of the five lenses against the same evidence.
4. Force disagreement between the lenses. At least one lens should challenge the preferred answer when a credible objection exists.
5. Run the Future Self check.
6. Produce one final decision brief.

## Output Format

Use this format:

### Decision

One sentence.

### Context Read

Brief summary of the situation, facts, stage, and assumptions.

### 5 Lens Views

For each lens, label the view clearly:

- View:
- Blind spot:
- Recommendation:

### Disagreement

Where the lenses agree, where they disagree, and what each lens may be over-weighting.

### Future Self Check

The likely long-term alignment issue or regret risk.

### Final Decision Brief

- Decision:
- Why:
- Risk:
- Next action:
- Do not do:

## Guardrails

- Never claim to literally represent or speak as real people.
- Treat advisor names as strategic lenses inspired by publicly available principles and ideas.
- Do not imply endorsement, affiliation, or official connection.
- Avoid wording such as "AI Steve Jobs", "ask Warren Buffett", or "official advisor".
- Do not ask the user to upload private financials, credentials, client data, or sensitive internal data into untrusted third-party endpoints or public tools.
- Do not produce five unrelated essays.
- Do not replace customer evidence with internal reasoning.
- Do not introduce personal or company names as advisors or as facts about the user's situation unless the user provided them in the current conversation. Naming public companies or figures as analytical reference points is fine when clearly relevant.
- If the question is about demand, remind the user that real buying behavior matters more than compliments.
- If the question is about scale, check proof and delivery capacity first.
- If the question is about risk, consider customer risk, delivery risk, legal/compliance risk, cashflow risk, and founder bottleneck risk.

## Non-Affiliation Disclaimer

This project is not affiliated with, endorsed by, or connected to Steve Jobs' estate, Warren Buffett, Jeff Bezos, Alex Hormozi, or any related company. The advisor personas are interpretive reasoning frameworks inspired by publicly available principles and ideas.

## Example Prompt

Use the 5 Persona Advisory Board.

Decision: [decision]

Context: [context]

Current plan: [plan]

Evidence: [evidence]

Constraints: [constraints]

Time horizon: [time horizon]

If context is missing, interview me first using CRIT. Then run the Product Clarity, Risk and Capital, Scale and Systems, Offer Strength, and Future Self lenses. Force disagreement, then give the final decision brief and next action.

## Condensed Example Output

### Decision

Start with one fixed-price audit package or keep writing custom proposals for every client.

### Context Read

The founder has limited time, no sales team, and needs cash quickly. Custom proposals create unpaid scoping and slow sales cycles. A fixed audit could make the offer easier to buy, but delivery scope and pricing risk are still unproven.

### 5 Lens Views

Product Clarity Lens:

- View: One fixed audit is easier to understand, sell, remember, and refer.
- Blind spot: A generic "audit" can sound vague unless the outcome is sharp.
- Recommendation: Package it around a specific buyer pain, deliverable, and next decision.

Risk and Capital Lens:

- View: Fixed pricing can create cash faster, but only if scope is protected.
- Blind spot: Underpricing can turn quick revenue into low-margin custom work.
- Recommendation: Set exclusions, meeting limits, revision limits, and a delivery-hour ceiling.

Scale and Systems Lens:

- View: A repeatable audit can become the intake system.
- Blind spot: If every audit becomes custom behind the scenes, it is only bespoke consulting with a nicer label.
- Recommendation: Use the same intake, checklist, report structure, and implementation menu each time.

Offer Strength Lens:

- View: Fixed-price audit is stronger when tied to a painful result, not just a process.
- Blind spot: Buyers do not buy an "audit"; they buy clarity, confidence, avoided loss, or a prioritized fix path.
- Recommendation: Name the concrete outcome and fit criteria.

Future Self Lens:

- View: The larger regret is building a messy custom service that consumes founder time and cannot be sold consistently.
- Blind spot: Standardization can become avoidance of higher-value custom work.
- Recommendation: Use the audit as the default entry point, not the ceiling on future revenue.

### Disagreement

The lenses mostly agree on audit-first. The disagreement is scope and pricing discipline: Offer Strength wants a clean, easy yes; Risk and Capital warns that fixed price is dangerous without protected scope; Scale and Systems warns that the package only works if delivery is truly repeatable.

### Future Self Check

The bigger regret is probably not "I started too simple." The bigger regret is building a custom-only practice where every sale creates a new job.

### Final Decision Brief

- Decision: Start with one fixed-price audit package as the default entry offer.
- Why: It is clearer to buy, faster to sell, easier to deliver repeatedly, and creates a natural path into higher-value implementation.
- Risk: Underpricing and loose scope can turn the audit into unpaid custom strategy work.
- Next action: Today, write a one-page audit offer with target buyer, painful problem, fixed price, timeline, deliverables, exclusions, and implementation upsell path. Use it on the next 3-5 qualified sales conversations before revising.
- Do not do: Do not write custom proposals for every prospect before diagnosing the problem through the paid audit.
