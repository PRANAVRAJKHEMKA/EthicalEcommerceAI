import unittest
import os
import tempfile
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.database import init_db
from backend.app.db.repository import CatalogRepository
from backend.scripts.seed_catalog import seed_catalog

class TestCatalogAPI(unittest.TestCase):
    """API contract and business logic tests for GET /api/v1/catalog."""

    @classmethod
    def setUpClass(cls):
        # Create a temporary database file for isolated testing
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_path = cls.temp_db.name
        cls.temp_db.close()
        
        # Seed test database
        seed_catalog(cls.temp_db_path)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        # Clean up temporary database file
        if os.path.exists(cls.temp_db_path):
            try:
                os.remove(cls.temp_db_path)
            except Exception:
                pass

    def test_catalog_endpoint_returns_twenty_products(self):
        """Verifies GET /api/v1/catalog returns 200 OK and exactly 20 validated products."""
        response = self.client.get("/api/v1/catalog")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 20)
        
        # Verify schema of the first item
        first_item = data[0]
        required_fields = [
            "id", "name", "category", "description",
            "reference_price", "cogs", "inventory",
            "complementary_ids", "image_url"
        ]
        for field in required_fields:
            self.assertIn(field, first_item, f"Missing required field: {field}")

    def test_catalog_monetary_consistency(self):
        """Verifies all reference prices and wholesale COGS are positive with 2-decimal precision."""
        response = self.client.get("/api/v1/catalog")
        self.assertEqual(response.status_code, 200)
        
        for item in response.json():
            price = item["reference_price"]
            cogs = item["cogs"]
            self.assertGreater(price, 0.0)
            self.assertGreater(cogs, 0.0)
            self.assertLess(cogs, price, f"COGS must be less than reference price for item {item['id']}")
            # Check 2-decimal rounding
            self.assertEqual(price, round(price, 2))
            self.assertEqual(cogs, round(cogs, 2))

    def test_catalog_category_coverage(self):
        """Verifies that all expected categories are present."""
        response = self.client.get("/api/v1/catalog")
        categories = {item["category"] for item in response.json()}
        expected_categories = {"Keyboards", "Accessories", "Mice", "Workspace", "Audio & Video", "Power & Cables"}
        for cat in expected_categories:
            self.assertIn(cat, categories, f"Expected category {cat} missing from catalog")

    def test_empty_catalog_handling(self):
        """Verifies that an unseeded database safely returns an empty list rather than an error."""
        empty_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        empty_db_path = empty_db.name
        empty_db.close()
        try:
            init_db(empty_db_path)
            empty_repo = CatalogRepository(empty_db_path)
            products = empty_repo.get_all_products()
            self.assertEqual(products, [])
            self.assertEqual(empty_repo.count_products(), 0)
        finally:
            if os.path.exists(empty_db_path):
                os.remove(empty_db_path)

if __name__ == "__main__":
    unittest.main()
