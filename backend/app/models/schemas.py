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

class CartItemInput(BaseModel):
    """Item present in shopper's cart."""
    product_id: str
    quantity: int = Field(default=1, ge=1)

class DecisionRequest(BaseModel):
    """Request payload for the primary /api/v1/decision endpoint."""
    session_id: str = Field(default="sess-default", description="Shopper session identifier")
    cart_items: list[CartItemInput] = Field(default_factory=list, description="Active cart items and quantities")
    dwell_time_seconds: int = Field(default=30, ge=0, description="Dwell time in current shopping session")
    margin_floor: float = Field(default=0.20, ge=0.0, le=1.0, description="Merchant minimum basket gross margin floor")
    discount_cap: float = Field(default=0.20, ge=0.0, le=0.50, description="Maximum single-item discount percentage cap")

class RecommendationResponse(BaseModel):
    """Engine A complementary recommendation output."""
    product_id: str
    name: str
    category: str
    reference_price: float
    affinity_score: float = Field(..., description="Explainable affinity relevance score in [0.0, 1.0]")
    compatibility_reason: str = Field(..., description="Factual basis for recommending this accessory")
    image_url: str = Field(default="", description="Product display image URL")

class IncentiveResponse(BaseModel):
    """Engine B economic incentive optimization output."""
    is_offered: bool
    tier: str = Field(..., description="Offer tier: BUNDLE_DISCOUNT or NONE")
    discount_percentage: float
    reference_price: float
    final_price: float
    savings: float
    currency: str = "USD"
    conditions: str

class DecisionResponse(BaseModel):
    """Engine C unified decision response."""
    request_id: str
    session_id: str
    decision: str = Field(..., description="Decision outcome: OFFER_APPLIED or NO_OFFER")
    recommendation: RecommendationResponse | None = Field(default=None, description="Recommended complementary product, if any")
    incentive: IncentiveResponse | None = Field(default=None, description="Optimized incentive details")
    deterministic_explanation: str
    decision_reason: str = Field(..., description="Audit log explanation detailing gross margin and utility checks")
    basket_gross_margin: float = Field(..., description="Resulting gross margin of the affected basket")
    fallback_applied: bool = False
    execution_latency_ms: float
