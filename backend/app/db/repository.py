import sqlite3
from dataclasses import dataclass
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

class CatalogRepository:
    """Repository handling all database queries for the product catalog and merchant settings."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

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
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products;")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def get_all_products(self) -> list[Product]:
        """Retrieves all products from the catalog as public schema models."""
        return [e.to_product_schema() for e in self.get_all_entities()]

    def get_all_entities(self) -> list[ProductEntity]:
        """Retrieves all products from the catalog as authoritative integer-cent ProductEntities."""
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products ORDER BY id ASC;")
            rows = cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]
        finally:
            conn.close()

    def get_product_by_id(self, product_id: str) -> Product | None:
        """Retrieves a single product by its unique ID as a public schema model."""
        entity = self.get_entity_by_id(product_id)
        return entity.to_product_schema() if entity else None

    def get_entity_by_id(self, product_id: str) -> ProductEntity | None:
        """Retrieves a single product by its unique ID as an authoritative ProductEntity."""
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
            row = cursor.fetchone()
            return self._row_to_entity(row) if row else None
        finally:
            conn.close()

    def get_products_by_ids(self, product_ids: list[str]) -> list[Product]:
        """Retrieves multiple products given a list of IDs as public schema models."""
        return [e.to_product_schema() for e in self.get_entities_by_ids(product_ids)]

    def get_entities_by_ids(self, product_ids: list[str]) -> list[ProductEntity]:
        """Retrieves multiple products given a list of IDs as authoritative ProductEntities."""
        if not product_ids:
            return []
        placeholders = ",".join("?" for _ in product_ids)
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM products WHERE id IN ({placeholders});", product_ids)
            rows = cursor.fetchall()
            return [self._row_to_entity(r) for r in rows]
        finally:
            conn.close()

    def get_merchant_settings(self) -> dict[str, float]:
        """Retrieves merchant policy settings (margin floor, discount cap) from SQLite."""
        settings = {"margin_floor": 0.20, "discount_cap": 0.20}
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM merchant_settings;")
            rows = cursor.fetchall()
            for r in rows:
                settings[r["key"]] = float(r["value"])
            return settings
        except Exception:
            return settings
        finally:
            conn.close()

    def update_merchant_setting(self, key: str, value: float) -> None:
        """Updates a merchant policy setting in SQLite."""
        conn = get_connection(self.db_path)
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

        conn = get_connection(self.db_path)
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
        conn = get_connection(self.db_path)
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
        conn = get_connection(self.db_path)
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
        conn = get_connection(self.db_path)
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
        conn = get_connection(self.db_path)
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
        conn = get_connection(self.db_path)
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
        conn = get_connection(self.db_path)
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
        conn = get_connection(self.db_path)
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


