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
    subcategory: str = ""
    description: str
    reference_price: float = Field(..., description="Base reference price in USD")
    cogs: float = Field(..., description="Wholesale Cost of Goods Sold in USD")
    inventory: int = Field(..., description="Units available in stock")
    complementary_ids: list[str] = Field(default_factory=list, description="IDs of compatible complementary items")
    tags: list[str] = Field(default_factory=list, description="Search and feature tags")
    use_cases: list[str] = Field(default_factory=list, description="Supported usage contexts (e.g. productivity, gaming, study, travel, wellness)")
    image_url: str

class CartItemInput(BaseModel):
    """Item present in shopper's cart."""
    product_id: str
    quantity: int = Field(default=1, ge=1)

class DecisionRequest(BaseModel):
    """Request payload for the primary /api/v1/decision endpoint."""
    session_id: str = Field(default="sess-default", description="Shopper session identifier")
    cart_items: list[CartItemInput] = Field(default_factory=list, description="Active cart items and quantities")
    applied_discounts: dict[str, float] = Field(default_factory=dict, description="Map of product_id to applied discount fraction")
    shopping_context: str = Field(default="all", description="Active shopping intent context: all, productivity, gaming, study, travel, entertainment")
    dwell_time_seconds: int = Field(default=30, ge=0, description="Dwell time in current shopping session")
    margin_floor: float = Field(default=0.20, ge=0.0, le=1.0, description="Merchant minimum basket gross margin floor")
    discount_cap: float = Field(default=0.20, ge=0.0, le=0.50, description="Maximum single-item discount percentage cap")

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

class RecommendationItem(BaseModel):
    """Single candidate in a multi-recommendation result, with independent incentive evaluation."""
    product_id: str
    name: str
    category: str
    subcategory: str = ""
    tags: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    reference_price: float
    cogs: float = 0.0
    inventory: int
    image_url: str
    affinity_score: float = Field(..., description="Explainable affinity relevance score in [0.0, 1.0]")
    compatibility_reason: str = Field(..., description="Factual basis for recommending this product")
    is_offered: bool
    tier: str = Field(..., description="Offer tier: BUNDLE_DISCOUNT or NONE")
    discount_percentage: float
    final_price: float
    savings: float
    currency: str = "USD"
    conditions: str
    basket_gross_margin: float
    decision_reason: str

# For backwards compatibility with single recommendation responses
RecommendationResponse = RecommendationItem

class BasketQuoteItem(BaseModel):
    """Authoritative price breakdown for a single item in the cart."""
    product_id: str
    name: str
    quantity: int
    reference_price: float
    unit_price: float
    discount_percentage: float
    savings: float
    line_total: float
    applied_condition: str

class BasketQuote(BaseModel):
    """Authoritative basket-level financial summary computed by the backend."""
    items: list[BasketQuoteItem]
    standard_subtotal: float
    final_subtotal: float
    total_savings: float
    basket_gross_margin: float

class DecisionResponse(BaseModel):
    """Engine C unified decision response supporting multi-recommendations and authoritative pricing."""
    request_id: str
    session_id: str
    shopping_context: str = "all"
    decision: str = Field(..., description="Overall decision outcome: OFFER_APPLIED or NO_OFFER")
    recommendations: list[RecommendationItem] = Field(default_factory=list, description="Ranked 3-5 complementary recommendations with independent incentives")
    recommendation: RecommendationItem | None = Field(default=None, description="Top ranked recommendation for single-card consumers")
    incentive: IncentiveResponse | None = Field(default=None, description="Top incentive details")
    cart_quote: BasketQuote | None = Field(default=None, description="Authoritative basket quote for current cart items")
    eligible_offers_by_product_id: dict[str, RecommendationItem] = Field(default_factory=dict, description="Map of product_id to eligible contextual offer")
    deterministic_explanation: str
    decision_reason: str = Field(..., description="Audit log explanation detailing gross margin and utility checks")
    basket_gross_margin: float = Field(..., description="Resulting gross margin of the affected basket")
    fallback_applied: bool = False
    execution_latency_ms: float

class QuoteRequest(BaseModel):
    """Request payload for authoritative basket quote calculation."""
    cart_items: list[CartItemInput] = Field(default_factory=list)
    applied_discounts: dict[str, float] = Field(default_factory=dict, description="Map of product_id to applied discount fraction")

class MerchantSettingsRequest(BaseModel):
    """Request payload for updating merchant policy guardrails."""
    margin_floor: float = Field(ge=0.0, le=1.0, description="Minimum gross margin threshold")
    discount_cap: float = Field(ge=0.0, le=0.50, description="Maximum single-item discount cap")
