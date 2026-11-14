---
name: spec-plan
description: Plan an intended software change against the current repository. Use to define scope, affected modules, implementation order, decision gates, and observable acceptance criteria before implementation.
license: MIT
---

# Spec Plan

Turn a requested future behavior into a plan someone else can implement and verify. Read repository instructions and use the project's existing planning format when it has one. The deliverable is the plan.

## Anchor the change

- Describe who benefits, what triggers the behavior, and what the user should observe afterward. State the current behavior separately and cite the actual route, module, symbol or spec section that supports it. Record the inspected revision if available and disclose relevant working tree changes.
- Trace the current flow far enough to find the shared contracts and callers that the change could affect. Include data, permissions, integration, migration or rollout implications only when the requested change touches them. Identify probable modules by path and point to the relevant symbol or contract. Mark proposed new files and uncertain impact as such.
- List required outcomes and explicit scope boundaries. Surface undecided behavior as a decision with options, impact and the steps it gates. Keep independent work actionable. State reversible assumptions and distinguish them from decisions already made.
- Check material claims in any existing specs, research or vault notes against source. Keep implementation evidence, documented intent, assumptions and executed checks distinct. Mark a test you read but did not run as `NOT RUN`.

## Make it implementable

For each step, state the behavior or contract that changes, the affected area, prerequisites and a check that would verify the change. Sequence shared contracts before dependent callers when relevant. Use smaller increments when they make review or rollback easier. Build on existing conventions and explain consequential choices with evidence.

Write acceptance criteria as checkable observations. A criterion should identify the setup, trigger and expected result at the right boundary. Cover the main outcome and the failures or regressions that matter to this change, such as a denied action leaving stored state unchanged. Include precise commands when known and distinguish planned checks from checks actually executed. Link acceptance criteria to steps or decisions wherever traceability helps.

Deliver the baseline and goal, scope, ordered work, acceptance criteria and open decisions. Use stable requirement, evidence and check IDs when a persistent report calls for them. Write in English unless requested otherwise. Return the plan inline by default or write it to the requested destination. When asked to add the plan to a canonical vault, follow the existing format only if the contract is available and compatible. Otherwise deliver a normal plan and report the missing contract.
