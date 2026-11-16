# Plan a change without building it

Turn a requested future behavior into a plan someone else can implement and verify. Read repository instructions and use the project's planning format if it has one. The deliverable is the plan; implementing it is separate.

## Anchor the change

- Say who benefits, what triggers the behavior and what they should observe afterwards. State the current behavior separately, citing the actual route, module, symbol or spec section. Record the inspected revision and disclose relevant working tree changes.
- Trace the current flow far enough to find the shared contracts and callers the change could affect. Mention data, permissions, integration, migration or rollout only when the change touches them. Name probable modules by path and symbol; mark new files and uncertain impact as such.
- List required outcomes and explicit scope boundaries. Turn undecided behavior into a decision with options, impact and the steps it gates, and keep independent work actionable. Separate reversible assumptions from decisions already made.
- Check claims in existing specs, research or vault notes against source. Keep implementation evidence, documented intent, assumptions and executed checks distinct, and mark tests you only read `NOT RUN`.

## Make it implementable

For each step state the behavior or contract that changes, the affected area, prerequisites and a check that verifies it. Put shared contracts before their callers and prefer small increments that are easy to review or roll back. Follow existing conventions and explain consequential choices with evidence.

Write acceptance criteria as checkable observations, each naming the setup, trigger and expected result at the right boundary. Cover the main outcome and the failures that matter here, such as a denied action leaving stored state unchanged. Give exact commands where known, and keep planned checks separate from checks actually run. Link criteria to steps or decisions where it helps.

## Report

Return the plan inline unless a destination is given, in English unless asked otherwise.

```text
# Plan: <change>
## Baseline and goal   current behavior with citations; the wanted outcome
## Scope               in scope, out of scope, assumptions
## Ordered work        numbered steps: change, files, prerequisites, check
## Acceptance          checkable observations; planned vs executed
## Open decisions      choices that gate steps, with options
```

Use stable requirement, evidence and check IDs when a persistent report calls for them.

## Recording the plan in the vault

When asked to plan a gap, or to add the plan to the vault, follow [gaps.md](gaps.md). If that file or the vault is not available, return the ordinary plan and say so.

- Plan only a gap whose `decision` is `accepted`, because the plan spends effort on something a person chose to pursue. Write it to `plans/<gap-id>.md` with `type: "plan"`, `gap: "<gap-id>"`, the gap's areas and `status: "planned"`. Link the spec notes that describe current behavior; do not add plan content to spec notes.
- If the gap is `open` (whether `needs-recheck` or `needs-decision`), say that a decision is needed first and stop. You may lay out the options, with their consequences, as an `agent` entry in that gap's `Discussion`. If the gap is `rejected`, `deferred` or `duplicate`, say that and write no plan.
- A request to plan is not an acceptance. Record `accepted` only if the person says in so many words that they accept the gap, and then under their name and the date.
- Do not change the gap's other fields. When the work is done, the gap moves to `done` through a later check of the code, not through the plan.
