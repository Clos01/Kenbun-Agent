# Compatibility Test Checklist

Use the same definition of "pass" for every platform.

## Missing-Context Test

Prompt:

```text
Use the 5 Persona Advisory Board skill.

Decision: Should I launch my new offer now or keep refining it?
```

Pass if the platform:

- Does not run the full board immediately
- Says context is missing
- Asks 1-3 focused interview questions
- Does not invent offer, evidence, constraints, risks, lean, or time horizon

## Full-Context Test

Prompt:

```text
Use the 5 Persona Advisory Board skill.

Decision: Should a small consulting business offer one fixed-price audit package first, or start with custom proposals for every client?

Constraints: The founder has limited time, no sales team, and needs cash quickly. The risks are underpricing the work, confusing buyers, and building a service that is hard to deliver repeatedly.

Current leaning: Start with one fixed-price audit package, then offer custom implementation only after the audit.
```

Pass if the platform:

- Produces Decision, Context Read, 5 Lens Views, Disagreement, Future Self Check, and Final Decision Brief
- Avoids celebrity roleplay
- Avoids private assumptions
- Does not claim affiliation or endorsement
- Gives specific, non-generic advice
- Forces at least one credible disagreement
- Gives a concrete next action and do-not-do

## Output Quality Failures

Treat output as failed if:

- Three or more lenses make essentially the same argument
- Advice would fit almost any decision
- Supplied constraints are ignored
- "Gather more data" substitutes for a decision
- The final action has no owner, threshold, or timing
- The preferred answer goes unchallenged despite credible risks
- The skill fabricates evidence
