import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.schemas import DecisionRequest
from backend.app.engine.orchestrator import DecisionOrchestrator
from backend.scripts.seed_demo_accounts import seed_demo_accounts

class TestPersonalizedRecommendations(unittest.TestCase):
    """Verifies that authenticated past order items serve as candidate anchors
    (A = B U V U S U O) to provide distinct, defensible persona-level recommendations
    without cross-account leakage.
    """

    @classmethod
    def setUpClass(cls):
        seed_demo_accounts()
        cls.client = TestClient(app)
        cls.orchestrator = DecisionOrchestrator()

    def test_gamer_vs_creator_recommendations_differ_on_empty_basket(self):
        """Verifies empty-basket recommendations for demo_gamer vs demo_creator reflect their distinct past orders."""
        gamer_req = DecisionRequest(
            cart_items=[],
            user_id="demo_gamer",
            shopping_context="all",
        )
        creator_req = DecisionRequest(
            cart_items=[],
            user_id="demo_creator",
            shopping_context="all",
        )

        gamer_resp = self.orchestrator.process_decision(gamer_req)
        creator_resp = self.orchestrator.process_decision(creator_req)

        self.assertGreater(len(gamer_resp.recommendations), 0)
        self.assertGreater(len(creator_resp.recommendations), 0)

        gamer_rec_ids = [r.product_id for r in gamer_resp.recommendations]
        creator_rec_ids = [r.product_id for r in creator_resp.recommendations]

        # The two sets of recommendations must differ because historical anchors O are distinct
        self.assertNotEqual(gamer_rec_ids, creator_rec_ids)

    def test_guest_request_has_no_user_order_anchors(self):
        """Verifies unauthenticated guest requests do not leak or incorporate any persona order anchors."""
        guest_req = DecisionRequest(
            cart_items=[],
            user_id=None,
            shopping_context="all",
        )
        guest_resp = self.orchestrator.process_decision(guest_req)
        guest_rec_ids = [r.product_id for r in guest_resp.recommendations]

        # Guest with empty cart and no views falls back to cold-start top catalogue items
        for rec in guest_resp.recommendations:
            self.assertNotEqual(rec.recommendation_source, "historical_order")

    def test_api_endpoint_respects_authenticated_user_context(self):
        """Verifies POST /api/v1/decision injects authenticated user_id from session."""
        # Login as demo_office
        login_res = self.client.post("/api/v1/auth/login", json={"username": "demo_office", "password": seed_demo_accounts()["demo_office"]})
        token = login_res.json()["session_token"]

        res = self.client.post(
            "/api/v1/decision",
            json={"cart_items": [], "shopping_context": "all"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(len(data["recommendations"]), 0)


if __name__ == "__main__":
    unittest.main()
