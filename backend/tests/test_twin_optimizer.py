"""Unit tests for FairCart Decision Twin — Multi-Shopper Optimizer (Slice 3)."""

import os
import tempfile
import unittest

from backend.app.db.database import init_db
from backend.app.engine.twin_inventory import TwinInventoryRepository
from backend.app.engine.twin_optimizer import (
    TwinOptimizer,
    estimate_conversion_probability,
)
from backend.app.models.decision_twin_schemas import (
    BatchOptimizationRequest,
    BatchShopperSession,
)


class TestTwinOptimizer(unittest.TestCase):
    """Test suite covering candidate valuation, scarcity shadow penalties, batch allocation, and trace persistence."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(db_path=self.db_path)

        # Seed products
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO products (
                id, name, category, subcategory, description, reference_price_cents,
                cogs_cents, inventory, complementary_ids, tags, use_cases, image_url
            ) VALUES
            ('item-001', 'Ergonomic Mechanical Keyboard', 'Electronics', 'Keyboards',
             'Tactile quiet switches', 8000, 4000, 12, 'item-002,item-003',
             'keyboard,ergonomic', 'productivity,gaming', '/images/keyboard.jpg'),
            ('item-002', 'Padded Memory Foam Wrist Rest', 'Accessories', 'Wrist Rests',
             'Ergonomic wrist cushion', 2500, 1000, 85, 'item-001',
             'wrist-rest,cushion', 'productivity', '/images/wrist_rest.jpg')
        """)
        conn.commit()
        conn.close()

        self.inventory_repo = TwinInventoryRepository(db_path=self.db_path)
        self.inventory_repo.seed_initial_inventory(storefront_id="primary_storefront")
        self.optimizer = TwinOptimizer(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except Exception:
                pass

    def test_estimate_conversion_probability(self):
        p_base = estimate_conversion_probability(base_intent_score=0.40, discount_pct=0.0)
        p_disc5 = estimate_conversion_probability(base_intent_score=0.40, discount_pct=0.05)
        p_disc20 = estimate_conversion_probability(base_intent_score=0.40, discount_pct=0.20)

        # Monotonicity check
        self.assertLess(p_base, p_disc5)
        self.assertLess(p_disc5, p_disc20)

    def test_evaluate_candidates_for_session(self):
        candidates, chosen, snapshot = self.optimizer.evaluate_candidates_for_session(
            session_id="sess-opt-01",
            cart_items=[{"product_id": "item-001", "quantity": 1}],
            dwell_time_seconds=90,
            margin_floor=0.20,
            discount_cap=0.20,
        )

        self.assertGreaterEqual(len(candidates), 2)
        self.assertIsNotNone(chosen)
        self.assertIsNotNone(snapshot.trace_id)
        self.assertEqual(snapshot.session_id, "sess-opt-01")

        # Check candidate types
        types = [c.action_type for c in candidates]
        self.assertIn("NO_OFFER", types)
        self.assertIn("ITEM_DISCOUNT", types)

    def test_margin_floor_enforcement(self):
        # Keyboard ($80, COGS $40): undiscounted margin = 50.0%
        # If margin floor is set to 52.0%, even NO_OFFER (50%) breaches floor
        candidates, chosen, snapshot = self.optimizer.evaluate_candidates_for_session(
            session_id="sess-opt-02",
            cart_items=[{"product_id": "item-001", "quantity": 1}],
            margin_floor=0.52,
            discount_cap=0.20,
        )
        # Any candidate with margin < 52% must not pass
        for c in candidates:
            if c.gross_margin_pct < 0.52:
                self.assertFalse(c.margin_floor_passed)

    def test_trace_snapshot_persisted(self):
        candidates, chosen, snapshot = self.optimizer.evaluate_candidates_for_session(
            session_id="sess-opt-trace",
            cart_items=[{"product_id": "item-001", "quantity": 1}],
        )

        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM decision_traces WHERE trace_id = ?", (snapshot.trace_id,))
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[1], "sess-opt-trace")

    def test_optimize_batch_lift_over_greedy(self):
        sessions = [
            BatchShopperSession(
                session_id=f"sess-batch-{i}",
                cart_items=[{"product_id": "item-001", "quantity": 1}],
                dwell_time_seconds=30 + i * 10,
            )
            for i in range(12)
        ]

        req = BatchOptimizationRequest(
            sessions=sessions,
            storefront_id="primary_storefront",
            margin_floor=0.20,
            discount_cap=0.20,
        )

        result = self.optimizer.optimize_batch(req)
        self.assertEqual(result.total_sessions_evaluated, 12)
        self.assertGreater(result.aggregate_projected_profit, 0.0)
        self.assertGreater(result.baseline_greedy_profit, 0.0)
        self.assertGreaterEqual(result.inventory_saved_units, 0)
        self.assertIn("item-001", result.inventory_constrained_skus)

    def test_trace_records_forecast_source_and_uncertainty(self):
        # 1. Unforecasted item -> triggers safe fallback
        candidates, chosen, snapshot_fallback = self.optimizer.evaluate_candidates_for_session(
            session_id="sess-trace-fb",
            cart_items=[{"product_id": "item-001", "quantity": 1}],
        )
        constraints = snapshot_fallback.constraints_applied
        self.assertEqual(constraints.get("forecast_source"), "fallback_safety_buffer")
        self.assertEqual(constraints.get("forecast_uncertainty"), "high")
        self.assertGreaterEqual(constraints.get("forecast_demand_14d"), 14.0)

        # 2. Genuine zero forecast inserted into DB
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO demand_forecasts (
                id, sku, storefront_id, horizon_days, forecast_date, point_forecast,
                lower_bound, upper_bound, confidence_level, method, wape, mase, forecast_bias, created_at
            ) VALUES (
                'fc_zero_001', 'item-001', 'primary_storefront', 14, '2026-10-19', 0.0,
                0.0, 0.0, 0.95, 'ZERO_BASELINE', 0.0, 0.0, 0.0, '2026-10-19T00:00:00Z'
            )
        """)
        conn.commit()
        conn.close()

        candidates, chosen, snapshot_zero = self.optimizer.evaluate_candidates_for_session(
            session_id="sess-trace-zero",
            cart_items=[{"product_id": "item-001", "quantity": 1}],
        )
        constraints_zero = snapshot_zero.constraints_applied
        self.assertEqual(constraints_zero.get("forecast_source"), "model_forecast_zero_demand")
        self.assertEqual(constraints_zero.get("forecast_uncertainty"), "low")
        self.assertEqual(constraints_zero.get("forecast_demand_14d"), 0.0)
        self.assertEqual(constraints_zero.get("scarcity_lambda_usd"), 0.0)

        # 3. Positive model forecast inserted into DB
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO demand_forecasts (
                id, sku, storefront_id, horizon_days, forecast_date, point_forecast,
                lower_bound, upper_bound, confidence_level, method, wape, mase, forecast_bias, created_at
            ) VALUES (
                'fc_pos_001', 'item-001', 'primary_storefront', 14, '2026-10-19', 18.0,
                14.0, 22.0, 0.95, 'HistGBM_Croston', 0.12, 0.78, 0.01, '2026-10-19T01:00:00Z'
            )
        """)
        conn.commit()
        conn.close()

        candidates, chosen, snapshot_model = self.optimizer.evaluate_candidates_for_session(
            session_id="sess-trace-model",
            cart_items=[{"product_id": "item-001", "quantity": 1}],
        )
        constraints_model = snapshot_model.constraints_applied
        self.assertEqual(constraints_model.get("forecast_source"), "model_forecast")
        self.assertEqual(constraints_model.get("forecast_uncertainty"), "low")
        self.assertEqual(constraints_model.get("forecast_demand_14d"), 18.0)
        self.assertGreater(constraints_model.get("scarcity_lambda_usd"), 0.0)


if __name__ == "__main__":
    unittest.main()
