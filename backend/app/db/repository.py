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
            description=self.description,
            reference_price=self.reference_price,
            cogs=self.cogs,
            inventory=self.inventory,
            complementary_ids=list(self.complementary_ids),
            image_url=self.image_url,
        )

class CatalogRepository:
    """Repository handling all database queries for the product catalog."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def _row_to_entity(self, row: sqlite3.Row) -> ProductEntity:
        """Converts an SQLite row into an immutable ProductEntity with integer cents."""
        comp_ids = tuple(cid.strip() for cid in row["complementary_ids"].split(",") if cid.strip())
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
