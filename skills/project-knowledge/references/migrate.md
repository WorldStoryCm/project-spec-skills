# Migrating a vault written before the spec/gap split

Use this when `check` fails on a vault made by an earlier version of this skill. Older vaults mixed everything in one layer: gap-like pages carried a `status`, spec notes linked to gaps and listed requirements as sources, and audit or implementation-plan results lived in index pages. The current format ([format.md](format.md), [gaps.md](gaps.md)) keeps the as-built spec and the gap layer apart, so each gap can be rechecked and decided on its own.

The aim of a migration is to change the shape of the vault without inventing facts. It does not research the code again, and it does not decide anything for anyone.

## What `check` reports on an old vault

Expect many errors at once, mostly of a few kinds:

- gap pages with a `status` (an error on gaps) and without `kind`, `recheck` or `decision`;
- gap pages missing one of the six sections;
- spec pages (`area`, `note`) linking to gaps or plans, or listing a requirements document in `sources`;
- hand-written audit or plan index pages that fit no current page type.

A page with a frontmatter error still counts as a target for links, embeds, area membership, a plan's `gap` and `duplicate_of`, so you will not also see a flood of "missing wikilink" errors for every link to it. A failing `check` ends with a count of errors and of the pages they are on. Page-level errors come first; fix those, then rerun to see what remains. If you find yourself fixing links, you are probably fixing the wrong thing.

## Order that worked

Do these in order, rerunning `check` between steps. Each step removes a class of errors, and later steps are hard to judge while earlier ones are still failing.

1. **Gap frontmatter.** On each gap page drop `status`, add `kind`, `recheck` and `decision`. Map the old state to the nearest honest value: an unchecked gap is `recheck: "not-checked"` and `decision: "open"`. Do not carry over a recheck or a decision unless the page itself records who did it and when; then use that name and date. An agent never writes its product name, and never writes a person's decision that the page does not show.
2. **Gap sections.** Give every gap the six sections (`Current behavior`, `Gap`, `Evidence`, `Recheck`, `Discussion`, `Decision`), moving the old text into the section where it belongs. Write "Not checked yet." and "Open." where nothing was recorded.
3. **Split multi-question pages.** A page that asks two things gets two pages, but only when the two aspects have different next steps or owners. A page that merely carries two kind tags for one question stays one page. In the real migration a vault of 21 gaps became 30 pages this way. Keep the original id on the page that continues the original question and cross-reference the new one in `Discussion`.
4. **Clean the spec pages.** Remove links, embeds and summaries that point from `areas/` and `notes/` to gaps or plans, and remove requirements documents from their `sources`. If a spec sentence is only intent, move it to the matching gap's `Evidence`, labelled as documented intent, and leave the spec to what the code does.
5. **Replace audit and plan index pages.** An audit or implementation-plan index becomes a `run` page that records the pass, plus a dated entry in each gap's `Discussion` carrying the options the old page listed. Do not keep a combined page of findings; the gaps are the findings.
6. **Plans.** `plans/` holds a plan only for a gap a person accepted. In the real migration it stayed empty, because no person had decided anything. Do not infer an acceptance from an old priority, a task, or an existing implementation plan.
7. **Fingerprints and views.** Run `snapshot --notes ID...` only for pages you actually re-read against their sources, and delete the files earlier versions generated (see below). `snapshot --notes` is blocked only by errors on the pages you select (or by an unknown or duplicated id, or an error that belongs to no page, such as a damaged `sources.json`), so it works on fixed pages while other pages still fail and tells you how many other errors it ignored; `snapshot --all` needs the whole vault valid. Accepting a fingerprint says "I read this page against these bytes", so never use it to clear a warning on a page you did not re-read.

## Run pages that link to everything

Older run pages linked every page they touched, and `check` now reports `run pages are history, not part of the map` with the number of links. Those links made each run a hub in Obsidian's graph and pulled all areas into one ball. The fix is mechanical and changes no claim: in each `runs/*.md` replace `[[notes/example|the example rule]]` with the label and the path in code formatting, `the example rule (`notes/example`)`, and do the same for embeds and Markdown links to vault pages. Links to source files and URLs stay. Nothing is generated into the vault any more: read it with the `serve` command, which always shows the current files. Delete what earlier versions generated: `AS-BUILT.md`, `GAPS.md`, `.knowledge/graph.json`, `graph.html` and `Map.canvas`. Until they are gone, `check` reads an old `AS-BUILT.md` or `GAPS.md` as a page and reports its missing frontmatter. A `01-coverage.md` page is no longer asked for; move what it says about each area into that area's page, or leave it as an ordinary index page.

## Vaults written before the rules and reference notes

A vault written before version 0.5.0 of this skill usually describes mechanisms ("a worker runs durable jobs") rather than the rules a person looks up, and has no reference notes. `check` cannot see this, so it does not fail; sync and update fill it in only for the pages they pass ("Leave each page better" in the skill). To bring the whole vault up at once, work through it one area at a time, as **explore <area>**:

1. Find where the code registers each kind of thing the area has (jobs, routes, forms and their schemas, actions, emails, permissions, flags) and write one reference note per kind, with every item and the registration point in `sources`.
2. Add the business rules with their values to the area's notes: required fields, limits, defaults, formats, when actions are available or disabled, empty states, error messages, who may do it.
3. List the reference notes first on the area page and name the kinds not listed yet.
4. Run `snapshot --notes` for the notes you re-read and `check`, and record the pass on a run page.

This changes content, not structure, so it is not part of a format migration: do it as its own pass, area by area, and keep the claims you did not re-read as they are.

## Rules that kept the migration honest

- No decision is inferred from priorities, tasks or plans. If a page does not show who decided and when, the gap is `open`.
- A migration changes structure. If the spec text is wrong, fix it from the code in a separate pass and say so in the run page.
- Write one `run` page for the migration listing what was split, moved and left unfinished, and the checks you ran.
