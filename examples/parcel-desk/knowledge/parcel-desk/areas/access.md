---
id: "access"
title: "Customer access"
type: "area"
status: "partial"
areas: []
sources: ["src/pickups.py", "src/routes.py", "SPEC.md", "tests/test_pickups.py"]
tags: ["area"]
updated: "2026-11-14"
---

# Customer access

The adapter accepts a customer identifier supplied by its caller. The service compares it with the pickup owner before inspecting state. This fixture demonstrates a policy check; it does not authenticate a network request.

- [[notes/ownership-check|Ownership rule]] constrains [[areas/pickups|pickup cancellation]].
- [[gaps/partner-decision|Partner cancellation]] is an undecided extension, not an accepted missing feature.
- [[gaps/deployment-evidence|Deployment evidence]] limits conclusions about real identity handling.

Inspected [service](../../../src/pickups.py), [adapter](../../../src/routes.py), [spec](../../../SPEC.md) and [tests](../../../tests/test_pickups.py). The other-customer unit test passed. External identity and real user sessions are outside the fixture.
