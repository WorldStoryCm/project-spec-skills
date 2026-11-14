"""Fictional pickup service used to demonstrate source/spec reconciliation."""
from dataclasses import dataclass


@dataclass
class Pickup:
    id: str
    customer_id: str
    state: str = "requested"


def cancel_pickup(pickup: Pickup, customer_id: str) -> Pickup:
    """Cancel a customer's own requested pickup."""
    if pickup.customer_id != customer_id:
        raise PermissionError("Pickup belongs to another customer")
    if pickup.state != "requested":
        raise ValueError("Only requested pickups can be cancelled")
    pickup.state = "cancelled"
    return pickup
