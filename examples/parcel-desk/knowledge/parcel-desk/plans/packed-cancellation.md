---
id: "packed-cancellation-plan"
title: "Plan: allow the owner to cancel a packed pickup"
type: "plan"
status: "planned"
gap: "packed-cancellation"
areas: ["pickups"]
sources: ["src/pickups.py", "src/routes.py", "tests/test_pickups.py"]
updated: "2026-11-15"
---

# Plan: allow the owner to cancel a packed pickup

Implements [[gaps/packed-cancellation|the accepted gap]]. This is a plan only; nothing here has been implemented or run.

## Current behavior

`cancel_pickup` permits only `requested` ([[notes/cancellation-boundary|cancellation boundary]]), after the [[notes/ownership-check|owner check]], and the adapter reports a refusal as 409 ([[notes/route-responses|response mapping]]).

## Steps

1. In [tests/test_pickups.py](../../../tests/test_pickups.py), add a packed-pickup check through `cancel_request` expecting status 200 and state `cancelled`. Run it first and confirm it fails with the current 409.
2. In [src/pickups.py](../../../src/pickups.py), accept `requested` and `packed` and keep the owner check before any state change. Keep every other state rejected.
3. Add regression cases: a packed pickup with the wrong customer returns 403 and stays `packed`; a `picked_up` pickup returns 409 and stays `picked_up`. Keep the existing requested case.
4. Run `python3 -m unittest discover -s tests -v` from the fixture root. After the new behavior is verified, update the cancellation notes from the code and mark the gap `done` with the location of the change.

## Acceptance

- The owner can cancel `requested` and `packed` pickups: status 200, state `cancelled`.
- Another customer receives 403 and the state is unchanged.
- A `picked_up` pickup receives 409 and the state is unchanged.

All of these are proposed checks: **NOT RUN**.

## Out of scope

Partner cancellation (see [[gaps/partner-decision|its gap]], still undecided), persistence, HTTP integration, and the behavior of cancelling an already cancelled pickup.
