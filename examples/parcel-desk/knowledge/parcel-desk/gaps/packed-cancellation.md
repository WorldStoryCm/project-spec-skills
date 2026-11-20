---
id: "packed-cancellation"
title: "Should a customer be able to cancel their own packed pickup?"
type: "gap"
created: "2026-11-14"
kind: "product-gap"
topic: "logic"
areas: ["pickups"]
sources: ["SPEC.md", "src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
recheck: "confirmed"
rechecked_by: "Tomas Brandt"
rechecked_on: "2026-11-15"
decision: "accepted"
decided_by: "Priya Nair"
decided_on: "2026-11-15"
priority: "high"
confidence: "high"
updated: "2026-11-15"
---

# Should a customer be able to cancel their own packed pickup?

## Current behavior

The service cancels only `requested` pickups and rejects every other state, including `packed`, after the owner check; the adapter reports that as status 409. See [[notes/cancellation-boundary|the cancellation boundary]], [[notes/ownership-check|the owner check]] and [[notes/route-responses|the response mapping]].

## Gap

CAN-1 in [the requirements](../../../SPEC.md) says a customer can cancel their own pickup before collection, "including when its state is `requested` or `packed`". The code does not do that for `packed`. Should the service change so the owner can cancel a packed pickup?

## Evidence

- Documented intent: CAN-1 in [SPEC.md](../../../SPEC.md).
- Static reading: the state guard in [cancel_pickup](../../../src/pickups.py) permits only `requested`; [cancel_request](../../../src/routes.py) maps the resulting `ValueError` to 409.
- The three existing [tests](../../../tests/test_pickups.py) pass and none uses a `packed` pickup, so they neither show nor contradict the mismatch.

## Recheck

2026-11-15, Tomas Brandt: ran `cancel_request(Pickup("example", "customer-a", "packed"), "customer-a")` in the fixture. Result: `{'status': 409, 'error': 'cancellation_conflict'}` and the state stays `packed`. The same call with `customer-b` returns 403 and also leaves the state unchanged. Confirmed against the current files; this is a local in-process call, not a request to a deployed service.

## Discussion

- 2026-11-14 · agent: Found while mapping the cancellation flow. The alternative to changing the code is revising CAN-1 to say `requested` only.
- 2026-11-15 · Priya Nair: CAN-1 stays as written; support has had packed-pickup complaints. The partner question is separate and does not block this.

## Decision

Accepted on 2026-11-15 by Priya Nair: keep CAN-1 and change the service. Planned in [[plans/packed-cancellation|the implementation plan]].
