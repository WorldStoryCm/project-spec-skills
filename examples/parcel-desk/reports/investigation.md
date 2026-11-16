# Investigation: why does a packed pickup return a conflict?

A worked example of the investigation report shape in the `project-knowledge` skill, based on the fictional source. No deployed behavior was observed. Used on a gap, the same findings would go into the gap's `Recheck` section; see [packed-cancellation](../knowledge/parcel-desk/gaps/packed-cancellation.md).

## Answer

The owner's request reaches the state guard in [cancel_pickup](../src/pickups.py), which rejects every state other than `requested`. [cancel_request](../src/routes.py) maps that rejection to status 409. CAN-1 in [SPEC.md](../SPEC.md) allows `packed`, so the behavior disagrees with the requirement. This holds for the in-process fixture; a deployed service was not examined.

## Evidence chain

1. `cancel_request(pickup, customer)` calls `cancel_pickup`.
2. `cancel_pickup` checks the owner first, then `pickup.state != "requested"` raises `ValueError`.
3. `cancel_request` catches `ValueError` and returns `{"status": 409, "error": "cancellation_conflict"}`.

## Alternatives

- Wrong customer: would raise `PermissionError` and return 403, a different path.
- Collected parcel: `picked_up` is rejected on purpose under CAN-3.
- Partner permissions: DEC-1 is undecided and the fixture has no partner flow.

## Checks

Run in the example's gap recheck (2026-11-15): `cancel_request(Pickup("example", "customer-a", "packed"), "customer-a")` returned `{'status': 409, 'error': 'cancellation_conflict'}` with the state unchanged; the same call with `customer-b` returned 403. Not run in this report: the repeat with `picked_up`.

## Next

Repeat the call with a `picked_up` pickup to confirm the CAN-3 boundary is unaffected by any change. Whether `packed` should be cancellable is a product decision, already made in the vault by a person (the gap is accepted).
