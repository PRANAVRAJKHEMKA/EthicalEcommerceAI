import sqlite3
from pathlib import Path
from backend.app.config import settings

def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Creates and returns an active SQLite database connection with row dictionary access."""
    target_path = db_path or settings.DATABASE_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str | None = None) -> None:
    """Initializes the database schema if tables do not exist and applies migrations."""
    target_path = db_path or settings.DATABASE_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = get_connection(target_path)
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

        # Migration helper: add new columns if upgrading from earlier schema
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
        
        # Indexes for fast candidate filtering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_use_cases ON products(use_cases);")
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
