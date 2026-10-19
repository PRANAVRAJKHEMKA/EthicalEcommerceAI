"""FairCart AI — Database Persistence, Dual-Driver Dialect & Restart Tests (Milestone 6C)

Verifies:
1. SQLite and PostgreSQL dialect adaptation (ANSI SQL translation).
2. DictRowCompat key and integer index accessibility.
3. Restart persistence: data survival across connection lifecycles and server restarts.
4. Graceful connection failure fallback (no unhandled server crash when DB is unreachable).
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from backend.app.db.database import (
    adapt_sql_for_postgres,
    DictRowCompat,
    get_connection,
    init_db,
    is_postgres,
    mask_db_url,
    PostgresCursorWrapper,
    PostgresConnectionWrapper,
)
from backend.app.db.repository import CatalogRepository


class TestDatabasePersistence(unittest.TestCase):
    """Tests for database persistence, dialect translation, and restart resilience."""

    def test_postgres_url_detection(self):
        """Verifies PostgreSQL URI detection handles postgres:// and postgresql:// schemes."""
        self.assertTrue(is_postgres("postgres://user:pass@ep-xyz.neon.tech/neondb?sslmode=require"))
        self.assertTrue(is_postgres("postgresql://user:pass@ep-xyz.neon.tech/neondb"))
        self.assertFalse(is_postgres("sqlite:///faircart.db"))
        self.assertFalse(is_postgres("faircart.db"))
        self.assertFalse(is_postgres(None))

    def test_adapt_sql_for_postgres_placeholders(self):
        """Verifies ? parameter placeholders are converted to %s for psycopg."""
        sql = "SELECT * FROM products WHERE id = ? AND category = ?;"
        adapted = adapt_sql_for_postgres(sql)
        self.assertEqual(adapted, "SELECT * FROM products WHERE id = %s AND category = %s;")

    def test_adapt_sql_for_postgres_merchant_settings(self):
        """Verifies INSERT OR REPLACE for merchant settings translates to ON CONFLICT UPDATE."""
        sql = "INSERT OR REPLACE INTO merchant_settings (key, value, updated_at) VALUES (?, ?, datetime('now'));"
        adapted = adapt_sql_for_postgres(sql)
        self.assertNotIn("INSERT OR REPLACE", adapted)
        self.assertIn("ON CONFLICT (key) DO UPDATE", adapted)
        self.assertIn("CURRENT_TIMESTAMP", adapted)
        self.assertIn("%s, %s", adapted)

    def test_adapt_sql_for_postgres_products(self):
        """Verifies INSERT OR REPLACE for catalog products translates to ON CONFLICT UPDATE."""
        sql = "INSERT OR REPLACE INTO products (id, name) VALUES (?, ?);"
        adapted = adapt_sql_for_postgres(sql)
        self.assertNotIn("INSERT OR REPLACE", adapted)
        self.assertIn("ON CONFLICT (id) DO UPDATE", adapted)

    def test_adapt_sql_for_postgres_decision_twin_tables(self):
        """Verifies INSERT OR REPLACE for Decision Twin tables translates to ON CONFLICT UPDATE."""
        # 1. sku_inventory
        sql_inv = "INSERT OR REPLACE INTO sku_inventory (sku, storefront_id) VALUES (?, ?);"
        adapted_inv = adapt_sql_for_postgres(sql_inv)
        self.assertNotIn("INSERT OR REPLACE", adapted_inv)
        self.assertIn("ON CONFLICT (sku, storefront_id) DO UPDATE", adapted_inv)

        # 2. demand_forecasts
        sql_fc = "INSERT OR REPLACE INTO demand_forecasts (id, sku) VALUES (?, ?);"
        adapted_fc = adapt_sql_for_postgres(sql_fc)
        self.assertNotIn("INSERT OR REPLACE", adapted_fc)
        self.assertIn("ON CONFLICT (id) DO UPDATE", adapted_fc)

        # 3. external_connector_configs
        sql_conn = "INSERT OR REPLACE INTO external_connector_configs (id, provider) VALUES (?, ?);"
        adapted_conn = adapt_sql_for_postgres(sql_conn)
        self.assertNotIn("INSERT OR REPLACE", adapted_conn)
        self.assertIn("ON CONFLICT (id) DO UPDATE", adapted_conn)

        # 4. decision_traces
        sql_trc = "INSERT OR REPLACE INTO decision_traces (trace_id, session_id) VALUES (?, ?);"
        adapted_trc = adapt_sql_for_postgres(sql_trc)
        self.assertNotIn("INSERT OR REPLACE", adapted_trc)
        self.assertIn("ON CONFLICT (trace_id) DO UPDATE", adapted_trc)

    def test_adapt_sql_for_postgres_insert_ignore(self):
        """Verifies INSERT OR IGNORE translates to ON CONFLICT DO NOTHING."""
        sql = "INSERT OR IGNORE INTO session_events (id, session_id) VALUES (?, ?);"
        adapted = adapt_sql_for_postgres(sql)
        self.assertNotIn("INSERT OR IGNORE", adapted)
        self.assertIn("ON CONFLICT DO NOTHING", adapted)

    def test_dict_row_compat_supports_key_and_index(self):
        """Verifies DictRowCompat allows access by column name AND integer index (matching sqlite3.Row)."""
        row = DictRowCompat({"id": "item-001", "name": "Mechanical Keyboard", "count": 42})
        # Key access
        self.assertEqual(row["id"], "item-001")
        self.assertEqual(row["name"], "Mechanical Keyboard")
        self.assertEqual(row["count"], 42)
        # Integer index access (critical for row[0] aggregate queries)
        self.assertEqual(row[0], "item-001")
        self.assertEqual(row[1], "Mechanical Keyboard")
        self.assertEqual(row[2], 42)
        # Keys inspection
        self.assertIn("name", row.keys())

    def test_mask_db_url_redacts_credentials(self):
        """Verifies mask_db_url strips user and password completely from connection strings."""
        raw_url = "postgresql://my_user:secret_pass_123@ep-cool-456.aws.neon.tech/faircart_db?sslmode=require"
        masked = mask_db_url(raw_url)
        self.assertNotIn("my_user", masked)
        self.assertNotIn("secret_pass_123", masked)
        self.assertIn("postgresql://***:***@ep-cool-456.aws.neon.tech/faircart_db", masked)

    def test_unreachable_postgres_in_production_raises_startup_error(self):
        """Verifies that when production/strict mode is active, PostgreSQL connection failure raises RuntimeError instead of falling back to SQLite."""
        unreachable_url = "postgresql://dummy_user:dummy_pass@127.0.0.1:59999/nonexistent?connect_timeout=1"
        with self.assertRaises(RuntimeError) as ctx:
            get_connection(database_url=unreachable_url, allow_fallback=False)
        self.assertIn("Silent SQLite fallback is prohibited", str(ctx.exception))
        # Ensure credentials were not leaked into the exception message
        self.assertNotIn("dummy_pass", str(ctx.exception))
        self.assertIn("***:***", str(ctx.exception))

    def test_unreachable_postgres_url_falls_back_in_dev_when_permitted(self):
        """Verifies database layer falls back to SQLite with warning when dev fallback is explicitly permitted."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        try:
            # Provide an unreachable dummy Postgres URL with fast 1s timeout and allow_fallback=True
            unreachable_url = "postgresql://dummy_user:dummy_pass@127.0.0.1:59999/nonexistent?connect_timeout=1"
            conn = get_connection(db_path=temp_db, database_url=unreachable_url, allow_fallback=True)
            self.assertIsNotNone(conn)
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            self.assertEqual(cur.fetchone()[0], 1)
            conn.close()
        finally:
            if os.path.exists(temp_db):
                try:
                    os.unlink(temp_db)
                except OSError:
                    pass

    def test_restart_persistence_simulation(self):
        """Verifies data survives simulated backend restart and re-initialization."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        try:
            # Phase 1: Initialize schema and seed data
            init_db(db_path=temp_db)
            repo1 = CatalogRepository(db_path=temp_db)

            # Insert a simulated user order
            repo1.create_user(
                user_id="usr_restart_test",
                username="test_restart_user",
                display_name="Restart Tester",
                persona_description="Persistence evaluation account",
                password_hash="argon2_dummy_hash",
            )
            order_entity = repo1.create_order(
                order_id="ord_restart_001",
                user_id="usr_restart_test",
                created_at="2026-10-15T22:00:00Z",
                status="completed_simulated",
                provenance="simulated_checkout",
                currency="USD",
                total_cents=12500,
                savings_cents=1500,
                items_json=json.dumps([{"product_id": "item-001", "quantity": 1, "simulated_price": 80.0}]),
            )
            self.assertEqual(order_entity.id, "ord_restart_001")

            # Update merchant settings
            repo1.update_merchant_setting("margin_floor", 0.28)
            repo1.update_merchant_setting("discount_cap", 0.18)

            # Record a session event
            repo1.record_session_event(
                session_id="sess_restart_123",
                event_type="product_view",
                product_id="item-001",
                shopping_context="ergonomics",
                metadata={"dwell_ms": 1200},
            )

            # Simulate restart: destroy repo1 and all connections
            del repo1

            # Phase 2: Start new repository instance from the same database (post-restart)
            repo2 = CatalogRepository(db_path=temp_db)

            # Verify user exists
            user = repo2.get_user_by_username("test_restart_user")
            self.assertIsNotNone(user)
            self.assertEqual(user.display_name, "Restart Tester")

            # Verify order persisted
            orders = repo2.get_orders_for_user("usr_restart_test")
            self.assertEqual(len(orders), 1)
            self.assertEqual(orders[0].id, "ord_restart_001")
            self.assertEqual(orders[0].total_amount, 125.0)
            self.assertEqual(orders[0].total_savings, 15.0)

            # Verify merchant settings persisted
            settings = repo2.get_merchant_settings()
            self.assertEqual(settings["margin_floor"], 0.28)
            self.assertEqual(settings["discount_cap"], 0.18)

            # Verify session events persisted
            events = repo2.get_session_events("sess_restart_123")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["product_id"], "item-001")
            self.assertEqual(events[0]["shopping_context"], "ergonomics")

        finally:
            if os.path.exists(temp_db):
                try:
                    os.unlink(temp_db)
                except OSError:
                    pass

    def test_postgres_wrapper_order_and_settings_persistence(self):
        """Verifies PostgresConnectionWrapper and PostgresCursorWrapper correctly adapt and handle orders and merchant settings."""
        mock_raw_cursor = MagicMock()
        mock_raw_conn = MagicMock()
        mock_raw_conn.cursor.return_value = mock_raw_cursor

        wrapper = PostgresConnectionWrapper(mock_raw_conn)
        cur = wrapper.cursor()

        # 1. Updating merchant settings translates to ON CONFLICT UPDATE
        cur.execute(
            "INSERT OR REPLACE INTO merchant_settings (key, value, updated_at) VALUES (?, ?, datetime('now'));",
            ["margin_floor", 0.25],
        )
        called_sql = mock_raw_cursor.execute.call_args[0][0]
        called_params = mock_raw_cursor.execute.call_args[0][1]
        self.assertIn("ON CONFLICT (key) DO UPDATE", called_sql)
        self.assertEqual(called_params, ["margin_floor", 0.25])

        # 2. Creating order translates ? to %s
        cur.execute(
            "INSERT INTO orders (id, user_id, created_at, status, provenance, currency, total_cents, savings_cents, items_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            ["ord-pg-01", "usr-pg-01", "2026-10-15T23:00:00Z", "completed_simulated", "simulated_checkout", "USD", 5000, 500, "[]"],
        )
        called_order_sql = mock_raw_cursor.execute.call_args[0][0]
        self.assertNotIn("?", called_order_sql)
        self.assertIn("%s, %s, %s", called_order_sql)

        # 3. fetchone returns DictRowCompat supporting key and index access
        mock_raw_cursor.fetchone.return_value = {"id": "ord-pg-01", "total_cents": 5000}
        row = cur.fetchone()
        self.assertIsInstance(row, DictRowCompat)
        self.assertEqual(row["id"], "ord-pg-01")
        self.assertEqual(row[0], "ord-pg-01")


if __name__ == "__main__":
    unittest.main()
