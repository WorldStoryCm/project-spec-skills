# Incremental sync

Use this for `sync` or a broad Git-based `update`. Deterministic discovery (the scan) finds which commits and sources are pending; your research decides what they mean. The helper cannot read code or certify that prose is true. `$SKILL_DIR`, `$REPO` and `$VAULT` are defined in [SKILL.md](../SKILL.md).

A sync does two jobs in order. First it brings the **spec notes** in line with the code. Then it revisits the **gaps** whose cited sources changed, because a code change may have closed or altered a question someone is still carrying.

## Shared and local state

- Canonical Markdown, `.knowledge/sources.json` and `.knowledge/review.json` travel with normal repository commits. `review.json` names the integrated branch and the last commit accounted for. It is a checkpoint, not a completeness score.
- `.knowledge/sync-plan.json`, `.knowledge/sync-status.md`, the review receipt and `sync.html` are local reports; keep them out of Git. They show what was observed at scan time.
- Use the repository's pinned copy of this skill if it supports the workflow; otherwise say there is a version mismatch and use a complete installed copy. Keep one version through a merge and the sync that follows it.

## 1. Discover the range

Read the repository instructions and check current edits and task ownership. If several contributors changed the vault, follow [the merge workflow](merge.md) first; sync reviews application history and does not reconcile competing note text, fingerprints or checkpoints. Then scan, read-only:

```sh
python3 "$SKILL_DIR/scripts/maintain.py" scan --repo "$REPO" --vault "$VAULT" --json
```

The default target is checkout HEAD. Review every reachable commit since `reviewed_through`, including merged branches and changes later reverted; do not filter by author or age. The vault, the portable skill directory and its two wrapper files (`knowledge/README.md`, `knowledge/.gitignore` when the vault is under `knowledge/`) are not part of the application queue. A range with only those paths needs no receipt or run page.

For a team-wide sync, refresh the remote tracking branch with `git fetch` only (no pull, merge or prune) and compare it with the integrated branch; scan `--target origin/main` if that is the real branch. A remote target that differs from checkout HEAD is triage only: do not advance the checkpoint or treat its content as local bytes. Label a local-only scan, or a failed fetch, as unknown upstream freshness. Unmerged branches are proposals, not current behavior.

Missing or shallow history, divergent ancestry, unresolved Git conflicts and an absent checkpoint each need an explanation; never reset the checkpoint to HEAD to make them go away. For a new vault, research the initial snapshot, write a run page describing its partial coverage, then initialize `review.json` with the observed revision:

```json
{"schema":1,"ref":"refs/heads/main","reviewed_through":"FULL_REVIEWED_SHA","run_path":"runs/initial.md","coverage":"partial"}
```

Existing clones reuse the shared checkpoint.

## 2. Update the spec, then revisit gaps

Follow the repository's task coordination for substantive writes, and respect other people's claims on specific notes and source areas.

**Spec notes.** Read each relevant diff in its execution context. Inspect the mapped notes, connected rules and uncovered files; a new route or service may need a new area or note. Classify every pending path as reviewed, excluded with a concrete reason, or deferred. A generated asset may be excluded; an unknown behavior may not be excluded just to empty the queue. Credential files are not evidence and their contents never enter the vault. Update claims from the code, keep manual text and stable IDs, and resolve deleted or renamed sources by investigation. A changed registration point (a new job, route, email, role or flag) updates the reference note that lists that kind of thing; a changed form or screen updates its feature note. A note you re-read gets what it is missing, what the feature is for and its rules with their values, and loses what a reader does not need; see "Leave each page better" in the skill. For a renamed or split file, point `sources` at where the rule lives now and re-read the page. If evidence is truly gone, keep the note as `stale` or `superseded` with a line saying what could not be found; open a gap only if a question about the product remains. a missing note is not evidence of missing functionality.

**Gaps.** List the gaps whose `sources` include a changed path, and any gap whose described behavior the diff touches. For each, re-read the current code:

