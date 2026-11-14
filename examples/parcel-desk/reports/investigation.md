# Why does a packed pickup return a conflict?

Worked example based on the fictional source; no deployed behavior observed.

The failure is explained by [cancel_pickup](../src/pickups.py): after checking the customer identity, it rejects every state other than `requested`. [cancel_request](../src/routes.py) maps that rejection to status 409. CAN-1 in [SPEC.md](../SPEC.md) allows `packed`, so the behavior disagrees with the current requirement.

## Alternatives checked

- Wrong customer: the ownership branch would produce `PermissionError` and status 403, a different path.
- Collected parcel: `picked_up` is intentionally rejected under CAN-3.
- Partner permissions: DEC-1 is undecided and the fixture has no partner flow.

## Smallest discriminating check

Create `Pickup("example", "customer-a", "packed")`, call `cancel_request` with `customer-a`, and compare its response and final state with CAN-1. Then repeat with a different customer and with `picked_up` to preserve the boundaries.

Checks executed in this worked report: **NOT RUN**. Source inspection supports the call-path explanation; an executed fixture check would confirm the predicted 409. Real authentication and persistence remain outside this in-memory example.
