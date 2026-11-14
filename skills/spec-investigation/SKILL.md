---
name: spec-investigation
description: Investigate one software behavior, discrepancy, or disputed claim using repository and runtime evidence. Use to answer a focused why or what-happens question or identify the check that would resolve it.
license: MIT
---

# Spec Investigation

Answer one question under defined conditions. Read the repository instructions and preserve existing edits. Keep the work scoped to diagnosis and the requested report.

1. State the question in observable terms. Include the affected actor, input, expected behavior, and observed or reported behavior when known. Establish the relevant commit and environment if available. Ask for an essential missing fact only when it prevents useful progress. Otherwise proceed and state the assumption.
2. Trace the narrowest path that can answer the question. Start at the reported entry point and follow its actual callers or handlers to the relevant rule, side effect, or state change. Inspect the spec, implementation, and applicable tests, logs, or prior observations. Keep user-reported observations separate from behavior reproduced during the investigation.
3. Compare credible explanations when the evidence supports more than one. Look for the condition that would differ between them, such as a role check, a feature flag, or a second entry point. Prefer an available safe check that distinguishes outcomes. Run it when it is in scope, executable, and useful. If static evidence settles the code path, stop broadening the search and qualify any remaining runtime claim.
4. Cite repository-relative paths with symbols, headings, or line anchors. Record the reviewed revision and relevant local changes when available. For each executed check, report the command or action, result, and what it establishes. Mark unexecuted checks as `NOT RUN`. Identify stale, incomplete, or indirect evidence that materially affects confidence.

Lead with the supported answer and the conditions under which it holds, or state what remains unresolved. Then give the decisive evidence chain and relevant alternatives. If a material uncertainty remains, name one practical next check and say what each plausible result would establish. A product decision may be the remaining dependency. Name the choice and the consequences of each option.

Write in English unless requested otherwise. Return the findings inline or at the requested destination. Keep existing evidence IDs stable in persisted reports and give new evidence short reusable IDs. An existing vault or prior report can guide discovery. Recheck consequential claims against their sources. For a requested canonical vault entry, use the existing contract only when it is available and compatible. Otherwise provide a normal report with a note about the missing contract.
