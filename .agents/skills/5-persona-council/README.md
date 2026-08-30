# 5 Persona Advisory Board

![5 Persona Advisory Board hero](assets/5-persona-advisory-board-hero.png)

Stress-test an important decision through five strategic lenses inspired by legendary business thinking, and leave with one clear next action.

The method is inspired by public business principles associated with Jobs, Buffett, Bezos, Hormozi, and long-term future-self thinking. These are analytical lenses, not celebrity simulations, endorsements, or affiliated advisors.

Built for founders, consultants, operators, and AI power users making high-leverage decisions about launches, pricing, hiring, pivots, client risk, strategic focus, and stop/continue calls.

## Quick Start

Choose the path that matches how you use AI tools.

Portable skill key: `5-persona-advisory-board`.

### Regular Claude User

No terminal required.

1. Open Claude.
2. Create a new Project.
3. Name it `5 Persona Advisory Board`.
4. Open Project Instructions or Custom Instructions.
5. Paste the full contents of [`SKILL.md`](SKILL.md).
6. Start a new chat inside that Project.
7. Give it an important decision.

### Regular ChatGPT User

No terminal required.

Use one of these paths:

- Paste the full contents of [`SKILL.md`](SKILL.md) into a ChatGPT Project instruction area.
- Paste it into Custom GPT instructions if you are making a reusable GPT.
- Paste it at the top of a normal ChatGPT chat, then provide your decision.

Then use:

```text
Use the 5 Persona Advisory Board on this decision:

[paste decision here]
```

### Agent User

If you use ChatGPT Codex, Claude Code, Codex, Hermes, OpenClaw, or another coding agent, give your agent this:

```text
Install this skill from GitHub:
https://github.com/harryvondiesel-web/5-persona-advisory-board

Use the portable skill key: 5-persona-advisory-board.

After installing, start a fresh session and run 5 Persona Advisory Board on the decision I provide.
```

### Terminal Install

Codex:

```bash
mkdir -p ~/.codex/skills/5-persona-advisory-board
cp SKILL.md ~/.codex/skills/5-persona-advisory-board/SKILL.md
```

Hermes:

```bash
mkdir -p ~/.hermes/skills/productivity/5-persona-advisory-board
cp SKILL.md ~/.hermes/skills/productivity/5-persona-advisory-board/SKILL.md
```

