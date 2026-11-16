# Audit a specification against the code

Compare a bounded set of requirements with what the code does, and show where the evidence supports a decision. Follow repository instructions, stay within the requested scope and preserve existing edits. This skill inspects and reports; changing the application or creating tickets is a separate task.

## Compare requirements with evidence

1. Inventory the requirements in scope, keeping their IDs or assigning short labels. Turn broad statements into observable conditions without hiding real ambiguity. Separate accepted requirements from proposals and historical documents, and note deliberate exclusions.
2. Trace each condition through the entry point, the policy or service, and the tests. Check role, configuration, feature flag or environment only where it can change the answer, and follow actual callers before calling a path missing. Record requirements the evidence supports as well as problems, and what you excluded or could not inspect.
3. Cite the requirement side and the implementation side separately, with repository-relative paths and a line range, heading, symbol or test name. Record the Git revision and any relevant uncommitted changes. Label documented intent, static reading, inference and observed execution. Give commands and outcomes for checks you ran; mark anything you only read or proposed `NOT RUN`.
4. When sources seem to contradict, check version, authority and the conditions each describes. If they genuinely disagree, keep both claims. A clear requirement with no implementation is a product gap; two credible sources that prescribe incompatible behavior under the same conditions are a conflict.

## Classify findings

Pick one primary classification per finding.

| Classification | Meaning |
| --- | --- |
| `product-gap` | An accepted requirement is missing or unmet on the inspected path. |
| `verification-gap` | Evidence falls short of confirming behavior, e.g. a boundary case has no test or a needed check was not run. |
| `product-plan` | The behavior is only planned, or the spec leaves a product choice open; name the decision. |
| `conflict` | Credible sources disagree under comparable conditions and it still needs reconciling. |
| `knowledge-gap` | Missing or outdated documentation makes established behavior hard to understand. |

Something you could not assess because of scope, access or a dependency is a limit of the audit, not a finding; state what would allow review. (Deferring a gap is a person's decision, not a classification.)

Set priority from user impact, urgency or decisions blocked, and state confidence separately, from the strength and coverage of the evidence. A potentially severe finding with weak evidence can deserve quick verification.

## Report

Return the report inline unless a destination is given, in English unless asked otherwise. Use these headings so audits can be compared:

```text
# Audit: <scope>
## Basis            revision, dirty files, requirement documents, what was and was not inspected
## Findings         per finding: id, condition, expected vs observed, classification,
                    evidence, impact, priority, confidence, smallest next action
## Confirmed        one row per requirement the code satisfies, with its evidence
## Open decisions   choices that need an owner, with options
## Limits and checks  commands run with results, NOT RUN items, what could not be assessed
```

Lead with the findings that most affect the next decision. In a persistent report keep finding and evidence IDs stable so later reviews can update them.

## Recording the audit in the vault

An existing vault is a pointer to sources, not evidence: verify against the cited code. If the user wants the audit recorded in a vault that uses gap pages (it has a `gaps/` folder), follow [gaps.md](gaps.md); otherwise return the ordinary report and say the vault format was not available.

- Each finding that needs action becomes **its own gap page** with `decision: "open"`, `recheck: "not-checked"` and the classification as `kind`. The audit that found it is not its recheck. Split a finding with two aspects that have different next steps.
- Requirements confirmed as implemented are not gaps. They belong in the report's Confirmed section; if the vault's spec notes are missing or wrong about them, say so, but do not turn that into a gap unless something is actually in doubt.
- Check for an existing gap on the same question before writing a new one; add to its `Discussion` instead.
- Record the audit itself as one `runs/` page (type `run`) listing the requirements assessed, the revision, the checks run and links to the gaps it created. Do not write a combined page of findings: the gaps are the findings.
- Do not set `accepted`, `rejected` or `deferred`. People decide those after rechecking.
