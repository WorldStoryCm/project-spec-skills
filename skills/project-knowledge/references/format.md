# Vault format and helper contract

A vault has two layers. The **spec layer** (`areas/`, `notes/`) is an as-built specification: what the source code does now, and nothing else. The **gap layer** (`gaps/`, `plans/`) holds everything that is missing, doubtful, contradictory or proposed, one question per page, each with its own recheck and human decision. Chat agreements, intentions and plans are not spec. See [gaps.md](gaps.md) for how to write the gap layer.

Plain Markdown, wikilinks and flat YAML properties. Use **JSON values inside YAML** so the stdlib-only helper needs no YAML dependency. Each value is a JSON string, array, boolean or number on one line; no nested YAML or block scalars. This is valid Obsidian YAML. Put complex evidence in prose.

## Layout

```text
knowledge/<project>/
  00-index.md           start here
  01-coverage.md        depth reached per area and next actions
  AS-BUILT.md           generated: the as-built specification in one document
  GAPS.md               generated: the gap queue by state
  areas/                maps of related capabilities (spec)
  notes/                source-backed behaviors and rules (spec)
  gaps/                 one question per page (gap)
  plans/                one plan per accepted gap (gap)
  runs/                 review history and evidence limits
  graph.html            generated offline browser view
  .knowledge/           sources.json (reviewed fingerprints), review.json (reviewed Git checkpoint), graph.json (generated view data)
```

`AS-BUILT.md` and `GAPS.md` start with a line saying they are generated. They have no frontmatter and are not notes; never edit them, rebuild instead. An older vault may still have a hand-written `02-gaps.md` index page; it stays valid but `GAPS.md` replaces it.

Wikilinks are vault-relative without `.md`; use full paths to avoid ambiguity. Filenames avoid `# | ^ :` and brackets. Code links are relative to the note location, URL-encoded as necessary. Source metadata paths are relative to the **repository**, not the vault.