OpenClaw: see [Installation Notes](#installation-notes).

Use this prompt:

```text
Use the 5 Persona Advisory Board skill.

Decision: Should I launch my new offer now or keep refining it?
```

Expected behavior: if the decision is missing context, the skill should interview first instead of running the full board.

For this prompt, an example interview may look like:

```text
That is not enough context yet. Running the five lenses now would mean inventing your offer, evidence, and constraints. Per CRIT, interview first.

1. What exactly is the offer, and what does "launch" mean in practice?
2. What evidence do you already have, and what is still unfinished?
3. What constraint cannot be ignored, and what are you leaning toward?
```

With enough context, it produces:

- Decision
- Context Read
- 5 Lens Views
- Disagreement
- Future Self Check
- Final Decision Brief

The interview questions should adapt to the decision. A pricing decision should ask about demand, margins, and buyer reaction. A hiring decision should ask about workload, risk, budget, and timing. A stop/continue decision should ask about evidence, opportunity cost, and what would change the answer.

## Why This Exists

Most AI advice sounds confident too early. This skill forces the AI to interview first, run five distinct lenses against the same evidence, surface disagreement, and end with one practical decision brief.

The point is to stop using AI only for minor tasks, like basic emails or summaries, and start using it as a strategic thought partner for the few decisions that actually change the business.

The workflow is CRIT:

- Context: understand the decision before evaluating it
- Role: apply five clearly separated strategic perspectives
- Interview: ask targeted questions instead of making assumptions
- Task: synthesize the analysis into a practical recommendation

Use it for the 20% of decisions that drive 80% of results:

- Launch now or keep refining
- Raise prices or hold
- Accept or reject a risky client
- Build a feature or stay focused
- Enter a new market
- Stop, continue, or restructure a struggling project

Do not use it for basic lookup, tiny admin choices, or decisions where no real action will follow.

## The Five Lenses

- Product Clarity: vision, product design, focus, taste, storytelling, and memorability; inspired by public principles associated with Jobs
- Risk and Capital: long-term planning, downside, incentives, durability, and margin of safety; inspired by public principles associated with Buffett
- Scale and Systems: customer value, operational efficiency, mechanisms, repeatability, and operating leverage; inspired by public principles associated with Bezos
- Offer Strength: demand, pricing, value, sales friction, and execution; inspired by public principles associated with Hormozi
- Future Self: long-term regret, alignment, identity, freedom, and the person you want to become

The Future Self lens is your own future self, not any named person. The Product Clarity lens is not for general marriage, parenting, or personal leadership advice; it is focused on product, story, taste, and strategic clarity.

## Compatibility

Current public version: `0.2.1`.

Core behavior tested on 2026-07-24 with skill version `0.2.0`.
OpenClaw status updated on 2026-07-28 after current OpenClaw behavior testing.

| Platform | Status | Notes |
| --- | --- | --- |
| Claude | Supported | Behavior validated before packaging. |
| ChatGPT | Expected | Paste `SKILL.md` into a Project, Custom GPT, or normal chat context. |
| Codex | Supported | Installed at `~/.codex/skills/5-persona-advisory-board/SKILL.md`; full-context and interview-first tests passed. |
| Hermes | Supported | Installed at `~/.hermes/skills/productivity/5-persona-advisory-board/SKILL.md`; full-context and interview-first tests passed. |
| OpenClaw | Supported | Current OpenClaw behavior validated on 2026-07-28; treat on equal footing with Claude, Codex, and Hermes for supported skill use. |

Compatibility can decay as platforms change.

## Installation Notes

### Claude

Create a Claude project or custom instruction set for the skill, then paste the full contents of `SKILL.md` into the project instructions/custom skill area. Start a fresh Claude conversation after adding it.

### ChatGPT

Paste the full contents of `SKILL.md` into a ChatGPT Project, Custom GPT instructions, or the top of a normal chat. Then provide an important decision and ask ChatGPT to use the 5 Persona Advisory Board.

### Codex

Copy `SKILL.md` into:

```bash
mkdir -p ~/.codex/skills/5-persona-advisory-board
cp SKILL.md ~/.codex/skills/5-persona-advisory-board/SKILL.md
```

Start a fresh Codex chat if the skill index was already loaded.

### Hermes

Copy `SKILL.md` into:

```bash
mkdir -p ~/.hermes/skills/productivity/5-persona-advisory-board
cp SKILL.md ~/.hermes/skills/productivity/5-persona-advisory-board/SKILL.md
```

Start a fresh Hermes session if the skill index was cached before install.

### OpenClaw

OpenClaw support is tested and supported for the `0.2.x` workflow. Current package version: `0.2.1`.

Current OpenClaw behavior was validated on 2026-07-28. OpenClaw should be treated on equal footing with Claude, Codex, and Hermes for this skill.

For independent verification, use the same shared checks in [docs/compatibility-test-checklist.md](docs/compatibility-test-checklist.md).

## Example Output

See [examples/fixed-price-audit-decision.md](examples/fixed-price-audit-decision.md).

The example is abbreviated for README readability. It shows the distinctive parts: the decision, conflicting lens views, central disagreement, final decision, risk, next action, and do-not-do.

## Pro Tips

Speak your answers. Messy is fine. When the AI starts the interview, use speech-to-text or a rough brain dump instead of trying to write polished answers. Context is king, and the AI can organize unstructured thoughts better than it can invent missing facts.

Use the "What else?" habit. When the AI is interviewing you and you think you have given enough detail, ask:

```text
What else should you know before running the board?
```

Push 2-3 levels deeper into context. Better context creates better strategy.

Do not trust the first draft. Treat the first board output as draft one, then respond with what you liked, what felt weak, and the top changes you want.

Play the AI against itself. After you get a strong recommendation, red-team it with a challenger prompt:

```text
Now act as an aggressive, risk-averse challenger board member.
Stress-test this plan and show me where the cracks are.
```

For customer-facing decisions, flip into the ideal customer perspective:

```text
Now act as the ideal customer persona we defined earlier.
Read this plan and tell me if it would actually make you buy, or if you would ignore it.
```

## Limits

This skill reorganizes and stress-tests the context you provide. It does not prove market demand, validate customer behavior, or make unsupported assumptions true.

Do not include secrets, credentials, private client data, regulated information, or sensitive internal records in prompts.

This is not legal, medical, financial, tax, or investment advice. For high-stakes regulated decisions, use qualified professionals.

## Scope

This repository is a free reusable decision-stress-testing skill.

It is not:

- A full business-scaling playbook
- An employee performance system
- A sales coaching automation
- A voice-of-customer automation
- An agentic CFO
- A general enterprise AI operating system

Those can be separate workflows. This repo stays focused on one job: helping users make better high-leverage decisions.

## Non-Affiliation Disclaimer

The 5 Persona Advisory Board is inspired by public business principles associated with Jobs, Buffett, Bezos, Hormozi, and long-term future-self thinking.

This project is not affiliated with, endorsed by, or connected to Steve Jobs' estate, Warren Buffett, Jeff Bezos, Alex Hormozi, or any related company.

## Feedback

Please open an issue with:

- Skill version
- Platform and version
- Installation method
- Prompt used
- Expected behavior
- Actual behavior
- Sanitized example output with private information removed

Use feedback labels such as `bug`, `compatibility`, `output-quality`, and `enhancement`.

## Contact

For bugs, compatibility reports, and output-quality issues, please open a GitHub issue.

Created by BVD AI CORE: https://www.bvdaicore.com

Direct contact: bvdaicore@outlook.com

## License

MIT. See [LICENSE](LICENSE).
