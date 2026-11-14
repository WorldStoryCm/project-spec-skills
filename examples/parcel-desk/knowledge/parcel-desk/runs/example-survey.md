---
id: "example-survey"
title: "Fictional project survey"
type: "run"
status: "current"
areas: []
sources: ["SPEC.md", "src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
tags: ["run"]
updated: "2026-11-14"
---

# Fictional project survey

This authored example surveys all four fixture source/spec/test files. It is not a transcript of an independent agent run. The fixture has no independent application revision: it is shipped inside the toolkit repository, whose Git commit identifies the exact version.

Created [[areas/pickups|pickup]] and [[areas/access|access]] maps, three behavior notes and three questions with different next actions. The accepted packed cancellation requirement diverges from code. Partner behavior is undecided. Deployment evidence is deliberately absent.

Executed `python3 -m unittest discover -s tests -v` from the fictional project: **PASS, 3 tests**. Reviewed source fingerprints were then accepted for the example; view generation does not make application claims true. Release checks, separate agent evaluations and browser observations are reported in the toolkit's `VALIDATION.md`.

See [[00-index|the index]] and [[01-coverage|coverage]]. No external system was queried and no real product behavior is implied.
