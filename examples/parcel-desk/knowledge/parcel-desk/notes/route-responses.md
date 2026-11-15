---
id: "route-responses"
title: "Cancellation exceptions become adapter statuses"
type: "note"
status: "current"
areas: ["pickups", "access"]
sources: ["src/routes.py", "src/pickups.py", "tests/test_pickups.py"]
tags: ["knowledge", "contract"]
summary: "A cancellation request gets one of three answers: cancelled, refused because the pickup belongs to someone else, or refused because it can no longer be cancelled."
updated: "2026-11-14"
---

# Cancellation exceptions become adapter statuses

Areas: [[areas/pickups|Pickup cancellation]] and [[areas/access|Customer access]].

The in-process `cancel_request` adapter calls `cancel_pickup` and returns a dictionary: `{"status": 403, "error": "forbidden"}` for `PermissionError`, `{"status": 409, "error": "cancellation_conflict"}` for `ValueError`, and `{"status": 200, "state": <new state>}` on success. See [the adapter](../../../src/routes.py) and [the called service](../../../src/pickups.py).

[[notes/ownership-check|Ownership]] decides the 403 case and [[notes/cancellation-boundary|state eligibility]] decides the 409 case, so a `packed` pickup owned by the caller reaches the 409 branch. The [existing tests](../../../tests/test_pickups.py) exercise the three branches with a requested, an other-customer and a collected pickup, and passed in the example check. The values are dictionaries returned in-process, not observed HTTP responses.
