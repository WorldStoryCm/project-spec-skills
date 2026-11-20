---
id: "deployment-evidence"
title: "What do an allowed and a denied cancellation return through a real entrypoint?"
type: "gap"
created: "2026-11-14"
kind: "verification-gap"
topic: "api"
areas: ["access", "pickups"]
sources: ["SPEC.md", "src/routes.py"]
recheck: "not-checked"
decision: "open"
priority: "low"
confidence: "medium"
updated: "2026-11-14"
---

# What do an allowed and a denied cancellation return through a real entrypoint?

## Current behavior

Cancellation runs as in-process Python calls: `cancel_request` returns dictionaries and takes an already-authenticated customer string. See [[notes/route-responses|the response mapping]] and [[notes/ownership-check|the owner check]].

## Gap

The [requirements](../../../SPEC.md) describe an in-memory fixture with no network server, identity provider or database. Nothing here shows what a real deployment returns. When an allowed and a denied cancellation go through a deployed entrypoint, do they produce the same responses and state changes as the in-process calls?

## Evidence

- Documented boundary: the "Boundary" section of [SPEC.md](../../../SPEC.md) says the fixture has no network server, identity provider, database or provider integration; the module docstring of [routes.py](../../../src/routes.py) says the same of the adapter.
- No deployment checks were run (NOT RUN). For this fictional example there is nothing to run.

## Recheck

Not checked yet.

## Discussion

- 2026-11-14 · agent: In an actual project the next step would be to name the real entrypoint and environment, then test one allowed and one denied cancellation. Authentication, persistence and concurrent cancellations would each be a separate gap. For this example the gap marks the limit of what the vault can claim.

## Decision

Open.
