---
id: "route-responses"
title: "What a cancellation request returns"
type: "note"
status: "current"
areas: ["pickups", "access"]
sources: ["src/routes.py", "src/pickups.py", "tests/test_pickups.py"]
tags: ["knowledge", "contract", "reference"]
summary: "A cancellation request gets one of three answers: cancelled, refused because the pickup belongs to someone else, or refused because it can no longer be cancelled."
updated: "2026-11-16"
---

# What a cancellation request returns

Every answer of `cancel_request`, the in-process adapter in [routes.py](../../../src/routes.py): three, one for each way out of `cancel_pickup` in [pickups.py](../../../src/pickups.py). The checks run in the order of the rows, and the first one that fails decides the answer.

| Case | Condition | Answer | Pickup state afterwards |
| --- | --- | --- | --- |
| Another customer's pickup | `pickup.customer_id` is not the caller's | `{"status": 403, "error": "forbidden"}` | unchanged |
| Can no longer be cancelled | the caller's pickup, in any state but `requested` (for example `packed` or `picked_up`) | `{"status": 409, "error": "cancellation_conflict"}` | unchanged |
| Cancelled | the caller's pickup, in state `requested` | `{"status": 200, "state": "cancelled"}` | `cancelled` |

There is no fourth answer: the adapter catches only `PermissionError` and `ValueError`, and any other exception propagates to its caller. Because [[notes/ownership-check|the owner check]] runs first, the answer for another customer's pickup does not depend on its state. [[notes/cancellation-boundary|The state rule]] decides the second row, so a `packed` pickup of the caller's own is refused.

The [existing tests](../../../tests/test_pickups.py) cover each row once (another customer, `picked_up`, `requested`); the first two assert the status and the unchanged state but not the `error` text. The answers are dictionaries returned in-process, not observed HTTP responses.
