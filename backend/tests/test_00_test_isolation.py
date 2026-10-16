"""Deterministic Test Isolation Bootstrap for FairCart AI.

Ensures that before any other test module executes, the test suite is explicitly
isolated from remote cloud databases (Neon PostgreSQL) configured in local .env files,
directing all tests hermetically to local SQLite fixtures.
"""

import os
import unittest

# Enforce test isolation before any other test module imports application code
os.environ["FAIRCART_TESTING"] = "1"
os.environ["DATABASE_URL"] = ""

from backend.app.config import settings

# Explicitly ensure settings.DATABASE_URL is None for the test suite
settings.DATABASE_URL = None


class TestTestIsolationBootstrap(unittest.TestCase):
    """Verifies that the test environment is hermetically isolated from live cloud databases."""

    def test_database_is_isolated_from_live_cloud(self):
        """Verifies settings.DATABASE_URL is None and test suite uses SQLite."""
        self.assertIsNone(settings.DATABASE_URL)
        self.assertEqual(os.environ.get("DATABASE_URL", ""), "")

    def test_health_reports_sqlite_under_test_isolation(self):
        """Verifies health check endpoint reports SQLite driver under test isolation."""
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)
        res = client.get("/api/v1/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["database"], "sqlite")
        self.assertEqual(data["status"], "healthy")