- The code now does what the question asked for (or the question no longer applies): set `decision: "done"` and say in `Decision` where the code does it. Reading the code to reach that conclusion is a recheck, so also record `recheck: "not-reproduced"`, `rechecked_by: "agent"`, today's `rechecked_on` and a dated `Recheck` entry saying what you read ([closing a gap as done](gaps.md#closing-a-gap-as-done)). Update the spec note from the code in the same pass. If you are unsure the question is closed, leave it open.
- Otherwise, if the gap has a recorded recheck (`confirmed` or `not-reproduced`) and a cited source changed, set `recheck: "outdated"`, keep `rechecked_by` and `rechecked_on` (they record the last recheck actually done), and add a dated line to `Recheck` naming the source and range. An open gap then returns to `needs-recheck`. Leave `decision` alone. A person, or an agent re-checking the gap (the investigate mode of this skill), records the fresh recheck, which replaces all three fields and adds a new dated entry. Run one yourself only if you really can.
- You do not have to catch every case by hand: the viewer shows a "recheck outdated" badge on the gap, and lists it under Recent changes, whenever a cited source's current bytes differ from its accepted fingerprint (line-ending-only differences are ignored). The marker exists so the queue shows staleness before anyone edits the gap; setting `outdated` makes it explicit in the page.
- New doubts found along the way become new gaps (one question each), not notes.

