import json
import sqlite3
import threading
import time
from typing import Any
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
    role: str = "customer"

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
        """Records an anonymous session event with zero PII, deduplication, and decision provenance."""
        import json
        import uuid
        from datetime import datetime, timezone

        final_id = event_id.strip() if event_id and event_id.strip() else f"evt-{uuid.uuid4().hex[:12]}"
        final_ts = timestamp.strip() if timestamp and timestamp.strip() else datetime.now(timezone.utc).isoformat()

        enriched_meta = dict(metadata or {})
        if "provenance" not in enriched_meta:
            enriched_meta["provenance"] = "observed_demo"
        if "storefront_id" not in enriched_meta:
            enriched_meta["storefront_id"] = "storefront_default"
        meta_str = json.dumps(enriched_meta)

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

    def get_outcome_funnel_metrics(
        self,
        time_window_hours: int = 24,
        provenance_filter: str | None = None,
        storefront_filter: str | None = None,
    ) -> dict:
        """Aggregates first-party interaction events into commerce funnel stages and conversion metrics.

        Distinguishes demo orders from live actual orders, tallies provenance, and computes rates.
        """
        import json
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        since_ts = (now - timedelta(hours=time_window_hours)).isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Query recent events
            cursor.execute("""
                SELECT id, session_id, event_type, product_id, shopping_context, metadata_json, timestamp
                FROM session_events
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 5000;
            """, (since_ts,))
            rows = cursor.fetchall()

            # Fallback to recent events if none within time window
            if not rows:
                cursor.execute("""
                    SELECT id, session_id, event_type, product_id, shopping_context, metadata_json, timestamp
                    FROM session_events
                    ORDER BY timestamp DESC
                    LIMIT 500;
                """)
                rows = cursor.fetchall()

            views = 0
            searches = 0
            rec_impressions = 0
            rec_clicks = 0
            cart_adds = 0
            cart_removes = 0
            offer_exposures = 0
            offer_acceptances = 0
            offer_rejections = 0
            checkouts_started = 0
            demo_orders = 0
            actual_orders = 0

            provenance_counts: dict[str, int] = {}
            storefront_counts: dict[str, int] = {}
            recent_events: list[dict] = []

            for r in rows:
                etype = r["event_type"]
                meta = {}
                if r["metadata_json"]:
                    try:
                        meta = json.loads(r["metadata_json"])
                    except Exception:
                        pass

                prov = meta.get("provenance", "observed_demo")
                sfront = meta.get("storefront_id", "storefront_default")

                if provenance_filter and prov != provenance_filter:
                    continue
                if storefront_filter and sfront != storefront_filter:
                    continue

                provenance_counts[prov] = provenance_counts.get(prov, 0) + 1
                storefront_counts[sfront] = storefront_counts.get(sfront, 0) + 1

                # Classify into funnel stage
                if etype in ("product_view", "product_viewed", "product_focus"):
                    views += 1
                elif etype in ("search_submitted",):
                    searches += 1
                elif etype in ("recommendation_impression", "recommendation_shown"):
                    rec_impressions += 1
                elif etype in ("recommendation_click", "recommendation_accepted"):
                    rec_clicks += 1
                elif etype in ("add_to_cart", "cart_item_added", "cart_add"):
                    cart_adds += 1
                elif etype in ("remove_from_cart", "cart_item_removed", "cart_remove"):
                    cart_removes += 1
                elif etype in ("offer_exposure", "offer_shown"):
                    offer_exposures += 1
                elif etype in ("offer_accepted",):
                    offer_acceptances += 1
                elif etype in ("offer_rejected",):
                    offer_rejections += 1
                elif etype in ("checkout_started",):
                    checkouts_started += 1
                elif etype in ("demo_order_completed", "simulated_purchase_completed"):
                    demo_orders += 1
                elif etype in ("order_completed",):
                    actual_orders += 1

                if len(recent_events) < 15:
                    recent_events.append({
                        "id": r["id"],
                        "session_id": r["session_id"],
                        "event_type": etype,
                        "product_id": r["product_id"],
                        "shopping_context": r["shopping_context"],
                        "provenance": prov,
                        "storefront_id": sfront,
                        "timestamp": r["timestamp"],
                    })

            total_evts = sum(provenance_counts.values())
            rec_ctr = min(1.0, round(rec_clicks / rec_impressions, 4)) if rec_impressions > 0 else 0.0
            offer_acc_rate = min(1.0, round(offer_acceptances / offer_exposures, 4)) if offer_exposures > 0 else 0.0
            chk_complete_rate = min(1.0, round((demo_orders + actual_orders) / checkouts_started, 4)) if checkouts_started > 0 else 0.0
            view_to_order = min(1.0, round((demo_orders + actual_orders) / views, 4)) if views > 0 else 0.0

            is_small = total_evts < 30
            tracking_full = views > 0 and rec_impressions > 0 and cart_adds > 0 and demo_orders > 0

            return {
                "time_window_hours": time_window_hours,
                "total_events": total_evts,
                "funnel_stages": {
                    "product_views": views,
                    "searches_submitted": searches,
                    "recommendation_impressions": rec_impressions,
                    "recommendation_clicks": rec_clicks,
                    "cart_adds": cart_adds,
                    "cart_removes": cart_removes,
                    "offer_exposures": offer_exposures,
                    "offer_acceptances": offer_acceptances,
                    "offer_rejections": offer_rejections,
                    "checkouts_started": checkouts_started,
                    "demo_orders_completed": demo_orders,
                    "actual_orders_completed": actual_orders,
                },
                "conversion_rates": {
                    "recommendation_ctr": rec_ctr,
                    "offer_acceptance_rate": offer_acc_rate,
                    "checkout_completion_rate": chk_complete_rate,
                    "view_to_order_rate": view_to_order,
                },
                "provenance_breakdown": provenance_counts,
                "storefront_breakdown": storefront_counts,
                "is_small_sample": is_small,
                "tracking_completeness": "full" if tracking_full else "partial_early_stage",
                "methodology_disclaimer": (
                    "First-party outcome ledger tracks observed events within the demo storefront. "
                    "Demo orders represent interactive customer simulation in a sandbox environment, "
                    "strictly distinguished from paid live transactions. Zero personal data (PII) is stored."
                ),
                "recent_events": recent_events,
            }
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
                WHERE session_id = ? AND product_id != '' AND event_type IN ('simulated_purchase_completed', 'demo_order_completed')
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
        role: str = "customer",
    ) -> UserEntity:
        """Creates a demonstration user with hashed credentials."""
        now = created_at or datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, username, display_name, persona_description, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (user_id, username, display_name, persona_description, password_hash, role, now))
            conn.commit()
            return UserEntity(
                id=user_id,
                username=username,
                display_name=display_name,
                persona_description=persona_description,
                password_hash=password_hash,
                created_at=now,
                role=role,
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
                role=row["role"] if "role" in row.keys() else "customer",
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
                role=row["role"] if "role" in row.keys() else "customer",
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
                    role=r["role"] if "role" in r.keys() else "customer",
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
                       u.username, u.display_name, u.persona_description, u.role
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
                "role": row["role"] if "role" in row.keys() else "customer",
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

    # -------------------------------------------------------------------------
    # MULTI-STORE PROFIT INTELLIGENCE (Step 5.20)
    # -------------------------------------------------------------------------
    def record_import_batch(self, batch_data: dict[str, Any]) -> str:
        """Records an import batch log for multi-store CSV ingestion audit trail, scoped to merchant_id."""
        import json
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO storefront_import_batches (
                    id, merchant_id, storefront_id, import_type, filename, schema_version, status,
                    total_rows, accepted_rows, rejected_rows, errors_json, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                batch_data["id"],
                batch_data.get("merchant_id", "usr_demo_merchant"),
                batch_data["storefront_id"],
                batch_data["import_type"],
                batch_data.get("filename", "uploaded.csv"),
                batch_data.get("schema_version", "1.0"),
                batch_data.get("status", "completed"),
                batch_data.get("total_rows", 0),
                batch_data.get("accepted_rows", 0),
                batch_data.get("rejected_rows", 0),
                json.dumps(batch_data.get("errors", [])),
                batch_data.get("imported_at", datetime.now(timezone.utc).isoformat()),
            ))
            conn.commit()
            return batch_data["id"]
        finally:
            conn.close()

    def get_import_batches(self, merchant_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieves recent multi-store import batches, optionally scoped to a specific merchant."""
        import json
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = """
                SELECT id, merchant_id, storefront_id, import_type, filename, schema_version, status,
                       total_rows, accepted_rows, rejected_rows, errors_json, imported_at
                FROM storefront_import_batches
                WHERE 1=1
            """
            params: list[Any] = []
            if merchant_id:
                query += " AND merchant_id = ?"
                params.append(merchant_id)
            query += " ORDER BY imported_at DESC LIMIT ?;"
            params.append(limit)
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                errs = []
                try:
                    errs = json.loads(r["errors_json"])
                except Exception:
                    pass
                results.append({
                    "id": r["id"],
                    "merchant_id": r["merchant_id"] if "merchant_id" in r.keys() else "usr_demo_merchant",
                    "storefront_id": r["storefront_id"],
                    "import_type": r["import_type"],
                    "filename": r["filename"],
                    "schema_version": r["schema_version"],
                    "status": r["status"],
                    "total_rows": r["total_rows"],
                    "accepted_rows": r["accepted_rows"],
                    "rejected_rows": r["rejected_rows"],
                    "errors": errs,
                    "imported_at": r["imported_at"],
                })
            return results
        finally:
            conn.close()

    def insert_storefront_order_lines(
        self,
        lines: list[dict[str, Any]],
        batch_id: str,
        merchant_id: str = "usr_demo_merchant",
    ) -> int:
        """Inserts validated order lines with stable IDs using INSERT OR IGNORE for idempotency."""
        if not lines:
            return 0
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            inserted_count = 0
            for l in lines:
                cursor.execute("""
                    INSERT OR IGNORE INTO storefront_order_lines (
                        id, merchant_id, batch_id, storefront_id, order_id, order_timestamp, order_status,
                        currency, product_id, quantity, gross_line_revenue_cents,
                        discount_cents, refund_cents, cogs_cents, attribution_channel
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    l["id"],
                    l.get("merchant_id", merchant_id),
                    batch_id,
                    l["storefront_id"],
                    l["order_id"],
                    l["order_timestamp"],
                    l.get("order_status", "completed"),
                    l.get("currency", "USD"),
                    l["product_id"],
                    l.get("quantity", 1),
                    l.get("gross_line_revenue_cents", 0),
                    l.get("discount_cents", 0),
                    l.get("refund_cents", 0),
                    l.get("cogs_cents", 0),
                    l.get("attribution_channel", "unattributed"),
                ))
                if cursor.rowcount > 0:
                    inserted_count += 1
            conn.commit()
            return inserted_count
        finally:
            conn.close()

    def insert_storefront_traffic_events(
        self,
        events: list[dict[str, Any]],
        batch_id: str,
        merchant_id: str = "usr_demo_merchant",
    ) -> int:
        """Inserts validated traffic events with stable IDs using INSERT OR IGNORE for idempotency."""
        if not events:
            return 0
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            inserted_count = 0
            for e in events:
                cursor.execute("""
                    INSERT OR IGNORE INTO storefront_traffic_events (
                        id, merchant_id, batch_id, storefront_id, event_id, event_timestamp, session_id,
                        event_type, acquisition_channel, product_id, order_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    e["id"],
                    e.get("merchant_id", merchant_id),
                    batch_id,
                    e["storefront_id"],
                    e["event_id"],
                    e["event_timestamp"],
                    e["session_id"],
                    e["event_type"],
                    e.get("acquisition_channel", "direct"),
                    e.get("product_id", ""),
                    e.get("order_id", ""),
                ))
                if cursor.rowcount > 0:
                    inserted_count += 1
            conn.commit()
            return inserted_count
        finally:
            conn.close()

    def get_storefront_order_lines(
        self,
        merchant_id: str | None = None,
        storefront_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        currency: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves raw order line items with optional merchant and storefront filtering."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM storefront_order_lines WHERE 1=1"
            params: list[Any] = []

            if merchant_id:
                query += " AND merchant_id = ?"
                params.append(merchant_id)
            if storefront_id:
                query += " AND storefront_id = ?"
                params.append(storefront_id)
            if date_from:
                query += " AND order_timestamp >= ?"
                params.append(date_from)
            if date_to:
                query += " AND order_timestamp <= ?"
                params.append(date_to)
            if currency:
                query += " AND currency = ?"
                params.append(currency)

            query += " ORDER BY order_timestamp ASC;"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "merchant_id": r["merchant_id"] if "merchant_id" in r.keys() else "usr_demo_merchant",
                    "batch_id": r["batch_id"],
                    "storefront_id": r["storefront_id"],
                    "order_id": r["order_id"],
                    "order_timestamp": r["order_timestamp"],
                    "order_status": r["order_status"],
                    "currency": r["currency"],
                    "product_id": r["product_id"],
                    "quantity": r["quantity"],
                    "gross_line_revenue_cents": r["gross_line_revenue_cents"],
                    "discount_cents": r["discount_cents"],
                    "refund_cents": r["refund_cents"],
                    "cogs_cents": r["cogs_cents"],
                    "attribution_channel": r["attribution_channel"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_storefront_traffic_events(
        self,
        merchant_id: str | None = None,
        storefront_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves traffic events with optional merchant and storefront filtering."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM storefront_traffic_events WHERE 1=1"
            params: list[Any] = []

            if merchant_id:
                query += " AND merchant_id = ?"
                params.append(merchant_id)
            if storefront_id:
                query += " AND storefront_id = ?"
                params.append(storefront_id)
            if date_from:
                query += " AND event_timestamp >= ?"
                params.append(date_from)
            if date_to:
                query += " AND event_timestamp <= ?"
                params.append(date_to)

            query += " ORDER BY event_timestamp ASC;"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "merchant_id": r["merchant_id"] if "merchant_id" in r.keys() else "usr_demo_merchant",
                    "batch_id": r["batch_id"],
                    "storefront_id": r["storefront_id"],
                    "event_id": r["event_id"],
                    "event_timestamp": r["event_timestamp"],
                    "session_id": r["session_id"],
                    "event_type": r["event_type"],
                    "acquisition_channel": r["acquisition_channel"],
                    "product_id": r["product_id"],
                    "order_id": r["order_id"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def clear_storefront_data(
        self,
        merchant_id: str | None = None,
        storefront_id: str | None = None,
    ) -> dict[str, int]:
        """Clears imported multi-store data, optionally isolated to a single merchant and/or storefront."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            where_sol = "WHERE 1=1"
            where_ste = "WHERE 1=1"
            where_bat = "WHERE 1=1"
            params: list[Any] = []

            if merchant_id:
                where_sol += " AND merchant_id = ?"
                where_ste += " AND merchant_id = ?"
                where_bat += " AND merchant_id = ?"
                params.append(merchant_id)
            if storefront_id:
                where_sol += " AND storefront_id = ?"
                where_ste += " AND storefront_id = ?"
                where_bat += " AND storefront_id = ?"
                params.append(storefront_id)

            cursor.execute(f"DELETE FROM storefront_order_lines {where_sol};", tuple(params))
            lines_cleared = cursor.rowcount
            cursor.execute(f"DELETE FROM storefront_traffic_events {where_ste};", tuple(params))
            traffic_cleared = cursor.rowcount
            cursor.execute(f"DELETE FROM storefront_import_batches {where_bat};", tuple(params))
            batches_cleared = cursor.rowcount

            conn.commit()
            return {
                "order_lines_cleared": lines_cleared,
                "traffic_events_cleared": traffic_cleared,
                "batches_cleared": batches_cleared,
            }
        finally:
            conn.close()
