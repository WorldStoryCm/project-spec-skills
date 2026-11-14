---
id: "packed-cancellation"
title: "Packed pickup cancellation contradicts CAN-1"
type: "gap"
status: "conflict"
areas: ["pickups"]
sources: ["SPEC.md", "src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
tags: ["product-gap", "conflict"]
updated: "2026-11-14"
---

# Packed pickup cancellation contradicts CAN-1

Area: [[areas/pickups|Pickup cancellation]]. **Kind: product gap; specification conflict.**

CAN-1 in [the accepted spec](../../../SPEC.md) permits a customer to cancel their own `packed` pickup before collection. The state guard in [cancel_pickup](../../../src/pickups.py) permits only `requested`. [cancel_request](../../../src/routes.py) maps the resulting `ValueError` to status 409.

This is a concrete mismatch in the inspected path. The existing three [tests](../../../tests/test_pickups.py) pass while omitting the packed acceptance case. Passing them is not proof of CAN-1 compliance. The shipped worked report uses static evidence; independent release checks are recorded outside this vault in `VALIDATION.md`.

**Priority:** first within this fixture's accepted cancellation scope. **Next action:** keep CAN-1 or explicitly revise it; if retained, add a failing packed-case regression test before changing the allowlist. Acceptance: the owner can cancel both requested and packed pickups; another customer still receives 403; collected pickups still receive 409; rejected calls preserve state.

See [[notes/cancellation-boundary|current behavior]] and [[notes/route-responses|response mapping]]. [[gaps/partner-decision|Partner support]] is a different decision and does not block this correction.
