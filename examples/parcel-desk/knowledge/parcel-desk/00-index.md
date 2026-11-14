---
id: "index"
title: "Parcel Desk knowledge"
type: "index"
status: "current"
areas: []
sources: []
tags: ["knowledge"]
updated: "2026-11-14"
---

# Parcel Desk knowledge

A small **fictional** pickup service. This map records inspected source, intended behavior and questions. It is a worked example, not a production readiness assessment.

## Areas

- **[[areas/pickups|Pickup cancellation]]** explains the state transition and response boundary.
- [[areas/access|Customer access]] explains whose pickup can be changed.

## Where to begin

Follow [[notes/cancellation-boundary|the cancellation boundary]], then [[notes/route-responses|the route response mapping]]. The ownership rule in [[notes/ownership-check|Customer ownership]] runs first.

There is one confirmed source/spec mismatch: [[gaps/packed-cancellation|Packed cancellation]]. [[gaps/partner-decision|Partner cancellation]] is an open product decision. [[gaps/deployment-evidence|Deployment evidence]] is outside this fixture's verification scope.

See [[01-coverage|Coverage]] and [[runs/example-survey|the example survey]] for limits. Open `graph.html` in a browser or `Map.canvas` in Obsidian. A flagged node does not by itself mean a missing feature.
