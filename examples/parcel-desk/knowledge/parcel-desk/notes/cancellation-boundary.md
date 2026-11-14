---
id: "cancellation-boundary"
title: "Only requested pickups are currently cancellable"
type: "note"
status: "current"
areas: ["pickups"]
sources: ["src/pickups.py", "SPEC.md"]
tags: ["knowledge", "workflow"]
updated: "2026-11-14"
---

# Only requested pickups are currently cancellable

Area: [[areas/pickups|Pickup cancellation]]. Use this note when changing allowed states or explaining a rejected cancellation.

**Implementation:** `cancel_pickup` checks ownership, then requires `pickup.state == "requested"`. Accepted calls set state to `cancelled`. Any other state raises `ValueError` before the mutation. The [service](../../../src/pickups.py) establishes this behavior; it is not inferred from the graph.

**Intent:** CAN-1 in the [spec](../../../SPEC.md) includes both `requested` and `packed` before collection. The difference is tracked by [[gaps/packed-cancellation|the packed cancellation gap]]. This current note describes code, not agreement with the requirement.

The [[notes/ownership-check|ownership guard]] runs first. The [[notes/route-responses|adapter]] converts state rejection to status 409. Existing tests verify requested and collected cases; they do not cover packed success. See [[01-coverage|coverage]] for the executed test command. A focused packed-case assertion remains a proposed regression test.
