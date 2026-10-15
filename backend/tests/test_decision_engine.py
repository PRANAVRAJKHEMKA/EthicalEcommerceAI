"""Unit and integration tests for FairCart AI Decision Engine (Engines A, B, and C).

Validates:
1. Engine A: Cart item exclusion, inventory availability, complementary affinity ranking.
2. Engine B: Strict margin floor enforcement, discount caps, price ceilings, zero-revenue safeguards.
3. Engine C: End-to-end orchestration, sub-25ms latency, independent recommendation and incentive handling.
4. HTTP API: POST /api/v1/decision schema compliance and error resilience.
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.optimizer import EconomicOptimizer
from backend.app.engine.recommender import RecommenderEngine
from backend.app.engine.orchestrator import DecisionOrchestrator
from backend.app.main import app
from backend.app.models.schemas import CartItemInput, DecisionRequest

class TestDecisionEngine(unittest.TestCase):
    """Test suite for Decision Engine A, B, and C."""

    def setUp(self):
        self.repo = CatalogRepository()
        self.recommender = RecommenderEngine()
        self.optimizer = EconomicOptimizer()
        self.orchestrator = DecisionOrchestrator(
            repository=self.repo,
            recommender=self.recommender,
            optimizer=self.optimizer,
        )
        self.client = TestClient(app)

    # =========================================================================
    # Engine A (RecommenderEngine) Tests
    # =========================================================================

    def test_recommender_never_recommends_item_already_in_cart(self):
        """Engine A must never recommend an item that is already in the shopper's cart."""
        catalog = self.repo.get_all_entities()
        # Put item "prod-001" (Ergonomic Keyboard) in cart
        item_001 = self.repo.get_entity_by_id("item-001")
        self.assertIsNotNone(item_001)

        rec = self.recommender.find_recommendation(
            cart_items=[(item_001, 1)],
            catalog=catalog,
        )
        self.assertIsNotNone(rec)
        self.assertNotEqual(rec.product.id, "item-001")

        # Now put all catalog items in cart; should return None
        all_in_cart = [(item, 1) for item in catalog]
        rec_empty = self.recommender.find_recommendation(
            cart_items=all_in_cart,
            catalog=catalog,
        )
        self.assertIsNone(rec_empty)

    def test_recommender_filters_out_of_stock_items(self):
        """Engine A must ignore out-of-stock items (inventory <= 0)."""
        parent = ProductEntity(
            id="parent-1",
            name="Main Unit",
            category="Keyboards",
            description="Main",
            reference_price_cents=10000,
            cogs_cents=5000,
            inventory=10,
            complementary_ids=("stock-0",),
            image_url="",
        )
        out_of_stock_candidate = ProductEntity(
            id="stock-0",
            name="Sold Out Companion",
            category="Accessories",
            description="Sold out",
            reference_price_cents=2000,
            cogs_cents=1000,
            inventory=0,  # Zero inventory
            complementary_ids=(),
            image_url="",
        )
        in_stock_candidate = ProductEntity(
            id="stock-1",
            name="Available Companion",
            category="Accessories",
            description="In stock",
            reference_price_cents=2500,
            cogs_cents=1200,
            inventory=5,
            complementary_ids=(),
            image_url="",
        )

        rec = self.recommender.find_recommendation(
            cart_items=[(parent, 1)],
            catalog=[parent, out_of_stock_candidate, in_stock_candidate],
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec.product.id, "stock-1")

    def test_recommender_prioritizes_explicit_complementary_link(self):
        """Engine A prioritizes products explicitly listed in complementary_ids."""
        # item-001 (Ergonomic Keyboard) has item-002 (Wrist Rest) in complementary_ids
        item_001 = self.repo.get_entity_by_id("item-001")
        catalog = self.repo.get_all_entities()

        rec = self.recommender.find_recommendation(
            cart_items=[(item_001, 1)],
            catalog=catalog,
        )
        self.assertIsNotNone(rec)
        self.assertIn("item-002", item_001.complementary_ids)
        self.assertEqual(rec.product.id, "item-002")
        self.assertGreaterEqual(rec.affinity_score, 0.50)

    # =========================================================================
    # Engine B (EconomicOptimizer) Tests
    # =========================================================================

    def test_optimizer_strictly_enforces_gross_margin_floor(self):
        """Engine B must never choose a discount where resulting basket gross margin < margin_floor."""
        # Low margin parent item
        parent = ProductEntity(
            id="low-margin-item",
            name="Low Margin Product",
            category="Keyboards",
            description="Tight margin",
            reference_price_cents=10000,  # $100
            cogs_cents=8000,              # $80 -> 20% margin
            inventory=10,
            complementary_ids=(),
            image_url="",
        )
        candidate = ProductEntity(
            id="candidate-1",
            name="Accessory",
            category="Accessories",
            description="Accessory",
            reference_price_cents=2000,   # $20
            cogs_cents=1600,              # $16 -> 20% margin
            inventory=10,
            complementary_ids=(),
            image_url="",
        )

        # Baseline margin is (120 - 96) / 120 = 20.0%
        # If margin_floor is set to 25%, any discount or even baseline fails floor!
        res_high_floor = self.optimizer.optimize(
            cart_items=[(parent, 1)],
            candidate=candidate,
            margin_floor=0.25,
            discount_cap=0.20,
        )
        self.assertFalse(res_high_floor.is_offered)
        self.assertEqual(res_high_floor.action_type, "NONE")
        self.assertEqual(res_high_floor.discount_percentage, 0.0)
        self.assertEqual(res_high_floor.final_price, 20.00)

        # If margin_floor is 18%, a 5% or 10% discount might still violate 18%:
        # Let's test with margin_floor = 0.20. With 5% off candidate ($19),
        # Revenue = 119, COGS = 96, Margin = 23/119 = 19.33% < 20% floor.
        # Thus optimizer MUST reject the discount.
        res_strict = self.optimizer.optimize(
            cart_items=[(parent, 1)],
            candidate=candidate,
            margin_floor=0.20,
            discount_cap=0.20,
        )
        self.assertFalse(res_strict.is_offered)
        self.assertGreaterEqual(res_strict.basket_gross_margin, 0.20)

    def test_optimizer_respects_discount_cap(self):
        """Engine B must never exceed the merchant's configured discount_cap."""
        # High-margin items where large discounts could otherwise be financially feasible
        parent = ProductEntity(
            id="high-margin-item",
            name="High Margin Cable",
            category="Power & Cables",
            description="High margin",
            reference_price_cents=5000,  # $50
            cogs_cents=500,              # $5 -> 90% margin
            inventory=20,
            complementary_ids=(),
            image_url="",
        )
        candidate = ProductEntity(
            id="high-margin-cand",
            name="Accessory",
            category="Accessories",
            description="Accessory",
            reference_price_cents=3000,  # $30
            cogs_cents=300,              # $3 -> 90% margin
            inventory=20,
            complementary_ids=(),
            image_url="",
        )

        res = self.optimizer.optimize(
            cart_items=[(parent, 1)],
            candidate=candidate,
            margin_floor=0.15,
            discount_cap=0.10,  # Cap at 10%
        )
        if res.is_offered:
            self.assertLessEqual(res.discount_percentage, 0.10)

    def test_optimizer_price_ceiling_and_non_negative_savings(self):
        """Engine B guarantees final_price <= reference_price and savings >= 0."""
        parent = self.repo.get_entity_by_id("item-001")
        candidate = self.repo.get_entity_by_id("item-002")

        res = self.optimizer.optimize(
            cart_items=[(parent, 1)],
            candidate=candidate,
            margin_floor=0.20,
            discount_cap=0.20,
        )
        self.assertLessEqual(res.final_price, res.reference_price)
        self.assertGreaterEqual(res.savings, 0.0)
        self.assertAlmostEqual(res.final_price + res.savings, res.reference_price, places=2)

    def test_optimizer_zero_revenue_safeguard(self):
        """Engine B returns safe NO_OFFER without crashing on zero or negative prices."""
        invalid_item = ProductEntity(
            id="zero-price",
            name="Zero",
            category="Accessories",
            description="Zero",
            reference_price_cents=0,
            cogs_cents=0,
            inventory=5,
            complementary_ids=(),
            image_url="",
        )
        res = self.optimizer.optimize(
            cart_items=[(invalid_item, 1)],
            candidate=invalid_item,
            margin_floor=0.20,
        )
        self.assertFalse(res.is_offered)
        self.assertEqual(res.basket_gross_margin, 0.0)
        self.assertEqual(res.action_type, "NONE")

    # =========================================================================
    # Engine C (DecisionOrchestrator) & API Tests
    # =========================================================================

    def test_orchestrator_sub_25ms_latency(self):
        """Engine C must execute the full decision pipeline in under 25ms locally."""
        req = DecisionRequest(
            session_id="test-perf-sess",
            cart_items=[CartItemInput(product_id="item-001", quantity=1)],
            margin_floor=0.20,
            discount_cap=0.20,
        )
        response = self.orchestrator.process_decision(req)
        self.assertLess(response.execution_latency_ms, 25.0)

    def test_orchestrator_empty_cart_returns_safe_no_offer(self):
        """Engine C returns safe empty-basket recommendations with NO_OFFER and zero discounts."""
        req = DecisionRequest(
            session_id="test-empty",
            cart_items=[],
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        self.assertIsNotNone(response.recommendation)
        self.assertGreater(len(response.recommendations), 0)
        self.assertFalse(response.recommendation.is_offered)
        self.assertEqual(response.recommendation.savings, 0.0)
        self.assertEqual(response.recommendation.final_price, response.recommendation.reference_price)
        self.assertIsNotNone(response.incentive)
        self.assertFalse(response.incentive.is_offered)
        self.assertEqual(response.incentive.savings, 0.0)
        self.assertIn("active cart is empty", response.decision_reason.lower())

    def test_independent_recommendation_and_incentive(self):
        """When Engine B returns NO_OFFER, Engine A's recommendation is still returned transparently."""
        # Use an artificially high margin floor (e.g. 95%) that no discount or item can satisfy
        req = DecisionRequest(
            session_id="test-high-margin",
            cart_items=[CartItemInput(product_id="item-001", quantity=1)],
            margin_floor=0.95,
            discount_cap=0.20,
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        self.assertIsNotNone(response.recommendation)
        self.assertIsNotNone(response.incentive)
        self.assertFalse(response.incentive.is_offered)
        self.assertEqual(response.incentive.savings, 0.0)
        self.assertEqual(response.incentive.final_price, response.incentive.reference_price)
        self.assertIn("Standard price", response.incentive.conditions)

    def test_api_endpoint_post_decision(self):
        """HTTP POST /api/v1/decision returns a verified 200 response with all required fields."""
        payload = {
            "session_id": "test-http-session",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "dwell_time_seconds": 30,
            "margin_floor": 0.20,
            "discount_cap": 0.20,
        }
        res = self.client.post("/api/v1/decision", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("request_id", data)
        self.assertIn("decision", data)
        self.assertIn(data["decision"], ["OFFER_APPLIED", "NO_OFFER"])
        self.assertIn("recommendation", data)
        self.assertIn("incentive", data)
        self.assertIn("basket_gross_margin", data)
        self.assertIn("execution_latency_ms", data)
        self.assertLess(data["execution_latency_ms"], 25.0)

    # =========================================================================
    # Milestone 3B Multi-Recommendation & Consistency Tests
    # =========================================================================

    def test_multi_recommendations_count_and_diversity(self):
        """Engine A & C return 3-5 ranked candidates with diverse functional categories."""
        req = DecisionRequest(
            session_id="test-multi-rec",
            cart_items=[CartItemInput(product_id="item-001", quantity=1)],
            shopping_context="productivity",
        )
        res = self.orchestrator.process_decision(req)
        self.assertGreaterEqual(len(res.recommendations), 3)
        self.assertLessEqual(len(res.recommendations), 5)

        # Ensure no candidate is item-001 (item in cart)
        cand_ids = [r.product_id for r in res.recommendations]
        self.assertNotIn("item-001", cand_ids)

        # Ensure diversity: at least 2 distinct categories among top candidates
        categories = {r.category for r in res.recommendations}
        self.assertGreaterEqual(len(categories), 2)

    def test_context_aware_shopping_intent_ranking(self):
        """Shopping context (e.g. gaming, travel) shifts candidate ranking appropriately."""
        catalog = self.repo.get_all_entities()
        cart = [(self.repo.get_entity_by_id("item-001"), 1)]

        # Context: Gaming
        gaming_recs = self.recommender.find_recommendations(
            cart_items=cart,
            catalog=catalog,
            shopping_context="gaming",
            top_k=4,
        )
        gaming_ids = [r.product.id for r in gaming_recs]
        # Gaming mouse or desk mat should appear in recommendations
        has_gaming_support = any("gaming" in r.product.use_cases for r in gaming_recs)
        self.assertTrue(has_gaming_support)

        # Context: Travel
        travel_recs = self.recommender.find_recommendations(
            cart_items=cart,
            catalog=catalog,
            shopping_context="travel",
            top_k=4,
        )
        has_travel_support = any("travel" in r.product.use_cases for r in travel_recs)
        self.assertTrue(has_travel_support)

    def test_independent_candidate_incentives(self):
        """Each candidate's discount eligibility is evaluated independently by Engine B."""
        req = DecisionRequest(
            session_id="test-indep-incentives",
            cart_items=[CartItemInput(product_id="item-001", quantity=1)],
            margin_floor=0.20,
            discount_cap=0.20,
        )
        res = self.orchestrator.process_decision(req)
        self.assertGreaterEqual(len(res.recommendations), 3)

        # Each recommendation must have authoritative pricing fields
        for rec in res.recommendations:
            self.assertGreater(rec.reference_price, 0.0)
            self.assertGreater(rec.final_price, 0.0)
            self.assertLessEqual(rec.final_price, rec.reference_price)
            self.assertGreaterEqual(rec.savings, 0.0)
            if rec.is_offered:
                self.assertGreater(rec.savings, 0.0)
                self.assertIn("Valid when bundled with", rec.conditions)
            else:
                self.assertEqual(rec.savings, 0.0)
                self.assertEqual(rec.final_price, rec.reference_price)
                self.assertIn("Standard price", rec.conditions)

    def test_authoritative_basket_quote_endpoint(self):
        """POST /api/v1/quote computes exact integer-cent line totals, subtotal, and savings."""
        payload = {
            "cart_items": [
                {"product_id": "item-001", "quantity": 1},
                {"product_id": "item-002", "quantity": 1},
            ],
            "applied_discounts": {
                "item-002": 0.20  # 20% bundle discount on $25.00 -> $5.00 off
            }
        }
        res = self.client.post("/api/v1/quote", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Item 1: $80.00; Item 2: $25.00 - $5.00 = $20.00
        # Standard: $105.00, Final: $100.00, Savings: $5.00
        self.assertEqual(data["standard_subtotal"], 105.00)
        self.assertEqual(data["final_subtotal"], 100.00)
        self.assertEqual(data["total_savings"], 5.00)
        self.assertGreater(data["basket_gross_margin"], 0.20)

    def test_consistent_eligible_offers_map(self):
        """Eligible offers map provides exact matching prices for the storefront cards."""
        req = DecisionRequest(
            session_id="test-consistency",
            cart_items=[CartItemInput(product_id="item-001", quantity=1)],
            margin_floor=0.20,
            discount_cap=0.20,
        )
        res = self.orchestrator.process_decision(req)
        
        # Any product in eligible_offers_by_product_id must match its corresponding recommendation
        for pid, offer in res.eligible_offers_by_product_id.items():
            matching_rec = next((r for r in res.recommendations if r.product_id == pid), None)
            self.assertIsNotNone(matching_rec)
            self.assertEqual(offer.final_price, matching_rec.final_price)
            self.assertEqual(offer.savings, matching_rec.savings)
            self.assertEqual(offer.conditions, matching_rec.conditions)

if __name__ == "__main__":
    unittest.main()
