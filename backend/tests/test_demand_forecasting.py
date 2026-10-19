"""Unit tests for FairCart Decision Twin — Demand Forecasting Engine (Slice 2)."""

import os
import tempfile
import unittest

import numpy as np

from backend.app.db.database import init_db
from backend.app.engine.forecasting import (
    DemandForecaster,
    calculate_forecast_bias,
    calculate_mase,
    calculate_wape,
    croston_forecast,
    seasonal_naive_forecast,
)
from backend.app.engine.twin_inventory import TwinInventoryRepository


class TestDemandForecasting(unittest.TestCase):
    """Test suite covering demand metrics, forecasting algorithms, intervals, and persistence."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        init_db(db_path=self.db_path)

        # Seed catalog item in test DB
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO products (
                id, name, category, subcategory, description, reference_price_cents,
                cogs_cents, inventory, complementary_ids, tags, use_cases, image_url
            ) VALUES (
                'item-001', 'Ergonomic Mechanical Keyboard', 'Electronics', 'Keyboards',
                'Tactile quiet switches', 8000, 4000, 12, 'item-002,item-003',
                'keyboard,ergonomic', 'productivity,gaming', '/images/keyboard.jpg'
            )
        """)
        conn.commit()
        conn.close()

        self.forecaster = DemandForecaster(db_path=self.db_path)
        self.inventory_repo = TwinInventoryRepository(db_path=self.db_path)
        self.inventory_repo.seed_initial_inventory(storefront_id="primary_storefront")

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except Exception:
                pass

    def test_wape_calculation(self):
        y_true = [10.0, 20.0, 30.0, 40.0]  # sum = 100
        y_pred = [12.0, 18.0, 32.0, 38.0]  # abs diffs = 2 + 2 + 2 + 2 = 8
        wape = calculate_wape(y_true, y_pred)
        self.assertEqual(wape, 0.08)

    def test_mase_calculation(self):
        y_train = [10.0, 12.0, 14.0, 16.0]  # naive diffs = 2, 2, 2 -> mean = 2.0
        y_true = [18.0, 20.0]
        y_pred = [17.0, 21.0]  # mae = (1 + 1) / 2 = 1.0 -> mase = 1.0 / 2.0 = 0.5
        mase = calculate_mase(y_true, y_pred, y_train)
        self.assertEqual(mase, 0.5)

    def test_forecast_bias_calculation(self):
        y_true = [10.0, 20.0]  # sum = 30
        y_pred = [13.0, 23.0]  # sum pred - true = +6 -> bias = +20.0%
        bias = calculate_forecast_bias(y_true, y_pred)
        self.assertEqual(bias, 20.0)

    def test_croston_forecast_intermittent(self):
        # Sparse demand: orders only every 3-4 days
        intermittent_series = [0, 0, 5, 0, 0, 0, 4, 0, 0, 6, 0, 0, 0, 5]
        forecast_7d = croston_forecast(intermittent_series, horizon=7)
        self.assertGreater(forecast_7d, 0.0)
        self.assertLess(forecast_7d, 35.0)

    def test_seasonal_naive_forecast(self):
        # Periodic 7-day pattern
        pattern = [1.0, 2.0, 1.0, 3.0, 2.0, 5.0, 4.0]  # sum = 18
        series = pattern * 4  # 28 days
        forecast_14d = seasonal_naive_forecast(series, horizon=14)
        self.assertEqual(forecast_14d, 36.0)  # 2 full cycles of 18

    def test_generate_forecast_hist_gbm(self):
        fc = self.forecaster.generate_forecast(
            sku="item-001",
            horizon_days=14,
            method="hist_gradient_boosting",
            confidence_level=0.95,
        )
        self.assertEqual(fc.sku, "item-001")
        self.assertEqual(fc.horizon_days, 14)
        self.assertGreater(fc.point_forecast, 0.0)
        self.assertLessEqual(fc.lower_bound, fc.point_forecast)
        self.assertGreaterEqual(fc.upper_bound, fc.point_forecast)
        self.assertGreaterEqual(fc.wape, 0.0)
        self.assertGreaterEqual(fc.mase, 0.0)

    def test_generate_forecast_multi_horizon(self):
        fc_7 = self.forecaster.generate_forecast(sku="item-001", horizon_days=7)
        fc_14 = self.forecaster.generate_forecast(sku="item-001", horizon_days=14)
        fc_30 = self.forecaster.generate_forecast(sku="item-001", horizon_days=30)

        # Longer horizons must predict strictly more cumulative demand
        self.assertLess(fc_7.point_forecast, fc_14.point_forecast)
        self.assertLess(fc_14.point_forecast, fc_30.point_forecast)

    def test_forecast_persistence_and_retrieval(self):
        fc = self.forecaster.generate_forecast(sku="item-001", horizon_days=14)
        retrieved = self.forecaster.get_forecasts_for_storefront(storefront_id="primary_storefront", horizon_days=14)
        self.assertGreaterEqual(len(retrieved), 1)
        item_fc = next((r for r in retrieved if r.sku == "item-001"), None)
        self.assertIsNotNone(item_fc)
        self.assertAlmostEqual(item_fc.point_forecast, fc.point_forecast, places=2)


if __name__ == "__main__":
    unittest.main()
