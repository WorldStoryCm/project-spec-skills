---
id: "pickups"
title: "Pickup cancellation"
type: "area"
status: "partial"
areas: []
sources: ["src/pickups.py", "src/routes.py", "SPEC.md", "tests/test_pickups.py"]
tags: ["area"]
updated: "2026-11-14"
---

# Pickup cancellation

This area covers the in-memory transition and its adapter response. It depends on [[areas/access|customer access]] before state changes are considered.

- [[notes/cancellation-boundary|Cancellation boundary]]: the service currently accepts only `requested`.
- [[notes/route-responses|Route responses]]: service exceptions become status values.
- [[gaps/packed-cancellation|Packed cancellation]]: the accepted requirement includes a state the implementation rejects.
- [[gaps/partner-decision|Partner cancellation]]: proposed actor variation awaiting a decision.

Evidence: [service](../../../src/pickups.py), [adapter](../../../src/routes.py), [requirements](../../../SPEC.md), [tests](../../../tests/test_pickups.py). All four files were inspected. Three existing tests passed during the example check. Real transport, persistence and deployment are not modeled; see [[gaps/deployment-evidence|verification limits]].
