# Writing gap and plan pages

This page is self-contained: it is enough to create, update or close a gap page, or to write a plan page, in a project-knowledge vault. Nothing else needs to be read first.

## Why gaps are separate from the spec

A vault has two layers. Spec pages (`areas/`, `notes/`) say what the code does today, nothing more. Gap pages (`gaps/`) hold every doubt, missing piece, contradiction or idea, one question per page. Plan pages (`plans/`) say how to build one accepted gap. The layers stay apart so a reader can trust the spec without wondering which sentences are proposals, and so a person can look at each gap on its own and decide it. An agent proposes; a person decides.

Gap and plan pages link to spec notes with wikilinks. Spec pages never link back to gaps or plans (the validator rejects it).

## Files and properties

A gap lives in `gaps/<slug>.md`; a plan in `plans/<gap-id>.md`. Frontmatter is one property per line with a JSON value (strings in double quotes, arrays on one line).

Every page: `id` (unique ASCII slug), `title`, `type`, `areas` (at least one existing area id), `sources` (repository-relative files read; may be empty for gaps and plans), `updated` (`YYYY-MM-DD`, last substantive edit).

A gap must not have `status`; its progress is carried by `recheck` and `decision`.

| Property | When | Values |
| --- | --- | --- |
| `type` | always | `"gap"` |
| `kind` | always | one of `product-gap` (accepted requirement missing or unmet), `verification-gap` (behavior exists but evidence is missing), `product-plan` (a proposal or open product choice), `conflict` (credible sources disagree), `knowledge-gap` (something is unexplained or undocumented) |
| `recheck` | always | `not-checked`, `confirmed`, `not-reproduced`, `outdated` (the cited sources changed after the last recorded recheck) |
| `rechecked_by` | when `recheck` is not `not-checked` | a person's name, or `agent`; an agent always writes `agent`, and a person's name appears only when that person ran the check and said so |
| `rechecked_on` | when `recheck` is not `not-checked` | `YYYY-MM-DD` |
| `decision` | always | `open`, `accepted`, `rejected`, `deferred`, `done`, `duplicate` |
| `decided_by` | when `decision` is `accepted`, `rejected` or `deferred` | a person's name; the value `agent` is an error |
| `decided_on` | when `decision` is `accepted`, `rejected` or `deferred` | `YYYY-MM-DD` |
| `duplicate_of` | when `decision` is `duplicate` | id of another existing gap (not itself) |
| `priority`, `confidence` | optional, gap and plan pages only | short strings, e.g. `"high"` |

`decided_by` and `decided_on` are also allowed on `done` and `duplicate` but not required. With `outdated`, `rechecked_by` and `rechecked_on` stay in place as the record of the last recheck actually done. A fresh recheck replaces all three fields and adds a new dated entry to the `Recheck` section; keep the older entries.

The `rechecked_*` fields must be absent only while `recheck` is `not-checked`; `decided_*` absent while `decision` is `open`; `duplicate_of` absent for any other decision. Optional `tags`, `aliases`, `task_ids`, `summary` and `verification` work as on other pages.

A plan page has `type: "plan"`, a `status` (`current`, `partial`, `planned`, `stale` or `superseded`; use `planned` until the work is done) and `gap`: the id of an existing gap whose `decision` is `accepted` or `done`.

## The six sections

Every gap has exactly these `##` headings, once each (order does not matter). A missing or repeated heading is a validation error.

- `## Current behavior`: what the code does today in this area, as plain fact, linking the relevant spec notes. No opinion about what it should do.
- `## Gap`: the one question this page asks, phrased so a person can answer it. If the finding has a second aspect with a different next step or owner, make it a second page.
- `## Evidence`: what supports the question: files and symbols read, commands run with results, `NOT RUN` for anything only read. Label documented intent, static reading and observed execution separately.
- `## Recheck`: while `not-checked`, write "Not checked yet." Otherwise: who re-verified, how, when, and what they found, newest entry last. When you set `outdated`, add a dated line saying which source changed. The pass that raised the gap is not a recheck.
- `## Discussion`: append-only log, see below.
- `## Decision`: while `open`, write "Open." Otherwise the decision and its reason, in the words of the person who decided. For `done`, say where in the code the question is now closed. For `duplicate`, name the surviving gap.

