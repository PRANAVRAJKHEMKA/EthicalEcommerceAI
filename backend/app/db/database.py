"""FairCart AI — Unified Database & Persistence Layer (Milestone 6C)

Supports dual database runtimes:
1. SQLite (default, zero configuration for local development and offline testing).
2. PostgreSQL (e.g. Neon Serverless PostgreSQL for permanent, durable cloud persistence).
Configured seamlessly via DATABASE_URL environment variable.
"""

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from backend.app.config import settings

logger = logging.getLogger("faircart.db")


def is_postgres(database_url: str | None = None) -> bool:
    """Returns True if the active or specified database connection is PostgreSQL."""
    url = database_url if database_url is not None else settings.DATABASE_URL
    if not url:
        return False
    clean = url.strip().lower()
    return clean.startswith("postgres://") or clean.startswith("postgresql://")


def adapt_sql_for_postgres(sql: str) -> str:
    """Translates SQLite query patterns to PostgreSQL ANSI SQL."""
    adapted = sql.strip()

    # 1. Translate INSERT OR REPLACE INTO merchant_settings
    if "INSERT OR REPLACE INTO merchant_settings" in adapted:
        adapted = adapted.replace("INSERT OR REPLACE INTO merchant_settings", "INSERT INTO merchant_settings")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + (
                " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at;"
            )

    # 2. Translate INSERT OR REPLACE INTO products
    elif "INSERT OR REPLACE INTO products" in adapted:
        adapted = adapted.replace("INSERT OR REPLACE INTO products", "INSERT INTO products")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + (
                " ON CONFLICT (id) DO UPDATE SET "
                "name = EXCLUDED.name, category = EXCLUDED.category, subcategory = EXCLUDED.subcategory, "
                "description = EXCLUDED.description, reference_price_cents = EXCLUDED.reference_price_cents, "
                "cogs_cents = EXCLUDED.cogs_cents, inventory = EXCLUDED.inventory, "
                "complementary_ids = EXCLUDED.complementary_ids, tags = EXCLUDED.tags, "
                "use_cases = EXCLUDED.use_cases, image_url = EXCLUDED.image_url;"
            )

    # 3. Translate general INSERT OR IGNORE INTO <table>
    elif "INSERT OR IGNORE INTO" in adapted:
        adapted = adapted.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + " ON CONFLICT DO NOTHING;"

    # 4. Translate SQLite datetime('now') to PostgreSQL CURRENT_TIMESTAMP
    adapted = adapted.replace("datetime('now')", "CURRENT_TIMESTAMP")

    # 5. Parameter placeholders: SQLite ? -> PostgreSQL %s
    adapted = adapted.replace("?", "%s")

    return adapted


