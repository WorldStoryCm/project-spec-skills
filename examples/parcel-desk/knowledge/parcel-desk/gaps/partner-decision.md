---
id: "partner-decision"
title: "Should a delivery partner be able to cancel on a customer's behalf?"
type: "gap"
kind: "product-plan"
areas: ["access", "pickups"]
sources: ["SPEC.md", "src/routes.py"]
recheck: "confirmed"
rechecked_by: "agent"
rechecked_on: "2026-11-15"
decision: "open"
priority: "low"
confidence: "high"
updated: "2026-11-15"
---

# Should a delivery partner be able to cancel on a customer's behalf?

## Current behavior

Only the pickup's owner can cancel: the service compares the supplied customer ID with the owner, and the adapter takes a customer identity and nothing else. See [[notes/ownership-check|the owner check]] and [[notes/route-responses|the response mapping]].

## Gap

DEC-1 in [the requirements](../../../SPEC.md) leaves partner cancellation undecided and outside the accepted scope. Does the product want it? If so, who may act for whom, what identity evidence is required, and in which states?

## Evidence

- Documented intent: DEC-1 in [SPEC.md](../../../SPEC.md) says permissions, identity checks and allowed states "have not been decided".
- Static reading: [cancel_request](../../../src/routes.py) has no partner parameter, role or contract.
- Nothing was run: the fixture defines no partner behavior to run.

## Recheck

2026-11-15, agent: re-read [SPEC.md](../../../SPEC.md) and [routes.py](../../../src/routes.py) (static only). DEC-1 is still undecided in the requirements and the adapter still has no partner path, so the description above holds. No command was run.

## Discussion

- 2026-11-14 · agent: Absence of a partner path is not a missing accepted feature. Options for a decider: (a) reject for now, (b) defer until a partner integration exists, (c) accept and define permissions, identity checks and states first.

## Decision

Open.
