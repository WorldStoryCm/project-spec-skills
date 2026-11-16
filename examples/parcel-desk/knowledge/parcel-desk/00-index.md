---
id: "index"
title: "Parcel Desk knowledge"
type: "index"
status: "current"
areas: []
sources: []
tags: ["knowledge"]
updated: "2026-11-15"
---

# Parcel Desk knowledge

A small **fictional** pickup service. The vault has two layers. The **as-built spec** says what the code does today and is derived only from source. The **gap queue** holds every question about what is missing, doubtful or proposed; people re-check and decide each one. This is a worked example, not a production readiness assessment.

## The spec

Read it as one document in [AS-BUILT](AS-BUILT.md) (generated), or page by page:

- **[[areas/pickups|Pickup cancellation]]** covers the state transition and the response mapping.
- [[areas/access|Customer access]] covers whose pickup can be changed.

Start with [[notes/cancellation-boundary|the cancellation boundary]], then [[notes/route-responses|the route response mapping]]. The rule in [[notes/ownership-check|Customer ownership]] runs first.

## The gap queue

[GAPS](GAPS.md) (generated) lists every gap by state. In this example:

- [[gaps/packed-cancellation|Packed cancellation]] is accepted, with [[plans/packed-cancellation|a plan]].
- [[gaps/partner-decision|Partner cancellation]] has been rechecked and awaits a person's decision.
- [[gaps/deployment-evidence|Deployment evidence]] has not been rechecked yet.

See [[01-coverage|Coverage]] and [[runs/example-survey|the example survey]] for limits. `AS-BUILT.md` and `GAPS.md` appear after `build`; the `serve` command shows the vault in a browser.
