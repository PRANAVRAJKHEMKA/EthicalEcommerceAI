"""FairCart AI — Step 5.20: Multi-Store Profit Intelligence Tests

Verifies:
1. Ingestion & Pre-Flight Validation:
   - Valid order-lines and traffic-events CSV parsing into structured records.
   - Resource limit bounds: 10 MB file cap, 20,000 row cap, 1,000 char cell cap.
   - Zero-PII privacy enforcement: immediate rejection of forbidden PII columns (customer_email, full_name, credit_card).
   - Strict column header checks.
2. Financial Accounting & Invariant Guarantees:
   - Net Revenue = Gross Line Revenue - Discounts - Refunds.
   - Gross Profit = Net Revenue - COGS.
   - Gross Margin % = (Gross Profit / Net Revenue) * 100.
   - Zero and negative net revenue denominator safety (no ZeroDivisionError, emits quality flag).
   - Distinct Order Grouping: Multiple item lines in the same order count as 1 order for distinct orders, AOV, and conversion rates.
3. Observational Channel Attribution & Diagnostics:
   - Attribution note explicitly clarifies observational association vs. incremental causation.
   - Diagnostic warnings flagged for uneconomic discounting (margin < 25% with discounts > 15%) and high refund rates.
4. Idempotency & Currency Isolation:
   - Stable deterministic row hashing (sol-... and ste-...) prevents duplicate inflation.
   - Currencies are strictly segregated (USD vs EUR).
5. FastAPI Endpoints:
   - POST /api/v1/analytics/multi-store/preview
   - POST /api/v1/analytics/multi-store/import
   - GET /api/v1/analytics/multi-store/profit
   - GET /api/v1/analytics/multi-store/batches
   - POST /api/v1/analytics/multi-store/seed-demo
   - DELETE /api/v1/analytics/multi-store/data
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import BASE_DIR, settings
from backend.app.db.database import get_connection, init_db
from backend.app.db.repository import CatalogRepository
from backend.app.engine.multi_store_analytics import (
    aggregate_profit_intelligence,
    validate_and_parse_csv,
    MAX_CSV_BYTES,
    MAX_CSV_ROWS,
    FORBIDDEN_PII_KEYWORDS,
)
from backend.app.main import app


class TestStep520MultiStoreIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_db_path = str(Path(cls.temp_dir.name) / "test_multi_store.db")
        init_db(cls.temp_db_path)
        cls.repo = CatalogRepository()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        # Clear storefront tables before each test for clean isolation
        self.repo.clear_storefront_data()

    # =========================================================================
    # 1. CSV VALIDATION & INGESTION
    # =========================================================================

    def test_csv_validation_order_lines_success(self):
        """Valid order lines CSV is successfully validated and parsed with correct types."""
        sample_csv = (
            "storefront_id,order_id,order_timestamp,product_id,quantity,gross_line_revenue,discount_amount,refund_amount,cogs_amount,attribution_channel,currency\n"
            "store-alpha,ord-001,2026-10-15T12:00:00Z,item-001,2,200.00,20.00,0.00,80.00,organic_search,USD\n"
            "store-alpha,ord-002,2026-10-15T13:00:00Z,item-002,1,100.00,0.00,10.00,40.00,paid_search,USD\n"
        )
        is_valid, rows, errors, metrics = validate_and_parse_csv(sample_csv, import_type="orders")
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["storefront_id"], "store-alpha")
        self.assertEqual(rows[0]["gross_line_revenue_cents"], 20000)
        self.assertEqual(rows[0]["discount_cents"], 2000)
        self.assertEqual(rows[0]["cogs_cents"], 8000)
        self.assertEqual(metrics["distinct_orders"], 2)
        self.assertEqual(metrics["estimated_gross_revenue"], 300.0)

    def test_csv_validation_traffic_events_success(self):
        """Valid traffic events CSV is parsed and canonical event types are recognized."""
        sample_csv = (
            "event_id,event_timestamp,session_id,storefront_id,event_type,acquisition_channel,product_id,order_id\n"
            "evt-01,2026-10-15T11:00:00Z,sess-01,store-alpha,product_view,organic_search,item-001,\n"
            "evt-02,2026-10-15T11:05:00Z,sess-01,store-alpha,add_to_cart,organic_search,item-001,\n"
            "evt-03,2026-10-15T11:10:00Z,sess-01,store-alpha,demo_order_completed,organic_search,item-001,ord-001\n"
        )
        is_valid, rows, errors, metrics = validate_and_parse_csv(sample_csv, import_type="traffic")
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(rows), 3)
        self.assertEqual(metrics["unique_sessions"], 1)
        self.assertEqual(metrics["product_views"], 1)
        self.assertEqual(metrics["cart_adds"], 1)

    def test_csv_validation_pii_rejection(self):
        """CSV containing forbidden PII headers must be immediately rejected to preserve privacy."""
        pii_csv = (
            "storefront_id,order_id,customer_email,customer_name,gross_line_revenue\n"
            "store-alpha,ord-001,shopper@example.com,Jane Doe,100.00\n"
        )
        is_valid, rows, errors, metrics = validate_and_parse_csv(pii_csv, import_type="orders")
        self.assertFalse(is_valid)
        self.assertEqual(len(rows), 0)
        self.assertTrue(any("Privacy violation" in e["message"] or "PII" in e["message"] for e in errors))

    def test_csv_validation_missing_required_headers(self):
        """Missing required headers such as product_id in orders must be caught."""
        broken_csv = (
            "storefront_id,order_id,gross_line_revenue\n"
            "store-alpha,ord-001,100.00\n"
        )
        is_valid, rows, errors, metrics = validate_and_parse_csv(broken_csv, import_type="orders")
        self.assertFalse(is_valid)
        self.assertTrue(any("Missing mandatory columns" in e["message"] for e in errors))

    def test_csv_validation_file_size_and_row_limits(self):
        """Enforces resource bounds on oversized payloads."""
        # 1. Byte limit check
        huge_csv = "a" * (MAX_CSV_BYTES + 10)
        is_valid, _, errors, _ = validate_and_parse_csv(huge_csv, import_type="orders")
        self.assertFalse(is_valid)
        self.assertTrue(any("exceeds maximum limit" in e["message"] for e in errors))

        # 2. Row limit check
        header = "storefront_id,order_id,product_id,gross_line_revenue\n"
        lines = [f"s,ord-{i},item-1,10.0\n" for i in range(MAX_CSV_ROWS + 5)]
        oversized_rows = header + "".join(lines)
        is_valid, _, errors, _ = validate_and_parse_csv(oversized_rows, import_type="orders")
        self.assertFalse(is_valid)
        self.assertTrue(any("Exceeded maximum row capacity" in e["message"] for e in errors))

    # =========================================================================
    # 2. DISTINCT ORDER GROUPING & FINANCIAL FORMULAS
    # =========================================================================

    def test_distinct_order_grouping_integrity(self):
        """An order with 3 line items must count as 1 distinct order, not 3 orders."""
        order_lines = [
            {
                "id": "sol-1",
                "storefront_id": "store-tech",
                "order_id": "ord-multi-line",
                "order_timestamp": "2026-10-15T12:00:00Z",
                "order_status": "completed",
                "currency": "USD",
                "product_id": "item-001",
                "quantity": 1,
                "gross_line_revenue_cents": 10000,
                "discount_cents": 1000,
                "refund_cents": 0,
                "cogs_cents": 5000,
                "attribution_channel": "direct",
            },
            {
                "id": "sol-2",
                "storefront_id": "store-tech",
                "order_id": "ord-multi-line",
                "order_timestamp": "2026-10-15T12:00:00Z",
                "order_status": "completed",
                "currency": "USD",
                "product_id": "item-002",
                "quantity": 2,
                "gross_line_revenue_cents": 6000,
                "discount_cents": 0,
                "refund_cents": 0,
                "cogs_cents": 2000,
                "attribution_channel": "direct",
            },
            {
                "id": "sol-3",
                "storefront_id": "store-tech",
                "order_id": "ord-multi-line",
                "order_timestamp": "2026-10-15T12:00:00Z",
                "order_status": "completed",
                "currency": "USD",
                "product_id": "item-003",
                "quantity": 1,
                "gross_line_revenue_cents": 4000,
                "discount_cents": 1000,
                "refund_cents": 0,
                "cogs_cents": 1000,
                "attribution_channel": "direct",
            },
        ]
        traffic = [
            {
                "id": "ste-1",
                "storefront_id": "store-tech",
                "session_id": "sess-01",
                "event_type": "product_view",
                "acquisition_channel": "direct",
                "order_id": "",
                "product_id": "item-001",
            },
            {
                "id": "ste-2",
                "storefront_id": "store-tech",
                "session_id": "sess-01",
                "event_type": "checkout_started",
                "acquisition_channel": "direct",
                "order_id": "",
                "product_id": "item-001",
            },
        ]

        result = aggregate_profit_intelligence(order_lines, traffic)
        sm = result["storefronts"][0]

        # Distinct orders must be strictly 1
        self.assertEqual(sm["distinct_orders"], 1)
        self.assertEqual(sm["units_sold"], 4)
        # Gross revenue = 100 + 60 + 40 = $200.00
        self.assertEqual(sm["gross_revenue"], 200.0)
        # Discounts = 10 + 0 + 10 = $20.00
        self.assertEqual(sm["discount_amount"], 20.0)
        # Net revenue = 200 - 20 = $180.00
        self.assertEqual(sm["net_revenue"], 180.0)
        # COGS = 50 + 20 + 10 = $80.00
        self.assertEqual(sm["cogs"], 80.0)
        # Gross profit = 180 - 80 = $100.00
        self.assertEqual(sm["gross_profit"], 100.0)
        # Margin % = (100 / 180) * 100 = 55.56%
        self.assertEqual(sm["gross_margin_pct"], 55.56)
        # AOV = Net Revenue / 1 = $180.00
        self.assertEqual(sm["aov"], 180.0)

    def test_zero_and_negative_net_revenue_safeguards(self):
        """When discounts + refunds equal or exceed gross revenue, margin calculation does not divide by zero."""
        order_lines = [
            {
                "id": "sol-zero",
                "storefront_id": "store-heavy-discounts",
                "order_id": "ord-free",
                "order_timestamp": "2026-10-15T12:00:00Z",
                "order_status": "completed",
                "currency": "USD",
                "product_id": "item-001",
                "quantity": 1,
                "gross_line_revenue_cents": 5000,
                "discount_cents": 4000,
                "refund_cents": 1000,  # Net revenue = 0
                "cogs_cents": 2500,
                "attribution_channel": "social_referral",
            }
        ]
        result = aggregate_profit_intelligence(order_lines, [])
        sm = result["storefronts"][0]
        self.assertEqual(sm["net_revenue"], 0.0)
        self.assertEqual(sm["gross_margin_pct"], 0.0)
        self.assertTrue(any("exceed gross revenue" in flag for flag in sm["data_quality_flags"]))

    # =========================================================================
    # 3. IDEMPOTENCY & CURRENCY ISOLATION
    # =========================================================================

    def test_idempotent_ingestion(self):
        """Re-ingesting the identical CSV rows produces stable hashes and does not duplicate database records."""
        sample_csv = (
            "storefront_id,order_id,order_timestamp,product_id,quantity,gross_line_revenue,discount_amount,refund_amount,cogs_amount,attribution_channel,currency\n"
            "store-alpha,ord-100,2026-10-15T12:00:00Z,item-001,1,100.00,0.00,0.00,40.00,organic_search,USD\n"
        )
        _, rows, _, _ = validate_and_parse_csv(sample_csv, import_type="orders")
        self.assertEqual(len(rows), 1)
        row_id = rows[0]["id"]

        # Insert first time
        c1 = self.repo.insert_storefront_order_lines(rows, batch_id="b1")
        self.assertEqual(c1, 1)

        # Insert second time (same row ID)
        c2 = self.repo.insert_storefront_order_lines(rows, batch_id="b2")
        self.assertEqual(c2, 0)  # Ignored

        stored = self.repo.get_storefront_order_lines()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["id"], row_id)

    def test_currency_isolation(self):
        """Orders in different currencies (USD vs EUR) are isolated and not blended."""
        order_lines = [
            {
                "id": "sol-usd",
                "storefront_id": "store-us",
                "order_id": "ord-us-1",
                "order_timestamp": "2026-10-15T12:00:00Z",
                "order_status": "completed",
                "currency": "USD",
                "product_id": "item-001",
                "quantity": 1,
                "gross_line_revenue_cents": 10000,
                "discount_cents": 0,
                "refund_cents": 0,
                "cogs_cents": 5000,
                "attribution_channel": "direct",
            },
            {
                "id": "sol-eur",
                "storefront_id": "store-eu",
                "order_id": "ord-eu-1",
                "order_timestamp": "2026-10-15T12:00:00Z",
                "order_status": "completed",
                "currency": "EUR",
                "product_id": "item-001",
                "quantity": 1,
                "gross_line_revenue_cents": 9000,
                "discount_cents": 0,
                "refund_cents": 0,
                "cogs_cents": 4500,
                "attribution_channel": "direct",
            },
        ]
        # Query for USD
        res_usd = aggregate_profit_intelligence(order_lines, [], currency_filter="USD")
        self.assertEqual(res_usd["selected_currency"], "USD")
        self.assertEqual(len(res_usd["storefronts"]), 1)
        self.assertEqual(res_usd["storefronts"][0]["storefront_id"], "store-us")
        self.assertEqual(res_usd["storefronts"][0]["gross_revenue"], 100.0)

        # Query for EUR
        res_eur = aggregate_profit_intelligence(order_lines, [], currency_filter="EUR")
        self.assertEqual(res_eur["selected_currency"], "EUR")
        self.assertEqual(len(res_eur["storefronts"]), 1)
        self.assertEqual(res_eur["storefronts"][0]["storefront_id"], "store-eu")
        self.assertEqual(res_eur["storefronts"][0]["gross_revenue"], 90.0)

    # =========================================================================
    # 4. OBSERVATIONAL ATTRIBUTION & DIAGNOSTICS
    # =========================================================================

    def test_observational_attribution_disclaimer_and_metrics(self):
        """Channel performance includes explicit non-causal attribution disclaimer."""
        order_lines = [
            {
                "id": "sol-ch-1",
                "storefront_id": "store-tech",
                "order_id": "ord-paid-1",
                "order_timestamp": "2026-10-15T12:00:00Z",
                "order_status": "completed",
                "currency": "USD",
                "product_id": "item-001",
                "quantity": 1,
                "gross_line_revenue_cents": 15000,
                "discount_cents": 1500,
                "refund_cents": 0,
                "cogs_cents": 6000,
                "attribution_channel": "paid_search",
            }
        ]
        traffic = [
            {
                "id": "ste-ch-1",
                "storefront_id": "store-tech",
                "session_id": "sess-ps-1",
                "event_type": "product_view",
                "acquisition_channel": "paid_search",
                "order_id": "",
                "product_id": "item-001",
            }
        ]
        result = aggregate_profit_intelligence(order_lines, traffic)
        self.assertEqual(len(result["channels"]), 1)
        ch = result["channels"][0]
        self.assertEqual(ch["channel"], "paid_search")
        self.assertEqual(ch["attributed_orders"], 1)
        self.assertIn("observational", ch["attribution_note"].lower())
        self.assertIn("does not prove incremental causation", ch["attribution_note"].lower())

    def test_uneconomic_discounting_diagnostic(self):
        """Flags diagnostic when discounts exceed 15% of gross sales and margin is below 25%."""
        order_lines = [
            {
                "id": "sol-diag",
                "storefront_id": "store-unprofitable",
                "order_id": "ord-heavy-sub",
                "order_timestamp": "2026-10-15T12:00:00Z",
                "order_status": "completed",
                "currency": "USD",
                "product_id": "item-001",
                "quantity": 1,
                "gross_line_revenue_cents": 20000,
                "discount_cents": 4000,  # 20% discount share
                "refund_cents": 0,
                "cogs_cents": 13000,     # Net = 160, COGS = 130 -> Profit = 30 -> Margin = 18.75% (<25%)
                "attribution_channel": "direct",
            }
        ]
        result = aggregate_profit_intelligence(order_lines, [])
        diagnostics = result["discounting_diagnostics"]
        self.assertTrue(any(d["metric"] == "Heavy Discounting with Compressed Margin" for d in diagnostics))

    # =========================================================================
    # 5. FASTAPI MULTI-STORE ENDPOINTS
    # =========================================================================

    def test_api_multi_store_preview(self):
        """POST /api/v1/analytics/multi-store/preview returns validation preview."""
        sample_csv = (
            "storefront_id,order_id,product_id,gross_line_revenue,cogs_amount\n"
            "store-alpha,ord-99,item-001,150.00,50.00\n"
        )
        resp = self.client.post(
            "/api/v1/analytics/multi-store/preview",
            json={
                "import_type": "orders",
                "csv_content": sample_csv,
                "filename": "orders_preview.csv",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["valid"])
        self.assertEqual(data["accepted_rows"], 1)
        self.assertEqual(data["detected_storefronts"], ["store-alpha"])

    def test_api_multi_store_import_orders_and_profit_metrics(self):
        """POST import orders and GET profit metrics end-to-end."""
        sample_csv = (
            "storefront_id,order_id,order_timestamp,product_id,quantity,gross_line_revenue,discount_amount,refund_amount,cogs_amount,attribution_channel,currency\n"
            "store-fastapi,ord-api-1,2026-10-15T10:00:00Z,item-001,1,100.00,10.00,0.00,40.00,organic_search,USD\n"
            "store-fastapi,ord-api-2,2026-10-15T11:00:00Z,item-002,1,200.00,20.00,0.00,80.00,paid_search,USD\n"
        )
        import_resp = self.client.post(
            "/api/v1/analytics/multi-store/import",
            json={
                "import_type": "orders",
                "csv_content": sample_csv,
                "filename": "test_import.csv",
            },
        )
        self.assertEqual(import_resp.status_code, 200)
        import_data = import_resp.json()
        self.assertEqual(import_data["status"], "completed")
        self.assertEqual(import_data["accepted_rows"], 2)

        # Query profit metrics
        profit_resp = self.client.get("/api/v1/analytics/multi-store/profit?storefront_id=store-fastapi")
        self.assertEqual(profit_resp.status_code, 200)
        profit_data = profit_resp.json()
        self.assertEqual(profit_data["total_storefronts"], 1)
        sm = profit_data["storefronts"][0]
        self.assertEqual(sm["distinct_orders"], 2)
        self.assertEqual(sm["gross_revenue"], 300.0)
        self.assertEqual(sm["discount_amount"], 30.0)
        self.assertEqual(sm["net_revenue"], 270.0)
        self.assertEqual(sm["cogs"], 120.0)
        self.assertEqual(sm["gross_profit"], 150.0)
        self.assertEqual(sm["gross_margin_pct"], 55.56)

    def test_api_seed_demo_and_clear_data(self):
        """POST /api/v1/analytics/multi-store/seed-demo loads fixtures and DELETE clears them."""
        # Seed demo fixtures
        seed_resp = self.client.post("/api/v1/analytics/multi-store/seed-demo")
        self.assertEqual(seed_resp.status_code, 200)
        seed_data = seed_resp.json()
        self.assertGreater(seed_data["order_lines_imported"], 0)
        self.assertGreater(seed_data["traffic_events_imported"], 0)

        # Verify profit metrics now reflect 3 demo stores
        profit_resp = self.client.get("/api/v1/analytics/multi-store/profit")
        self.assertEqual(profit_resp.status_code, 200)
        profit_data = profit_resp.json()
        self.assertEqual(profit_data["total_storefronts"], 3)
        store_names = [s["storefront_id"] for s in profit_data["storefronts"]]
        self.assertIn("store-alpha-tech", store_names)
        self.assertIn("store-beta-living", store_names)
        self.assertIn("store-gamma-pantry", store_names)

        # Check batches log
        batch_resp = self.client.get("/api/v1/analytics/multi-store/batches")
        self.assertEqual(batch_resp.status_code, 200)
        batches = batch_resp.json()
        self.assertGreaterEqual(len(batches), 2)

        # Clear data
        clear_resp = self.client.delete("/api/v1/analytics/multi-store/data")
        self.assertEqual(clear_resp.status_code, 200)
        clear_data = clear_resp.json()
        self.assertEqual(clear_data["status"], "success")

        # Verify profit metrics are now 0 stores
        post_clear_resp = self.client.get("/api/v1/analytics/multi-store/profit")
        self.assertEqual(post_clear_resp.status_code, 200)
        self.assertEqual(post_clear_resp.json()["total_storefronts"], 0)

    # =========================================================================
    # 6. SECURITY & AUTHORIZATION REGRESSION TESTS
    # =========================================================================

    def test_admin_authorization_in_production(self):
        """In production environment, mutating endpoints strictly require the configured ADMIN_TOKEN."""
        orig_env = settings.ENVIRONMENT
        orig_token = settings.ADMIN_TOKEN
        try:
            settings.ENVIRONMENT = "production"
            settings.ADMIN_TOKEN = "test-prod-secret-token"

            # 1. Unauthenticated request to seed-demo fails with 403
            resp = self.client.post("/api/v1/analytics/multi-store/seed-demo")
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Merchant authorization required", resp.json()["detail"])

            # 2. Invalid token fails with 403
            resp = self.client.post(
                "/api/v1/analytics/multi-store/seed-demo",
                headers={"X-Admin-Token": "wrong-token"},
            )
            self.assertEqual(resp.status_code, 403)

            # 3. Valid token succeeds
            resp = self.client.post(
                "/api/v1/analytics/multi-store/seed-demo",
                headers={"X-Admin-Token": "test-prod-secret-token"},
            )
            self.assertEqual(resp.status_code, 200)

            # 4. Unauthenticated DELETE /data fails with 403
            resp = self.client.delete("/api/v1/analytics/multi-store/data")
            self.assertEqual(resp.status_code, 403)

            # 5. Valid token on DELETE /data succeeds
            resp = self.client.delete(
                "/api/v1/analytics/multi-store/data",
                headers={"X-Admin-Token": "test-prod-secret-token"},
            )
            self.assertEqual(resp.status_code, 200)

            # 6. If ADMIN_TOKEN is not configured in production, admin actions are completely disabled
            settings.ADMIN_TOKEN = ""
            resp = self.client.post("/api/v1/analytics/multi-store/seed-demo")
            self.assertEqual(resp.status_code, 403)
            self.assertIn("administrative token not configured", resp.json()["detail"])
        finally:
            settings.ENVIRONMENT = orig_env
            settings.ADMIN_TOKEN = orig_token

    def test_customer_session_token_rejected_from_admin_and_read_endpoints(self):
        """Customer session tokens (cookies or headers) must NEVER access merchant admin or profit intelligence."""
        # Ensure a test user exists
        user = self.repo.get_user_by_username("demo_gamer")
        if not user:
            user = self.repo.create_user("user-test-gamer", "demo_gamer", "Gamer User", "Gamer", "hashedpw")

        # Create an active customer session
        customer_token = "shopper-token-abc123xyz"
        expires_at = "2099-01-01T00:00:00Z"
        self.repo.create_session(customer_token, user.id, expires_at)

        try:
            # 1. DELETE /data with customer cookie is rejected with 403
            resp = self.client.delete(
                "/api/v1/analytics/multi-store/data",
                cookies={"faircart_session": customer_token},
            )
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Customer session tokens cannot be used", resp.json()["detail"])

            # 2. POST /seed-demo with customer Authorization header is rejected with 403
            resp = self.client.post(
                "/api/v1/analytics/multi-store/seed-demo",
                headers={"Authorization": f"Bearer {customer_token}"},
            )
            self.assertEqual(resp.status_code, 403)

            # 3. POST /import with customer cookie is rejected with 403
            resp = self.client.post(
                "/api/v1/analytics/multi-store/import",
                json={"import_type": "orders", "csv_content": "dummy", "filename": "test.csv"},
                cookies={"faircart_session": customer_token},
            )
            self.assertEqual(resp.status_code, 403)

            # 4. GET /profit with customer session is rejected with 403
            resp = self.client.get(
                "/api/v1/analytics/multi-store/profit",
                cookies={"faircart_session": customer_token},
            )
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Customer session tokens cannot access merchant profit intelligence", resp.json()["detail"])

            # 5. POST /preview with customer session is rejected with 403
            resp = self.client.post(
                "/api/v1/analytics/multi-store/preview",
                json={"import_type": "orders", "csv_content": "dummy", "filename": "test.csv"},
                cookies={"faircart_session": customer_token},
            )
            self.assertEqual(resp.status_code, 403)
        finally:
            self.repo.delete_session(customer_token)

    def test_invalid_storefront_id_sanitization(self):
        """Rejects malicious or invalid storefront IDs to prevent path traversal or injection."""
        # Path traversal attempt
        resp = self.client.get("/api/v1/analytics/multi-store/profit?storefront_id=../../etc/passwd")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid storefront_id", resp.json()["detail"])

        # Special character / SQL injection attempt
        resp = self.client.delete("/api/v1/analytics/multi-store/data?storefront_id=store';DROP%20TABLE")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid storefront_id", resp.json()["detail"])

    def test_scoped_storefront_deletion(self):
        """Deleting a specific storefront removes only that storefront's data, preserving others."""
        # Seed 3 demo stores
        seed_resp = self.client.post("/api/v1/analytics/multi-store/seed-demo")
        self.assertEqual(seed_resp.status_code, 200)

        # Confirm all 3 exist
        initial_profit = self.client.get("/api/v1/analytics/multi-store/profit").json()
        self.assertEqual(initial_profit["total_storefronts"], 3)
        initial_stores = {s["storefront_id"] for s in initial_profit["storefronts"]}
        self.assertEqual(initial_stores, {"store-alpha-tech", "store-beta-living", "store-gamma-pantry"})

        # Delete ONLY store-alpha-tech
        del_resp = self.client.delete("/api/v1/analytics/multi-store/data?storefront_id=store-alpha-tech")
        self.assertEqual(del_resp.status_code, 200)
        del_data = del_resp.json()
        self.assertEqual(del_data["storefront_id"], "store-alpha-tech")
        self.assertGreater(del_data["cleared"]["order_lines_cleared"], 0)

        # Check profit metrics: store-alpha-tech is gone, but beta and gamma remain
        post_del_profit = self.client.get("/api/v1/analytics/multi-store/profit").json()
        self.assertEqual(post_del_profit["total_storefronts"], 2)
        remaining_stores = {s["storefront_id"] for s in post_del_profit["storefronts"]}
        self.assertEqual(remaining_stores, {"store-beta-living", "store-gamma-pantry"})
        self.assertNotIn("store-alpha-tech", remaining_stores)

    # =========================================================================
    # 7. AUTHENTICATED MERCHANT FLOW & CROSS-MERCHANT ISOLATION
    # =========================================================================

    def test_intended_authenticated_merchant_flow(self):
        """A legitimately authenticated merchant can preview, import, view profit, and view history without ADMIN_TOKEN."""
        orig_env = settings.ENVIRONMENT
        orig_token = settings.ADMIN_TOKEN
        try:
            # Simulate production environment with NO ADMIN_TOKEN configured
            settings.ENVIRONMENT = "production"
            settings.ADMIN_TOKEN = ""

            # Ensure demo_merchant exists
            m_user = self.repo.get_user_by_username("demo_merchant")
            if not m_user:
                m_user = self.repo.create_user("usr_demo_merchant", "demo_merchant", "Merchant One", "Owner", "hash", role="merchant")

            m_token = "merchant-session-token-111"
            self.repo.create_session(m_token, m_user.id, "2099-01-01T00:00:00Z")

            sample_csv = (
                "storefront_id,order_id,order_timestamp,product_id,quantity,gross_line_revenue,discount_amount,refund_amount,cogs_amount,attribution_channel,currency\n"
                "store-merchant-1,ord-m1,2026-10-15T12:00:00Z,item-001,1,100.00,10.00,0.00,40.00,organic_search,USD\n"
            )

            # 1. Preview succeeds with HTTP 200
            preview_res = self.client.post(
                "/api/v1/analytics/multi-store/preview",
                json={"import_type": "orders", "csv_content": sample_csv, "filename": "m1_orders.csv"},
                cookies={"faircart_session": m_token},
            )
            self.assertEqual(preview_res.status_code, 200)
            self.assertTrue(preview_res.json()["valid"])

            # 2. Import succeeds with HTTP 200
            import_res = self.client.post(
                "/api/v1/analytics/multi-store/import",
                json={"import_type": "orders", "csv_content": sample_csv, "filename": "m1_orders.csv"},
                cookies={"faircart_session": m_token},
            )
            self.assertEqual(import_res.status_code, 200)
            self.assertEqual(import_res.json()["accepted_rows"], 1)

            # 3. View profit metrics succeeds with HTTP 200
            profit_res = self.client.get(
                "/api/v1/analytics/multi-store/profit",
                cookies={"faircart_session": m_token},
            )
            self.assertEqual(profit_res.status_code, 200)
            p_data = profit_res.json()
            self.assertEqual(p_data["total_storefronts"], 1)
            self.assertEqual(p_data["storefronts"][0]["storefront_id"], "store-merchant-1")

            # 4. View import batches succeeds with HTTP 200
            batch_res = self.client.get(
                "/api/v1/analytics/multi-store/batches",
                cookies={"faircart_session": m_token},
            )
            self.assertEqual(batch_res.status_code, 200)
            self.assertEqual(len(batch_res.json()), 1)
            self.assertEqual(batch_res.json()[0]["filename"], "m1_orders.csv")

            # Clean up
            self.repo.delete_session(m_token)
        finally:
            settings.ENVIRONMENT = orig_env
            settings.ADMIN_TOKEN = orig_token

    def test_unauthenticated_requests_rejected_in_production(self):
        """In production, unauthenticated requests to merchant analytics return HTTP 401."""
        orig_env = settings.ENVIRONMENT
        orig_token = settings.ADMIN_TOKEN
        try:
            settings.ENVIRONMENT = "production"
            settings.ADMIN_TOKEN = ""

            # Unauthenticated GET /profit returns 401
            resp = self.client.get("/api/v1/analytics/multi-store/profit")
            self.assertEqual(resp.status_code, 401)
            self.assertIn("Merchant authentication required", resp.json()["detail"])

            # Unauthenticated POST /preview returns 401
            resp = self.client.post("/api/v1/analytics/multi-store/preview", json={"import_type": "orders", "csv_content": "dummy", "filename": "test.csv"})
            self.assertEqual(resp.status_code, 401)

            # Unauthenticated POST /import returns 401
            resp = self.client.post("/api/v1/analytics/multi-store/import", json={"import_type": "orders", "csv_content": "dummy", "filename": "test.csv"})
            self.assertEqual(resp.status_code, 401)

            # Unauthenticated GET /batches returns 401
            resp = self.client.get("/api/v1/analytics/multi-store/batches")
            self.assertEqual(resp.status_code, 401)
        finally:
            settings.ENVIRONMENT = orig_env
            settings.ADMIN_TOKEN = orig_token

    def test_cross_merchant_access_prevention(self):
        """Merchant B cannot access or delete Merchant A's data or audit batches."""
        # 1. Create two distinct merchants
        m1 = self.repo.get_user_by_username("demo_merchant")
        if not m1:
            m1 = self.repo.create_user("usr_demo_merchant", "demo_merchant", "Merchant One", "Owner", "hash1", role="merchant")
        m2 = self.repo.get_user_by_username("demo_merchant_2")
        if not m2:
            m2 = self.repo.create_user("usr_demo_merchant_2", "demo_merchant_2", "Merchant Two", "Owner", "hash2", role="merchant")

        tok1 = "token-merchant-1-aaa"
        tok2 = "token-merchant-2-bbb"
        self.repo.create_session(tok1, m1.id, "2099-01-01T00:00:00Z")
        self.repo.create_session(tok2, m2.id, "2099-01-01T00:00:00Z")

        try:
            # 2. Merchant 1 imports store-alpha
            csv_m1 = (
                "storefront_id,order_id,order_timestamp,product_id,quantity,gross_line_revenue,discount_amount,refund_amount,cogs_amount,attribution_channel,currency\n"
                "store-alpha,ord-a1,2026-10-15T12:00:00Z,item-001,1,200.00,0.00,0.00,80.00,direct,USD\n"
            )
            self.client.post(
                "/api/v1/analytics/multi-store/import",
                json={"import_type": "orders", "csv_content": csv_m1, "filename": "m1_alpha.csv"},
                headers={"Authorization": f"Bearer {tok1}"},
            )

            # 3. Merchant 2 imports store-beta
            csv_m2 = (
                "storefront_id,order_id,order_timestamp,product_id,quantity,gross_line_revenue,discount_amount,refund_amount,cogs_amount,attribution_channel,currency\n"
                "store-beta,ord-b1,2026-10-15T12:00:00Z,item-002,1,150.00,0.00,0.00,50.00,direct,USD\n"
            )
            self.client.post(
                "/api/v1/analytics/multi-store/import",
                json={"import_type": "orders", "csv_content": csv_m2, "filename": "m2_beta.csv"},
                headers={"Authorization": f"Bearer {tok2}"},
            )

            # 4. Merchant 1 queries profit: sees ONLY store-alpha
            p1 = self.client.get("/api/v1/analytics/multi-store/profit", headers={"Authorization": f"Bearer {tok1}"}).json()
            self.assertEqual(p1["total_storefronts"], 1)
            self.assertEqual(p1["storefronts"][0]["storefront_id"], "store-alpha")
            self.assertEqual(p1["storefronts"][0]["gross_revenue"], 200.0)

            # 5. Merchant 2 queries profit: sees ONLY store-beta
            p2 = self.client.get("/api/v1/analytics/multi-store/profit", headers={"Authorization": f"Bearer {tok2}"}).json()
            self.assertEqual(p2["total_storefronts"], 1)
            self.assertEqual(p2["storefronts"][0]["storefront_id"], "store-beta")
            self.assertEqual(p2["storefronts"][0]["gross_revenue"], 150.0)

            # 6. Merchant 2 attempts to query store-alpha: returns 0 storefronts (cannot spy on Merchant 1)
            p2_spy = self.client.get(
                "/api/v1/analytics/multi-store/profit?storefront_id=store-alpha",
                headers={"Authorization": f"Bearer {tok2}"},
            ).json()
            self.assertEqual(p2_spy["total_storefronts"], 0)

            # 7. Merchant 2 attempts to delete store-alpha: deletes 0 lines because Merchant 2 doesn't own it
            del_attempt = self.client.delete(
                "/api/v1/analytics/multi-store/data?storefront_id=store-alpha",
                headers={"Authorization": f"Bearer {tok2}"},
            ).json()
            self.assertEqual(del_attempt["cleared"]["order_lines_cleared"], 0)

            # Confirm Merchant 1's store-alpha is completely intact
            p1_after = self.client.get("/api/v1/analytics/multi-store/profit", headers={"Authorization": f"Bearer {tok1}"}).json()
            self.assertEqual(p1_after["total_storefronts"], 1)
            self.assertEqual(p1_after["storefronts"][0]["gross_revenue"], 200.0)

            # 8. Merchant 1 views batches: only sees m1_alpha.csv
            b1 = self.client.get("/api/v1/analytics/multi-store/batches", headers={"Authorization": f"Bearer {tok1}"}).json()
            self.assertEqual(len(b1), 1)
            self.assertEqual(b1[0]["filename"], "m1_alpha.csv")

            # Merchant 2 views batches: only sees m2_beta.csv
            b2 = self.client.get("/api/v1/analytics/multi-store/batches", headers={"Authorization": f"Bearer {tok2}"}).json()
            self.assertEqual(len(b2), 1)
            self.assertEqual(b2[0]["filename"], "m2_beta.csv")

        finally:
            self.repo.delete_session(tok1)
            self.repo.delete_session(tok2)

    def test_global_destructive_operation_requires_admin_authorization(self):
        """Global DELETE /data without storefront_id is restricted to explicit administrative authorization."""
        m_user = self.repo.get_user_by_username("demo_merchant")
        if not m_user:
            m_user = self.repo.create_user("usr_demo_merchant", "demo_merchant", "Merchant One", "Owner", "hash", role="merchant")
        m_token = "merchant-session-token-333"
        self.repo.create_session(m_token, m_user.id, "2099-01-01T00:00:00Z")

        orig_env = settings.ENVIRONMENT
        orig_token = settings.ADMIN_TOKEN
        try:
            settings.ENVIRONMENT = "production"
            settings.ADMIN_TOKEN = "admin-secret-xyz"

            # Merchant session attempting global deletion (no storefront_id) is rejected with 403
            resp = self.client.delete(
                "/api/v1/analytics/multi-store/data",
                cookies={"faircart_session": m_token},
            )
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Merchant authorization required", resp.json()["detail"])

            # Passing valid ADMIN_TOKEN succeeds
            admin_resp = self.client.delete(
                "/api/v1/analytics/multi-store/data",
                headers={"X-Admin-Token": "admin-secret-xyz"},
            )
            self.assertEqual(admin_resp.status_code, 200)
            self.assertEqual(admin_resp.json()["storefront_id"], "all")
        finally:
            self.repo.delete_session(m_token)
            settings.ENVIRONMENT = orig_env
            settings.ADMIN_TOKEN = orig_token

    def test_schema_migration_idempotency_and_safe_backfill(self):
        """Migration logic runs repeatedly without data loss and preserves safe default tenant scoping."""
        import sqlite3
        temp_db = str(Path(self.temp_dir.name) / "test_migration_idempotency.db")
        # Run init_db multiple times to test idempotency
        init_db(temp_db)
        init_db(temp_db)
        init_db(temp_db)

        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check users table columns and default
        cursor.execute("PRAGMA table_info(users);")
        u_cols = {r["name"]: r for r in cursor.fetchall()}
        self.assertIn("role", u_cols)
        self.assertEqual(u_cols["role"]["dflt_value"], "'customer'")

        # Check multi-store tables and default
        for tbl in ("storefront_import_batches", "storefront_order_lines", "storefront_traffic_events"):
            cursor.execute(f"PRAGMA table_info({tbl});")
            cols = {r["name"]: r for r in cursor.fetchall()}
            self.assertIn("merchant_id", cols)
            self.assertEqual(cols["merchant_id"]["dflt_value"], "'usr_demo_merchant'")

        conn.close()

    def test_benchmark_demo_storefront_protected_from_deletion_by_ordinary_demo_user(self):
        """In production, ordinary demo merchant sessions cannot delete the protected benchmark demonstration storefronts."""
        m_user = self.repo.get_user_by_username("demo_merchant")
        if not m_user:
            m_user = self.repo.create_user("usr_demo_merchant", "demo_merchant", "Merchant One", "Owner", "hash", role="merchant")
        m_token = "demo-merchant-protect-token-999"
        self.repo.create_session(m_token, m_user.id, "2099-01-01T00:00:00Z")

        orig_env = settings.ENVIRONMENT
        orig_token = settings.ADMIN_TOKEN
        try:
            settings.ENVIRONMENT = "production"
            settings.ADMIN_TOKEN = "admin-secret-xyz"

            # Attempting to delete protected benchmark storefront 'store-alpha-tech' with only a demo merchant session returns 403
            resp = self.client.delete(
                "/api/v1/analytics/multi-store/data?storefront_id=store-alpha-tech",
                cookies={"faircart_session": m_token},
            )
            self.assertEqual(resp.status_code, 403)
            self.assertIn("protected benchmark demonstration dataset", resp.json()["detail"])

            # An authorized admin can delete it if needed
            admin_resp = self.client.delete(
                "/api/v1/analytics/multi-store/data?storefront_id=store-alpha-tech",
                headers={"X-Admin-Token": "admin-secret-xyz"},
            )
            self.assertEqual(admin_resp.status_code, 200)
        finally:
            self.repo.delete_session(m_token)
            settings.ENVIRONMENT = orig_env
            settings.ADMIN_TOKEN = orig_token


if __name__ == "__main__":
    unittest.main()