class DictRowCompat(dict):
    """Provides dual key and integer index access compatible with sqlite3.Row."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PostgresCursorWrapper:
    """Wraps a psycopg Cursor to match sqlite3.Cursor interface and translate SQLite dialect."""

    def __init__(self, raw_cursor):
        self._cur = raw_cursor

    def execute(self, query: str, params: Any = None):
        adapted = adapt_sql_for_postgres(query)
        if params is not None:
            if isinstance(params, tuple):
                params = list(params)
            return self._cur.execute(adapted, params)
        return self._cur.execute(adapted)

    def executemany(self, query: str, seq_of_params):
        adapted = adapt_sql_for_postgres(query)
        return self._cur.executemany(adapted, seq_of_params)

    def fetchone(self):
        row = self._cur.fetchone()
        return DictRowCompat(row) if row is not None else None

    def fetchall(self):
        rows = self._cur.fetchall()
        return [DictRowCompat(r) for r in rows] if rows else []

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        return [DictRowCompat(r) for r in rows] if rows else []

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        return self._cur.close()


class PostgresConnectionWrapper:
    """Wraps a psycopg Connection to provide sqlite3-like dictionary row access and transaction management."""

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()


def get_connection(db_path: str | None = None, database_url: str | None = None) -> Any:
    """Creates and returns an active database connection.
    
    If database_url (or settings.DATABASE_URL) is a valid PostgreSQL URI, connects via
    psycopg to PostgreSQL (e.g. Neon Serverless Postgres). Otherwise, returns a standard
    SQLite connection with Row dictionary mapping.
    """
    target_url = database_url if database_url is not None else settings.DATABASE_URL
    if is_postgres(target_url):
        try:
            import psycopg
            from psycopg.rows import dict_row

            pg_url = target_url.strip()
            if pg_url.startswith("postgres://"):
                pg_url = "postgresql://" + pg_url[11:]

            conn = psycopg.connect(pg_url, row_factory=dict_row, connect_timeout=2)
            return PostgresConnectionWrapper(conn)
        except Exception as e:
            logger.warning(
                f"PostgreSQL connection to '{target_url[:25]}...' failed: {e}. "
                f"Falling back gracefully to local SQLite database."
            )

    # SQLite fallback / default
    target_path = db_path or settings.DATABASE_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None, database_url: str | None = None) -> None:
    """Initializes the database schema if tables do not exist and applies migrations.
    
    Compatible with both SQLite and PostgreSQL.
    """
    target_url = database_url if database_url is not None else settings.DATABASE_URL
    conn = get_connection(db_path, target_url)
    try:
        cursor = conn.cursor()

        # Products table: stores catalog with integer cents and rich contextual attributes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL,
                reference_price_cents INTEGER NOT NULL CHECK (reference_price_cents > 0),
                cogs_cents INTEGER NOT NULL CHECK (cogs_cents >= 0),
                inventory INTEGER NOT NULL DEFAULT 50 CHECK (inventory >= 0),
                complementary_ids TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '',
                use_cases TEXT NOT NULL DEFAULT '',
                image_url TEXT NOT NULL
            );
        """)

        # Migration helper for earlier SQLite schemas
        if not is_postgres(target_url):
            cursor.execute("PRAGMA table_info(products);")
            columns = [row["name"] for row in cursor.fetchall()]
            if "subcategory" not in columns:
                cursor.execute("ALTER TABLE products ADD COLUMN subcategory TEXT NOT NULL DEFAULT '';")
            if "tags" not in columns:
                cursor.execute("ALTER TABLE products ADD COLUMN tags TEXT NOT NULL DEFAULT '';")
            if "use_cases" not in columns:
                cursor.execute("ALTER TABLE products ADD COLUMN use_cases TEXT NOT NULL DEFAULT '';")

        # Decision audit logs: tracks every session recommendation & offer decision
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                shopping_context TEXT NOT NULL DEFAULT 'all',
                cart_items TEXT NOT NULL,
                recommended_product_id TEXT,
                decision_type TEXT NOT NULL,
                discount_percentage REAL NOT NULL,
                savings_cents INTEGER NOT NULL,
                basket_margin REAL NOT NULL,
                fallback_applied BOOLEAN NOT NULL,
                latency_ms REAL NOT NULL
            );
        """)

        # Merchant policy settings: persists margin floor and discount cap across restarts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS merchant_settings (
                key TEXT PRIMARY KEY,
                value REAL NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Default merchant settings if not set
        cursor.execute("""
            INSERT OR IGNORE INTO merchant_settings (key, value, updated_at)
            VALUES 
                ('margin_floor', 0.20, datetime('now')),
                ('discount_cap', 0.20, datetime('now'));
        """)

        # Anonymous Session Events: stores strictly anonymous browsing & interaction events (zero PII)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_events (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                product_id TEXT NOT NULL DEFAULT '',
                shopping_context TEXT NOT NULL DEFAULT 'all',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                timestamp TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_events_session ON session_events(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_events_timestamp ON session_events(timestamp);")

        # Association Rules from Historical/Synthetic Transactions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS basket_association_rules (
                id TEXT PRIMARY KEY,
                antecedent_ids TEXT NOT NULL,
                consequent_id TEXT NOT NULL,
                support REAL NOT NULL,
                confidence REAL NOT NULL,
                lift REAL NOT NULL,
                co_occurrence_count INTEGER NOT NULL,
                is_synthetic INTEGER NOT NULL DEFAULT 1
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assoc_antecedent ON basket_association_rules(antecedent_ids);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assoc_consequent ON basket_association_rules(consequent_id);")

        # Indexes for fast candidate filtering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_use_cases ON products(use_cases);")

        # Simulation Runs: stores historical 3-policy simulation comparator results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_runs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                random_seed INTEGER NOT NULL,
                num_sessions INTEGER NOT NULL,
                margin_floor REAL NOT NULL,
                discount_cap REAL NOT NULL,
                results_json TEXT NOT NULL,
                execution_latency_ms REAL NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_runs_timestamp ON simulation_runs(timestamp);")

        # Demonstration Users (Milestone 6B)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                persona_description TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")

        # Server-Validated User Sessions (Milestone 6B)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON user_sessions(expires_at);")

        # Account Orders: persistent itemized synthetic orders & simulated checkouts (Milestone 6B)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed_simulated',
                provenance TEXT NOT NULL DEFAULT 'synthetic_demonstration',
                currency TEXT NOT NULL DEFAULT 'USD',
                total_cents INTEGER NOT NULL,
                savings_cents INTEGER NOT NULL DEFAULT 0,
                items_json TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
