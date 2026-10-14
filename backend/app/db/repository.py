import sqlite3
from backend.app.db.database import get_connection
from backend.app.models.schemas import Product

class CatalogRepository:
    """Repository handling all database queries for the product catalog."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def _row_to_product(self, row: sqlite3.Row) -> Product:
        """Converts an SQLite row (with integer cents) to a domain Product model (with USD floats)."""
        comp_ids = [cid.strip() for cid in row["complementary_ids"].split(",") if cid.strip()]
        return Product(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            description=row["description"],
            reference_price=round(row["reference_price_cents"] / 100.0, 2),
            cogs=round(row["cogs_cents"] / 100.0, 2),
            inventory=row["inventory"],
            complementary_ids=comp_ids,
            image_url=row["image_url"],
        )

    def count_products(self) -> int:
        """Returns the total number of products in the catalog."""
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products;")
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_all_products(self) -> list[Product]:
        """Retrieves all products from the catalog."""
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products ORDER BY id ASC;")
            rows = cursor.fetchall()
            return [self._row_to_product(r) for r in rows]

    def get_product_by_id(self, product_id: str) -> Product | None:
        """Retrieves a single product by its unique ID."""
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
            row = cursor.fetchone()
            return self._row_to_product(row) if row else None

    def get_products_by_ids(self, product_ids: list[str]) -> list[Product]:
        """Retrieves multiple products given a list of IDs."""
        if not product_ids:
            return []
        placeholders = ",".join("?" for _ in product_ids)
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM products WHERE id IN ({placeholders});", product_ids)
            rows = cursor.fetchall()
            return [self._row_to_product(r) for r in rows]
