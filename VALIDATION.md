# Release validation

> The entries below record what was checked at the time, in the terms of that time. Since then the five skills were merged into two (`spec-audit` and `spec-investigation` into `project-knowledge`, `spec-plan` into `spec-change`), the generated `AS-BUILT.md`, `GAPS.md` and `graph.html` were replaced by the viewer, and the `build` command was removed. None of that has been evaluated with a fresh agent yet; `spec-change` has not been run on a real change.

## 2026-11-15: first real use, and fixes since

Observed facts, with their limits:

- The spec/gap format was used for a real migration, and then for a first sync, of a 99-page vault in another project. The structural check of the migrated vault finished with no errors.
- `maintain.py finish` could not advance the checkpoint, because another contributor had uncommitted edits to files the range touched. The documented `deferred` disposition was not accepted by the helper at that time.
- That use exposed eight problems: `deferred` could not be used; strict `check` could not pass while someone else's work was uncommitted; a vault commit made during a pending range moved the scan target; `receipt` cleared dispositions without saying so; the recheck values read as "the defect was reproduced", which left proposal and research gaps without an honest route to `needs-decision`; one frontmatter error produced many misleading "missing wikilink" errors; `snapshot --notes` was blocked by unrelated errors; and nothing said how `done` and a recheck relate.
- The code fixes in this change have automated tests: partial finish (`deferred`, exit status 3), `check --strict --ignore-dirty`, the target and receipt messages and retargeting, the recheck labels printed in `GAPS.md`, link registration for pages with errors, and `snapshot --notes` on selected pages. The rule for closing a gap as `done` (an agent that sets `done` records a `not-reproduced` recheck), the single meaning of recheck for every gap kind, and the migration guide are instruction text only: no test checks that an agent follows them, and the helpers do not enforce the `done` rule. No fresh agent has yet been run with the changed instructions, and the migrated vault has not been re-synced with them.

This is one project, one vault and one contributor setup. It shows that the format could be applied and which things went wrong; it is not a measure of how reliably an agent will follow the changed instructions.

## 2026-11-15: spec/gap split, not yet revalidated

The vault format, validator, viewer and skill instructions changed to separate the as-built spec from a per-item gap layer (new `gap` properties, `plan` pages, generated `AS-BUILT.md` and `GAPS.md`, new `maintain.py receipt`, merge rules for gap pages). Every observation recorded below was made on the **previous** version. The agent smoke tests, the concurrent merge evaluation and the browser observations have **NOT been rerun** against the new format, and nothing below should be read as a result for it. The example vault's Markdown was migrated by hand and its generated artifacts are regenerated separately. Rerun `python3 scripts/verify.py` and the scenarios in [the evaluation guide](docs/evaluation.md) before relying on this release.

## Observations on the previous version

This file records observed checks for the toolkit and its concurrent-merge update. The fictional worked reports under `examples/parcel-desk/reports/` illustrate output shapes; they are not transcripts of these independent evaluations.

## Independent agent smoke tests

Fresh Codex agent contexts received one skill and only the raw fictional spec, source and tests, without the example reports or expected answers.

| Skill | Observed outcome |
| --- | --- |
| `spec-audit` | Found CAN-1's packed-owner mismatch, reproduced the adapter response, distinguished the missing regression test and left DEC-1 as an open decision. Covered the stated ownership and collected-state requirements. No application edits. |
| `spec-investigation` | Traced the service exception and adapter mapping, reproduced owner 409 versus other-customer 403 with unchanged state, and distinguished the local fixture from a real failed request. No application edits. |
| `spec-plan` | Proposed the shared service change with ordered tests, observable response/state criteria and unchanged ownership/collected rules. Kept partner behavior undecided. No implementation edits. |
| `project-knowledge` | Built a source-backed map in a separate Git fixture, preserving a preexisting human note byte for byte. After a new commit, discovered two changed source paths including a previously unmapped entrypoint, updated affected notes, retained all original IDs, and advanced the reviewed checkpoint using an exact-plan receipt. A no-change rerun left canonical notes, views, fingerprints and cursor byte-identical. |

Each of these three runs also executed the existing fixture suite: 3 tests passed. The suite intentionally lacks the packed success case. Passing it does not establish compliance with CAN-1.

