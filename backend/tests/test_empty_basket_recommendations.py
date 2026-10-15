"""Unit and integration tests for Milestone 4C: Empty-Basket Recommendations,
Historical Personalization & Cold-Start Intelligence.

Tests cover:
1. Empty basket with recent viewed items (Case A)
2. Empty basket with saved cart (Case B1)
3. Empty basket with historical orders (Case B2)
4. Empty basket with shopping context / intent alignment (Case C)
5. Empty basket cold-start fallback (Case D)
6. Dynamic view shifts
7. Context shifts
8. Bounded repetition guard
9. Commercial vs historical cart separation (zero unearned bundle discounts)
10. History reset graceful fallback
11. Finite ML features with empty basket
12. Honest copy and provenance integrity
13. Engine B reference pricing protection under high discount caps
14. Cart mutation transition from cold-start to active bundle offers
15. MMR diversity on empty-basket recommendations
"""

import math
import unittest

from backend.app.db.repository import CatalogRepository
from backend.app.engine.optimizer import EconomicOptimizer
from backend.app.engine.recommender import RecommenderEngine, RecommendationAnchor
from backend.app.engine.orchestrator import DecisionOrchestrator
from backend.app.models.schemas import CartItemInput, DecisionRequest


class TestEmptyBasketRecommendations(unittest.TestCase):
    """Test suite validating empty-basket intelligence and cold-start fallback."""

    def setUp(self):
        self.repo = CatalogRepository()
        self.recommender = RecommenderEngine()
        self.optimizer = EconomicOptimizer()
        self.orchestrator = DecisionOrchestrator(
            repository=self.repo,
            recommender=self.recommender,
            optimizer=self.optimizer,
        )

    # 1. Empty basket with viewed items (Case A)
    def test_case_a_recent_views_anchors(self):
        """Shopper with empty cart but viewed items receives complementary recommendations."""
        req = DecisionRequest(
            session_id="test-empty-views",
            cart_items=[],
            viewed_product_ids=["item-001"],  # Mechanical Keyboard
            shopping_context="general",
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        self.assertGreater(len(response.recommendations), 0)
        
        # Recommendations should include accessories relevant to keyboard
        rec_ids = [r.product_id for r in response.recommendations]
        self.assertNotIn("item-001", rec_ids, "Viewed item itself should not be recommended")
        
        # First recommendation provenance
        top_rec = response.recommendation
        self.assertIsNotNone(top_rec)
        self.assertIn(top_rec.recommendation_source, ["product_view", "association_rule", "product_views"])
        self.assertIn("viewed", top_rec.provenance_label.lower())

    # 2. Empty basket with saved cart (Case B1)
    def test_case_b1_saved_cart_anchors(self):
        """Shopper with saved cart receives complements with saved-cart provenance."""
        req = DecisionRequest(
            session_id="test-empty-saved",
            cart_items=[],
            saved_cart_product_ids=["item-002"],  # Ergonomic Wireless Mouse
            shopping_context="general",
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        self.assertGreater(len(response.recommendations), 0)
        
        top_rec = response.recommendation
        self.assertIsNotNone(top_rec)
        self.assertIn("saved cart", top_rec.provenance_label.lower())
        self.assertIn(top_rec.recommendation_source, ["saved_cart", "association_rule"])

    # 3. Empty basket with historical order (Case B2)
    def test_case_b2_historical_order_anchors(self):
        """Shopper with past order history receives complementary accessories."""
        req = DecisionRequest(
            session_id="test-empty-order",
            cart_items=[],
            historical_order_product_ids=["item-001"],
            shopping_context="general",
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        self.assertGreater(len(response.recommendations), 0)
        
        top_rec = response.recommendation
        self.assertIsNotNone(top_rec)
        self.assertIn("previous faircart order", top_rec.provenance_label.lower())
        self.assertIn(top_rec.recommendation_source, ["historical_order", "association_rule"])

    # 4. Empty basket with shopping context / intent alignment (Case C)
    def test_case_c_shopping_context_intent_alignment(self):
        """Shopper with selected context but empty cart receives intent-aligned candidates."""
        req = DecisionRequest(
            session_id="test-empty-gaming",
            cart_items=[],
            shopping_context="gaming",
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        self.assertGreater(len(response.recommendations), 0)
        
        top_rec = response.recommendation
        self.assertIsNotNone(top_rec)
        self.assertIn("gaming", top_rec.provenance_label.lower())
        # Top rec must have gaming in its use cases
        self.assertIn("gaming", [u.lower() for u in top_rec.use_cases])

    # 5. Empty basket cold-start fallback (Case D)
    def test_case_d_cold_start_popularity_and_connectivity(self):
        """Shopper with zero history and general context receives deterministic popular picks."""
        req = DecisionRequest(
            session_id="test-empty-cold-start",
            cart_items=[],
            viewed_product_ids=[],
            saved_cart_product_ids=[],
            historical_order_product_ids=[],
            shopping_context="general",
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        self.assertEqual(len(response.recommendations), 4)
        
        for rec in response.recommendations:
            self.assertEqual(rec.recommendation_source, "catalog_popular")
            self.assertEqual(rec.provenance_label, "Popular picks from our catalogue")
            self.assertFalse(rec.is_offered)
            self.assertEqual(rec.savings, 0.0)
            self.assertEqual(rec.final_price, rec.reference_price)

    # 6. Dynamic view shifts
    def test_dynamic_view_shifts_recommendations(self):
        """Viewing different products dynamically shifts recommendation candidates."""
        # View keyboard (item-001)
        req_kb = DecisionRequest(
            session_id="test-shift-1",
            cart_items=[],
            viewed_product_ids=["item-001"],
            shopping_context="general",
        )
        res_kb = self.orchestrator.process_decision(req_kb)
        kb_recs = [r.product_id for r in res_kb.recommendations]

        # View microphone / audio (item-005)
        req_audio = DecisionRequest(
            session_id="test-shift-2",
            cart_items=[],
            viewed_product_ids=["item-005"],
            shopping_context="general",
        )
        res_audio = self.orchestrator.process_decision(req_audio)
        audio_recs = [r.product_id for r in res_audio.recommendations]

        # Recommendations should differ based on the anchor
        self.assertNotEqual(kb_recs, audio_recs)

    # 7. Context shifts
    def test_context_shifts_recommendations(self):
        """Changing shopping context shifts candidate ranking and scores."""
        req_gaming = DecisionRequest(
            session_id="test-ctx-gaming",
            cart_items=[],
            shopping_context="gaming",
        )
        res_gaming = self.orchestrator.process_decision(req_gaming)

        req_wellness = DecisionRequest(
            session_id="test-ctx-wellness",
            cart_items=[],
            shopping_context="wellness",
        )
        res_wellness = self.orchestrator.process_decision(req_wellness)

        gaming_pids = [r.product_id for r in res_gaming.recommendations]
        wellness_pids = [r.product_id for r in res_wellness.recommendations]
        self.assertNotEqual(gaming_pids, wellness_pids)

    # 8. Bounded repetition guard
    def test_bounded_repetition_guard(self):
        """Repeated product views are bounded logarithmically and never cause scores > 1.0."""
        catalog = self.repo.get_all_entities()
        anchors_single = [
            RecommendationAnchor(
                product_id="item-001",
                source="product_view",
                weight=0.6,
                age_hours=0.1,
                view_count=1,
            )
        ]
        anchors_repeated = [
            RecommendationAnchor(
                product_id="item-001",
                source="product_view",
                weight=0.6,
                age_hours=0.1,
                view_count=50,
            )
        ]

        # Calculate scores
        for cand in catalog:
            if cand.id == "item-001":
                continue
            score_single, _ = self.recommender.calculate_anchor_complementarity_score(cand, anchors_single, catalog=catalog)
            score_repeated, _ = self.recommender.calculate_anchor_complementarity_score(cand, anchors_repeated, catalog=catalog)
            
            # Repetition guard caps at 1.5 multiplier
            self.assertLessEqual(score_repeated, 1.0, "Score must never exceed 1.0")
            if score_single > 0:
                ratio = score_repeated / score_single
                self.assertLessEqual(ratio, 1.50001, "Repetition multiplier must not exceed 1.5")

    # 9. Commercial vs historical cart separation (zero unearned bundle discounts)
    def test_cart_separation_no_unearned_bundle_discount(self):
        """Historical or viewed anchors must NEVER trigger active bundle discounts."""
        req = DecisionRequest(
            session_id="test-separation",
            cart_items=[],  # Active cart is empty
            viewed_product_ids=["item-001", "item-002"],
            saved_cart_product_ids=["item-003"],
            historical_order_product_ids=["item-004"],
            margin_floor=0.10,
            discount_cap=0.30,
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        for rec in response.recommendations:
            self.assertFalse(rec.is_offered, f"Empty cart must not offer discount on {rec.product_id}")
            self.assertEqual(rec.tier, "NONE")
            self.assertEqual(rec.discount_percentage, 0.0)
            self.assertEqual(rec.savings, 0.0)
            self.assertEqual(rec.final_price, rec.reference_price)
            self.assertIn("Standard price", rec.conditions)

    # 10. History reset graceful fallback
    def test_session_history_reset_clears_anchors(self):
        """When history is reset/empty, engine gracefully falls back to cold-start."""
        req = DecisionRequest(
            session_id="test-reset-session",
            cart_items=[],
            viewed_product_ids=[],
            saved_cart_product_ids=[],
            historical_order_product_ids=[],
            shopping_context="all",
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.decision, "NO_OFFER")
        self.assertGreater(len(response.recommendations), 0)
        self.assertEqual(response.recommendation.recommendation_source, "catalog_popular")

    # 11. Finite ML features with empty basket
    def test_finite_ml_features_empty_basket(self):
        """Empty basket produces finite features without NaN or Inf."""
        catalog = self.repo.get_all_entities()
        recs = self.recommender.find_recommendations(
            cart_items=[],
            catalog=catalog,
            shopping_context="productivity",
            session_viewed_ids=["item-001"],
            session_events=[],
            anchors=[RecommendationAnchor("item-001", "product_view", 0.6, 0.1, 1)],
            top_k=4,
        )
        self.assertEqual(len(recs), 4)
        for cand in recs:
            self.assertTrue(math.isfinite(cand.affinity_score))
            self.assertGreaterEqual(cand.affinity_score, 0.0)
            self.assertLessEqual(cand.affinity_score, 1.0)

    # 12. Honest copy and provenance integrity
    def test_honest_provenance_labels(self):
        """Cold-start copy states catalogue popularity without false personalization."""
        req = DecisionRequest(
            session_id="test-honest-copy",
            cart_items=[],
            shopping_context="general",
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(response.recommendation.provenance_label, "Popular picks from our catalogue")
        self.assertIn("popular workspace essentials", response.deterministic_explanation.lower())

    # 13. Engine B reference pricing protection under high discount caps
    def test_engine_b_zero_discount_protection_even_with_high_cap(self):
        """High discount cap (e.g. 50%) cannot override empty cart safety."""
        req = DecisionRequest(
            session_id="test-empty-high-cap",
            cart_items=[],
            discount_cap=0.50,
            margin_floor=0.01,
        )
        response = self.orchestrator.process_decision(req)
        for rec in response.recommendations:
            self.assertFalse(rec.is_offered)
            self.assertEqual(rec.savings, 0.0)
            self.assertEqual(rec.final_price, rec.reference_price)

    # 14. Cart mutation transition from cold-start to active bundle offers
    def test_cart_mutation_transitions_from_cold_start_to_active_bundle(self):
        """Adding an item to the basket transitions from NO_OFFER cold-start to bundle evaluation."""
        # Step 1: Empty cart
        req_empty = DecisionRequest(
            session_id="test-mutation-sess",
            cart_items=[],
            margin_floor=0.15,
            discount_cap=0.20,
        )
        res_empty = self.orchestrator.process_decision(req_empty)
        self.assertEqual(res_empty.decision, "NO_OFFER")
        self.assertFalse(res_empty.recommendation.is_offered)

        # Step 2: Add keyboard to cart
        req_active = DecisionRequest(
            session_id="test-mutation-sess",
            cart_items=[CartItemInput(product_id="item-001", quantity=1)],
            margin_floor=0.15,
            discount_cap=0.20,
        )
        res_active = self.orchestrator.process_decision(req_active)
        # Should now evaluate bundle offers with active cart
        self.assertIsNotNone(res_active.cart_quote)
        self.assertEqual(res_active.cart_quote.standard_subtotal, 80.0)
        # If margins allow, an offer may be applied
        if res_active.decision == "OFFER_APPLIED":
            self.assertTrue(res_active.recommendation.is_offered)
            self.assertGreater(res_active.recommendation.savings, 0.0)

    # 15. MMR diversity on empty-basket recommendations
    def test_mmr_diversity_on_empty_basket(self):
        """Top-k empty-basket recommendations exhibit category/subcategory diversity."""
        req = DecisionRequest(
            session_id="test-empty-diversity",
            cart_items=[],
            shopping_context="general",
        )
        response = self.orchestrator.process_decision(req)
        self.assertEqual(len(response.recommendations), 4)
        
        # Check that recommendations are not all the exact same subcategory
        subcategories = {r.subcategory for r in response.recommendations}
        self.assertGreater(len(subcategories), 1, "MMR reranking must ensure diverse subcategories")


if __name__ == "__main__":
    unittest.main()
