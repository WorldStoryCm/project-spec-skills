# Contributing

Keep each skill focused on a distinct user request. A new skill should solve a recurring problem that the existing entry points handle poorly, with an example showing the difference. Describe categories in the root catalog; keep installable directories under `skills/`.

Use English instructions and invented fixtures. Cite the license and provenance of any third-party contribution. Never contribute private project notes, tokens, customer data or absolute paths to your machine. A knowledge graph often contains source-derived information: review it before making it public.

## Local checks

```sh
python3 scripts/verify.py
```

This runs the helper regression suite, the fictional app tests, skill/package checks and the example vault validator. Node.js, when present, also checks the viewer's JavaScript syntax. It does not run an agent or prove the instructions produce correct conclusions.

For changes to instructions, try the relevant request in [the evaluation scenarios](docs/evaluation.md) in a disposable copy with a fresh agent session. Give the agent the request and raw fixture, then compare its actual work with the rubric. Reading the expected answer is not a forward test. Record checks as PASS, FAIL or NOT RUN and retain their revision and scope.

For changes to source tracking, demonstrate that drift is detected without accepting new evidence or changing the reviewed cursor. Preserve stable IDs and manually authored notes. Add regression tests for the observed failure, rather than testing that particular prose appears.

For viewer changes, open a generated example and check search, filters, internal navigation and narrow-screen layout. Use DOM text for note content; do not execute embedded HTML or load remote scripts, fonts or analytics.

## Scope and publishing

The skills produce evidence and documents. A report does not grant permission to change application code, create issues, send messages or deploy. Respect authorization already present in the user's request and the target repository's coordination rules.

Knowledge is an interpretation of a bounded investigation. Keep missing evidence distinct from a missing feature, and keep proposed behavior distinct from today's behavior. Release notes should state actual checks and important limitations without presenting note counts as completeness scores.
