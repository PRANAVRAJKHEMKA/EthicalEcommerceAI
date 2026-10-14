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
    """Initializes the database schema if tables do not exist."""
    target_path = db_path or settings.DATABASE_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    
    with get_connection(target_path) as conn:
        cursor = conn.cursor()
        
        # Products table: stores 20-item catalog with prices in integer cents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                reference_price_cents INTEGER NOT NULL CHECK (reference_price_cents > 0),
                cogs_cents INTEGER NOT NULL CHECK (cogs_cents >= 0),
                inventory INTEGER NOT NULL DEFAULT 50 CHECK (inventory >= 0),
                complementary_ids TEXT NOT NULL,
                image_url TEXT NOT NULL
            );
        """)
        
        # Decision audit logs: tracks every session recommendation & offer decision
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_logs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
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
        
        # Index on category and id for fast candidate retrieval
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
