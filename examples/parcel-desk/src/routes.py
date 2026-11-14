"""An in-process route adapter; no real HTTP server or authentication."""
from src.pickups import Pickup, cancel_pickup


def cancel_request(pickup: Pickup, authenticated_customer: str) -> dict:
    """The caller supplies an already-authenticated customer identity."""
    try:
        result = cancel_pickup(pickup, authenticated_customer)
    except PermissionError:
        return {"status": 403, "error": "forbidden"}
    except ValueError:
        return {"status": 409, "error": "cancellation_conflict"}
    return {"status": 200, "state": result.state}
