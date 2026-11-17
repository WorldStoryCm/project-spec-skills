---
id: "cancellation-boundary"
title: "Only requested pickups are currently cancellable"
type: "note"
status: "current"
areas: ["pickups"]
sources: ["src/pickups.py", "tests/test_pickups.py"]
tags: ["knowledge", "workflow"]
summary: "A customer can cancel a pickup only while it is still requested. Once it is packed or picked up, the cancellation is refused and nothing changes."
updated: "2026-11-14"
---

# Only requested pickups are currently cancellable

A customer who no longer needs a pickup cancels it, and the service lets that happen only before anyone has started work on it.

## How it works

`cancel_pickup` in the [service](../../../src/pickups.py) first runs the [[notes/ownership-check|ownership check]], then looks at the pickup's state. A pickup that passes both is set to `cancelled` and returned. The [[notes/route-responses|adapter]] turns a refusal into status 409.

## Business rules

| ID | Rule |
| --- | --- |
| BR-CANCEL-01 | A pickup can be cancelled only while its state is `requested`. |
| BR-CANCEL-02 | In any other state, including `packed` and `picked_up`, the cancellation is refused with "Only requested pickups can be cancelled" and nothing is changed. |
| BR-CANCEL-03 | The code has no list of states: it names only `requested` and treats every other value the same way. |

The existing [tests](../../../tests/test_pickups.py) cover a `requested` pickup (cancelled) and a `picked_up` pickup (409, unchanged); none uses `packed`.
