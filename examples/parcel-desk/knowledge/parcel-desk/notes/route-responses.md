---
id: "route-responses"
title: "Cancellation exceptions become adapter statuses"
type: "note"
status: "current"
areas: ["pickups", "access"]
sources: ["src/routes.py", "src/pickups.py", "tests/test_pickups.py"]
tags: ["knowledge", "contract"]
updated: "2026-11-14"
---

# Cancellation exceptions become adapter statuses

Area: [[areas/pickups|Pickup cancellation]].

The in-process `cancel_request` adapter calls `cancel_pickup`. It returns 403 for `PermissionError`, 409 for `ValueError`, and a 200 result containing the updated state on success. See [the adapter](../../../src/routes.py) and [the called service](../../../src/pickups.py).

[[notes/ownership-check|Ownership]] determines forbidden responses; [[notes/cancellation-boundary|state eligibility]] determines conflicts. The packed scenario reaches the latter guard, which explains [[gaps/packed-cancellation|the requirement mismatch]].

The [existing tests](../../../tests/test_pickups.py) exercise these three response branches with requested, other-customer and collected fixtures; the suite passed. These are dictionary status values, not observed network responses. Real HTTP mapping and authentication are [[gaps/deployment-evidence|outside the example]].
