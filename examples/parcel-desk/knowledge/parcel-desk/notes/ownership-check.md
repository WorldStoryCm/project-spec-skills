---
id: "ownership-check"
title: "The owner check runs before the state check"
type: "note"
status: "current"
areas: ["access", "pickups"]
sources: ["src/pickups.py", "src/routes.py", "tests/test_pickups.py", "SPEC.md"]
tags: ["knowledge", "rule"]
updated: "2026-11-14"
---

# The owner check runs before the state check

Areas: [[areas/access|Customer access]] and [[areas/pickups|Pickup cancellation]].

`cancel_pickup` compares `pickup.customer_id` with the supplied customer ID before checking the state. Mismatch raises `PermissionError`; no mutation occurs. The adapter maps this to status 403. See [the service](../../../src/pickups.py) and [the adapter](../../../src/routes.py).

This supports CAN-2 in [the spec](../../../SPEC.md). `test_other_customer_cannot_cancel` in [the tests](../../../tests/test_pickups.py) checks a requested pickup, the 403 status and unchanged state. The three-test suite passed during this example's verification; the test does not establish a real authentication boundary.

[[notes/cancellation-boundary|State eligibility]] applies only after the owner check. [[gaps/partner-decision|Partner cancellation]] cannot be inferred from this customer-only contract. Deployed identity remains [[gaps/deployment-evidence|unverified]].
