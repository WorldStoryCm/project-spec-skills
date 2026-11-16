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

Start from an area:

- **[[areas/pickups|Pickup cancellation]]** covers the state transition and the response mapping.
- [[areas/access|Customer access]] covers whose pickup can be changed.

Start with [[notes/cancellation-boundary|the cancellation boundary]], then [[notes/route-responses|the route response mapping]]. The rule in [[notes/ownership-check|Customer ownership]] runs first.

## The gap queue

One question per page. In this example:

- [[gaps/packed-cancellation|Packed cancellation]] is accepted, with [[plans/packed-cancellation|a plan]].
- [[gaps/partner-decision|Partner cancellation]] has been rechecked and awaits a person's decision.
- [[gaps/deployment-evidence|Deployment evidence]] has not been rechecked yet.

## Limits

Each area page says what was read and what the fixture does not model. No real service, logs or customer data were inspected, and the fixture's source fingerprints describe the files shipped with this example; [[runs/example-survey|the example survey]] records the pass. The `serve` command shows the vault in a browser.
