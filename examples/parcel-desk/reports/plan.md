# Allow packed pickups to be cancelled — worked plan

Requested outcome: fulfill CAN-1 by allowing the owning customer to cancel a `packed` pickup before collection. This is a plan, not an applied change. See [the audit](audit.md) and [the investigation](investigation.md).

## Scope and sequence

1. In [tests/test_pickups.py](../tests/test_pickups.py), add a packed-pickup acceptance check through `cancel_request`: status 200 and state `cancelled`. Demonstrate the current failure first.
2. In [src/pickups.py](../src/pickups.py), allow both accepted pre-collection states. Keep the ownership check before the state mutation. Keep collected and unknown states denied.
3. Expand the regression cases: packed plus wrong customer returns 403 and leaves the state unchanged; `picked_up` returns 409 and remains unchanged. Retain the requested-state case.
4. Run `python3 -m unittest discover -s tests -v` from the fixture root. Update the canonical cancellation note and reconcile the confirmed gap after the new behavior is verified.

## Decisions and exclusions

DEC-1 partner cancellation remains undecided and blocks only that future feature. No partner roles, database migrations or HTTP integration are part of this change. Repeated cancellation of an already cancelled pickup keeps its current rejection unless a separate requirement changes it.

## Acceptance

Both `requested` and `packed` succeed for their owner. Wrong-customer requests and collected pickups remain denied without mutation. The listed tests are proposed checks: their result in this plan is **NOT RUN**.
