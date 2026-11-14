"""Tests for the fictional current implementation, with intentional coverage gaps."""
import unittest
from src.pickups import Pickup
from src.routes import cancel_request


class PickupTests(unittest.TestCase):
    def test_requested_pickup_can_be_cancelled(self):
        p = Pickup("example-1", "customer-a")
        self.assertEqual(cancel_request(p, "customer-a"),
                         {"status": 200, "state": "cancelled"})

    def test_other_customer_cannot_cancel(self):
        p = Pickup("example-2", "customer-a")
        self.assertEqual(cancel_request(p, "customer-b")["status"], 403)
        self.assertEqual(p.state, "requested")

    def test_collected_pickup_cannot_be_cancelled(self):
        p = Pickup("example-3", "customer-a", "picked_up")
        self.assertEqual(cancel_request(p, "customer-a")["status"], 409)
        self.assertEqual(p.state, "picked_up")


if __name__ == "__main__":
    unittest.main()
