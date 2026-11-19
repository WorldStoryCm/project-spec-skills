---
id: "state-leak"
title: "Can a customer learn the state of someone else's pickup from a refusal?"
type: "gap"
created: "2026-11-14"
kind: "verification-gap"
areas: ["access"]
sources: ["src/pickups.py", "src/routes.py"]
recheck: "not-reproduced"
rechecked_by: "agent"
rechecked_on: "2026-11-16"
decision: "done"
priority: "medium"
confidence: "high"
updated: "2026-11-16"
---

# Can a customer learn the state of someone else's pickup from a refusal?

## Current behavior

A cancellation can be refused for two reasons, and the caller sees which one: 403 `forbidden` when the pickup is not theirs, 409 `cancellation_conflict` when its state does not allow it. See [[notes/ownership-check|the owner check]] and [[notes/route-responses|the response mapping]].

## Gap

If the state were checked before the owner, a customer could try another customer's pickup ID and read its progress from the answer: 409 would mean "already packed". CAN-2 in [the requirements](../../../SPEC.md) says a customer acts only on their own pickups. Does the order of the two checks keep that?

## Evidence

- Static reading: [cancel_pickup](../../../src/pickups.py) compares the customer ID first and raises `PermissionError` before it looks at `pickup.state`.
- The fixture's tests do not try someone else's pickup in a state other than `requested`.

## Recheck

2026-11-16, agent: re-read [pickups.py](../../../src/pickups.py) and [routes.py](../../../src/routes.py) (static only). The owner comparison is the first statement of `cancel_pickup`, and the adapter maps `PermissionError` to 403 whatever the state, so someone else's pickup always answers 403 `forbidden`. The leak described above does not exist (not reproduced). No command was run.

## Discussion

- 2026-11-14 · agent: Raised while reading the two refusals; the order of the checks decides it.

## Decision

Done. Closed by BR-OWNER-02 on [[notes/ownership-check|the owner check]]: the owner check comes first in `cancel_pickup`, so the refusal does not depend on the pickup's state.
