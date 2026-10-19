"""Unit tests for FairCart Decision Twin — Shopper Intent Engine (Slice 4)."""

import unittest

from backend.app.engine.intent import (
    INTENT_STATES,
    ShopperIntentEngine,
    compute_recency_weight,
    compute_transition_entropy,
    get_laplace_smoothed_transitions,
)


class TestShopperIntent(unittest.TestCase):
    """Test suite covering recency decay, transition matrix smoothing, state inference, and intent scoring."""

    def setUp(self):
        self.engine = ShopperIntentEngine(gamma=0.001)

    def test_recency_decay(self):
        w_0 = compute_recency_weight(0.0)
        w_60 = compute_recency_weight(60.0)
        w_300 = compute_recency_weight(300.0)
        w_600 = compute_recency_weight(600.0)

        self.assertEqual(w_0, 1.0)
        self.assertLess(w_60, w_0)
        self.assertLess(w_300, w_60)
        self.assertLess(w_600, w_300)
        self.assertGreater(w_600, 0.0)

    def test_laplace_smoothed_transitions(self):
        matrix = get_laplace_smoothed_transitions(alpha=1.0)
        for from_state in INTENT_STATES:
            self.assertIn(from_state, matrix)
            row = matrix[from_state]
            # Every transition probability must be > 0 (Laplace smoothing guarantee)
            for to_state in INTENT_STATES:
                self.assertGreater(row[to_state], 0.0)
            row_sum = sum(row.values())
            self.assertAlmostEqual(row_sum, 1.0, places=2)

    def test_infer_discovery_state(self):
        # Empty cart, single search query, low dwell
        state = self.engine.infer_intent_state(
            session_id="sess-disc",
            cart_items=[],
            viewed_product_ids=[],
            dwell_time_seconds=10,
            search_query="gadgets",
        )
        self.assertEqual(state.current_state, "DISCOVERY")
        self.assertLess(state.intent_score, 0.35)
        self.assertGreater(state.price_sensitivity_estimate, 1.0)

    def test_infer_product_comparison_state(self):
        # Multiple items viewed without adding to cart
        state = self.engine.infer_intent_state(
            session_id="sess-comp",
            cart_items=[],
            viewed_product_ids=["item-001", "item-003", "item-005", "item-007"],
            dwell_time_seconds=60,
        )
        self.assertEqual(state.current_state, "PRODUCT_COMPARISON")
        self.assertGreaterEqual(state.price_sensitivity_estimate, 1.2)

    def test_infer_cart_completion_state(self):
        # Active cart with multiple items
        state = self.engine.infer_intent_state(
            session_id="sess-cart",
            cart_items=[{"product_id": "item-001", "quantity": 1}, {"product_id": "item-002", "quantity": 2}],
            viewed_product_ids=["item-001", "item-002"],
            dwell_time_seconds=120,
        )
        self.assertEqual(state.current_state, "CART_COMPLETION")
        self.assertGreaterEqual(state.intent_score, 0.60)
        # Cart completion shoppers are less price sensitive (high commitment)
        self.assertLess(state.price_sensitivity_estimate, 1.0)

    def test_infer_replenishment_state(self):
        # Returning shopper with historical orders
        state = self.engine.infer_intent_state(
            session_id="sess-rep",
            cart_items=[],
            viewed_product_ids=["item-002"],
            historical_order_ids=["ord-101", "ord-102", "ord-103"],
            dwell_time_seconds=40,
        )
        self.assertEqual(state.current_state, "REPLENISHMENT")
        self.assertGreater(state.intent_score, 0.40)

    def test_transition_entropy(self):
        # Uniform distribution should have higher entropy than deterministic
        uniform = {s: 0.20 for s in INTENT_STATES}
        peaked = {INTENT_STATES[0]: 0.96, INTENT_STATES[1]: 0.01, INTENT_STATES[2]: 0.01, INTENT_STATES[3]: 0.01, INTENT_STATES[4]: 0.01}
        self.assertGreater(compute_transition_entropy(uniform), compute_transition_entropy(peaked))


if __name__ == "__main__":
    unittest.main()
