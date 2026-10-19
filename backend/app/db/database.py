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


_DEFAULT = object()


def is_postgres(database_url: Any = _DEFAULT) -> bool:
    """Returns True if the active or specified database connection is PostgreSQL."""
    url = settings.DATABASE_URL if database_url is _DEFAULT else database_url
    if not url:
        return False
    clean = str(url).strip().lower()
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

    # 3. Translate INSERT OR REPLACE INTO sku_inventory
    elif "INSERT OR REPLACE INTO sku_inventory" in adapted:
        adapted = adapted.replace("INSERT OR REPLACE INTO sku_inventory", "INSERT INTO sku_inventory")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + (
                " ON CONFLICT (sku, storefront_id) DO UPDATE SET "
                "on_hand = EXCLUDED.on_hand, reserved = EXCLUDED.reserved, "
                "safety_stock = EXCLUDED.safety_stock, incoming = EXCLUDED.incoming, "
                "lead_time_days = EXCLUDED.lead_time_days, updated_at = EXCLUDED.updated_at;"
            )

    # 4. Translate INSERT OR REPLACE INTO demand_forecasts
    elif "INSERT OR REPLACE INTO demand_forecasts" in adapted:
        adapted = adapted.replace("INSERT OR REPLACE INTO demand_forecasts", "INSERT INTO demand_forecasts")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + (
                " ON CONFLICT (id) DO UPDATE SET "
                "point_forecast = EXCLUDED.point_forecast, lower_bound = EXCLUDED.lower_bound, "
                "upper_bound = EXCLUDED.upper_bound, confidence_level = EXCLUDED.confidence_level, "
                "method = EXCLUDED.method, wape = EXCLUDED.wape, mase = EXCLUDED.mase, "
                "forecast_bias = EXCLUDED.forecast_bias, metrics_json = EXCLUDED.metrics_json, "
                "created_at = EXCLUDED.created_at;"
            )

    # 5. Translate INSERT OR REPLACE INTO external_connector_configs
    elif "INSERT OR REPLACE INTO external_connector_configs" in adapted:
        adapted = adapted.replace("INSERT OR REPLACE INTO external_connector_configs", "INSERT INTO external_connector_configs")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + (
                " ON CONFLICT (id) DO UPDATE SET "
                "status = EXCLUDED.status, masked_account_id = EXCLUDED.masked_account_id, "
                "encrypted_credentials = EXCLUDED.encrypted_credentials, settings_json = EXCLUDED.settings_json, "
                "last_sync_at = EXCLUDED.last_sync_at, audit_log_json = EXCLUDED.audit_log_json, "
                "updated_at = EXCLUDED.updated_at;"
            )

    # 6. Translate INSERT OR REPLACE INTO decision_traces
    elif "INSERT OR REPLACE INTO decision_traces" in adapted:
        adapted = adapted.replace("INSERT OR REPLACE INTO decision_traces", "INSERT INTO decision_traces")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + (
                " ON CONFLICT (trace_id) DO UPDATE SET "
                "chosen_action = EXCLUDED.chosen_action, scarcity_lambda = EXCLUDED.scarcity_lambda, "
                "net_margin = EXCLUDED.net_margin, margin_floor_passed = EXCLUDED.margin_floor_passed, "
                "payload_json = EXCLUDED.payload_json, created_at = EXCLUDED.created_at;"
            )

    # 7. Translate INSERT OR REPLACE INTO storefront_import_batches
    elif "INSERT OR REPLACE INTO storefront_import_batches" in adapted:
        adapted = adapted.replace("INSERT OR REPLACE INTO storefront_import_batches", "INSERT INTO storefront_import_batches")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + (
                " ON CONFLICT (id) DO UPDATE SET "
                "status = EXCLUDED.status, total_rows = EXCLUDED.total_rows, "
                "accepted_rows = EXCLUDED.accepted_rows, rejected_rows = EXCLUDED.rejected_rows, "
                "errors_json = EXCLUDED.errors_json, imported_at = EXCLUDED.imported_at;"
            )

    # 8. Translate general INSERT OR IGNORE INTO <table>
    elif "INSERT OR IGNORE INTO" in adapted:
        adapted = adapted.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        if "ON CONFLICT" not in adapted:
            adapted = re.sub(r";\s*$", "", adapted.strip()) + " ON CONFLICT DO NOTHING;"

    # 9. Translate SQLite datetime('now') to PostgreSQL CURRENT_TIMESTAMP
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


