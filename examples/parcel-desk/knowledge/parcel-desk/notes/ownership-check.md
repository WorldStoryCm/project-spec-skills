---
id: "ownership-check"
title: "The owner check runs before the state check"
type: "note"
status: "current"
areas: ["access", "pickups"]
sources: ["src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
tags: ["knowledge", "rule"]
updated: "2026-11-14"
---

# The owner check runs before the state check

Areas: [[areas/access|Customer access]] and [[areas/pickups|Pickup cancellation]].

`cancel_pickup` compares `pickup.customer_id` with the supplied customer ID before it looks at the state. A mismatch raises `PermissionError` and nothing is changed; the adapter maps it to status 403 ([service](../../../src/pickups.py), [adapter](../../../src/routes.py)). The only caller identity in the code is that supplied string: the adapter's docstring says the caller has already authenticated the customer, and no partner or staff identity exists.

`test_other_customer_cannot_cancel` in the [tests](../../../tests/test_pickups.py) uses a `requested` pickup and checks status 403 and unchanged state; it passed in the example check. [[notes/cancellation-boundary|State eligibility]] applies only after this check passes.
