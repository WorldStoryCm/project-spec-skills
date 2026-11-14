# Evaluating skill changes

Run `python3 scripts/verify.py` for package, helper and example checks. Those checks do not establish that an agent will apply a skill well. For changes to reasoning or workflow, also run a realistic request in a fresh agent context.

## Keep the evaluation independent

Copy only `examples/parcel-desk/SPEC.md`, `src/` and `tests/` into a disposable directory. Do not give the agent the worked reports, ready-made vault, this rubric or another agent's conclusions. Give it one selected skill and the request below. Keep the original fixture unchanged. The copies require no network or packages.

Ask for an actual deliverable, not a review of the prompt. Preserve the output and executed commands. Record the host, skill version and any unavailable tools. A successful run on one fixture and host is a smoke test, not a general reliability score.

## Requests

| Skill | Request |
| --- | --- |
| `spec-audit` | Audit the cancellation section of the pickup spec against this repo. Tell me which contradictions need attention and what still needs a product decision. Leave the files alone. |
| `spec-investigation` | Why does cancellation fail for my packed pickup? Compare the route and service paths, tell me what you actually verified, then name the smallest check that would settle what is still unclear. Leave project files alone. |
| `spec-plan` | Plan support for customer cancellations before pickup, including packed parcels. Keep the partner variation undecided and tell me how we can accept the change. Don't implement it. |
| `project-knowledge` | Build an Obsidian-compatible project map for pickups and cancellations. Keep my existing note about QA handoffs. Show me which behavior comes from code and how I can open the graph. Set up the reviewed state so I can manually review new commits later. |

For the knowledge request, initialize the disposable fixture as a Git repository. Add a small human-written note before the first run and keep a byte-for-byte copy. Use compatible frontmatter if the note is inside the vault. Allow vault writes, but keep the application and requirements read-only during the run.

After the initial map, the evaluator makes a second application commit: change a documented behavior and add a previously unmapped entrypoint. Ask the agent to review new commits and update relevant knowledge. Do not give it the expected note edits. A final no-change scan should not duplicate notes or advance an already-current checkpoint.

## Evaluator's rubric

- **Audit:** finds the packed-owner mismatch with CAN-1; records CAN-2 and CAN-3 as supported within the inspected boundary; distinguishes missing test coverage from missing behavior; leaves partner cancellation as DEC-1, an open product decision.
- **Investigation:** follows `cancel_request` into `cancel_pickup`, distinguishes ownership denial from state denial, and reports the fixture boundary. It reproduces a useful local check or explicitly qualifies a static conclusion. It does not invent a live deployment observation.
- **Plan:** changes the shared state rule rather than only the adapter, preserves ownership and collected-state rejection, specifies observable tests and leaves partner work gated. It does not implement the plan or claim future tests passed.
- **Knowledge:** creates a navigable, source-backed map; preserves the human note and stable IDs; distinguishes intent, implementation and runtime evidence. The later commit flags changed sources and new scope. Review updates meanings before accepting fingerprints and advancing the cursor. A clear queue is not called full coverage.
- **All skills:** preserve unrelated files, cite the inspected material, state missing revision metadata, and separate executed checks from proposed or unrun checks. Reports remain within the requested scope.

Judge a failure by its effect on the user's next action. Improve the narrow instruction or helper behavior that caused it; avoid adding a universal checklist for every example-specific detail. Re-run the affected scenario after a meaningful change.

## Concurrent knowledge merge

In an isolated Git fixture, begin with an already reviewed vault and create two contributor branches from the same base. Give each side a useful compatible addition and an overlapping note edit. Include different reviewed-state proposals and a contradiction that the available source does not settle. Keep expected outcomes with the evaluator.

Ask a fresh agent using only `project-knowledge`: “Reconcile the knowledge updates on these two branches. Preserve both contributors' useful work and existing IDs, keep unresolved claims visible, and report what was merged and what still needs review.” Authorize only the disposable fixture's vault integration; do not give the agent an expected resolution.

Check that both compatible additions survive; base/ours/theirs provenance is inspectable; duplicate IDs or renamed paths are reconciled without losing incoming links; unknown claims remain actionable conflicts; and raw conflict markers are rejected. The agent must not pick the newest cursor, union source hashes, snapshot everything, or claim that a clean text merge proves consistency. The inspected inputs must remain recoverable in Git. Derived views should be rebuilt only from resolved canonical files. Record pending evidence and distinguish a local two-branch test from a real cross-clone or hosted integration test.

## View checks

Open the generated `graph.html` in a real browser. Check search, area/gap filters, note selection, internal navigation, readable Markdown and evidence links. Record direct-file versus local-server loading and viewport limits. Check the vault in Obsidian when available; valid Markdown and Canvas JSON alone do not count as an Obsidian GUI test.
