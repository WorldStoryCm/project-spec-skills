# Incremental knowledge sync

Use this workflow for `sync`, a broad Git-based `update`, or an authorized scheduled run. It combines deterministic discovery with an agent's source research. The Python helper cannot understand changes or certify that prose is true.

## Shared and local state

- Canonical Markdown, `.knowledge/sources.json` and `.knowledge/review.json` travel with normal repository commits. The review file identifies the integrated branch and the last accounted-for commit. It is not a completeness score.
- `.knowledge/sync-plan.json`, `.knowledge/sync-status.md` and `sync.html` are local generated reports. Ignore them in Git. They show what was observed at scan time, not a live watch of every keystroke.
- Use the repository's portable skill bundle when present; otherwise the installed bundle. Resolve `SKILL_DIR`, `REPO` and `VAULT` in the commands below. Python 3.10+ and Git are sufficient.
- No hooks, daemon, automatic commit/push, pull/reset or implicit timer installation. Other clones receive changes through their usual Git workflow. Installing the skill and running the timer on one computer does not install it for teammates.

## 1. Discover the range

Read repository instructions and inspect current edits and task ownership. Start with a read-only scan:

```sh
python3 "$SKILL_DIR/scripts/maintain.py" scan --repo "$REPO" --vault "$VAULT" --json
```

The default target is checkout HEAD. Review all reachable commits since `reviewed_through`, including merged branches and changes later reverted. Do not filter authors or silently discard commits older than seven days. The checkpoint defines what remains to be reviewed. The vault, the standard portable skill directory and its two wrapper files (`knowledge/README.md` and `knowledge/.gitignore` when the vault is under `knowledge/`) are excluded from the application change queue; other `knowledge/` paths remain eligible. A range with only excluded paths needs no review receipt or run note.

For a team-wide sync, including manual runs, refresh the authorized remote tracking branch (`git fetch origin` when `origin` is the configured remote; no prune/pull/merge). Compare the integrated branch with its remote tracking branch. Scan `--target origin/main` if that is the actual branch. Label local-only scans or fetch failures as unknown upstream freshness. A remote target different from checkout HEAD is triage only: do not advance the cursor or accept its evidence as local bytes. Report pending upstream commits and the required alignment; preserve dirty work. Unmerged branches are proposals, not current application behavior.

Missing/shallow history, divergent ancestry, unresolved Git conflicts or an absent checkpoint require an explicit explanation. Do not reset the checkpoint to HEAD. For a new vault, research the initial snapshot, write a run note describing its partial coverage, then explicitly initialize:

```json
{"schema":1,"ref":"refs/heads/main","reviewed_through":"FULL_REVIEWED_SHA","run_path":"runs/initial.md","coverage":"partial"}
```

Use the observed initial revision, not a guessed latest commit. Existing clones must reuse the shared checkpoint.

## 2. Research and update meaning

For substantive writes, follow the repository's task coordination. Reuse the current implementation task for its own related notes; a broad maintenance pass needs its own matching task/claim when the repository requires it. Respect concurrent claims on specific notes and source areas.

Read each relevant diff and its current execution context. Inspect mapped notes, connected rules and uncovered files; a new route or service may need a new area or note. Classify each pending path as reviewed, excluded with a concrete reason, or deferred. A generated asset may be excluded; an unknown behavior cannot be excluded just to make the queue empty. Credential paths are not evidence and their contents must not be read into the graph.

Update canonical claims and links, distinguish code from plans and runtime evidence, preserve manual text and stable IDs. Resolve deleted/renamed sources by investigation. If evidence is genuinely unavailable, retain an explicit stale/superseded note and an actionable gap. Do not label missing functionality merely because the map lacks a note.

Keep unrelated dirty sources deferred. In this version, `finish` refuses to accept selected notes whose sources are dirty: it only advances the integrated checkpoint on the configured branch at the exact target HEAD. A normal implementation task can still reread its own edited files, update its own notes, then use `knowledge.py snapshot --notes ID...` and `build` without advancing the shared Git checkpoint. Never snapshot someone else's ongoing work.

