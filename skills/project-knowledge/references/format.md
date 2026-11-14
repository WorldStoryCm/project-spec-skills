# Vault format and helper contract

Plain Markdown, wikilinks and flat YAML properties. Use **JSON values inside YAML** so the stdlib-only helper needs no YAML dependency. Each value is a JSON string, array, boolean or number on one line; no nested YAML/block scalars. This is valid Obsidian YAML. Put complex evidence in prose.

## Layout

```text
00-index.md
01-coverage.md
02-gaps.md
areas/<area-slug>.md
notes/<claim-slug>.md
gaps/<question-slug>.md
runs/<date>-<run-slug>.md
Map.canvas                     generated
graph.html                     generated
.knowledge/sources.json         reviewed source fingerprints
.knowledge/graph.json           generated view data
```

Wikilinks are vault-relative without `.md`; use full paths to avoid ambiguity. Filenames avoid `# | ^ :` and brackets. Code links are relative to the note location, URL-encoded as necessary. Source metadata paths are relative to the **repository**, not the vault.

Markdown beneath any `.obsidian`, `.trash`, or `.knowledge` path component is excluded from note discovery and validation. Deleted notes and plugin documentation must not become graph nodes.

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

Required: `id`, `title`, `type`, `status`, `areas`, `sources`, `updated`.

- `id`: unique stable ASCII slug (`[a-z0-9-]+`).
- `type`: `index`, `area`, `note`, `gap`, `run`.
- `status`: `current`, `partial`, `planned`, `unverified`, `conflict`, `stale`, `superseded`.
- `areas`: existing **area IDs**. Each `note`/`gap` needs at least one. Area pages may list themselves or leave empty; index/run pages may be empty.
- `sources`: existing files read as evidence, repository-relative; no directories, credentials, absolute paths or paths escaping the repo. A `current` note needs evidence. Gaps/maps may have none if their text explains why.
- `updated`: last substantive review date (`YYYY-MM-DD`).
- Optional `tags`, `aliases`, `task_ids`: string arrays. Optional `summary`, `verification`: strings.

`current` means supported by inspected current sources, **not runtime-tested or deployed**. `partial` means sampled; `unverified` lacks required evidence; `planned` is intent. State checked version/environment in prose.

## Body

Usually 150–350 words per behavior; be shorter when sufficient. Do not pad/split to quotas. Include:

- A precise title and `Area: [[areas/collections|Collections]]`.
- When the note is useful; behavior and boundaries; explicit labels on inference.
- Evidence links and symbols, e.g. `[service.ts](../../../src/server/cases/service.ts#L40)`, `createPeriod`, with what each demonstrates.
- An existing verification command and actual PASS/FAIL/NOT RUN.
- Semantic links with reasons, e.g. depends on `[[notes/another-rule|rule]]` because …

All sample paths/symbols here are illustrative; verify and replace them. Area pages list reviewed/discovered/deferred scope. Index links all areas. Coverage uses depth and next actions, not invented completeness percentages. Gaps state kind, evidence, impact and next check, plus related existing tasks. Runs record revision, dirty scope, bounds and outcomes.

## Gap triage

Red or flagged nodes are review items. Use tags to explain why each item is open:

- `product-gap`: a traced source path omits or diverges from a stated product requirement. Cite the requirement and the current behavior; state whether the effect was observed at runtime.
- `verification-gap`: behavior exists or is plausible, but the required scenario, revision or environment lacks evidence. Record any earlier successful checks with their scope before asking for a rerun.
- `product-plan`: proposed capability or contract decision. Say what exists today, what would be added, and which decisions block it.
- `conflict`, `knowledge-gap`, `deferred`: conflicting accounts, missing research, or work excluded with a reason. Distinguish outdated documentation from a product failure.

An item can have more than one aspect. Name each separately with its evidence and next action, or split the note if the actions have different owners. Check existing tasks and results when available, since a source note can be newer than a draft and a historic test can be newer than a gap note's assumptions. Order work by observed impact, urgency and dependencies. Give specific acceptance checks, reuse existing owners and do not turn every red node into a feature task.

## Helper

`knowledge.py {check,build,snapshot} --repo PATH --vault PATH`

- `check`: read-only, exit 1 for structural errors; freshness warnings normally leave exit status 0. Add `--strict` to also fail on warnings. Missing source files are errors except on explicitly `stale`/`superseded` notes (warnings). Changed or unbaselined evidence warns; no auto-status rewrites. Strict mode is available only for `check`, never for accepting fingerprints.
- `snapshot --notes ID...` or `--all`: explicitly accept SHA-256 fingerprints of selected notes' sources into `.knowledge/sources.json`; preserve other baselines. No unrelated source content reads. No-change snapshots keep stable state.
- `build`: validate first, fail on errors, generate view artifacts. Never accept evidence fingerprints or rewrite canonical notes.

Data contract for the included HTML template:

```json
{
  "title": "Project knowledge", "generatedAt": "ISO-8601",
  "nodes": [{
    "id": "collection-periods", "title": "A rule", "type": "note",
    "status": "current", "areas": ["collections"], "tags": ["knowledge"],
    "path": "notes/collection-periods.md", "body": "Markdown without frontmatter",
    "sources": ["src/service.ts"], "summary": "", "updated": "2026-11-14", "stale": false
  }],
  "edges": [{"source": "collections", "target": "collection-periods"}],
  "warnings": []
}
```

Extract prose wikilinks, excluding inline/fenced code examples. Resolve full vault paths and unique basenames; reject missing/ambiguous notes. Strip aliases and heading/block fragments when checking file existence; no claim to validate headings. Area membership also adds navigation edges. Label this as a knowledge/coverage map, not a runtime dependency graph.

Canonical Markdown must not contain raw merge conflicts. Validation rejects complete Git groups with a labeled opening marker, matching marker widths (including configured widths), and an optional diff3 base section, even inside code fences. Unlabeled/custom conflict formats are outside this detector; also inspect unresolved Git index entries. A deliberate `status: "conflict"` note containing attributed claims and next actions is valid; that status does not itself resolve the claims or authorize accepting their fingerprints. See [concurrent merges](merge.md).

`assets/viewer.html` has exactly one `__KNOWLEDGE_DATA__` placeholder for script-safe JSON. Treat contents as untrusted text: no raw Markdown HTML execution, unsafe URL schemes, external scripts/fonts/analytics/fetches. Render readable basic Markdown and wikilinks; leave unsupported syntax as text. Canvas uses valid JSON Canvas 1.0 file nodes (vault-relative paths) and edges. Generated filenames are reserved; preserve manual changes separately before rebuilding.

## Format references

- [Internal links](https://help.obsidian.md/links)
- [Properties](https://help.obsidian.md/properties)
- [Graph view](https://help.obsidian.md/plugins/graph)
- [JSON Canvas](https://jsoncanvas.org/spec/1.0/)

The bundle is self-contained. [Official Obsidian Skills](https://github.com/obsidianmd/obsidian-skills) can help with advanced format requests but are optional.
