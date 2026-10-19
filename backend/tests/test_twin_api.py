"""Unit tests for FairCart Decision Twin API endpoints."""

import json
import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.engine.forecasting import DemandForecaster
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

        # Seed demo user accounts and session tokens for role verification
        cur.execute("""
            INSERT OR REPLACE INTO users (
                id, username, display_name, persona_description, role, password_hash, created_at
            ) VALUES
            ('usr_customer_1', 'demo_student', 'Student Demo', 'Student persona', 'customer', 'fakehash', '2026-01-01T00:00:00'),
            ('usr_demo_merchant', 'demo_merchant', 'Demo Merchant', 'Primary merchant', 'merchant', 'fakehash', '2026-01-01T00:00:00'),
            ('usr_merchant_other', 'other_merchant', 'Other Merchant', 'Secondary merchant', 'merchant', 'fakehash', '2026-01-01T00:00:00')
        """)
        cur.execute("""
            INSERT OR REPLACE INTO user_sessions (
                session_token, user_id, created_at, expires_at
            ) VALUES
            ('tok_customer_1', 'usr_customer_1', '2026-01-01T00:00:00', '2099-01-01T00:00:00'),
            ('tok_merchant_1', 'usr_demo_merchant', '2026-01-01T00:00:00', '2099-01-01T00:00:00'),
            ('tok_merchant_other', 'usr_merchant_other', '2026-01-01T00:00:00', '2099-01-01T00:00:00')
        """)
        conn.commit()
        conn.close()

        # Seed inventory and forecasts for primary storefront
        TwinInventoryRepository(db_path=cls.db_path).seed_initial_inventory(storefront_id="primary_storefront", force=True)
        DemandForecaster(db_path=cls.db_path).generate_and_save_forecasts(storefront_id="primary_storefront", horizon_days=14)

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
        resp = self.client.get("/api/v1/twin/inventory", headers={"Authorization": "Bearer tok_merchant_1"})
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 2)
        kb = next((i for i in items if i["sku"] == "item-001"), None)
        self.assertIsNotNone(kb)
        self.assertIn("atp", kb)
        self.assertIn("scarcity_lambda", kb)

    def test_get_inventory_alerts(self):
        resp = self.client.get("/api/v1/twin/inventory-alerts", headers={"Authorization": "Bearer tok_merchant_1"})
        self.assertEqual(resp.status_code, 200)
        alerts = resp.json()
        self.assertIsInstance(alerts, list)

    def test_get_forecasts(self):
        resp = self.client.get(
            "/api/v1/twin/forecasts?horizon_days=14&sku=item-001&storefront_id=primary_storefront",
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(resp.status_code, 200)
        fcs = resp.json()
        self.assertEqual(len(fcs), 1)
        self.assertEqual(fcs[0]["sku"], "item-001")
        self.assertIn("point_forecast", fcs[0])
        self.assertIn("lower_bound", fcs[0])
        self.assertIn("upper_bound", fcs[0])

    def test_forecasts_generate_endpoint(self):
        resp = self.client.post(
            "/api/v1/twin/forecasts/generate?horizon_days=7&storefront_id=primary_storefront",
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(resp.status_code, 200)
        fcs = resp.json()
        self.assertIsInstance(fcs, list)
        self.assertGreaterEqual(len(fcs), 2)

    def test_pure_read_no_seeding_on_get(self):
        """Verifies GET /api/v1/twin/inventory and /forecasts are strictly read-only and never seed database."""
        # 1. Unseeded storefront inventory
        resp_inv = self.client.get(
            "/api/v1/twin/inventory?storefront_id=empty_storefront",
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(resp_inv.status_code, 200)
        self.assertEqual(resp_inv.json(), [])

        # 2. Unseeded storefront forecasts
        resp_fc = self.client.get(
            "/api/v1/twin/forecasts?storefront_id=empty_storefront",
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(resp_fc.status_code, 200)
        self.assertEqual(resp_fc.json(), [])

        # Confirm zero database rows were inserted
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sku_inventory WHERE storefront_id = 'empty_storefront'")
        self.assertEqual(cur.fetchone()[0], 0)
        cur.execute("SELECT COUNT(*) FROM demand_forecasts WHERE storefront_id = 'empty_storefront'")
        self.assertEqual(cur.fetchone()[0], 0)
        conn.close()

    def test_customer_role_denied_on_merchant_twin_endpoints(self):
        """Customer sessions must receive HTTP 403 Forbidden on confidential merchant Decision Twin endpoints."""
        customer_headers = {"Authorization": "Bearer tok_customer_1"}

        resp_inv = self.client.get("/api/v1/twin/inventory", headers=customer_headers)
        self.assertEqual(resp_inv.status_code, 403)

        resp_alerts = self.client.get("/api/v1/twin/inventory-alerts", headers=customer_headers)
        self.assertEqual(resp_alerts.status_code, 403)

        resp_fc = self.client.get("/api/v1/twin/forecasts", headers=customer_headers)
        self.assertEqual(resp_fc.status_code, 403)

        resp_gen = self.client.post("/api/v1/twin/forecasts/generate", headers=customer_headers)
        self.assertEqual(resp_gen.status_code, 403)

        resp_seed = self.client.post("/api/v1/twin/inventory/seed-demo", headers=customer_headers)
        self.assertEqual(resp_seed.status_code, 403)

        resp_batch = self.client.post(
            "/api/v1/twin/optimize-batch",
            json={"sessions": [], "storefront_id": "primary_storefront"},
            headers=customer_headers,
        )
        self.assertEqual(resp_batch.status_code, 403)

        resp_conns = self.client.get("/api/v1/twin/connectors", headers=customer_headers)
        self.assertEqual(resp_conns.status_code, 403)

    def test_unauthenticated_in_production_rejected(self):
        """In production environment, unauthenticated calls must return HTTP 401 Unauthorized."""
        orig_env = settings.ENVIRONMENT
        try:
            settings.ENVIRONMENT = "production"
            resp = self.client.get("/api/v1/twin/inventory")
            self.assertEqual(resp.status_code, 401)
        finally:
            settings.ENVIRONMENT = orig_env

    def test_evaluate_twin_decision_dual_role(self):
        """Verifies dual-role behavior: public shoppers receive redacted view; merchants receive full diagnostics."""
        payload = {
            "session_id": "sess-twin-dual-role",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "dwell_time_seconds": 65,
            "margin_floor": 0.20,
            "discount_cap": 0.20,
        }

        # 1. Public Shopper (unauthenticated)
        resp_shopper = self.client.post("/api/v1/twin/decision", json=payload)
        self.assertEqual(resp_shopper.status_code, 200)
        data_shopper = resp_shopper.json()
        self.assertIn("trace_id", data_shopper)
        self.assertIn("intent_state", data_shopper)
        self.assertIn("chosen_action", data_shopper)
        self.assertIn("redacted_shopper_view", data_shopper)
        # Verify merchant internal data is strictly scrubbed
        self.assertNotIn("candidates_evaluated", data_shopper)
        self.assertNotIn("constraints_applied", data_shopper)
        self.assertNotIn("scarcity_lambda", data_shopper)

        # 2. Authenticated Merchant
        resp_merchant = self.client.post(
            "/api/v1/twin/decision",
            json=payload,
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(resp_merchant.status_code, 200)
        data_merchant = resp_merchant.json()
        self.assertIn("trace_id", data_merchant)
        self.assertIn("candidates_evaluated", data_merchant)
        self.assertIn("constraints_applied", data_merchant)
        self.assertIn("scarcity_lambda", data_merchant)

    def test_decision_trace_tenant_isolation_and_public_transparency(self):
        """Verifies tenant isolation and the separate public transparency trace route."""
        # Generate decision under merchant 1
        payload = {
            "session_id": "sess-twin-trace-tenant",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "dwell_time_seconds": 65,
            "margin_floor": 0.20,
            "discount_cap": 0.20,
        }
        dec_resp = self.client.post(
            "/api/v1/twin/decision",
            json=payload,
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(dec_resp.status_code, 200)
        trace_id = dec_resp.json()["trace_id"]

        # 1. Merchant 1 (owner) can retrieve full trace
        resp_owner = self.client.get(
            f"/api/v1/twin/traces/{trace_id}",
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(resp_owner.status_code, 200)
        trace_data = resp_owner.json()
        self.assertEqual(trace_data["trace_id"], trace_id)
        self.assertIn("candidates_evaluated", trace_data)
        self.assertIn("constraints_applied", trace_data)

        # 2. Merchant 2 (cross-tenant) is denied access
        resp_other = self.client.get(
            f"/api/v1/twin/traces/{trace_id}",
            headers={"Authorization": "Bearer tok_merchant_other"}
        )
        self.assertEqual(resp_other.status_code, 403)
        self.assertIn("Cross-tenant access forbidden", resp_other.json()["detail"])

        # 3. Public shopper can retrieve redacted view via public endpoint
        resp_pub = self.client.get(f"/api/v1/twin/traces/{trace_id}/public")
        self.assertEqual(resp_pub.status_code, 200)
        pub_data = resp_pub.json()
        self.assertEqual(pub_data["trace_id"], trace_id)
        self.assertTrue(pub_data.get("margin_protected", False))
        self.assertNotIn("candidates_evaluated", pub_data)
        self.assertNotIn("constraints_applied", pub_data)
        self.assertNotIn("scarcity_lambda", pub_data)

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
        resp = self.client.post(
            "/api/v1/twin/optimize-batch",
            json=payload,
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_sessions_evaluated"], 2)
        self.assertIn("aggregate_projected_profit", data)
        self.assertIn("projected_profit_lift_pct", data)

    def test_seed_demo_inventory_endpoint(self):
        # 1. Non-production / test environment allows authorized seeding
        resp = self.client.post(
            "/api/v1/twin/inventory/seed-demo?storefront_id=demo_storefront",
            headers={"Authorization": "Bearer tok_merchant_1"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        self.assertGreaterEqual(data.get("seeded_count", 0), 2)

        # 2. In production with ENABLE_DEMO_INVENTORY_SEEDING=False, admin authorization is strictly rejected
        orig_env = settings.ENVIRONMENT
        orig_flag = settings.ENABLE_DEMO_INVENTORY_SEEDING
        orig_admin = settings.ADMIN_TOKEN
        try:
            settings.ENVIRONMENT = "production"
            settings.ENABLE_DEMO_INVENTORY_SEEDING = False
            settings.ADMIN_TOKEN = "hermetic-test-admin-secret"
            admin_headers = {"Authorization": "Bearer hermetic-test-admin-secret"}

            resp_prod_disabled = self.client.post(
                "/api/v1/twin/inventory/seed-demo?storefront_id=demo_storefront_prod",
                headers=admin_headers
            )
            self.assertEqual(resp_prod_disabled.status_code, 403)
            self.assertIn("strictly disabled in production", resp_prod_disabled.json()["detail"])
            self.assertIn("cannot override", resp_prod_disabled.json()["detail"])

            # 3. Only when ENABLE_DEMO_INVENTORY_SEEDING is explicitly True is admin seeding allowed in production
            settings.ENABLE_DEMO_INVENTORY_SEEDING = True
            resp_prod_enabled = self.client.post(
                "/api/v1/twin/inventory/seed-demo?storefront_id=demo_storefront_prod",
                headers=admin_headers
            )
            self.assertEqual(resp_prod_enabled.status_code, 200)
            self.assertEqual(resp_prod_enabled.json().get("status"), "success")
        finally:
            settings.ENVIRONMENT = orig_env
            settings.ENABLE_DEMO_INVENTORY_SEEDING = orig_flag
            settings.ADMIN_TOKEN = orig_admin

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