For integrated finishing, every existing selected source must be a regular tracked file whose working bytes match the raw blob at the target commit. This check is independent of the change-queue exclusions and Git's ignore, assume-unchanged and skip-worktree behavior. It conservatively rejects checkout transformations such as CRLF conversion or smudge-filter output; it does not execute filters to normalize evidence. Explain the mismatch and leave the checkpoint pending until the checkout is aligned through the project's normal workflow. Missing evidence may remain on explicitly stale or superseded notes. The vault lock and repeated drift checks do not lock application source files against other writers.

Write a concise run note under `runs/`: exact range, observed dirty state, changed notes, exclusions, unresolved gaps and actual checks. It must be a canonical Markdown note with `type: "run"` and JSON-string frontmatter fields `review_base` and `review_target` equal to the full scanned SHAs. An old run or a symlink is not a receipt for a new interval. Do not create a new run or churn note dates for an empty no-change scan.

## 3. Produce a reviewable plan and finish

After research and intentional note edits, refresh the plan and status:

```sh
python3 "$SKILL_DIR/scripts/maintain.py" scan --repo "$REPO" --vault "$VAULT" --write-status
```

Compare this final scan with the discovery scan. If sources changed during research, reread them before accepting the new plan. New notes and the run note must exist at final scan time. The scan writes only local reports; it does not rewrite claims, fingerprints or the reviewed checkpoint. `sync.html` remains usable when missing evidence prevents the canonical graph from rebuilding.

Create a local review receipt matching the exact plan bytes. Example shape (replace every illustrative value):

```json
{
  "plan_sha256": "SHA256_OF_SYNC_PLAN_FILE",
  "paths": {
    "src/example.ts": {"status": "reviewed", "reason": "Read the diff and caller; updated the documented contract."}
  },
  "notes": {
    "example-rule": {"status": "updated", "expected_sha256": "SHA256_OF_CURRENT_NOTE_FILE"}
  },
  "run_path": "runs/2026-11-14-sync.md",
  "run_sha256": "SHA256_OF_SCANNED_RUN_NOTE"
}
```

Path status: `reviewed`, `excluded`, `deferred`; always give the reason. Note status: `updated`, `unchanged`, `deferred`; include `expected_sha256` for every selected note. Every applicable changed path and affected note must have an accountable disposition. Impact includes previous fingerprint sources as well as current links, so replacing a deleted source cannot hide a note. For integrated finish, selected source paths must be canonical and clean; alias/symlink evidence requires explicit canonicalization and rereview. Do not invent a review receipt without doing the source research. Put the receipt in `.knowledge/` and ignore it, or use a temporary directory.

```sh
python3 "$SKILL_DIR/scripts/maintain.py" finish --repo "$REPO" --vault "$VAULT" \
  --plan "$VAULT/.knowledge/sync-plan.json" --review /tmp/knowledge-review.json
```

The helper validates plan identity, checkout/target, source and note drift, and complete dispositions; locks writes; accepts only reviewed note fingerprints; validates/builds views; and writes the cursor last. Deferred applicable work keeps the interval pending. On drift or a held lock, inspect the new state and ownership rather than forcing it. The checks protect bookkeeping; the agent remains responsible for the claims.

After finishing, scan again for the local status. Report reviewed range, added/changed pages, pending or upstream scope, verification evidence, and the paths to `graph.html` and `sync.html`. A clear incremental queue still does not mean the whole repository has been researched.

## Optional scheduling

Manual invocation is sufficient. If the user separately requests recurring runs, use a supported scheduling integration in their agent host. Include the repository, vault and skill paths, review requirements and stop conditions in its prompt; inspect existing schedules to avoid duplicates. A plain shell timer cannot execute a skill's research instructions. A saved schedule is not evidence that a future review succeeded.
