---
name: spec-audit
description: Audit a set of software requirements against repository evidence. Use to find missing behavior, conflicting specs, unverified coverage, and product decisions across a feature or document.
license: MIT
---

# Spec Audit

Review a bounded set of requirements and show where the evidence supports a decision. Follow repository instructions, use the requested scope and preserve existing edits. Inspect sources and report findings. Application changes and ticket creation are separate tasks.

## Compare requirements with evidence

1. Inventory the requirements in scope. Keep their existing IDs or assign short labels. Turn broad statements into observable conditions while preserving ambiguity. Identify deliberate exclusions and distinguish accepted requirements from proposals and historical docs.
2. Trace each condition through the relevant entry point, policy or service, and tests. Check role, configuration, feature flag or environment only when it can change the answer. Follow actual callers before declaring a missing path. Record requirements supported by evidence as well as problems, and record what you excluded or could not inspect.
3. Cite the spec and implementation sides separately, using repository-relative paths and a line range, heading, symbol, or test name. Record the Git revision when available and mention relevant uncommitted changes. Label documented intent, static implementation evidence, inference, and observed execution. Give commands and outcomes for checks you executed. Mark checks you only read or proposed as `NOT RUN`.
4. Reconcile apparent contradictions by checking version, authority, and the conditions each source describes. Preserve both claims when they genuinely disagree. A clear requirement with an absent implementation can be a product gap. If two credible sources prescribe or demonstrate incompatible behavior under the same conditions and the desired behavior needs a decision, record a conflict.

## Classify findings

Choose a primary classification per finding. Use a secondary classification only if it changes the next action.

| Classification | Evidence needed |
| --- | --- |
| `product-gap` | An accepted requirement is missing or unmet on the inspected behavior path. |
| `verification-gap` | Evidence falls short of confirming the behavior, such as a missing test for a boundary case or an unrun check needed for a conclusion. |
| `product-plan` | The behavior is explicitly planned, or the spec leaves a product choice open. Preserve the distinction and name the decision, if any. |
| `conflict` | Credible sources disagree under comparable conditions, and the inconsistency still needs reconciliation. |
| `knowledge-gap` | A documentation omission or outdated explanation makes established behavior hard to understand. |
| `deferred` | A relevant question remains unassessed because of a stated scope, access, or dependency constraint. Record what would allow review. |

Set priority from user impact, urgency, or decisions blocked. State confidence separately, based on the strength and coverage of evidence. A potentially severe finding with weak evidence can merit prompt verification.

## Deliver the audit

Lead with the findings that most affect the next decision. For each, give the condition, expected and observed behavior, classification, evidence, user impact, priority, confidence and smallest next action. Include a coverage list or table with one outcome for each assessed requirement, plus clear limits, open decisions and checks. Reuse stable finding and evidence IDs in persistent reports so later reviews can update or resolve them.

Write in English unless requested otherwise. Return the report inline by default or in the requested destination. An existing vault can help locate sources. Treat its notes as pointers and verify against the cited material. If the user requests canonical vault notes, use the established format only when its contract is available and the vault supports it. Otherwise provide a normal report and flag the missing format information.
