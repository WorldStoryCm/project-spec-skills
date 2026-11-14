# Parcel Desk requirements

This is an invented service for skill examples. It is not a production application.

## Accepted cancellation requirements

- **CAN-1:** A customer can cancel their own pickup before collection, including when its state is `requested` or `packed`.
- **CAN-2:** A customer cannot cancel another customer's pickup.
- **CAN-3:** A `picked_up` pickup cannot be cancelled.

## Open decision

**DEC-1:** A delivery partner may eventually request cancellation on behalf of a customer. Its permissions, identity checks and allowed states have not been decided. Partner cancellation is outside the accepted scope.

## Boundary

The fixture models state transitions in memory. It has no network server, identity provider, database or provider integration. Passing its tests cannot establish any of those properties.
