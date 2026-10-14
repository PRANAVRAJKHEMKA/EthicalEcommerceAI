from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(..., description="Operational status of the service")
    catalog_items_loaded: int = Field(..., description="Total count of active catalog products in SQLite")
    database: str = Field(default="sqlite", description="Database technology in use")
    gemini_configured: bool = Field(..., description="Whether a Gemini API key is configured")
    version: str = Field(..., description="Application version")

class Product(BaseModel):
    """Catalog product schema returned in API responses."""
    id: str
    name: str
    category: str
    description: str
    reference_price: float = Field(..., description="Base reference price in USD")
    cogs: float = Field(..., description="Wholesale Cost of Goods Sold in USD")
    inventory: int = Field(..., description="Units available in stock")
    complementary_ids: list[str] = Field(default_factory=list, description="IDs of compatible complementary items")
    image_url: str

class CartItem(BaseModel):
    """Item present in shopper's cart."""
    product_id: str
    quantity: int = Field(default=1, ge=1)
