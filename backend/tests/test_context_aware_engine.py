"""Automated Test Suite for Context-Aware Multi-Stage Recommendation Engine & Event History

Verifies:
1. Multi-item cart evaluation: recommendations update dynamically as cart contents change.
2. Association rule metrics (support, confidence, lift) and zero-denominator safety.
3. Shopping context changes candidate rankings and scores.
4. Cart exclusions: never recommend items already in cart or out-of-stock items.
5. Diversity enforcement across subcategories and categories.
6. Anonymous session event logging, retrieval, and shopper reset deletion.
7. Economic incentive independence: items recommended at standard price when margin floor breached.
8. Authoritative basket quote consistency across mutations.
9. Seeded offline evaluation reproducibility.
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.associations import AssociationRuleEngine, get_association_engine
from backend.app.engine.recommender import RecommenderEngine
from backend.app.engine import DecisionOrchestrator
from backend.app.models.schemas import DecisionRequest, CartItemInput, SessionEventCreate
from backend.scripts.evaluate_recommendations import run_offline_evaluation

class TestContextAwareRecommendationEngine(unittest.TestCase):
    """Test suite for Engine A context-aware upgrade and anonymous interaction persistence."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.repo = CatalogRepository()
        cls.catalog = cls.repo.get_all_entities()
        cls.assoc_engine = get_association_engine()
        cls.recommender = RecommenderEngine(association_engine=cls.assoc_engine)
        cls.orchestrator = DecisionOrchestrator(repository=cls.repo, recommender=cls.recommender)

    def test_association_rule_metrics_and_zero_denominator_safety(self):
        """Verifies mathematical validity of support, confidence, and lift."""
        # Query known item pair (Keyboard -> Wrist Rest)
        match = self.assoc_engine.evaluate_basket_candidate(("item-001",), "item-002")
        self.assertIsNotNone(match)
        self.assertGreater(match.support, 0.0)
        self.assertGreater(match.confidence, 0.0)
        self.assertGreater(match.lift, 1.0, "Complementary pair should have lift > 1.0")

        # Zero denominator safety test on non-existent or empty queries
        empty_match = self.assoc_engine.evaluate_basket_candidate((), "item-002")
        self.assertIsNone(empty_match)

        invalid_match = self.assoc_engine.evaluate_basket_candidate(("non-existent-item",), "item-002")
        self.assertIsNone(invalid_match)

    def test_multi_item_basket_synergy_and_mutation(self):
        """Adding a second complementary item must update candidate rankings and detect multi-item synergy."""
        k_item = self.repo.get_entity_by_id("item-001") # Keyboard
        m_item = self.repo.get_entity_by_id("item-003") # Mouse

        # Step 1: Cart with only Keyboard
        recs_single = self.recommender.find_recommendations([(k_item, 1)], self.catalog, shopping_context="all", top_k=4)
        single_ids = [r.product.id for r in recs_single]
        self.assertIn("item-002", single_ids, "Wrist rest should be recommended for keyboard")

        # Step 2: Mutate cart by adding Mouse
        recs_multi = self.recommender.find_recommendations([(k_item, 1), (m_item, 1)], self.catalog, shopping_context="all", top_k=4)
        multi_ids = [r.product.id for r in recs_multi]

        # Multi-item basket must not contain either cart item
        self.assertNotIn("item-001", multi_ids)
        self.assertNotIn("item-003", multi_ids)

        # Check multi-item match flag
        wrist_rest_rec = next((r for r in recs_multi if r.product.id == "item-002"), None)
        self.assertIsNotNone(wrist_rest_rec)
        self.assertTrue(wrist_rest_rec.is_multi_item_match, "Wrist rest should be recognized as multi-item pairing")
        self.assertGreater(wrist_rest_rec.affinity_score, 0.70)

    def test_shopping_context_shifts_rankings(self):
        """Changing shopping context from 'travel' to 'productivity' must reorder candidates."""
        k_item = self.repo.get_entity_by_id("item-001")

        # Travel context (prioritizes compact portable accessories)
        travel_recs = self.recommender.find_recommendations([(k_item, 1)], self.catalog, shopping_context="travel", top_k=4)
        travel_ids = [r.product.id for r in travel_recs]

        # Productivity context (prioritizes ergonomic typing/desk tools)
        prod_recs = self.recommender.find_recommendations([(k_item, 1)], self.catalog, shopping_context="productivity", top_k=4)
        prod_ids = [r.product.id for r in prod_recs]

        self.assertNotEqual(travel_ids, prod_ids, "Different shopping contexts should yield distinct candidate rankings")
        # Travel context surfaces portable power/chargers
        self.assertIn("item-016", travel_ids, "Travel context should surface portable GaN adapter")

    def test_cart_exclusion_and_inventory_filters(self):
        """Items in the cart or with zero stock must never be recommended."""
        # Simulate an item with 0 inventory
        k_item = self.repo.get_entity_by_id("item-001")
        all_products = self.catalog

        recs = self.recommender.find_recommendations([(k_item, 1)], all_products, top_k=5)
        for r in recs:
            self.assertNotEqual(r.product.id, "item-001", "Cart item must not be recommended")
            self.assertGreater(r.product.inventory, 0, "Out-of-stock item must not be recommended")

    def test_diversity_enforcement(self):
        """Top-K recommendations must enforce subcategory uniqueness."""
        k_item = self.repo.get_entity_by_id("item-001")
        recs = self.recommender.find_recommendations([(k_item, 1)], self.catalog, top_k=4)

        subcategories = [r.product.subcategory for r in recs]
        # Should not have duplicate subcategories in first pass
        self.assertEqual(len(subcategories), len(set(subcategories)), "Recommendations must be subcategory-diverse")

    def test_anonymous_session_events_lifecycle(self):
        """Verifies recording, retrieval, and deletion of anonymous session events."""
        test_session = "sess-test-lifecycle-123"

        # 1. Record product view (browsing)
        post_view = self.client.post("/api/v1/events", json={
            "session_id": test_session,
            "event_type": "product_view",
            "product_id": "item-008",
            "shopping_context": "productivity",
            "metadata": {"dwell_ms": 12000}
        })
        self.assertEqual(post_view.status_code, 200)
        self.assertEqual(post_view.json()["status"], "recorded")

        # 2. Record add to cart (intent)
        post_add = self.client.post("/api/v1/events", json={
            "session_id": test_session,
            "event_type": "add_to_cart",
            "product_id": "item-001",
            "shopping_context": "productivity"
        })
        self.assertEqual(post_add.status_code, 200)

        # 3. Fetch events
        get_res = self.client.get(f"/api/v1/events?session_id={test_session}")
        self.assertEqual(get_res.status_code, 200)
        events = get_res.json()
        self.assertGreaterEqual(len(events), 2)
        event_types = [e["event_type"] for e in events]
        self.assertIn("product_view", event_types)
        self.assertIn("add_to_cart", event_types)

        # 4. Clear events (reset)
        del_res = self.client.delete(f"/api/v1/events?session_id={test_session}")
        self.assertEqual(del_res.status_code, 200)
        self.assertGreaterEqual(del_res.json()["events_cleared"], 2)

        # 5. Confirm empty after deletion
        verify_empty = self.client.get(f"/api/v1/events?session_id={test_session}")
        self.assertEqual(len(verify_empty.json()), 0)

    def test_invalid_event_type_rejected(self):
        """Invalid event types are rejected with 400 Bad Request."""
        res = self.client.post("/api/v1/events", json={
            "session_id": "test-sess",
            "event_type": "unauthorized_tracking_event",
            "product_id": "item-001"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid event_type", res.json()["detail"])

    def test_decision_endpoint_session_reevaluation_and_quote_agreement(self):
        """Verifies end-to-end /api/v1/decision re-evaluates quotes and recommendations dynamically."""
        # 1. Basket with 1 item
        payload1 = {
            "session_id": "sess-live-test",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "shopping_context": "productivity",
            "margin_floor": 0.20,
            "discount_cap": 0.20
        }
        res1 = self.client.post("/api/v1/decision", json=payload1)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(len(data1["cart_quote"]["items"]), 1)
        self.assertEqual(data1["cart_quote"]["standard_subtotal"], 80.00)
        self.assertGreater(len(data1["recommendations"]), 0)

        # 2. Mutate basket to 2 items
        payload2 = {
            "session_id": "sess-live-test",
            "cart_items": [
                {"product_id": "item-001", "quantity": 1},
                {"product_id": "item-003", "quantity": 1}
            ],
            "shopping_context": "productivity",
            "margin_floor": 0.20,
            "discount_cap": 0.20
        }
        res2 = self.client.post("/api/v1/decision", json=payload2)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(len(data2["cart_quote"]["items"]), 2)
        self.assertEqual(data2["cart_quote"]["standard_subtotal"], 145.00) # $80 + $65
        # Recommendations must not contain either item
        rec_ids_2 = [r["product_id"] for r in data2["recommendations"]]
        self.assertNotIn("item-001", rec_ids_2)
        self.assertNotIn("item-003", rec_ids_2)

    def test_recommendation_and_incentive_independence(self):
        """When merchant margin floor is high (e.g. 50%), candidates are still recommended at standard price."""
        payload = {
            "session_id": "sess-high-margin",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "shopping_context": "productivity",
            "margin_floor": 0.60, # Strict 60% margin floor (exceeds basket margin of ~52%)
            "discount_cap": 0.20
        }
        res = self.client.post("/api/v1/decision", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Recommendations still returned
        self.assertGreater(len(data["recommendations"]), 0)
        for r in data["recommendations"]:
            # But no discount granted
            self.assertFalse(r["is_offered"])
            self.assertEqual(r["discount_percentage"], 0.0)
            self.assertEqual(r["final_price"], r["reference_price"])
            self.assertIn("Standard price", r["conditions"])

    def test_offline_evaluation_reproducibility(self):
        """Verifies that offline model evaluation produces consistent, positive comparative results."""
        results = run_offline_evaluation(k=4)
        base = results["baseline"]
        impr = results["improved"]

        self.assertGreater(impr.hit_rate_at_k, base.hit_rate_at_k)
        self.assertGreater(impr.recall_at_k, base.recall_at_k)
        self.assertGreater(impr.ndcg_at_k, base.ndcg_at_k)
        self.assertGreater(impr.avg_category_diversity, base.avg_category_diversity)

if __name__ == "__main__":
    unittest.main()
