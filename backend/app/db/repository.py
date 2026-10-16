import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from backend.app.config import settings
from backend.app.db.database import get_connection
from backend.app.models.schemas import Product

@dataclass(frozen=True)
class ProductEntity:
    """Internal authoritative domain entity maintaining integer-cent financial precision."""
    id: str
    name: str
    category: str
    description: str
    reference_price_cents: int
    cogs_cents: int
    inventory: int
    complementary_ids: tuple[str, ...]
    image_url: str
    subcategory: str = ""
    tags: tuple[str, ...] = ()
    use_cases: tuple[str, ...] = ()

    @property
    def reference_price(self) -> float:
        return round(self.reference_price_cents / 100.0, 2)

    @property
    def cogs(self) -> float:
        return round(self.cogs_cents / 100.0, 2)

    def to_product_schema(self) -> Product:
        return Product(
            id=self.id,
            name=self.name,
            category=self.category,
            subcategory=self.subcategory,
            description=self.description,
            reference_price=self.reference_price,
            cogs=self.cogs,
            inventory=self.inventory,
            complementary_ids=list(self.complementary_ids),
            tags=list(self.tags),
            use_cases=list(self.use_cases),
            image_url=self.image_url,
        )

@dataclass(frozen=True)
class UserEntity:
    """Internal user domain entity for authenticated demo accounts."""
    id: str
    username: str
    display_name: str
    persona_description: str
    password_hash: str
    created_at: str

@dataclass(frozen=True)
class OrderEntity:
    """Internal order domain entity representing past simulated purchases."""
    id: str
    user_id: str
    created_at: str
    status: str
    provenance: str
    currency: str
    total_cents: int
    savings_cents: int
    items_json: str

    @property
    def total_amount(self) -> float:
        return round(self.total_cents / 100.0, 2)

    @property
    def total_savings(self) -> float:
        return round(self.savings_cents / 100.0, 2)

    @property
    def items(self) -> list[dict]:
        try:
            return json.loads(self.items_json)
        except Exception:
            return []