class PooledPostgresConnectionWrapper(PostgresConnectionWrapper):
    """Wraps a pooled psycopg connection. Calling close() returns connection to pool instead of destroying socket."""

    def __init__(self, raw_conn, pool: "PostgresConnectionPool"):
        super().__init__(raw_conn)
        self._pool = pool
        self._closed = False

    def close(self):
        if not self._closed:
            self._closed = True
            self._pool.return_connection(self._conn)

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()


class PostgresConnectionPool:
    """Thread-safe connection pool for PostgreSQL (e.g. Neon Serverless Postgres).

    Eliminates redundant ~1.8s TLS/TCP connection handshakes on every repository query
    while ensuring thread-safe access, transaction isolation, and stale connection recovery.
    """

    def __init__(self, target_url: str, max_connections: int = 5, connect_timeout: int = 4):
        import queue
        import threading

        self.target_url = target_url
        self.max_connections = max_connections
        self.connect_timeout = connect_timeout
        self._pool: queue.Queue = queue.Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._active_count = 0

    def _create_raw_connection(self):
        import psycopg
        from psycopg.rows import dict_row

        pg_url = self.target_url.strip()
        if pg_url.startswith("postgres://"):
            pg_url = "postgresql://" + pg_url[11:]

        return psycopg.connect(pg_url, row_factory=dict_row, connect_timeout=self.connect_timeout)

    def get_connection(self) -> PooledPostgresConnectionWrapper:
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                if not conn.closed:
                    try:
                        conn.rollback()
                        return PooledPostgresConnectionWrapper(conn, self)
                    except Exception:
                        try:
                            conn.close()
                        except Exception:
                            pass
            except Exception:
                break

        # Pool empty or discarded dead connection: open fresh connection
        raw_conn = self._create_raw_connection()
        return PooledPostgresConnectionWrapper(raw_conn, self)

    def return_connection(self, raw_conn):
        if raw_conn.closed:
            return
        try:
            raw_conn.rollback()
            self._pool.put_nowait(raw_conn)
        except Exception:
            try:
                raw_conn.close()
            except Exception:
                pass

    def close_all(self):
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Exception:
                pass


import threading

_pg_pools: dict[str, PostgresConnectionPool] = {}
_pg_pools_lock = threading.Lock()


def get_postgres_pool(target_url: str) -> PostgresConnectionPool:
    """Retrieves or creates a thread-safe connection pool for the specified PostgreSQL target."""
    with _pg_pools_lock:
        if target_url not in _pg_pools:
            _pg_pools[target_url] = PostgresConnectionPool(target_url)
        return _pg_pools[target_url]


def close_all_postgres_pools() -> None:
    """Closes all underlying physical sockets across all active PostgreSQL connection pools."""
    with _pg_pools_lock:
        for pool in _pg_pools.values():
            pool.close_all()
        _pg_pools.clear()


def mask_db_url(url: str | None) -> str:
    """Masks credentials in a database URL for safe logging and error reporting (e.g. postgresql://***:***@host:port/db)."""
    if not url:
        return ""
    return re.sub(r"://([^:@\s]+)(?::([^@\s]+))?@", r"://***:***@", url)


