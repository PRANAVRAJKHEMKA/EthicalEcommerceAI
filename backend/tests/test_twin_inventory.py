"""Unit tests for FairCart Decision Twin — Inventory & ATP Engine (Slice 1 & 2)."""

import os
import tempfile
import unittest

from backend.app.db.database import init_db
from backend.app.engine.twin_inventory import (
    TwinInventoryRepository,
    calculate_atp,
    calculate_scarcity_lambda,
    determine_stock_status,
)


class TestTwinInventory(unittest.TestCase):
    """Test suite covering ATP formulas, scarcity shadow costs, inventory mutations, and alerts."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(db_path=self.db_path)

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

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except Exception:
                pass

    def test_calculate_atp(self):
        self.assertEqual(calculate_atp(on_hand=50, reserved=10), 40)
        self.assertEqual(calculate_atp(on_hand=5, reserved=10), 0)
        self.assertEqual(calculate_atp(on_hand=0, reserved=0), 0)

    def test_determine_stock_status(self):
        self.assertEqual(determine_stock_status(atp=0, safety_stock=10), "OUT_OF_STOCK")
        self.assertEqual(determine_stock_status(atp=4, safety_stock=10), "CRITICAL_STOCKOUT_RISK")
        self.assertEqual(determine_stock_status(atp=8, safety_stock=10), "LOW_STOCK")
        self.assertEqual(determine_stock_status(atp=25, safety_stock=10), "HEALTHY")
        self.assertEqual(determine_stock_status(atp=120, safety_stock=10, demand_forecast_14d=15.0), "OVERSTOCKED")

    def test_scarcity_lambda_abundant_stock(self):
        # Keyboard with ATP=50, safety_stock=10 -> abundant -> lambda must be 0.0
        scarcity = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=50,
            safety_stock=10,
            forecast_demand_14d=14.0,
        )
        self.assertEqual(scarcity, 0.0)

    def test_scarcity_lambda_constrained_stock(self):
        # Keyboard with ATP=5, safety_stock=10, unit margin=$40 -> scarce -> lambda > 0 and <= unit margin
        scarcity = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=5,
            safety_stock=10,
            forecast_demand_14d=14.0,
        )
        self.assertGreater(scarcity, 0.0)
        self.assertLessEqual(scarcity, 40.0)  # Strictly bounded by regular unit margin ($40)

    def test_scarcity_lambda_depleted_atp_and_negative_inventory(self):
        # ATP <= 0 -> stock depleted -> lambda equals full unit margin ($40)
        scarcity_zero = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=0,
            safety_stock=10,
            forecast_demand_14d=14.0,
        )
        self.assertEqual(scarcity_zero, 40.0)

        # Negative ATP (backordered) -> also bounded at full unit margin ($40)
        scarcity_neg = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=-5,
            safety_stock=10,
            forecast_demand_14d=14.0,
        )
        self.assertEqual(scarcity_neg, 40.0)

    def test_scarcity_lambda_zero_safety_stock(self):
        # Zero safety stock: threshold=max(forecast, clean_safety*1.5, 1.0)
        # If ATP=0 -> full penalty ($40.0)
        scarcity_atp0 = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=0,
            safety_stock=0,
            forecast_demand_14d=14.0,
        )
        self.assertEqual(scarcity_atp0, 40.0)

        # If ATP=5 and forecast=14.0 -> constrained (5 <= 14), demand outstrips supply -> lambda=40.0
        scarcity_atp5_demand14 = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=5,
            safety_stock=0,
            forecast_demand_14d=14.0,
        )
        self.assertEqual(scarcity_atp5_demand14, 40.0)

        # If ATP=5 and forecast=2.0 -> abundant (5 > 2.0) -> lambda=0.0
        scarcity_atp5_demand2 = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=5,
            safety_stock=0,
            forecast_demand_14d=2.0,
        )
        self.assertEqual(scarcity_atp5_demand2, 0.0)

    def test_scarcity_lambda_missing_vs_zero_forecast(self):
        # Missing forecast (None) on constrained stock (ATP=2, safety=10)
        # -> safe fallback (effective_forecast >= 14.0) protects scarce inventory -> lambda > 0
        scarcity_none_constrained = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=2,
            safety_stock=10,
            forecast_demand_14d=None,
        )
        self.assertGreater(scarcity_none_constrained, 0.0)
        self.assertLessEqual(scarcity_none_constrained, 40.0)

        # Missing forecast (None) on abundant stock (ATP=50, safety=10)
        # -> safe fallback (forecast=15.0) correctly recognizes ATP=50 as abundant -> lambda = 0.0
        scarcity_none_abundant = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=50,
            safety_stock=10,
            forecast_demand_14d=None,
        )
        self.assertEqual(scarcity_none_abundant, 0.0)

        # Explicit genuine zero forecast (0.0) on constrained stock (ATP=2, safety=10)
        # -> genuine zero organic buyers -> zero opportunity cost ($0.00)
        scarcity_zero_fc = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=2,
            safety_stock=10,
            forecast_demand_14d=0.0,
        )
        self.assertEqual(scarcity_zero_fc, 0.0)

    def test_scarcity_lambda_negative_demand_pressure(self):
        # Negative demand pressure (e.g. forecast = -5.0) -> clamped to 0.0 -> lambda = 0.0
        scarcity_neg_fc = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=2,
            safety_stock=10,
            forecast_demand_14d=-5.0,
        )
        self.assertEqual(scarcity_neg_fc, 0.0)

    def test_scarcity_lambda_unusually_large_demand(self):
        # Extreme demand (e.g. 100,000 units) -> cleanly saturated at unit margin without overflow
        scarcity_large = calculate_scarcity_lambda(
            reference_price=80.0,
            cogs=40.0,
            atp=2,
            safety_stock=10,
            forecast_demand_14d=100_000.0,
        )
        self.assertEqual(scarcity_large, 40.0)

    def test_scarcity_lambda_zero_or_negative_margin(self):
        # Reference price <= COGS -> unit margin is 0 -> lambda must be 0.0
        scarcity_loss = calculate_scarcity_lambda(
            reference_price=30.0,
            cogs=40.0,
            atp=2,
            safety_stock=10,
            forecast_demand_14d=14.0,
        )
        self.assertEqual(scarcity_loss, 0.0)

    def test_list_and_update_inventory(self):
        item = self.inventory_repo.get_inventory_item("item-001")
        self.assertIsNotNone(item)
        self.assertEqual(item.sku, "item-001")
        initial_atp = item.atp

        # Reserve 2 units
        success = self.inventory_repo.update_stock("item-001", reserved_delta=2)
        self.assertTrue(success)

        updated = self.inventory_repo.get_inventory_item("item-001")
        self.assertEqual(updated.atp, initial_atp - 2)

    def test_get_inventory_alerts(self):
        alerts = self.inventory_repo.get_inventory_alerts(storefront_id="primary_storefront")
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)
        # Verify severities are sorted CRITICAL before WARNING/INFO
        severities = [a.severity for a in alerts]
        if "CRITICAL" in severities and "WARNING" in severities:
            crit_idx = severities.index("CRITICAL")
            warn_idx = severities.index("WARNING")
            self.assertLess(crit_idx, warn_idx)


if __name__ == "__main__":
    unittest.main()
