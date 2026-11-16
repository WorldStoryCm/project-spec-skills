# Vault format and helper contract

A vault has two layers. The **spec layer** (`areas/`, `notes/`) is an as-built specification: what the source code does now, and nothing else. The **gap layer** (`gaps/`, `plans/`) holds everything that is missing, doubtful, contradictory or proposed, one question per page, each with its own recheck and human decision. Chat agreements, intentions and plans are not spec. See [gaps.md](gaps.md) for how to write the gap layer.

Plain Markdown, wikilinks and flat YAML properties. Use **JSON values inside YAML** so the stdlib-only helper needs no YAML dependency. Each value is a JSON string, array, boolean or number on one line; no nested YAML or block scalars. This is valid Obsidian YAML. Put complex evidence in prose.

## Layout

```text
knowledge/<project>/
  00-index.md           start here
  areas/                maps of related capabilities (spec)
  notes/                source-backed behaviors and rules (spec)
  gaps/                 one question per page (gap)
  plans/                one plan per accepted gap (gap)
  runs/                 review history and evidence limits
  .knowledge/           sources.json (reviewed fingerprints), review.json (reviewed Git checkpoint)
```

Nothing in the vault is generated for reading: every file is a page someone wrote or the reviewed state under `.knowledge/`. The local reports of a sync scan (`sync.html`, `.knowledge/sync-plan.json`, `.knowledge/sync-status.md`) are ignored by Git and are not part of the vault's content. The viewer shows the spec and the gap queue from the pages themselves.

Wikilinks are vault-relative without `.md`; use full paths to avoid ambiguity. Filenames avoid `# | ^ :` and brackets. Code links are relative to the note location, URL-encoded as necessary. Source metadata paths are relative to the **repository**, not the vault.

Markdown beneath any `.obsidian`, `.trash`, or `.knowledge` path component is excluded from note discovery and validation. Deleted notes and plugin documentation must not become graph nodes.

## Page types

| Layer | `type` | Folder | Meaning |
| --- | --- | --- | --- |
| Spec | `area` | `areas/` | Map of one capability area as implemented. |
| Spec | `note` | `notes/` | One implemented behavior, rule or workflow, backed by source. |
| Gap | `gap` | `gaps/` | One question about something missing, unverified, contradictory or proposed. |
| Gap | `plan` | `plans/` | Implementation plan for exactly one accepted gap. |
| Navigation | `index` | vault root | Hand-written entry pages. |
| History | `run` | `runs/` | Record of one research, sync, audit or investigation pass. |

## Properties

```yaml
---
id: "collection-periods"
title: "Each period stores its own checklist and files"
type: "note"
status: "current"
areas: ["collections"]
tags: ["knowledge", "workflow"]
aliases: ["Collection periods"]
sources: ["src/server/cases/service.ts"]
updated: "2026-11-14"
---
```

Required on every page: `id`, `title`, `type`, `areas`, `sources`, `updated`. `status` is also required on `area`, `note`, `index`, `run` and `plan`, and is an error on `gap`.

- `id`: unique stable ASCII slug (`[a-z0-9-]+`).
- `status` on `area` and `note`: `current`, `partial`, `stale`, `superseded`. On `index`, `run` and `plan` additionally `planned`.
  - `current`: supported by inspected current sources. This is not a runtime test or a deployment claim; say in prose which version and environment you checked.
  - `partial`: sampled; some of the area or behavior was not read.
  - `stale`: its sources changed or disappeared and it has not been re-read.
  - `superseded`: replaced by another page, kept as a pointer.
  - `planned` (index, run, plan): describes intent not yet carried out.
  - Doubt about a claim is not a status. If you cannot support a statement, leave it out of the spec note and open a gap.
- `areas`: existing **area IDs**. Each `note`, `gap` and `plan` needs at least one. Area pages may list themselves or leave empty; index and run pages may be empty.
- `sources`: existing files read as evidence, repository-relative; no directories, credentials, absolute paths or paths escaping the repo. A `current` note needs evidence; gaps, plans and maps may have none.
- `updated`: last substantive review date (`YYYY-MM-DD`).
- Optional `tags`, `aliases`, `task_ids`: string arrays. Optional `summary` and `verification`: strings. An area's `summary` introduces it in the viewer; a note's `summary` is its plain-language statement of what the product does, shown first in the viewer's Read view (write one for every note; `check` does not require it, so older vaults still open).