class CatalogRepository:
    """Repository handling all database queries for the product catalog and merchant settings.

    Employs thread-safe, bounded in-process caching for static catalog products and merchant settings,
    eliminating redundant database round-trips while preserving full isolation and cache invalidation.
    """

    # Bounded in-process cache keyed by target database identifier
    _catalog_cache: dict[str, tuple[float, list[ProductEntity]]] = {}
    _settings_cache: dict[str, tuple[float, dict[str, float]]] = {}
    _cache_lock = threading.Lock()
    _CATALOG_TTL_SECONDS = 300.0  # 5 minutes for immutable catalog items
    _SETTINGS_TTL_SECONDS = 60.0  # 1 minute for merchant policy settings

    def __init__(
        self,
        db_path: str | None = None,
        database_url: str | None = None,
        allow_fallback: bool | None = None,
    ):
        self.db_path = db_path
        self.database_url = database_url
        self.allow_fallback = allow_fallback

    def _get_db_key(self) -> str:
        """Computes a unique key for the target database to ensure isolated cache entries."""
        if self.database_url:
            return f"pg:{self.database_url}"
        if self.db_path:
            return f"sqlite:{self.db_path}"
        active_url = settings.DATABASE_URL
        if active_url:
            return f"pg:{active_url}"
        return f"sqlite:{settings.DATABASE_PATH}"

    @classmethod
    def invalidate_cache(cls, db_key: str | None = None) -> None:
        """Invalidates in-process catalog and settings cache for a given database target or all targets."""
        with cls._cache_lock:
            if db_key is not None:
                cls._catalog_cache.pop(db_key, None)
                cls._settings_cache.pop(db_key, None)
            else:
                cls._catalog_cache.clear()
                cls._settings_cache.clear()

    def _get_connection(self):
        """Creates an active database connection using the configured path or database URL."""
        return get_connection(self.db_path, self.database_url, allow_fallback=self.allow_fallback)

    def _row_to_entity(self, row: sqlite3.Row) -> ProductEntity:
        """Converts an SQLite row into an immutable ProductEntity with integer cents."""
        comp_ids = tuple(cid.strip() for cid in row["complementary_ids"].split(",") if cid.strip())
        tags = tuple(t.strip() for t in (row["tags"] if "tags" in row.keys() and row["tags"] else "").split(",") if t.strip())
        use_cases = tuple(u.strip() for u in (row["use_cases"] if "use_cases" in row.keys() and row["use_cases"] else "").split(",") if u.strip())
        subcategory = row["subcategory"] if "subcategory" in row.keys() and row["subcategory"] else row["category"]

        return ProductEntity(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            description=row["description"],
            reference_price_cents=int(row["reference_price_cents"]),
            cogs_cents=int(row["cogs_cents"]),
            inventory=int(row["inventory"]),
            complementary_ids=comp_ids,
            image_url=row["image_url"],
            subcategory=subcategory,
            tags=tags,
            use_cases=use_cases,
        )

    def _row_to_product(self, row: sqlite3.Row) -> Product:
        """Converts an SQLite row to a public API Product model."""
        return self._row_to_entity(row).to_product_schema()

    def count_products(self) -> int:
        """Returns the total number of products in the catalog."""
        return len(self.get_all_entities())

    def get_all_products(self) -> list[Product]:
        """Retrieves all products from the catalog as public schema models."""
        return [e.to_product_schema() for e in self.get_all_entities()]

    def get_all_entities(self) -> list[ProductEntity]:
        """Retrieves all products from the catalog as authoritative integer-cent ProductEntities.

        Uses in-process caching to eliminate repetitive ~2s database network latency during high-frequency
        recommendation decision requests.
        """
        db_key = self._get_db_key()
        now = time.perf_counter()
        with self._cache_lock:
            cached = self._catalog_cache.get(db_key)
            if cached and (now - cached[0]) < self._CATALOG_TTL_SECONDS:
                return cached[1]

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products ORDER BY id ASC;")
            rows = cursor.fetchall()
            entities = [self._row_to_entity(r) for r in rows]
            with self._cache_lock:
                self._catalog_cache[db_key] = (now, entities)
            return entities
        finally:
            conn.close()

    def get_product_by_id(self, product_id: str) -> Product | None:
        """Retrieves a single product by its unique ID as a public schema model."""
        entity = self.get_entity_by_id(product_id)
        return entity.to_product_schema() if entity else None

    def get_entity_by_id(self, product_id: str) -> ProductEntity | None:
        """Retrieves a single product by its unique ID as an authoritative ProductEntity."""
        all_entities = self.get_all_entities()
        for e in all_entities:
            if e.id == product_id:
                return e
        return None

    def get_products_by_ids(self, product_ids: list[str]) -> list[Product]:
        """Retrieves multiple products given a list of IDs as public schema models."""
        return [e.to_product_schema() for e in self.get_entities_by_ids(product_ids)]

    def get_entities_by_ids(self, product_ids: list[str]) -> list[ProductEntity]:
        """Retrieves multiple products given a list of IDs as authoritative ProductEntities."""
        if not product_ids:
            return []
        all_entities = self.get_all_entities()
        entity_map = {e.id: e for e in all_entities}
        result = [entity_map[pid] for pid in product_ids if pid in entity_map]
        if len(result) == len(set(product_ids)):
            return result

        # Fallback to direct query if any requested product is missing from cache
        placeholders = ",".join("?" for _ in product_ids)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM products WHERE id IN ({placeholders});", product_ids)
            rows = cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]
        finally:
            conn.close()

    def get_merchant_settings(self) -> dict[str, float]:
        """Retrieves merchant policy settings (margin floor, discount cap) from SQLite with bounded caching."""
        db_key = self._get_db_key()
        now = time.perf_counter()
        with self._cache_lock:
            cached = self._settings_cache.get(db_key)
            if cached and (now - cached[0]) < self._SETTINGS_TTL_SECONDS:
                return dict(cached[1])

        settings_dict = {"margin_floor": 0.20, "discount_cap": 0.20}
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM merchant_settings;")
            rows = cursor.fetchall()
            for r in rows:
                settings_dict[r["key"]] = float(r["value"])
            with self._cache_lock:
                self._settings_cache[db_key] = (now, settings_dict)
            return settings_dict
        except Exception:
            return settings_dict
        finally:
            conn.close()

    def update_merchant_setting(self, key: str, value: float) -> None:
        """Updates a merchant policy setting in SQLite and invalidates cached settings."""
        db_key = self._get_db_key()
        with self._cache_lock:
            self._settings_cache.pop(db_key, None)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO merchant_settings (key, value, updated_at)
                VALUES (?, ?, datetime('now'));
            """, (key, value))
            conn.commit()
        finally:
            conn.close()

    def record_session_event(
        self,
        session_id: str,
        event_type: str,
        product_id: str = "",
        shopping_context: str = "all",
        metadata: dict | None = None,
        event_id: str | None = None,
        timestamp: str | None = None,
    ) -> str:
        """Records an anonymous session event with zero PII and idempotency."""
        import json
        import uuid
        from datetime import datetime, timezone

        final_id = event_id.strip() if event_id and event_id.strip() else f"evt-{uuid.uuid4().hex[:12]}"
        final_ts = timestamp.strip() if timestamp and timestamp.strip() else datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata or {})

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO session_events (id, session_id, event_type, product_id, shopping_context, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (final_id, session_id, event_type, product_id, shopping_context, meta_str, final_ts))
            conn.commit()
            return final_id
        finally:
            conn.close()

    def get_session_events(self, session_id: str, limit: int = 100) -> list[dict]:
        """Retrieves anonymous event history for a given session."""
        import json
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, session_id, event_type, product_id, shopping_context, metadata_json, timestamp
                FROM session_events
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?;
            """, (session_id, limit))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "session_id": r["session_id"],
                    "event_type": r["event_type"],
                    "product_id": r["product_id"],
                    "shopping_context": r["shopping_context"],
                    "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_session_viewed_product_ids(self, session_id: str) -> list[str]:
        """Returns distinct product IDs viewed, hovered, or interacted with in the active session."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT product_id
                FROM session_events
                WHERE session_id = ? AND product_id != '' AND event_type IN ('product_view', 'product_hover', 'product_focus', 'search_submitted')
                ORDER BY timestamp DESC
                LIMIT 30;
            """, (session_id,))
            rows = cursor.fetchall()
            return [r["product_id"] for r in rows if r["product_id"]]
        finally:
            conn.close()

    def get_session_saved_cart_ids(self, session_id: str) -> list[str]:
        """Returns distinct product IDs in the session's saved cart."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT product_id
                FROM session_events
                WHERE session_id = ? AND product_id != '' AND event_type = 'cart_saved'
                ORDER BY timestamp DESC
                LIMIT 20;
            """, (session_id,))
            rows = cursor.fetchall()
            return [r["product_id"] for r in rows if r["product_id"]]
        finally:
            conn.close()

    def get_session_historical_order_ids(self, session_id: str) -> list[str]:
        """Returns distinct product IDs from completed simulated FairCart purchases for this session."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT product_id
                FROM session_events
                WHERE session_id = ? AND product_id != '' AND event_type = 'simulated_purchase_completed'
                ORDER BY timestamp DESC
                LIMIT 20;
            """, (session_id,))
            rows = cursor.fetchall()
            return [r["product_id"] for r in rows if r["product_id"]]
        finally:
            conn.close()

    def clear_session_events(self, session_id: str) -> int:
        """Deletes all anonymous interaction events for a session upon shopper reset."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session_events WHERE session_id = ?;", (session_id,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            conn.close()

    def save_simulation_run(
        self,
        run_id: str,
        timestamp: str,
        random_seed: int,
        num_sessions: int,
        margin_floor: float,
        discount_cap: float,
        results_json: str,
        execution_latency_ms: float,
    ) -> None:
        """Persists a 3-policy simulation comparator run to SQLite."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO simulation_runs (
                    id, timestamp, random_seed, num_sessions, margin_floor, discount_cap, results_json, execution_latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id, timestamp, random_seed, num_sessions, margin_floor, discount_cap, results_json, execution_latency_ms
            ))
            conn.commit()
        finally:
            conn.close()

    def get_latest_simulation_run(self) -> dict | None:
        """Retrieves the most recent simulation run from SQLite."""
        import json
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timestamp, random_seed, num_sessions, margin_floor, discount_cap, results_json, execution_latency_ms
                FROM simulation_runs
                ORDER BY timestamp DESC
                LIMIT 1;
            """)
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "random_seed": row["random_seed"],
                "num_sessions": row["num_sessions"],
                "margin_floor": row["margin_floor"],
                "discount_cap": row["discount_cap"],
                "results": json.loads(row["results_json"]),
                "execution_latency_ms": row["execution_latency_ms"],
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # USER ACCOUNTS & SESSIONS (Milestone 6B)
    # --------------------------------------------------------------------------

    def create_user(
        self,
        user_id: str,
        username: str,
        display_name: str,
        persona_description: str,
        password_hash: str,
        created_at: str | None = None,
    ) -> UserEntity:
        """Creates a demonstration user with hashed credentials."""
        now = created_at or datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, username, display_name, persona_description, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (user_id, username, display_name, persona_description, password_hash, now))
            conn.commit()
            return UserEntity(
                id=user_id,
                username=username,
                display_name=display_name,
                persona_description=persona_description,
                password_hash=password_hash,
                created_at=now,
            )
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> UserEntity | None:
        """Retrieves a user by exact username."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?;", (username,))
            row = cursor.fetchone()
            if not row:
                return None
            return UserEntity(
                id=row["id"],
                username=row["username"],
                display_name=row["display_name"],
                persona_description=row["persona_description"],
                password_hash=row["password_hash"],
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def get_user_by_id(self, user_id: str) -> UserEntity | None:
        """Retrieves a user by unique identifier."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return UserEntity(
                id=row["id"],
                username=row["username"],
                display_name=row["display_name"],
                persona_description=row["persona_description"],
                password_hash=row["password_hash"],
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def get_all_users(self) -> list[UserEntity]:
        """Retrieves all registered demonstration users."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY username ASC;")
            rows = cursor.fetchall()
            return [
                UserEntity(
                    id=r["id"],
                    username=r["username"],
                    display_name=r["display_name"],
                    persona_description=r["persona_description"],
                    password_hash=r["password_hash"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def count_users(self) -> int:
        """Returns the total number of users."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users;")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def update_user_password(self, username: str, new_password_hash: str) -> bool:
        """Updates the password hash for a demonstration user."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?;", (new_password_hash, username))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def create_session(self, session_token: str, user_id: str, expires_at: str) -> None:
        """Stores a server-validated session token."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_sessions (session_token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?);
            """, (session_token, user_id, now, expires_at))
            conn.commit()
        finally:
            conn.close()

    def get_session(self, session_token: str) -> dict | None:
        """Retrieves an active session if not expired."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.session_token, s.user_id, s.created_at, s.expires_at,
                       u.username, u.display_name, u.persona_description
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = ? AND s.expires_at > ?;
            """, (session_token, now))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "session_token": row["session_token"],
                "user_id": row["user_id"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "username": row["username"],
                "display_name": row["display_name"],
                "persona_description": row["persona_description"],
            }
        finally:
            conn.close()

    def delete_session(self, session_token: str) -> bool:
        """Revokes a session token."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_sessions WHERE session_token = ?;", (session_token,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_user_sessions(self, user_id: str) -> int:
        """Revokes all active sessions for a user."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_sessions WHERE user_id = ?;", (user_id,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # ACCOUNT-SPECIFIC ORDER HISTORIES (Milestone 6B)
    # --------------------------------------------------------------------------

    def create_order(
        self,
        order_id: str,
        user_id: str,
        created_at: str,
        status: str,
        provenance: str,
        currency: str,
        total_cents: int,
        savings_cents: int,
        items_json: str,
    ) -> OrderEntity:
        """Persists a new order record under a specific user account."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (
                    id, user_id, created_at, status, provenance, currency, total_cents, savings_cents, items_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (order_id, user_id, created_at, status, provenance, currency, total_cents, savings_cents, items_json))
            conn.commit()
            return OrderEntity(
                id=order_id,
                user_id=user_id,
                created_at=created_at,
                status=status,
                provenance=provenance,
                currency=currency,
                total_cents=total_cents,
                savings_cents=savings_cents,
                items_json=items_json,
            )
        finally:
            conn.close()

    def get_orders_for_user(self, user_id: str) -> list[OrderEntity]:
        """Retrieves all past orders belonging strictly to the specified user account."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM orders
                WHERE user_id = ?
                ORDER BY created_at DESC;
            """, (user_id,))
            rows = cursor.fetchall()
            return [
                OrderEntity(
                    id=r["id"],
                    user_id=r["user_id"],
                    created_at=r["created_at"],
                    status=r["status"],
                    provenance=r["provenance"],
                    currency=r["currency"],
                    total_cents=r["total_cents"],
                    savings_cents=r["savings_cents"],
                    items_json=r["items_json"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def get_order_by_id(self, order_id: str, user_id: str) -> OrderEntity | None:
        """Retrieves a specific order, enforcing that it belongs to the authenticated user."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ? AND user_id = ?;", (order_id, user_id))
            row = cursor.fetchone()
            if not row:
                return None
            return OrderEntity(
                id=row["id"],
                user_id=row["user_id"],
                created_at=row["created_at"],
                status=row["status"],
                provenance=row["provenance"],
                currency=row["currency"],
                total_cents=row["total_cents"],
                savings_cents=row["savings_cents"],
                items_json=row["items_json"],
            )
        finally:
            conn.close()

    def count_orders_for_user(self, user_id: str) -> int:
        """Counts orders associated with a specific user."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?;", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def count_all_orders(self) -> int:
        """Counts total orders across all users."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders;")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def get_user_purchased_product_ids(self, user_id: str) -> list[str]:
        """Extracts unique product IDs purchased across all completed orders for a user.
        Accepts either user ID or username for seamless resolution.
        """
        effective_user_id = user_id
        user = self.get_user_by_id(user_id)
        if not user:
            user = self.get_user_by_username(user_id)
        if user:
            effective_user_id = user.id

        orders = self.get_orders_for_user(effective_user_id)
        purchased_pids: list[str] = []
        seen = set()
        for o in orders:
            for item in o.items:
                pid = item.get("product_id")
                if pid and pid not in seen:
                    seen.add(pid)
                    purchased_pids.append(pid)
        return purchased_pids