Markdown beneath any `.obsidian`, `.trash`, or `.knowledge` path component is excluded from note discovery and validation, as are the two generated files by name. A hand-written root page named like a generated file (`AS-BUILT.md`, `GAPS.md`, `graph.html`), ignoring case, is an error and is never overwritten. Deleted notes and plugin documentation must not become graph nodes.

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
- Optional `tags`, `aliases`, `task_ids`: string arrays. Optional `summary` (a line used as the area's introduction in `AS-BUILT.md`) and `verification`: strings.

Gap-only properties are errors on any other page type, `gap` is an error on a page that is not a plan, and `priority` and `confidence` are allowed only on gap and plan pages. String properties (and strings inside arrays) may not contain control characters, including line separators. Gap-only properties (`kind`, `recheck`, `rechecked_by`, `rechecked_on`, `decision`, `decided_by`, `decided_on`, `duplicate_of`, optional `priority`, `confidence`) and the plan-only `gap` property are defined in [gaps.md](gaps.md), with the rules for who may set each. Gap state (`needs-recheck`, `needs-decision`, or the decision value) is derived from them and never written into Markdown. A recheck has one meaning for every gap kind: does the `Current behavior` section still describe the code? `confirmed` means it does (confirmed, still holds; for a proposal, the capability is still absent) and `not-reproduced` means it no longer does; neither judges whether a proposal is worth doing, which is a person's decision (see [what a recheck means](gaps.md#what-a-recheck-means)). `recheck: "outdated"` means the cited sources changed after the last recorded recheck; `rechecked_by` and `rechecked_on` stay, the `Recheck` section must have text, and an open gap with it is `needs-recheck`.

## Body

Spec pages state facts about the code. Include for a note, usually 150-350 words and shorter when sufficient:

- A precise title and `Area: [[areas/collections|Collections]]`.
- When the note is useful; behavior and boundaries; explicit labels on inference.
- Evidence links and symbols, e.g. `[service.ts](../../../src/server/cases/service.ts#L40)`, `createPeriod`, with what each demonstrates.
- An existing verification command and actual PASS/FAIL/NOT RUN.
- Semantic links to other spec pages with reasons, e.g. depends on `[[notes/another-rule|rule]]` because ...

All sample paths and symbols are illustrative. Area pages list reviewed, discovered and deferred scope. The index links all areas and mentions the generated files. Coverage uses depth and next actions, not invented completeness percentages. Runs record revision, dirty scope, bounds and outcomes.

The validator enforces these body rules:

1. An `area` or `note` page may not reference the gap layer in any form: a wikilink, an embed (`![[...]]`) or a Markdown link to a `gap` or `plan` page, a Markdown link to `GAPS.md`, or any link inside its `title` or `summary`. Link from the gap to the note instead. Links from gaps, plans and index pages to anything are fine.
2. A `run` page links to no vault page, by wikilink, embed or Markdown link. It names the pages it touched by path in code formatting (`notes/example`). A run touches many pages; as links they would make every run a hub and the area clusters would collapse into one ball in Obsidian's graph. Links to source files and URLs are fine, and the index may link to a run.
3. A gap has six `##` sections with exactly these headings, each once: `Current behavior`, `Gap`, `Evidence`, `Recheck`, `Discussion`, `Decision`. Headings inside code fences do not count.
4. When `decision` is not `open`, `Decision` needs text; when `recheck` is not `not-checked`, `Recheck` needs text.

## Helper

Three scripts in `$SKILL_DIR/scripts/`; see [SKILL.md](../SKILL.md) for the variables.

`knowledge.py {check,build,snapshot} --repo PATH --vault PATH`

- `check`: read-only, exit 1 for structural errors; freshness warnings normally leave exit status 0. Add `--strict` to also fail on warnings. Page-level errors are printed first, and a failing `check`, `snapshot` or `build` ends with a line giving the number of errors and the number of pages they are on. A page whose frontmatter fails validation still counts as a target for links, embeds, area membership, a plan's `gap` and `duplicate_of`, so one broken page yields its own errors only; fix it and nothing else needs touching. Only the "missing" error is hidden this way: an ambiguous link (two or more candidates), a link to a page of the wrong type (a spec page linking a gap, or an `areas` entry naming a page known to be another type) and a run page's link are still reported. `snapshot --notes X` refuses X while X's area references, links, `gap` or `duplicate_of` point at a page that failed validation. Missing source files are errors except on explicitly `stale` or `superseded` notes (warnings). Changed or unbaselined evidence warns. A source that differs from its baseline only by line endings (typically a Windows checkout) warns "line endings differ in source X"; do not snapshot on that checkout, because it would record the converted bytes. Nothing is rewritten.

  `--strict --ignore-dirty` is for a working tree shared with someone else's uncommitted work. Only the "changed source" and "line endings differ" warnings can be forgiven, and only when the drift is purely uncommitted: the file has uncommitted changes (modified or staged) and the accepted fingerprint equals the file's content at `HEAD` (or that content with LF/CRLF converted). If `HEAD` itself differs from what was accepted, the change was committed unreviewed and the warning counts, however many uncommitted edits sit on top. A forgiven warning is still printed, marked as not counted, and the summary says how many were forgiven. Never forgiven: a source with no baseline (unbaselined; nothing was accepted, so there is no uncommitted-only drift) and an untracked file or one new since `HEAD` (no committed content to compare with, even if a baseline exists). A Git-ignored file never counts as uncommitted. Without the flag nothing changes. Structural errors, missing files and committed drift stay visible and fatal. The flag is valid only with `check`. It is not for CI: a CI checkout has no uncommitted work, and using it there would only let real drift through. Outside a Git work tree the flag is an error. There is no acknowledgement file, so when the other contributor commits, the warning counts again.
- `snapshot --notes ID...` or `--all`: explicitly accept raw-byte SHA-256 fingerprints of selected pages' sources into `.knowledge/sources.json`; preserve other baselines. `--notes` is blocked only by errors on the selected pages themselves (frontmatter, body rules, resolvable links, acceptable sources), by an unknown or duplicated selected id, and by errors that belong to no page, such as a damaged `sources.json`. It reports how many errors on other pages it is not blocked by, which lets you accept a fixed page while others are still being repaired. `--all` needs a fully valid vault.
- `build`: validate the whole vault first, fail on errors, then write `graph.html`, `.knowledge/graph.json`, `AS-BUILT.md` and `GAPS.md`. It never accepts fingerprints or rewrites canonical notes. A `Map.canvas` left by an earlier version is deleted when it is exactly what that version generated (cards moved, or edges with the `fromSide`/`toSide` Obsidian adds on save, still count as generated); a canvas with anything hand-made in it is left alone. `AS-BUILT.md` and `GAPS.md` are deterministic; `graph.html` and `.knowledge/graph.json` carry a `generatedAt` time.

Rules the validator applies beyond the basics: `decided_by: "agent"` is rejected in every decision state; `decided_by` and `decided_on` are validated but optional on `done` and `duplicate`; a missing source file cited by a gap is an error while its decision is `open`, `accepted` or `deferred` and a warning once it is `done`, `rejected` or `duplicate`, and a plan follows its gap (a warning when the gap is `done`).

`maintain.py {scan,receipt,finish}` supports [sync](sync.md); `merge.py inspect` supports [merge](merge.md).

`AS-BUILT.md` starts with a "generated, do not edit" line and `# {index title}: as-built specification`. It has one `##` per area (sorted by title) with the area `summary`; each note whose first listed area it is appears as a `###` with a line of id, status, updated and sources, and its own headings demoted to levels 4-6. Notes also listed under other areas appear there as "See also" lines; superseded notes are omitted. No gap or plan content appears. `GAPS.md` starts with the same line and `# {index title}: gap queue`, then one `## {state}` per non-empty state in the order `needs-recheck`, `needs-decision`, `accepted`, `deferred`, `rejected`, `done`, `duplicate`, each a table with columns `Gap | Kind | Areas | Recheck | Decision | Priority | Plan`. A Recheck cell reads "confirmed (still holds)" or "not reproduced (no longer holds)" for the stored values `confirmed` and `not-reproduced` (the stored values do not change) followed by who and when; `not-checked` and `outdated` read as before, and the cell ends with ` · sources changed since` when `recheck` is `confirmed` or `not-reproduced` and a cited source's current bytes differ from its accepted fingerprint (line-ending-only differences do not count).

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

`assets/viewer.html` has exactly one `__KNOWLEDGE_DATA__` placeholder for script-safe JSON. Treat contents as untrusted text: no raw Markdown HTML execution, unsafe URL schemes, external scripts, fonts, analytics or fetches. Render readable basic Markdown and wikilinks; leave unsupported syntax as text. The map draws one frame per primary area (the area page, or the first entry of `areas`) with its pages inside; an edge between a page and its primary area is not drawn because the frame says it, links inside one area are solid and links across areas dashed; `nav` pages are not drawn. Generated filenames are reserved; preserve manual changes separately before rebuilding.

## Format references

- [Internal links](https://help.obsidian.md/links)
- [Properties](https://help.obsidian.md/properties)
- [Graph view](https://help.obsidian.md/plugins/graph)

The bundle is self-contained. [Official Obsidian Skills](https://github.com/obsidianmd/obsidian-skills) can help with advanced format requests but are optional.
