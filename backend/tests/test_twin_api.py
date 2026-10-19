"""Unit tests for FairCart Decision Twin API endpoints."""

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.engine.twin_inventory import TwinInventoryRepository
from backend.app.main import app


class TestTwinAPI(unittest.TestCase):
    """Test suite covering FastAPI routes for Decision Twin inventory, forecasting, traces, and connectors."""

    @classmethod
    def setUpClass(cls):
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.db_path = cls.temp_db.name
        cls.temp_db.close()

        # Point settings to temp DB
        cls._orig_db_path = settings.DATABASE_PATH
        cls._orig_db_url = settings.DATABASE_URL
        cls._orig_vault_key = settings.CONNECTOR_VAULT_KEY
        settings.DATABASE_PATH = cls.db_path
        settings.DATABASE_URL = None
        settings.CONNECTOR_VAULT_KEY = "hermetic-test-vault-key-32bytes-secret!"

        init_db(db_path=cls.db_path)

        # Seed catalog
        import sqlite3
        conn = sqlite3.connect(cls.db_path)
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

        TwinInventoryRepository(db_path=cls.db_path).seed_initial_inventory(storefront_id="primary_storefront")
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        settings.DATABASE_PATH = cls._orig_db_path
        settings.DATABASE_URL = cls._orig_db_url
        settings.CONNECTOR_VAULT_KEY = cls._orig_vault_key
        if os.path.exists(cls.db_path):
            try:
                os.unlink(cls.db_path)
            except Exception:
                pass

    def test_get_inventory(self):
        resp = self.client.get("/api/v1/twin/inventory")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 2)
        kb = next((i for i in items if i["sku"] == "item-001"), None)
        self.assertIsNotNone(kb)
        self.assertIn("atp", kb)
        self.assertIn("scarcity_lambda", kb)

    def test_get_inventory_alerts(self):
        resp = self.client.get("/api/v1/twin/inventory-alerts")
        self.assertEqual(resp.status_code, 200)
        alerts = resp.json()
        self.assertIsInstance(alerts, list)

    def test_get_forecasts(self):
        resp = self.client.get("/api/v1/twin/forecasts?horizon_days=14&sku=item-001")
        self.assertEqual(resp.status_code, 200)
        fcs = resp.json()
        self.assertEqual(len(fcs), 1)
        self.assertEqual(fcs[0]["sku"], "item-001")
        self.assertIn("point_forecast", fcs[0])
        self.assertIn("lower_bound", fcs[0])
        self.assertIn("upper_bound", fcs[0])

    def test_evaluate_twin_decision(self):
        payload = {
            "session_id": "sess-twin-api-test",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "dwell_time_seconds": 65,
            "margin_floor": 0.20,
            "discount_cap": 0.20,
        }
        resp = self.client.post("/api/v1/twin/decision", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("trace_id", data)
        self.assertIn("intent_state", data)
        self.assertIn("chosen_action", data)

        # Retrieve trace
        trace_id = data["trace_id"]
        trace_resp = self.client.get(f"/api/v1/twin/traces/{trace_id}")
        self.assertEqual(trace_resp.status_code, 200)
        trace_data = trace_resp.json()
        self.assertEqual(trace_data["trace_id"], trace_id)

    def test_optimize_twin_batch(self):
        payload = {
            "sessions": [
                {
                    "session_id": "sess-batch-api-1",
                    "cart_items": [{"product_id": "item-001", "quantity": 1}],
                    "dwell_time_seconds": 45,
                },
                {
                    "session_id": "sess-batch-api-2",
                    "cart_items": [{"product_id": "item-002", "quantity": 1}],
                    "dwell_time_seconds": 90,
                },
            ],
            "storefront_id": "primary_storefront",
            "margin_floor": 0.20,
            "discount_cap": 0.20,
        }
        resp = self.client.post("/api/v1/twin/optimize-batch", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_sessions_evaluated"], 2)
        self.assertIn("aggregate_projected_profit", data)
        self.assertIn("projected_profit_lift_pct", data)

    def test_connectors_api_lifecycle(self):
        # Authenticate as demo merchant
        headers = {"x-demo-merchant": "true"}

        # 1. List
        resp = self.client.get("/api/v1/twin/connectors", headers=headers)
        self.assertEqual(resp.status_code, 200)
        conns = resp.json()
        self.assertEqual(len(conns), 2)

        # 2. Configure Shopify
        cfg_payload = {
            "provider": "shopify",
            "credentials": {
                "shop_url": "test-twin-store.myshopify.com",
                "access_token": "shpat_12345678901234567890",
            },
        }
        conf_resp = self.client.post("/api/v1/twin/connectors/configure", json=cfg_payload, headers=headers)
        self.assertEqual(conf_resp.status_code, 200)
        self.assertEqual(conf_resp.json()["status"], "connected")

        # 3. Sync
        sync_resp = self.client.post("/api/v1/twin/connectors/shopify/sync", headers=headers)
        self.assertEqual(sync_resp.status_code, 200)
        self.assertEqual(sync_resp.json()["status"], "success")

        # 4. Disconnect
        del_resp = self.client.delete("/api/v1/twin/connectors/shopify", headers=headers)
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json()["disconnected"])


if __name__ == "__main__":
    unittest.main()
