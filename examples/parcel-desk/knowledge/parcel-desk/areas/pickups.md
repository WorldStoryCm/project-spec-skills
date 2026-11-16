---
id: "pickups"
title: "Pickup cancellation"
type: "area"
status: "partial"
areas: []
sources: ["src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
tags: ["area"]
summary: "How a customer's pickup is cancelled in the in-memory service and how the adapter reports the outcome."
updated: "2026-11-14"
---

# Pickup cancellation

This area covers the in-memory cancellation transition and the adapter response built from it. It depends on [[areas/access|customer access]], whose owner check runs before any state is considered.

- [[notes/route-responses|What a cancellation request returns]] (reference): every answer, with the condition behind it.
- [[notes/cancellation-boundary|Cancellation boundary]]: the service cancels only pickups whose state is `requested`.

Not listed yet: the states a pickup can be in.

Read: [service](../../../src/pickups.py), [adapter](../../../src/routes.py) and [tests](../../../tests/test_pickups.py). The three existing tests passed in the example check. Not modeled: real transport, persistence, concurrent requests and deployment.