Gap-only properties are errors on any other page type, `gap` is an error on a page that is not a plan, and `priority` and `confidence` are allowed only on gap and plan pages. String properties (and strings inside arrays) may not contain control characters, including line separators. Gap-only properties (`kind`, `recheck`, `rechecked_by`, `rechecked_on`, `decision`, `decided_by`, `decided_on`, `duplicate_of`, optional `priority`, `confidence`) and the plan-only `gap` property are defined in [gaps.md](gaps.md), with the rules for who may set each. Gap state (`needs-recheck`, `needs-decision`, or the decision value) is derived from them and never written into Markdown. A recheck has one meaning for every gap kind: does the `Current behavior` section still describe the code? `confirmed` means it does (confirmed, still holds; for a proposal, the capability is still absent) and `not-reproduced` means it no longer does; neither judges whether a proposal is worth doing, which is a person's decision (see [what a recheck means](gaps.md#what-a-recheck-means)). `recheck: "outdated"` means the cited sources changed after the last recorded recheck; `rechecked_by` and `rechecked_on` stay, the `Recheck` section must have text, and an open gap with it is `needs-recheck`.

## Body

Spec pages state facts about the code, and the facts a person looks up are the concrete rules: limits, required fields, defaults, formats, when an action is available or disabled, what an empty list shows, which message appears, who may do it, what starts a job and how often. A note gives these values, not only the mechanism that applies them.

There are two shapes of note. A **behavior note** explains one rule or flow in prose, usually 150-350 words and shorter when sufficient; when its rules need more, split it by behavior rather than leaving rules out. A **reference note** lists every item of one kind in an area (jobs, forms and their fields, the actions on a screen, routes, emails, notifications, roles and permissions, flags, states, limits) as one Markdown table, one row per item, with the count and the place in the code the list comes from, which is also in `sources`; it is as long as the table needs. Include for a note:

- A precise title and `Area: [[areas/collections|Collections]]`.
- When the note is useful; behavior and boundaries; explicit labels on inference.
- Evidence links and symbols, e.g. `[service.ts](../../../src/server/cases/service.ts#L40)`, `createPeriod`, with what each demonstrates.
- An existing verification command and actual PASS/FAIL/NOT RUN.
- Semantic links to other spec pages with reasons, e.g. depends on `[[notes/another-rule|rule]]` because ...
- For a reference note: the table, how many rows it has and why that is all of them ("every job registered in `worker/index.ts`"). Columns name the facts a reader asks about; a cell holds a value from the code ("60 characters", "daily at 06:00 UTC", "disabled while the list is empty"), not a description. Inside a table a wikilink's alias separator is written `\|`.

A behavior note (illustrative), with the rules and their values in the text:

```markdown
---
id: "team-invitations"
title: "A teammate is invited by email and joins on the first sign-in with it"
type: "note"
status: "current"
areas: ["identity"]
sources: ["src/server/teams/invite.ts", "src/features/team/InviteForm.tsx"]
summary: "An owner or admin invites someone by email. The invitation is valid for 7 days and is used up when that address signs in."
updated: "2026-11-16"
---

# A teammate is invited by email and joins on the first sign-in with it

Area: [[areas/identity|Accounts, teams and access]].

Only an owner or an admin sees **Invite**; for a member it is hidden. The email is required, trimmed and lower-cased, at most 254 characters, and must not already belong to the team ("This person is already on the team"). The form's **Send** stays disabled until the address is valid. A team on the Free plan can have 3 members; the fourth invitation is refused with "Your plan allows 3 members".

An invitation expires after 7 days (`INVITE_TTL_DAYS`), and resending it starts the 7 days again. ... evidence, checks and related notes follow.
```

A reference note (illustrative): one table, every item, the count and where the list comes from:

```markdown
# Background jobs

Area: [[areas/automation|Background jobs and notifications]].

All 4 jobs registered in [`worker/index.ts`](../../../src/worker/index.ts), the only place jobs are registered.

| Job | Starts | Does | Runs when | On failure |
| --- | --- | --- | --- | --- |
| `send-digest` | daily at 06:00 UTC | emails each member the day's open items | `DIGEST_ENABLED` is set | retried 3 times, 5 minutes apart |
| `purge-links` | hourly | deletes share links expired more than 30 days ago | always | next run picks them up |
| `finalize-upload` | an upload completes | checks size and type, moves the file to storage | always | the upload is marked failed |
| `rollover-period` | a person completes a period | opens the next period from the series plan | the series repeats | the period stays complete, the next one is not opened |
```

All sample paths and symbols are illustrative. Area pages list their notes with one line each and the reviewed, discovered and deferred scope; they describe no behavior themselves. The index links all areas. Scope is stated as what was read and what comes next, never as an invented completeness percentage. Runs record revision, dirty scope, bounds and outcomes.

The validator enforces these body rules:

1. An `area` or `note` page may not reference the gap layer in any form: a wikilink, an embed (`![[...]]`) or a Markdown link to a `gap` or `plan` page, or any link inside its `title` or `summary`. Link from the gap to the note instead. Links from gaps, plans and index pages to anything are fine.
2. A `run` page links to no vault page, by wikilink, embed or Markdown link. It names the pages it touched by path in code formatting (`notes/example`). A run touches many pages; as links they would make every run a hub and the area clusters would collapse into one ball in Obsidian's graph. Links to source files and URLs are fine, and the index may link to a run.
3. An `area` page holds no table and links whole notes only, never a heading or block inside one (`[[notes/x#Part]]`). Behavior is described in notes; a part that needs its own link is its own note. Tables and links to parts of a note are fine on other pages, and a table inside a code fence does not count.
4. A gap has six `##` sections with exactly these headings, each once: `Current behavior`, `Gap`, `Evidence`, `Recheck`, `Discussion`, `Decision`. Headings inside code fences do not count.
5. When `decision` is not `open`, `Decision` needs text; when `recheck` is not `not-checked`, `Recheck` needs text.

## Helper

Three scripts in `$SKILL_DIR/scripts/`; see [SKILL.md](../SKILL.md) for the variables.

`knowledge.py {check,snapshot,serve} --repo PATH [--vault PATH]`

- `check`: read-only, exit 1 for structural errors; freshness warnings normally leave exit status 0. Add `--strict` to also fail on warnings. Page-level errors are printed first, and a failing `check` or `snapshot` ends with a line giving the number of errors and the number of pages they are on. A page whose frontmatter fails validation still counts as a target for links, embeds, area membership, a plan's `gap` and `duplicate_of`, so one broken page yields its own errors only; fix it and nothing else needs touching. Only the "missing" error is hidden this way: an ambiguous link (two or more candidates), a link to a page of the wrong type (a spec page linking a gap, or an `areas` entry naming a page known to be another type) and a run page's link are still reported. `snapshot --notes X` refuses X while X's area references, links, `gap` or `duplicate_of` point at a page that failed validation. Missing source files are errors except on explicitly `stale` or `superseded` notes (warnings). Changed or unbaselined evidence warns. A source that differs from its baseline only by line endings (typically a Windows checkout) warns "line endings differ in source X"; do not snapshot on that checkout, because it would record the converted bytes. Nothing is rewritten.

  `--strict --ignore-dirty` is for a working tree shared with someone else's uncommitted work. Only the "changed source" and "line endings differ" warnings can be forgiven, and only when the drift is purely uncommitted: the file has uncommitted changes (modified or staged) and the accepted fingerprint equals the file's content at `HEAD` (or that content with LF/CRLF converted). If `HEAD` itself differs from what was accepted, the change was committed unreviewed and the warning counts, however many uncommitted edits sit on top. A forgiven warning is still printed, marked as not counted, and the summary says how many were forgiven. Never forgiven: a source with no baseline (unbaselined; nothing was accepted, so there is no uncommitted-only drift) and an untracked file or one new since `HEAD` (no committed content to compare with, even if a baseline exists). A Git-ignored file never counts as uncommitted. Without the flag nothing changes. Structural errors, missing files and committed drift stay visible and fatal. The flag is valid only with `check`. It is not for CI: a CI checkout has no uncommitted work, and using it there would only let real drift through. Outside a Git work tree the flag is an error. There is no acknowledgement file, so when the other contributor commits, the warning counts again.
- `snapshot --notes ID...` or `--all`: explicitly accept raw-byte SHA-256 fingerprints of selected pages' sources into `.knowledge/sources.json`; preserve other baselines. `--notes` is blocked only by errors on the selected pages themselves (frontmatter, body rules, resolvable links, acceptable sources), by an unknown or duplicated selected id, and by errors that belong to no page, such as a damaged `sources.json`. It reports how many errors on other pages it is not blocked by, which lets you accept a fixed page while others are still being repaired. `--all` needs a fully valid vault.

Rules the validator applies beyond the basics: `decided_by: "agent"` is rejected in every decision state; `decided_by` and `decided_on` are validated but optional on `done` and `duplicate`; a missing source file cited by a gap is an error while its decision is `open`, `accepted` or `deferred` and a warning once it is `done`, `rejected` or `duplicate`, and a plan follows its gap (a warning when the gap is `done`).

`maintain.py {scan,receipt,finish}` supports [sync](sync.md); `merge.py inspect` supports [merge](merge.md).

## Data contract for the HTML view

```json
{
  "title": "Project knowledge", "generatedAt": "ISO-8601",
  "nodes": [{
    "id": "collection-periods", "title": "A rule", "type": "note",
    "status": "current", "areas": ["collections"], "tags": ["knowledge"],
    "path": "notes/collection-periods.md", "body": "Markdown without frontmatter",
    "sources": ["src/service.ts"], "summary": "", "updated": "2026-11-14", "stale": false,
    "kind": "", "recheck": "", "recheckedBy": "", "recheckedOn": "",
    "decision": "", "decidedBy": "", "decidedOn": "", "state": "",
    "gap": "", "layer": "spec", "recheckOutdated": false, "priority": "", "confidence": "", "duplicateOf": ""
  }],
  "edges": [{"source": "collections", "target": "collection-periods"}],
  "warnings": []
}
```

