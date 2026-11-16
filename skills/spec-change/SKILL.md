---
name: spec-change
description: Develop from an edited specification. A person edits the spec text on a branch; the diff is the change request. Use to review that diff for contradictions, ambiguity and missing cases before any code is written, then implement it and check every changed statement against the code. Works on a project-knowledge vault or on any specification kept as Markdown in Git.
license: MIT
---

# Spec Change

The person describes what they want by editing the specification, not by describing code. Your job is to make the code say what the edited spec says, and to tell them where their text cannot be built as written. They follow the work by reading the spec and your questions, so write for a reader who does not open the source.

This skill changes application code. It is the only one in this bundle that does. Read the repository's instructions first, work on the branch that holds the spec edits, and leave committing, pushing and merging to the person unless they ask.

## Read the change request

- Find the base the person branched from (ask if it is not obvious) and read the spec diff against it: committed and uncommitted edits to the spec pages. In a project-knowledge vault these are `areas/` and `notes/`; ignore generated files (`AS-BUILT.md`, `GAPS.md`, `.knowledge/`).
- The base spec must describe the base code. If it is behind (a pending sync, freshness warnings), the diff mixes the person's intent with ordinary drift; say so and separate the two before going on.
- Restate every changed statement as one line in plain language: what happens today, what should happen instead. A removed sentence is a change too. Edits that only reword a page without changing behavior are listed as such and need no code.
- Do not treat anything outside the diff as a request. An idea in a chat message or a gap page becomes part of the change only when the person puts it into the spec text.

## Ask before writing code

Review the change as a careful colleague would review a requirement, against both the rest of the spec and the code.

- **Contradictions.** Read the pages linked from the changed ones, the rest of their area and the pages that cite the same sources. Name each statement elsewhere that the edit now contradicts.
- **Ambiguity.** For each changed statement, say who triggers it, when, and what they observe. If two reasonable readings lead to different code, that is a question.
- **Missing cases.** Check what the edit leaves unsaid: failure and denial, permissions, empty and boundary values, existing stored data, concurrent use, and what other features that call the same code will now do.
- **Cost surprises.** Trace the current code path far enough to see what the change touches. Tell the person when a one-line edit implies a migration, a contract change for other callers or a new dependency.

Sort the findings into two lists. **Questions** need the person's answer because the answer changes behavior; give each a number, the options and the one you would pick. **Assumptions** are choices you can make and reverse cheaply; state them and proceed. Keep the lists short and written in the language of the spec, not of the code.

Stop and wait for answers while any question is open. Each answer goes into the spec text, written by the person or by you in their words, so that the spec, not the conversation, holds the decision. If the person cannot answer now, take that statement out of this round: restore its as-built wording and, in a vault, record the open choice as a gap following [gaps.md](references/gaps.md).

## Implement

- For more than a small change, lay out the ordered steps first: shared contracts before their callers, each step with the check that verifies it.
- Every changed statement gets a check that would fail on the old behavior, at the boundary the statement describes. Follow the project's conventions and keep the change inside the scope of the diff. If you find something else wrong on the way, report it; do not fix it silently.
- If the code shows that a statement cannot hold as written, stop and return to the person with the reason and options. Do not reword their spec to match what was easy to build.

## Check the code against the spec

When the code is done, read it again as if you had not written it and compare it with each changed page, statement by statement.

- A statement that holds: note the file and symbol that implement it and the check that ran. Reading a test is not running it; mark checks you did not run `NOT RUN`.
- A statement that does not hold: fix the code, or bring it to the person. The spec changes only on their word.
- In a vault, update each changed page's `sources` to the files it now rests on, then run `check`, `snapshot --notes` for the pages you re-read, and `build`, as the project-knowledge skill describes. No spec page may be left describing behavior the branch does not implement: before the work is called done, such text goes back to its as-built wording and the intent moves to a gap.

## Report

```text
# Spec change: <title>
## What changed        one line per statement: before, after
## Answered questions  the question, the answer, where the spec now says it
## Assumptions         choices made without asking, and how to reverse them
## Evidence            statement -> file and symbol -> check, PASS / FAIL / NOT RUN
## Not done            statements taken out of this round, with their gaps
## Spec text I edited  every wording change made by the agent, so the person can review it
```

Keep the report in the person's language and in terms of behavior. Code references belong in the Evidence section only.
