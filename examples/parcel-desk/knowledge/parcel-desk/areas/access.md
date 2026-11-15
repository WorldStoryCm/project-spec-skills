---
id: "access"
title: "Customer access"
type: "area"
status: "partial"
areas: []
sources: ["src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
tags: ["area"]
summary: "Whose pickup a caller may change: the owner comparison in the service and how the adapter reports a refusal."
updated: "2026-11-14"
---

# Customer access

The adapter accepts a customer identifier supplied by its caller, and the service compares it with the pickup's owner before looking at state. This is a policy check on a supplied value; nothing in the fixture authenticates a request.

- [[notes/ownership-check|Ownership rule]] constrains [[areas/pickups|pickup cancellation]].
- [[notes/route-responses|Route responses]] shows how a refusal is reported as status 403.

Read: [service](../../../src/pickups.py), [adapter](../../../src/routes.py), and [tests](../../../tests/test_pickups.py). The other-customer test passed in the example check. Identity providers, sessions and any partner identity are not present in the fixture.
