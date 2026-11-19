# Plan: allow packed pickups to be cancelled

A worked example of the plan report shape in the `project-knowledge` skill's planning guide. It is a plan, not an applied change. In the vault the same plan lives at [plans/packed-cancellation.md](../knowledge/parcel-desk/plans/packed-cancellation.md) because the gap [packed-cancellation](../knowledge/parcel-desk/gaps/packed-cancellation.md) was accepted by a person; a skill asked to plan an undecided gap would stop and ask for that decision first. See also [the audit](audit.md) and [the investigation](investigation.md).

## Baseline and goal

Today `cancel_pickup` in [src/pickups.py](../src/pickups.py) permits only `requested`, after the owner check. Goal: fulfil CAN-1 in [SPEC.md](../SPEC.md) so the owning customer can cancel a `packed` pickup before collection.

## Scope

In: the state rule in the service, and tests. Out: partner cancellation (DEC-1, undecided), persistence, HTTP integration, and repeated cancellation of an already cancelled pickup, which keeps its current rejection.

## Ordered work

1. In [tests/test_pickups.py](../tests/test_pickups.py), add a packed-pickup check through `cancel_request` expecting 200 and `cancelled`; confirm it fails today.
2. In [src/pickups.py](../src/pickups.py), accept `requested` and `packed`, keeping the owner check before any state change and every other state rejected.
3. Add regressions: packed with the wrong customer gives 403 and stays `packed`; `picked_up` gives 409 and is unchanged. Keep the requested case.
4. Run `python3 -m unittest discover -s tests -v` from the fixture root; then update the spec notes from the code and mark the gap done.

## Acceptance

Both `requested` and `packed` succeed for their owner. Wrong-customer requests and collected pickups stay denied with no state change. All checks above are proposed: **NOT RUN**.

## Open decisions

DEC-1 blocks only the partner feature, not this plan.