Keep unrelated dirty sources deferred; `finish` handles that case without losing the rest of the work (see [partial finish](#partial-finish-when-something-is-deferred)). A normal implementation task can still reread its own edited files, update its own notes, then run `knowledge.py snapshot --notes ID...` without advancing the shared checkpoint; never snapshot someone else's work in progress.

At finish time, each selected source must be a regular tracked file whose working bytes equal the raw blob at the target commit, whatever Git ignore, assume-unchanged or skip-worktree flags say. This rejects CRLF conversion and smudge-filter output rather than normalizing it. Explain the mismatch, defer the notes that cite such a file, and leave the checkpoint pending until the checkout is aligned. Missing evidence may remain on explicitly `stale` or `superseded` notes.

Write a run page under `runs/`: exact range, observed dirty state, pages changed, exclusions, gaps closed, outdated or created, and the checks you actually ran. Name pages by path in code formatting (`notes/example`), not as links ([why](format.md)). It needs `type: "run"` and the JSON-string properties `review_base` and `review_target`, equal to the full scanned SHAs. An old run page is not a receipt for a new interval, and an empty no-change scan gets no new run page.

## 3. Plan, receipt, finish

After research and edits, refresh the plan and status:

```sh
python3 "$SKILL_DIR/scripts/maintain.py" scan --repo "$REPO" --vault "$VAULT" --write-status
```

Compare it with the discovery scan; if sources changed during research, reread them. New notes and the run page must exist now. Then have the helper generate the receipt. It fills in every hash from the plan, the notes and the run page, so none is typed by hand:

```sh
python3 "$SKILL_DIR/scripts/maintain.py" receipt --repo "$REPO" --vault "$VAULT" \
  --plan "$VAULT/.knowledge/sync-plan.json" \
  --out "$VAULT/.knowledge/sync-review.json" --run runs/2026-11-15-sync.md
```

`--run` is optional and takes the run page's path inside the vault. Without it the helper picks the single `runs/*.md` page whose `review_base` and `review_target` equal the plan's range, and asks for `--run` if there are none or several. The file gets `plan_sha256`, `run_path` and `run_sha256`, each pending path with an empty `status` and `reason`, and each affected note with an empty `status` and its current `expected_sha256`. Running it again with the same `--out` refreshes the hashes and drops entries that left the plan. It keeps a path's status and reason only when the plan is byte-identical to the one the old receipt was written for, and a note's status only when that note file is unchanged since; otherwise the entry comes back empty and must be reviewed again, because a disposition belongs to the bytes that were reviewed. When an earlier receipt had dispositions, `receipt` tells you how many path and note dispositions it kept, how many it reset and why (the plan changed since the receipt was written, or a note file changed, naming the notes), and how many were dropped because they are no longer in the plan, so you know exactly what to review again. A `reason` you entered on a note is carried over with its status. You fill the dispositions after doing the research:

- paths: `reviewed`, `excluded` or `deferred`;
- notes: `updated`, `unchanged` or `deferred`;
- a short reason for each, naming what you read. A `deferred` path or note needs a reason that says why it is waiting and for whom.

Do not edit the hashes, and do not fill a disposition for work you did not do. Affected notes include those whose previous fingerprints cite a changed path, so replacing a deleted source cannot hide a note. Selected source paths must be canonical and clean; alias or symlink evidence needs canonicalizing and rereading. Then:

```sh
python3 "$SKILL_DIR/scripts/maintain.py" finish --repo "$REPO" --vault "$VAULT" \
  --plan "$VAULT/.knowledge/sync-plan.json" --review "$VAULT/.knowledge/sync-review.json"
```

`finish` rejects empty or unknown dispositions, checks plan identity, checkout and target, source and note drift, and holds a lock while it accepts only the reviewed notes' fingerprints and writes the checkpoint last. On drift or a held lock, inspect the new state and its owner instead of forcing it. The lock covers one local finish; it does not protect concurrent note editing, so use separate branches or worktrees, or one writer per note, and merge explicitly afterwards.

### Partial finish when something is deferred

Sometimes part of the range cannot be accepted yet: another contributor has uncommitted edits to a file you would have read, or a note depends on work still in progress. `deferred` exists for this, and `finish` does not abort the whole run because of it. Mark the waiting paths and the notes that cite them `deferred`, each with a reason, and finish as usual. A dirty source no longer makes `finish` fail by itself; it requires that a dirty changed path be `deferred` (or cleaned and rescanned), and that every note citing a dirty source or a deferred path be `deferred` too. A source a note was fingerprinted on before but no longer cites is checked against the deferred paths only (a match requires the note to be `deferred`); it is not checked for dirtiness. A note that cites one and is marked `updated` or `unchanged` makes `finish` reject the whole receipt and write nothing, because its claims could not be checked against committed bytes. A deferred note needs a `reason` just as a deferred path does; the generated receipt has a `reason` field on paths only, so add one to the note when you defer it. The run page is required for a partial finish as for a full one.

What a partial finish does:

- It accepts fingerprints only for notes marked `updated` or `unchanged` whose currently cited sources are clean, tracked, pass the raw-bytes check and are not among the deferred or dirty paths, and none of whose cited or previously fingerprinted sources is a deferred path. Deferred notes keep their previous fingerprints, so they keep showing as needing review.
- It writes `sources.json`.
- It writes `.knowledge/review.json` only when nothing is deferred, so in a partial finish it leaves it alone. The checkpoint moves only when nothing applicable is deferred. This is the guarantee that matters: if the checkpoint advanced past deferred work, nobody would ever be told that work was never reviewed.
- It ends with exit status 3 (2 is reserved for command-line usage errors, 1 for any other failure) and lists each deferred path and note with its reason, and what was accepted. Exit status 0 still means a full finish with the checkpoint advanced, so a script or an agent can tell the two apart. Report a partial finish as partial; do not describe the sync as complete.

A scan over the same range still lists the deferred paths as pending, because the checkpoint did not move. It also still lists the notes accepted in the partial finish as affected, since affected means only that a note cites a changed path; they show no freshness warnings. When the other contributor's work is committed, scan again, re-read those files, mark the paths reviewed and the deferred notes `updated` or `unchanged`, give the already-accepted notes a disposition again (normally `unchanged`, if nothing about them changed since) and finish again. That second finish advances the checkpoint if nothing else is deferred. A range with no application paths at all still finishes with exit 0 and leaves the checkpoint as it was.

While you wait, `knowledge.py check --strict --ignore-dirty` lets you validate the vault without the other contributor's uncommitted files failing it ([what it hides](format.md)). It forgives a changed source only when the accepted fingerprint still equals the file at `HEAD`, so a change that was committed without review keeps failing, however many uncommitted edits sit on top; untracked and unbaselined sources are never forgiven. It is for a shared working tree, not for CI.

### Committing the vault before the sync is finished

Prefer to finish the sync before committing vault changes. A vault commit made while an application range is still pending moves HEAD, and the plan and the run page then name an older target. Both `finish` and `receipt` recognize this when every commit between the plan's target and HEAD touches only excluded paths (the vault, the portable skill copy and their wrapper files) and say so. If it happens, first set the run page's `review_target` to the new HEAD (`review_base` stays), because the plan records the run page's bytes; then re-run `scan --write-status`, regenerate the receipt, fill in the dispositions and finish again. Editing the run page after the scan makes the receipt fail its run-hash check. Do not commit the vault between those steps, since that moves HEAD again. If an application commit is in between, the ordinary plan-changed error applies and you need a normal re-scan and review. A range made only of excluded commits needs none of this and no receipt.

Finally scan again for the local status and report: the reviewed range, pages added or changed, gaps closed or marked outdated, pending or upstream scope, verification evidence, the path to `sync.html` and the `serve` command that shows the vault. A clear queue does not mean the whole repository has been researched.