The first knowledge sync produced 12 pages and 52 links. After the final evidence-guard correction, a further test-only commit was reviewed with the updated helper: the checkpoint advanced successfully, all previous IDs and the human note were preserved, and a fresh scan was clear. This final map had 13 pages and 62 links with zero validation warnings. Its four tests and focused probes passed. The fixture had no remote, so this demonstrates local integrated history review, not a live multi-contributor remote sync. The intentional partner decision remained open.

## Repeatable checks

`python3 scripts/verify.py` passed locally on macOS with Python 3.14, including an invocation from outside the repository directory:

- All four skill frontmatter entries and local Markdown links.
- 43 knowledge helper tests, including changed-source freshness, incremental review safeguards and concurrent-merge inspection. Regression cases reject local-only evidence, dirty excluded paths and changes hidden by Git index flags, without advancing fingerprints or the reviewed cursor; clean tracked evidence is accepted.
- 3 fictional application tests.
- Strict example vault validation: 11 notes, 59 links, zero warnings.
- The regenerated graph matches the shipped one, ignoring only generation time.
- Viewer JavaScript syntax, using the available Node executable, plus a focused DOM-stub check that bold text preserves nested wiki links, source links and code without interpreting raw HTML. The stub check does not independently test URL validation or replace browser observations.

The skill-authoring validator also passed for all four skill folders. The portable verification command requires no installed skill-authoring tools. Node is optional and its syntax check reports `NOT RUN` when unavailable.

## Concurrent merge validation

A fresh Codex agent used the merge workflow on updates created in two separate local clones sharing a local bare remote. It resolved five textual conflicts, retained both contributors' useful handoffs, reconciled duplicate IDs through a canonical note and a superseded pointer, and preserved both email-policy proposals as an explicit conflict. Source, spec and tests were unchanged; both contributor tips remained in the integration history.

The divergent reviewed-state proposals were replaced with the coherent common-base pair. After raw tracked-byte verification, only selected reviewed guard notes received accepted fingerprints. The shared cursor stayed at the common checkpoint. The final vault had 15 pages and 84 links with zero strict validation warnings; three existing fixture tests passed. The integration branch guard remained visible and shared `finish` was not run on that temporary branch. No remote push, browser or Obsidian GUI check was part of this merge evaluation. This verifies local two-clone reconciliation, not a hosted multi-user service or live simultaneous editing.

Independent review also reproduced and verified fixes for bytecode writes during inspection and conflict-marker false negatives. Tests cover ordinary and configured marker widths, a conflict containing a standalone `<` line, and valid fenced operator text. The inspector denies Git transports and rejects partial/promisor configuration before object inspection; its tests use simulated configuration, not a live promisor remote. Snapshot checks compare the repository and a copied skill folder before and after inspection to verify no file changes. Marker detection covers complete labeled Git groups; custom unlabeled conflict formats still require manual/index inspection.

## Browser observations

Chrome on macOS loaded the example through a loopback HTTP server. Observed: 11 materials; search for `packed` narrowed the list; the gap filter showed three items; side-list and graph-node selection opened readable notes; bold text rendered; an internal wikilink changed the selected note; and the planned item showed the `Product plan` badge. After the renderer correction, a bold internal link still navigated correctly and coverage sections displayed as readable prose.

The evidence link targeted the correct fictional `src/pickups.py` URL. Chrome blocked opening its content with `ERR_BLOCKED_BY_CLIENT`. A separate HTTP read returned 200 and bytes identical to that source file. Browser evidence-content viewing is therefore **BLOCKED**, not passed. The README describes the repository-relative path fallback for an editor.

Direct `file://` loading, a narrow viewport and this example's Obsidian GUI were **NOT RUN**. The generated HTML embeds its data and scripts and has no external resource dependency, but static inspection is not a direct-file browser test.

## Limits

These are bounded smoke tests, not a benchmark or a guarantee of complete project coverage. Codex agents executed the skills from their folders; an installation/restart round trip was not part of the evaluation. Other agent hosts and their installation mechanisms have not been integration-tested. No production system, authentication provider, database or real customer data is part of this fixture.

See [the evaluation guide](docs/evaluation.md) for repeatable prompts, isolation requirements and the evaluator's rubric.
