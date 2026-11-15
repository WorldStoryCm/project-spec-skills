---
name: spec-investigation
description: Investigate one software behavior, discrepancy, or disputed claim using repository and runtime evidence. Use to answer a focused why or what-happens question, identify the check that would resolve it, or re-check one gap page in a project-knowledge vault.
license: MIT
---

# Spec Investigation

Answer one question under defined conditions. Read repository instructions, preserve existing edits and keep the work to diagnosis and the report.

1. State the question in observable terms: the actor, input, expected behavior and reported behavior when known, plus the commit and environment if you can establish them. Ask for a missing fact only if it blocks useful progress; otherwise proceed and state the assumption.
2. Trace the narrowest path that can answer it. Start at the reported entry point and follow its actual callers or handlers to the rule, side effect or state change. Look at the spec, the implementation and the applicable tests, logs or earlier observations. Keep what users reported separate from what you reproduced.
3. When the evidence supports more than one explanation, find the condition that would differ between them (a role check, a flag, a second entry point). Prefer a safe check that tells them apart and run it when it is in scope and executable. If static evidence settles the code path, stop widening the search and qualify any remaining runtime claim.
4. Cite repository-relative paths with symbols, headings or line anchors. Record the reviewed revision and relevant local changes. For each check you ran give the command or action, the result and what it establishes; mark unexecuted checks `NOT RUN`. Say which evidence is stale, incomplete or indirect where that affects confidence.

## Report

Return the findings inline unless a destination is given, in English unless asked otherwise.

```text
# Investigation: <question>
## Answer          the supported answer and the conditions under which it holds, or what is unresolved
## Evidence chain  the decisive path, with citations
## Alternatives    other explanations and why they do or do not hold
## Checks          commands run with results; NOT RUN items
## Next            one practical next check and what each plausible result would establish;
                   any product decision that remains, with options
```

Keep existing evidence IDs stable in persisted reports and give new evidence short reusable IDs.

## With a project-knowledge vault

This is the tool for re-checking one gap. An existing vault or earlier report can guide discovery, but verify consequential claims against their sources. When asked to re-check a gap, or to record a result in the vault, follow [gaps.md](references/gaps.md). If that file or the vault is not available, return the ordinary report and say so.

- Re-check what that gap actually asks, against the current code, and run what can be run. Write the outcome into the gap's `Recheck` section: what you did, when, what you found, with the usual `NOT RUN` honesty.
- Set `recheck` to `confirmed` (the gap's description is still true) or `not-reproduced` (it is not), `rechecked_by` to `agent` (a person's name goes there only when that person ran the check and told you so), and `rechecked_on` to today's date. This replaces an earlier `outdated` mark and its dated record; add a new dated entry to `Recheck` and keep the older ones. Update `updated`.
- Do not touch `decision`, `decided_by` or `decided_on`. The recheck informs a person; it does not settle the question, even when it finds the gap is not reproduced or already closed by the code. Say so in `Recheck` and in your report.
- If you found options or consequences a decider needs, add them as an `agent` entry in `Discussion`. If the investigation raises a different question that needs action, open it as a new gap rather than widening this one.