The added fields are empty strings when they do not apply. `recheckOutdated` is true when `recheck` is `outdated` or the automatic marker applies. `priority`, `confidence` and `duplicateOf` are gap properties, empty when absent. `layer` is `spec` for areas and notes, `gap` for gaps and plans, `nav` for index and run pages. For a gap node `status` is `""` and `gap` stays empty; for a plan node `gap` holds the gap id. The viewer treats missing fields as empty, so older data still opens.

Extract prose wikilinks, excluding inline and fenced code examples. Resolve full vault paths and unique basenames; reject missing or ambiguous notes. Strip aliases and heading or block fragments when checking file existence; headings are not validated. Area membership also adds navigation edges. Label the result as a knowledge and coverage map, not a runtime dependency graph.

Canonical Markdown must not contain raw merge conflicts. Validation rejects complete Git groups with a labeled opening marker, matching marker widths (including configured widths), and an optional diff3 base section, even inside code fences. Unlabeled or custom conflict formats are outside this detector; also inspect unresolved Git index entries. A `conflict` gap that records attributed claims and a next check is valid; it does not resolve them. See [concurrent merges](merge.md).

`serve` shows the vault in a browser: `knowledge.py serve --repo REPO [--vault VAULT] [--port N] [--open]`. Without `--vault`, this and every other command use the single vault under `knowledge/` (`knowledge/00-index.md` or `knowledge/*/00-index.md`) and stop with a message when there is none or several. It listens on `127.0.0.1` only (port 8757, or a free one when that is taken), answers only `/` and only when addressed as this machine, never writes, and builds the page again from disk on every request, so a reload shows the current files. When the vault has errors the page lists them. The page data is the graph above plus `live: true`, `vaultPath` (the vault's path relative to the repository), `history`, `pending` and `files`. `history` is the last 30 commits that touched vault pages (not `.knowledge/`), newest first, each `{"sha", "date", "subject", "pages", "more"}`; a page entry is `{"path", "status"}` with `status` `added`, `changed` or `removed`, plus `was` and `now` when the commit changed the page's `summary` (or, failing that, its `title`); at most 80 pages are listed per commit and `more` counts the rest. `pending` lists vault pages with uncommitted changes in the same `{"path", "status"}` shape. Both are empty outside a Git work tree. `files` is the text of the repository files that pages cite in `sources` or link to, keyed by repository-relative path, each `{"text", "truncated"}`. A file is included only when it is inside the repository and outside the vault, is not a credential path, and is UTF-8 text; one file is cut at 300,000 characters and all files together at 4,000,000, after which the rest stay ordinary links. The viewer opens a link to an included file in place: Markdown rendered, anything else as numbered lines, with the lines of a `#L10` or `#L10-L20` fragment marked.

`assets/viewer.html` has exactly one `__KNOWLEDGE_DATA__` placeholder for script-safe JSON. Treat contents as untrusted text: no raw Markdown HTML execution, unsafe URL schemes, external scripts, fonts, analytics or fetches. Render readable basic Markdown, pipe tables and wikilinks; leave unsupported syntax as text. The viewer has a tree of areas with their notes (a note is listed under its first area; superseded notes are not listed), a search over pages, gaps and the cited files, and five places: the overview, a page, the gap queue, the map and recent changes. A spec page shows its title, `summary`, related pages and the gaps about it that are not closed, then folded sections for the page text (shown unfolded when the page has no `summary` or holds a table, as a reference note does) and its source files. Navigation keeps a trail for Back and Forward and writes the place into the address (`#/page/notes/example`, `#/gaps`), so a reload or a copied link returns to it. The map draws one frame per primary area (the area page, or the first entry of `areas`) with its pages inside; an edge between a page and its primary area is not drawn because the frame says it, links inside one area are solid and links across areas dashed; `nav` pages are not drawn. Recent changes reads `history`, `pending` and the "changed source" lines of `warnings`. "Copy for AI" only composes text from the page, a choice of what the agent should do and the reader's own words, and copies it to the clipboard. The reader's name, the recently viewed pages and the last commit seen are kept in the browser's `localStorage`, and the viewer works without it.

## Format references

- [Internal links](https://help.obsidian.md/links)
- [Properties](https://help.obsidian.md/properties)
- [Graph view](https://help.obsidian.md/plugins/graph)

The bundle is self-contained. [Official Obsidian Skills](https://github.com/obsidianmd/obsidian-skills) can help with advanced format requests but are optional.