def get_connection(
    db_path: str | None = None,
    database_url: str | None = None,
    allow_fallback: bool | None = None,
    use_pool: bool = True,
) -> Any:
    """Creates and returns an active database connection.
    
    If database_url (or settings.DATABASE_URL when db_path is not specified) is a valid PostgreSQL URI,
    connects via psycopg to PostgreSQL (e.g. Neon Serverless Postgres) using safe connection pooling.
    
    Persistence Safeguards:
    - In production (settings.ENVIRONMENT in ('production', 'prod')), silent fallback to SQLite
      is strictly forbidden to prevent silent ephemeral data loss on container restarts.
    - If allow_fallback is False, a connection failure will immediately raise a RuntimeError.
    - In development (settings.ENVIRONMENT != 'production') when allow_fallback is True (the default),
      it falls back to local SQLite with a warning for offline developer workflows.
    - Credentials in target_url are masked before any logging or exception messages.
    """
    if database_url is not None:
        target_url = database_url
    elif db_path is not None:
        target_url = None
    else:
        target_url = settings.DATABASE_URL

    is_prod = settings.ENVIRONMENT.lower() in ("production", "prod")
    fallback_permitted = False if is_prod else (allow_fallback if allow_fallback is not None else True)

    if is_postgres(target_url):
        masked_url = mask_db_url(target_url)
        try:
            if use_pool:
                pool = get_postgres_pool(target_url)
                return pool.get_connection()
            else:
                import psycopg
                from psycopg.rows import dict_row

                pg_url = target_url.strip()
                if pg_url.startswith("postgres://"):
                    pg_url = "postgresql://" + pg_url[11:]

                conn = psycopg.connect(pg_url, row_factory=dict_row, connect_timeout=4)
                return PostgresConnectionWrapper(conn)
        except Exception as e:
            if not fallback_permitted:
                logger.error(
                    f"CRITICAL: Failed to connect to PostgreSQL at '{masked_url}': {e}. "
                    f"Operation halted to prevent silent ephemeral SQLite fallback."
                )
                raise RuntimeError(
                    f"PostgreSQL connection failed to '{masked_url}': {e}. "
                    f"Silent SQLite fallback is prohibited in production or strict mode to prevent data loss."
                ) from e

            logger.warning(
                f"PostgreSQL connection to '{masked_url}' failed: {e}. "
                f"Development fallback permitted: using local SQLite database."
            )

    # SQLite fallback / default
    target_path = db_path or settings.DATABASE_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(
    db_path: str | None = None,
    database_url: str | None = None,
    allow_fallback: bool | None = None,
) -> None:
    """Initializes the database schema if tables do not exist and applies migrations.
    
    Compatible with both SQLite and PostgreSQL.
    """
    conn = get_connection(db_path, database_url, allow_fallback=allow_fallback)
    is_pg = isinstance(conn, PostgresConnectionWrapper)
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
        if not is_pg:
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
                role TEXT NOT NULL DEFAULT 'customer',
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")

        # Migration: ensure role column exists in users
        if is_pg:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'customer';")
        else:
            cursor.execute("PRAGMA table_info(users);")
            u_cols = [r[1] for r in cursor.fetchall()]
            if u_cols and "role" not in u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'customer';")

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

        # Multi-Store Import Batches (Step 5.20)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS storefront_import_batches (
                id TEXT PRIMARY KEY,
                merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant',
                storefront_id TEXT NOT NULL,
                import_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                schema_version TEXT NOT NULL DEFAULT '1.0',
                status TEXT NOT NULL,
                total_rows INTEGER NOT NULL DEFAULT 0,
                accepted_rows INTEGER NOT NULL DEFAULT 0,
                rejected_rows INTEGER NOT NULL DEFAULT 0,
                errors_json TEXT NOT NULL DEFAULT '[]',
                imported_at TEXT NOT NULL
            );
        """)

        # Multi-Store Order Lines (Step 5.20)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS storefront_order_lines (
                id TEXT PRIMARY KEY,
                merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant',
                batch_id TEXT NOT NULL,
                storefront_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                order_timestamp TEXT NOT NULL,
                order_status TEXT NOT NULL DEFAULT 'completed',
                currency TEXT NOT NULL DEFAULT 'USD',
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
                gross_line_revenue_cents INTEGER NOT NULL CHECK (gross_line_revenue_cents >= 0),
                discount_cents INTEGER NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
                refund_cents INTEGER NOT NULL DEFAULT 0 CHECK (refund_cents >= 0),
                cogs_cents INTEGER NOT NULL DEFAULT 0 CHECK (cogs_cents >= 0),
                attribution_channel TEXT NOT NULL DEFAULT 'unattributed'
            );
        """)

        # Multi-Store Traffic & Funnel Events (Step 5.20)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS storefront_traffic_events (
                id TEXT PRIMARY KEY,
                merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant',
                batch_id TEXT NOT NULL,
                storefront_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                acquisition_channel TEXT NOT NULL DEFAULT 'direct',
                product_id TEXT NOT NULL DEFAULT '',
                order_id TEXT NOT NULL DEFAULT ''
            );
        """)

        # Multi-Store Migration: ensure merchant_id column exists before creating indexes on it
        if is_pg:
            cursor.execute("ALTER TABLE storefront_import_batches ADD COLUMN IF NOT EXISTS merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant';")
            cursor.execute("ALTER TABLE storefront_order_lines ADD COLUMN IF NOT EXISTS merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant';")
            cursor.execute("ALTER TABLE storefront_traffic_events ADD COLUMN IF NOT EXISTS merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant';")
        else:
            for tbl in ("storefront_import_batches", "storefront_order_lines", "storefront_traffic_events"):
                cursor.execute(f"PRAGMA table_info({tbl});")
                cols = [r[1] for r in cursor.fetchall()]
                if cols and "merchant_id" not in cols:
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant';")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_merchant ON storefront_import_batches(merchant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_storefront ON storefront_import_batches(storefront_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sol_merchant_store ON storefront_order_lines(merchant_id, storefront_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sol_store_time ON storefront_order_lines(storefront_id, order_timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sol_order ON storefront_order_lines(order_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sol_channel ON storefront_order_lines(attribution_channel);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ste_merchant_store ON storefront_traffic_events(merchant_id, storefront_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ste_store_time ON storefront_traffic_events(storefront_id, event_timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ste_session ON storefront_traffic_events(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ste_channel ON storefront_traffic_events(acquisition_channel);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ste_event_type ON storefront_traffic_events(event_type);")

        # Decision Twin: SKU Inventory & ATP Tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sku_inventory (
                sku TEXT NOT NULL,
                storefront_id TEXT NOT NULL DEFAULT 'primary_storefront',
                on_hand INTEGER NOT NULL DEFAULT 50 CHECK (on_hand >= 0),
                reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
                safety_stock INTEGER NOT NULL DEFAULT 10 CHECK (safety_stock >= 0),
                incoming INTEGER NOT NULL DEFAULT 0 CHECK (incoming >= 0),
                lead_time_days INTEGER NOT NULL DEFAULT 7 CHECK (lead_time_days >= 1),
                updated_at TEXT NOT NULL,
                PRIMARY KEY (sku, storefront_id)
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_storefront ON sku_inventory(storefront_id);")

        # Decision Twin: Multi-Horizon Predictive Demand Forecasts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS demand_forecasts (
                id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                storefront_id TEXT NOT NULL DEFAULT 'primary_storefront',
                horizon_days INTEGER NOT NULL,
                forecast_date TEXT NOT NULL,
                point_forecast REAL NOT NULL,
                lower_bound REAL NOT NULL,
                upper_bound REAL NOT NULL,
                confidence_level REAL NOT NULL DEFAULT 0.95,
                method TEXT NOT NULL,
                wape REAL NOT NULL DEFAULT 0.0,
                mase REAL NOT NULL DEFAULT 0.0,
                forecast_bias REAL NOT NULL DEFAULT 0.0,
                metrics_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_forecast_sku ON demand_forecasts(sku);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_forecast_store_horizon ON demand_forecasts(storefront_id, horizon_days);")

        # Decision Twin: External Analytics Connector Configurations (GA4 / Shopify)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_connector_configs (
                id TEXT PRIMARY KEY,
                merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant',
                provider TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unconfigured',
                masked_account_id TEXT,
                encrypted_credentials TEXT NOT NULL DEFAULT '',
                settings_json TEXT NOT NULL DEFAULT '{}',
                last_sync_at TEXT,
                audit_log_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_connector_merchant_provider ON external_connector_configs(merchant_id, provider);")

        # Decision Twin: Traceable Decision Audit Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_traces (
                trace_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                merchant_id TEXT NOT NULL DEFAULT 'usr_demo_merchant',
                storefront_id TEXT NOT NULL DEFAULT 'primary_storefront',
                chosen_action TEXT NOT NULL,
                scarcity_lambda REAL NOT NULL DEFAULT 0.0,
                net_margin REAL NOT NULL,
                margin_floor_passed BOOLEAN NOT NULL DEFAULT TRUE,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_traces_session ON decision_traces(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_traces_merchant ON decision_traces(merchant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_traces_created ON decision_traces(created_at);")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
