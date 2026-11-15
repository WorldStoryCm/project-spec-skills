---
id: "example-survey"
title: "Fictional project survey"
type: "run"
status: "current"
areas: []
sources: ["SPEC.md", "src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
tags: ["run"]
updated: "2026-11-15"
---

# Fictional project survey

This authored example surveys the four fixture source, requirements and test files. It is not a transcript of an independent agent run. The fixture has no independent application revision: it ships inside the toolkit repository, whose Git commit identifies the exact version.

## 2026-11-14: survey

Wrote the pickup (`areas/pickups`) and access (`areas/access`) maps and three behavior notes from the code. Raised three gaps, each with `decision: "open"`: packed cancellation (`gaps/packed-cancellation`; the code rejects a state the requirements allow), partner cancellation (`gaps/partner-decision`; the requirements leave it undecided) and deployment evidence (`gaps/deployment-evidence`; not checkable in this fixture). Ran `python3 -m unittest discover -s tests -v` from the fictional project: **PASS, 3 tests**. Reviewed source fingerprints were then accepted; view generation does not make claims true.

## 2026-11-15: gap queue

Tomas Brandt rechecked packed cancellation by running the fixture; Priya Nair accepted it and a plan (`plans/packed-cancellation`) was written. The agent rechecked partner cancellation by reading the code and left the decision open. Deployment evidence has not been rechecked. No spec note changed.

No external system was queried and no real product behavior is implied. Release checks and browser observations are in the toolkit's `VALIDATION.md`.
