# Release validation

This file records observed checks for the initial release. The fictional worked reports under `examples/parcel-desk/reports/` illustrate output shapes; they are not transcripts of these independent evaluations.

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
- 33 knowledge helper tests, including changed-source freshness and incremental review safeguards. Regression cases reject local-only evidence, dirty excluded paths and changes hidden by Git index flags, without advancing fingerprints or the reviewed cursor; clean tracked evidence is accepted.
- 3 fictional application tests.
- Strict example vault validation: 11 notes, 59 links, zero warnings.
- Regenerated graph, HTML payload and Canvas match their shipped artifacts, ignoring only generation time.
- Viewer JavaScript syntax, using the available Node executable, plus a focused DOM-stub check that bold text preserves nested wiki links, source links and code without interpreting raw HTML. The stub check does not independently test URL validation or replace browser observations.

The skill-authoring validator also passed for all four skill folders. The portable verification command requires no installed skill-authoring tools. Node is optional and its syntax check reports `NOT RUN` when unavailable.

## Browser observations

Chrome on macOS loaded the example through a loopback HTTP server. Observed: 11 materials; search for `packed` narrowed the list; the gap filter showed three items; side-list and graph-node selection opened readable notes; bold text rendered; an internal wikilink changed the selected note; and the planned item showed the `Product plan` badge. After the renderer correction, a bold internal link still navigated correctly and coverage sections displayed as readable prose.

The evidence link targeted the correct fictional `src/pickups.py` URL. Chrome blocked opening its content with `ERR_BLOCKED_BY_CLIENT`. A separate HTTP read returned 200 and bytes identical to that source file. Browser evidence-content viewing is therefore **BLOCKED**, not passed. The README describes the repository-relative path fallback for an editor.

Direct `file://` loading, a narrow viewport and this example's Obsidian GUI were **NOT RUN**. The generated HTML embeds its data and scripts and has no external resource dependency, but static inspection is not a direct-file browser test.

## Limits

These are bounded smoke tests, not a benchmark or a guarantee of complete project coverage. Codex agents executed the skills from their folders; an installation/restart round trip was not part of the evaluation. Other agent hosts and their installation mechanisms have not been integration-tested. No production system, authentication provider, database or real customer data is part of this fixture.

See [the evaluation guide](docs/evaluation.md) for repeatable prompts, isolation requirements and the evaluator's rubric.