When `recheck` is not `not-checked`, the Recheck section must have text; when `decision` is not `open`, so must Decision.

## Discussion entries

One bullet per entry, oldest first, never edited or removed afterwards:

```text
- 2026-11-15 · Name: what was said, proposed or learned.
```

Use `agent` as the name for entries you write yourself. Layout of options, objections and questions belongs here, not in `Decision`, which records only the outcome.

## Who sets which field

| Field | Who |
| --- | --- |
| New gap: `kind`, `recheck: "not-checked"`, `decision: "open"`, optional `priority`/`confidence` | The agent that found it |
| `recheck`, `rechecked_by`, `rechecked_on`, `Recheck` text | Whoever actually performed the check; an agent writes `agent` only for a check it ran itself, with its commands and results. An agent may also set `recheck: "outdated"` when a cited source changed since the recorded recheck, keeping the other two fields |
| `decision: accepted`, `rejected`, `deferred` with `decided_by`, `decided_on` | A person only. An agent writes it only when a person said so in the conversation, and records that person's name |
| `decision: done` | An agent may set it after reading current code that closes the question; it cites where in `Decision` |
| `decision: duplicate`, `duplicate_of` | Agent or person (bookkeeping) |
| `Discussion` | Anyone, by appending |

Never guess a decision from silence, from a plan existing, or from a task being created. If it is unclear whether a person decided, leave `open` and ask in `Discussion`.

## Derived state

Computed by the helper, never written into Markdown:

| `decision` | `recheck` | State |
| --- | --- | --- |
| `open` | `not-checked` or `outdated` | `needs-recheck` |
| `open` | `confirmed` or `not-reproduced` | `needs-decision` |
| anything else | any | the `decision` value |

## Example gap page (illustrative)

````markdown
---
id: "invoice-retry-limit"
title: "Should failed invoice emails retry more than once?"
type: "gap"
kind: "product-plan"
areas: ["billing"]
sources: ["src/billing/mailer.py"]
recheck: "confirmed"
rechecked_by: "Dana Ruiz"
rechecked_on: "2026-11-15"
decision: "open"
priority: "medium"
updated: "2026-11-15"
---

# Should failed invoice emails retry more than once?

## Current behavior

`send_invoice` makes one delivery attempt and logs a failure; it does not schedule another. See [[notes/invoice-delivery|Invoice delivery]].

## Gap

Customers with a temporary mail outage never receive the invoice. Should the mailer retry, and if so how many times and over what period?

## Evidence

- Static: `send_invoice` in `src/billing/mailer.py` has no retry loop or queue call.
- Documented intent: none found; no requirement mentions retries.
- No test covers a failed first attempt (NOT RUN, nothing to run).

## Recheck

2026-11-15, Dana Ruiz: reproduced with a stubbed transport that raises on the first call; the invoice stays unsent and one error is logged. Confirmed.

## Discussion

- 2026-11-15 · agent: Options are (a) fixed three retries within an hour, (b) hand the email to the existing job queue, (c) leave as is and show a "resend" button.
- 2026-11-16 · Dana Ruiz: Leaning to (b); need to check queue limits first.

## Decision

Open.
````

## Writing a plan page

Create one only for a gap whose `decision` is `accepted`. Name it `plans/<gap-id>.md`, give it its own `id` (for example `<gap-id>-plan`), set `gap` to the gap's id and use the gap's areas. The body states the goal and what exists today (with links to spec notes), the ordered steps with the files they touch, observable acceptance checks, what is out of scope, and which checks have not been run. A plan records intent for one decision; it does not add facts to the spec. When the work lands, an agent that reads the code may set the gap to `done`, and the spec notes are then updated from the code.
