import unittest
import os
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient

from fastapi.middleware.cors import CORSMiddleware

from backend.app.main import app, resolve_cors_origins
from backend.app.db.database import init_db, get_connection
from backend.app.db.repository import CatalogRepository
from backend.scripts.seed_catalog import seed_catalog, SAMPLE_PRODUCTS

class TestFoundationAndHealth(unittest.TestCase):
    """Milestone 1 Foundation tests covering DB, Seed Data, Repository, and Health API."""

    @classmethod
    def setUpClass(cls):
        # Create a temporary database file for isolated testing
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_path = cls.temp_db.name
        cls.temp_db.close()
        
        # Seed test database
        seed_catalog(cls.temp_db_path)
        cls.repo = CatalogRepository(cls.temp_db_path)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        # Clean up temporary database file
        if os.path.exists(cls.temp_db_path):
            try:
                os.remove(cls.temp_db_path)
            except Exception:
                pass

    def test_database_has_twenty_products(self):
        """Verifies that the catalog contains all verified seed products."""
        count = self.repo.count_products()
        self.assertEqual(count, len(SAMPLE_PRODUCTS), f"Expected {len(SAMPLE_PRODUCTS)} products, found {count}")

    def test_product_schema_and_financial_positivity(self):
        """Verifies that all seeded products have valid prices, non-negative COGS, and stock."""
        products = self.repo.get_all_products()
        self.assertEqual(len(products), len(SAMPLE_PRODUCTS))
        
        for p in products:
            self.assertTrue(p.id.startswith("item-"), f"Invalid ID format: {p.id}")
            self.assertGreater(p.reference_price, 0.0, f"Price must be positive: {p.id}")
            self.assertGreaterEqual(p.cogs, 0.0, f"COGS cannot be negative: {p.id}")
            self.assertLess(p.cogs, p.reference_price, f"COGS should be less than reference price for profitability: {p.id}")
            self.assertGreater(p.inventory, 0, f"Initial inventory must be positive: {p.id}")
            self.assertTrue(len(p.complementary_ids) > 0, f"Must have complementary accessories: {p.id}")
            self.assertTrue(len(p.use_cases) > 0, f"Must have supported use cases: {p.id}")

    def test_repository_get_by_id(self):
        """Verifies single item retrieval and integer-cent precision."""
        product = self.repo.get_product_by_id("item-001")
        self.assertIsNotNone(product)
        self.assertEqual(product.name, "Ergonomic Mechanical Keyboard")
        self.assertEqual(product.reference_price, 80.00)
        self.assertEqual(product.cogs, 40.00)
        self.assertIn("item-002", product.complementary_ids)

    def test_repository_get_by_ids(self):
        """Verifies batch retrieval for basket queries."""
        items = self.repo.get_products_by_ids(["item-001", "item-002"])
        self.assertEqual(len(items), 2)
        ids = [i.id for i in items]
        self.assertIn("item-001", ids)
        self.assertIn("item-002", ids)

    def test_health_endpoint(self):
        """Verifies that GET /api/v1/health returns 200 OK with correct schema."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "sqlite")
        self.assertGreaterEqual(data["catalog_items_loaded"], 20)
        self.assertIn("gemini_configured", data)
        self.assertIn("version", data)

    def test_health_endpoint_reports_unhealthy_on_db_failure(self):
        """Verifies health check endpoint returns 503 and unhealthy status if database query fails."""
        with patch.object(CatalogRepository, "count_products", side_effect=Exception("Database connection terminated")):
            response = self.client.get("/api/v1/health")
            self.assertEqual(response.status_code, 503)
            data = response.json()
            self.assertEqual(data["status"], "unhealthy")
            self.assertEqual(data["catalog_items_loaded"], 0)
            self.assertIn("unhealthy", data["database"])

    def test_root_endpoint(self):
        """Verifies root endpoint returns basic API discovery information."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("documentation", data)
        self.assertIn("health", data)

    def test_cors_preflight_headers_with_allowed_origin(self):
        """Verifies CORS preflight OPTIONS request returns correct origin and credential headers."""
        response = self.client.options(
            "/api/v1/catalog",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_cors_preflight_unallowed_origin_rejected(self):
        """Verifies CORS preflight from unallowed origin does NOT return allow-origin header."""
        response = self.client.options(
            "/api/v1/catalog",
            headers={
                "Origin": "https://unauthorized-attacker.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertIsNone(response.headers.get("access-control-allow-origin"))

    def test_production_wildcard_cors_rejected(self):
        """Verifies wildcard '*' in production mode raises RuntimeError preventing insecure startup."""
        with self.assertRaises(RuntimeError) as ctx:
            resolve_cors_origins("*", environment="production")
        self.assertIn("Wildcard '*' origin is prohibited in production", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx2:
            resolve_cors_origins("https://faircart.onrender.com, *", environment="production")
        self.assertIn("Wildcard '*' origin is prohibited in production", str(ctx2.exception))

        with self.assertRaises(RuntimeError) as ctx3:
            resolve_cors_origins("*", environment="prod")
        self.assertIn("Wildcard '*' origin is prohibited in production", str(ctx3.exception))

        with self.assertRaises(RuntimeError) as ctx4:
            resolve_cors_origins("", environment="production")
        self.assertIn("CORS_ORIGINS cannot be empty in production", str(ctx4.exception))

    def test_explicit_origin_normalization_and_functionality(self):
        """Verifies explicit origins are trimmed, trailing slashes removed, and deduplicated."""
        origins = resolve_cors_origins(
            "https://faircart.onrender.com/,  https://store.example.com  , https://faircart.onrender.com",
            environment="production",
        )
        self.assertEqual(origins, ["https://faircart.onrender.com", "https://store.example.com"])

        # Local development defaults when omitted
        dev_origins = resolve_cors_origins("", environment="development")
        self.assertIn("http://localhost:5173", dev_origins)
        self.assertIn("http://127.0.0.1:5173", dev_origins)

    def test_development_wildcard_cors_rejected(self):
        """Verifies wildcard '*' is rejected even in development with ValueError rather than silent fallback."""
        with self.assertRaises(ValueError) as ctx:
            resolve_cors_origins("*", environment="development")
        self.assertIn("Wildcard '*' origin cannot be used when allow_credentials=True", str(ctx.exception))

    def test_zero_silent_fallback_to_wildcard(self):
        """Verifies that CORS middleware never configures wildcard allow_origins with credentials enabled."""
        # Check active FastAPI app middleware configuration
        cors_middlewares = [m for m in app.user_middleware if m.cls == CORSMiddleware]
        self.assertTrue(len(cors_middlewares) > 0, "CORSMiddleware must be present on app")
        kwargs = cors_middlewares[0].kwargs
        self.assertTrue(kwargs.get("allow_credentials"), "allow_credentials must remain True")
        configured_origins = kwargs.get("allow_origins", [])
        self.assertNotIn("*", configured_origins, "Configured origins must never contain wildcard '*'")
        self.assertNotEqual(configured_origins, ["*"], "Configured origins must never fall back to ['*']")

    def test_merchant_settings_endpoint(self):
        """Verifies GET and POST /api/v1/settings for merchant margin floor and discount cap."""
        # Read current settings
        res = self.client.get("/api/v1/settings")
        self.assertEqual(res.status_code, 200)
        settings = res.json()
        self.assertIn("margin_floor", settings)
        self.assertIn("discount_cap", settings)

        # Update settings
        update_payload = {"margin_floor": 0.25, "discount_cap": 0.15}
        post_res = self.client.post("/api/v1/settings", json=update_payload)
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.json()["status"], "updated")

        # Verify persisted values
        verify_res = self.client.get("/api/v1/settings")
        self.assertEqual(verify_res.status_code, 200)
        updated_settings = verify_res.json()
        self.assertEqual(updated_settings["margin_floor"], 0.25)
        self.assertEqual(updated_settings["discount_cap"], 0.15)

        # Restore default 20%/20%
        self.client.post("/api/v1/settings", json={"margin_floor": 0.20, "discount_cap": 0.20})

if __name__ == "__main__":
    unittest.main()
