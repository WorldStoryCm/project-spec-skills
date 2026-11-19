---
id: "ownership-check"
title: "The owner check runs before the state check"
type: "note"
status: "current"
areas: ["access", "pickups"]
sources: ["src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
tags: ["knowledge", "rule"]
summary: "Only the customer who owns a pickup can cancel it. Anyone else is refused before the state of the pickup is looked at, and nothing changes."
updated: "2026-11-14"
---

# The owner check runs before the state check

A customer can cancel only their own pickups, and they learn nothing about anyone else's: the refusal is the same whatever state the other customer's pickup is in.

## How it works

`cancel_pickup` in the [service](../../../src/pickups.py) compares `pickup.customer_id` with the supplied customer ID before it looks at the state. A mismatch raises `PermissionError`, which the [adapter](../../../src/routes.py) maps to status 403. [[notes/cancellation-boundary|State eligibility]] applies only after this check passes.

## Business rules

| ID | Rule |
| --- | --- |
| BR-OWNER-01 | Only the customer a pickup belongs to can cancel it. For anyone else the service refuses with "Pickup belongs to another customer", the adapter answers 403 `forbidden`, and nothing is changed. |
| BR-OWNER-02 | The owner check comes first, so the refusal does not depend on the pickup's state. |
| BR-OWNER-03 | The only caller identity is the customer ID the adapter is given. Its docstring says the caller has already authenticated the customer, and no partner or staff identity exists. |

`test_other_customer_cannot_cancel` in the [tests](../../../tests/test_pickups.py) uses a `requested` pickup and checks status 403 and unchanged state.
