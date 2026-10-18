import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.scripts.seed_demo_accounts import seed_demo_accounts
from backend.app.db.repository import CatalogRepository

class TestAccountOrderHistory(unittest.TestCase):
    """Verifies Milestone 6B itemized past order history, cross-account access isolation,
    and simulated checkout order persistence.
    """

    @classmethod
    def setUpClass(cls):
        cls.credentials_map = seed_demo_accounts()
        cls.tokens = {}
        for username, password in cls.credentials_map.items():
            client = TestClient(app)
            res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
            cls.tokens[username] = res.json()["session_token"]

    def test_unauthenticated_request_to_orders_returns_401(self):
        """Verifies GET /api/v1/orders rejects unauthenticated requests."""
        client = TestClient(app)
        res = client.get("/api/v1/orders")
        self.assertEqual(res.status_code, 401)

    def test_all_five_personas_have_three_itemized_orders(self):
        """Verifies all 5 demo personas have exactly 3 itemized synthetic orders."""
        customer_personas = {"demo_gamer", "demo_student", "demo_creator", "demo_traveler", "demo_office"}
        for username in customer_personas:
            token = self.tokens[username]
            client = TestClient(app)
            res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(res.status_code, 200, f"Failed fetching orders for {username}")
            orders = res.json()
            self.assertGreaterEqual(len(orders), 3, f"Expected at least 3 orders for {username}")

            for order in orders:
                self.assertTrue(order["id"])
                self.assertEqual(order["status"], "completed_simulated")
                self.assertEqual(order["currency"], "USD")
                self.assertGreater(order["total_amount"], 0)
                self.assertGreater(len(order["items"]), 0)
                for item in order["items"]:
                    self.assertTrue(item["product_id"])
                    self.assertTrue(item["name"])
                    self.assertGreater(item["quantity"], 0)
                    self.assertGreater(item["reference_price"], 0)
                    self.assertGreater(item["simulated_price"], 0)
                    self.assertGreater(item["line_total"], 0)

    def test_cross_account_order_isolation_returns_404(self):
        """Verifies User A cannot access User B's order by ID (HTTP 404)."""
        gamer_token = self.tokens["demo_gamer"]
        creator_token = self.tokens["demo_creator"]

        # Fetch creator's orders
        creator_client = TestClient(app)
        creator_orders = creator_client.get("/api/v1/orders", headers={"Authorization": f"Bearer {creator_token}"}).json()
        creator_order_id = creator_orders[0]["id"]

        # Attempt to access creator's order as demo_gamer
        gamer_client = TestClient(app)
        res = gamer_client.get(f"/api/v1/orders/{creator_order_id}", headers={"Authorization": f"Bearer {gamer_token}"})
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"], "Order not found")

    def test_simulated_checkout_persistence_records_order(self):
        """Verifies authenticated POST /api/v1/orders records an order under the user's account."""
        traveler_token = self.tokens["demo_traveler"]
        client = TestClient(app)

        # Baseline count
        initial_orders = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {traveler_token}"}).json()
        initial_count = len(initial_orders)

        # Create a new simulated checkout
        checkout_payload = {
            "items": [
                {"product_id": "item-021", "quantity": 1},  # 65W Power Bank
                {"product_id": "item-023", "quantity": 2},  # 100W GaN Wall Charger
            ],
            "applied_discounts": {"item-023": 0.10},
        }

        res = client.post(
            "/api/v1/orders",
            json=checkout_payload,
            headers={"Authorization": f"Bearer {traveler_token}"},
        )
        self.assertEqual(res.status_code, 200)
        order = res.json()
        self.assertTrue(order["id"].startswith("ord_"))
        self.assertEqual(order["status"], "completed_simulated")
        self.assertEqual(order["provenance"], "simulated_checkout")
        self.assertEqual(len(order["items"]), 2)

        # Verify new order count in user's history
        refreshed_orders = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {traveler_token}"}).json()
        self.assertEqual(len(refreshed_orders), initial_count + 1)
        self.assertEqual(refreshed_orders[0]["id"], order["id"])


if __name__ == "__main__":
    unittest.main()
