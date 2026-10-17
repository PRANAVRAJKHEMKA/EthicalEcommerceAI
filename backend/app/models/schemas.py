import math
from pydantic import BaseModel, Field, field_validator

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
    # Milestone 4C: Independent Recommendation Anchors
    viewed_product_ids: list[str] = Field(default_factory=list, description="Recently viewed product IDs in current session")
    hovered_product_ids: list[str] = Field(default_factory=list, description="Recently hovered product IDs passing >=700ms dwell threshold in active session")
    saved_cart_product_ids: list[str] = Field(default_factory=list, description="Product IDs in an explicitly saved cart")
    historical_order_product_ids: list[str] = Field(default_factory=list, description="Product IDs from completed prior FairCart orders")
    user_id: str | None = Field(default=None, description="Authenticated shopper user ID if signed in")
    search_query: str = Field(default="", description="Active or recent search query within the application")

    @field_validator("margin_floor")
    @classmethod
    def validate_margin_floor(cls, v: float) -> float:
        if v is None:
            return 0.20
        if not math.isfinite(v) or math.isnan(v):
            raise ValueError("margin_floor must be a finite numerical value")
        if v < 0.0 or v > 1.0:
            raise ValueError("margin_floor must be between 0.0 and 1.0")
        return round(float(v), 4)

    @field_validator("discount_cap")
    @classmethod
    def validate_discount_cap(cls, v: float) -> float:
        if v is None:
            return 0.20
        if not math.isfinite(v) or math.isnan(v):
            raise ValueError("discount_cap must be a finite numerical value")
        if v < 0.0 or v > 0.50:
            raise ValueError("discount_cap must be between 0.0 and 0.50 (50% max promotional cap)")
        return round(float(v), 4)

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
    association_lift: float = Field(default=1.0, description="Mined association rule lift (> 1.0 indicates positive co-occurrence)")
    association_confidence: float = Field(default=0.0, description="Mined association rule confidence")
    is_multi_item_match: bool = Field(default=False, description="True if recommendation associates with 2 or more cart items")
    is_offered: bool
    tier: str = Field(..., description="Offer tier: BUNDLE_DISCOUNT or NONE")
    discount_percentage: float
    final_price: float
    savings: float
    currency: str = "USD"
    conditions: str
    basket_gross_margin: float
    decision_reason: str
    recommendation_source: str = Field(default="active_basket", description="Provenance source: active_basket, product_views, saved_cart, historical_order, shopping_context, catalog_popular")
    provenance_label: str = Field(default="", description="Modest, factual UI explanation of recommendation source")

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

class PassportPolicyChecks(BaseModel):
    """Evaluation outcomes for individual mathematical guardrails."""
    margin_floor_passed: bool
    discount_cap_passed: bool
    bundle_rule_passed: bool

class PassportMerchantMetrics(BaseModel):
    """Confidential internal merchant economics returned ONLY in merchant view mode."""
    basket_revenue: float
    basket_cogs: float
    gross_profit: float
    margin_delta_vs_baseline: float
    status: str

class PassportScenario(BaseModel):
    """One of three counterfactual scenarios for the exact same cart snapshot."""
    scenario_id: str  # "no_discount" | "faircart_approved" | "aggressive_alternative"
    label: str
    discount_percentage: float
    candidate_price: float
    candidate_savings: float
    basket_subtotal: float
    basket_savings: float
    basket_gross_margin: float
    is_approved: bool
    rejection_reason: str | None = None
    policy_checks: PassportPolicyChecks
    shopper_explanation: str
    merchant_explanation: str
    merchant_metrics: PassportMerchantMetrics | None = None

class FairDealPassport(BaseModel):
    """Fair Deal Passport: Complete counterfactual transparency report for an offer."""
    passport_id: str
    cart_snapshot_hash: str
    generated_at: str
    candidate_product_id: str
    candidate_product_name: str
    candidate_reference_price: float
    active_margin_floor: float
    active_discount_cap: float
    selected_scenario_id: str
    scenarios: list[PassportScenario]
    macro_simulation_summary: dict[str, str | float] | None = None
    explanation_source: str = "deterministic_rules"

class DealPassportRequest(BaseModel):
    """Request payload for generating a Fair Deal Passport."""
    cart_items: list[CartItemInput] = Field(default_factory=list)
    candidate_product_id: str
    candidate_discount_pct: float | None = None
    alternative_discount_pct: float | None = None
    applied_discounts: dict[str, float] = Field(default_factory=dict)
    margin_floor: float | None = None
    discount_cap: float | None = None
    shopping_context: str = "all"
    session_id: str = "sess-shopper"
    view_mode: str = "shopper"  # "shopper" or "merchant"

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
    deal_passport: FairDealPassport | None = None
    execution_latency_ms: float

class QuoteRequest(BaseModel):
    """Request payload for authoritative basket quote calculation."""
    cart_items: list[CartItemInput] = Field(default_factory=list)
    applied_discounts: dict[str, float] = Field(default_factory=dict, description="Map of product_id to applied discount fraction")
    margin_floor: float | None = Field(default=None, ge=0.0, le=1.0, description="Optional margin floor threshold for discount validation")
    discount_cap: float | None = Field(default=None, ge=0.0, le=0.50, description="Optional maximum discount cap for discount validation")


class MerchantSettingsRequest(BaseModel):
    """Request payload for updating merchant policy guardrails."""
    margin_floor: float = Field(ge=0.0, le=1.0, description="Minimum gross margin threshold")
    discount_cap: float = Field(ge=0.0, le=0.50, description="Maximum single-item discount cap")

    @field_validator("margin_floor")
    @classmethod
    def validate_settings_margin_floor(cls, v: float) -> float:
        if not math.isfinite(v) or math.isnan(v):
            raise ValueError("margin_floor must be a finite numerical value")
        if v < 0.0 or v > 1.0:
            raise ValueError("margin_floor must be between 0.0 and 1.0")
        return round(float(v), 4)

    @field_validator("discount_cap")
    @classmethod
    def validate_settings_discount_cap(cls, v: float) -> float:
        if not math.isfinite(v) or math.isnan(v):
            raise ValueError("discount_cap must be a finite numerical value")
        if v < 0.0 or v > 0.50:
            raise ValueError("discount_cap must be between 0.0 and 0.50 (50% max promotional cap)")
        return round(float(v), 4)

class ExplanationRequest(BaseModel):
    """Request payload for asynchronous Gemini natural language explanation."""
    session_id: str = "sess-default"
    shopping_context: str = "all"
    cart_product_ids: list[str] = Field(default_factory=list, description="IDs of products currently in cart")
    candidate_product_ids: list[str] = Field(default_factory=list, description="IDs of recommendation candidates to explain")

class ItemExplanation(BaseModel):
    """Individual product explanation result."""
    product_id: str
    explanation: str
    factual_signals: list[str] = Field(default_factory=list, description="Factual attributes used in explanation")
    source: str = Field(default="gemini", description="Explanation generator: gemini or deterministic_fallback")

class ExplanationResponse(BaseModel):
    """Response schema for the /api/v1/explanation service."""
    session_id: str
    shopping_context: str
    explanations: dict[str, ItemExplanation] = Field(default_factory=dict, description="Map of product_id to generated explanation")
    ai_generated: bool = Field(..., description="True if generated by Gemini; False if offline fallback was used")
    fallback_applied: bool = Field(default=False)
    fallback_reason: str | None = None
    execution_latency_ms: float

class SessionEventCreate(BaseModel):
    """Schema for recording an anonymous session event (Zero PII)."""
    session_id: str = Field(..., description="Anonymous session identifier")
    event_type: str = Field(..., description="product_view, product_hover, product_focus, search_submitted, add_to_cart, remove_from_cart, cart_saved, recommendation_shown, recommendation_accepted, offer_shown, simulated_purchase_completed")
    product_id: str = Field(default="", description="Target product ID if applicable")
    shopping_context: str = Field(default="all", description="Declared shopping intent context")
    metadata: dict = Field(default_factory=dict, description="Validated event metadata")
    event_id: str | None = Field(default=None, description="Optional client-provided unique event ID or idempotency key")
    timestamp: str | None = Field(default=None, description="Optional ISO timestamp string")

class SessionEvent(BaseModel):
    """Persisted anonymous session event schema."""
    id: str
    session_id: str
    event_type: str
    product_id: str
    shopping_context: str
    metadata: dict
    timestamp: str

class SimulationRequest(BaseModel):
    """Request payload for running the 3-policy economic simulation comparator."""
    num_sessions: int = Field(default=1000, ge=10, le=10000, description="Number of synthetic sessions to simulate")
    random_seed: int = Field(default=42, description="Pseudorandom seed for reproducible paired scenario generation")
    margin_floor: float | None = Field(default=None, ge=0.0, le=1.0, description="Override gross margin floor (defaults to active SQLite merchant setting)")
    discount_cap: float | None = Field(default=None, ge=0.0, le=0.50, description="Override discount cap (defaults to active SQLite merchant setting)")

    @field_validator("margin_floor")
    @classmethod
    def validate_sim_margin_floor(cls, v: float | None) -> float | None:
        if v is not None:
            if not math.isfinite(v) or math.isnan(v):
                raise ValueError("margin_floor must be a finite numerical value")
            if v < 0.0 or v > 1.0:
                raise ValueError("margin_floor must be between 0.0 and 1.0")
            return round(float(v), 4)
        return None

    @field_validator("discount_cap")
    @classmethod
    def validate_sim_discount_cap(cls, v: float | None) -> float | None:
        if v is not None:
            if not math.isfinite(v) or math.isnan(v):
                raise ValueError("discount_cap must be a finite numerical value")
            if v < 0.0 or v > 0.50:
                raise ValueError("discount_cap must be between 0.0 and 0.50 (50% max promotional cap)")
            return round(float(v), 4)
        return None

class PolicyMetrics(BaseModel):
    """Authoritative aggregated financial and conversion metrics for a simulated policy."""
    policy_id: str
    policy_name: str
    description: str
    sessions_count: int
    completed_orders_count: int
    conversion_rate: float
    conversion_rate_ci_95: list[float]
    average_order_value: float
    total_gross_sales: float
    total_net_sales_revenue: float
    total_incentive_expense: float
    total_cogs: float
    total_contribution_profit: float
    avg_contribution_profit_per_session: float
    avg_contribution_profit_per_session_ci_95: list[float]
    avg_contribution_profit_per_order: float
    total_gross_margin: float
    order_avg_gross_margin: float
    margin_floor_violations_count: int
    margin_floor_violation_rate: float
    recommendations_surfaced_count: int = 0
    recommendations_accepted_count: int = 0
    recommendation_acceptance_rate: float = 0.0

class SimulationResponse(BaseModel):
    """Response schema for the POST /api/v1/simulate comparator."""
    simulation_id: str
    timestamp: str
    version: str = "1.0.0"
    parameters: dict
    active_merchant_settings: dict
    policies: dict[str, PolicyMetrics]
    relative_comparison: dict
    dataset_provenance: dict
    run_metadata: dict

# ------------------------------------------------------------------------------
# AUTHENTICATION & DEMO ACCOUNTS (Milestone 6B)
# ------------------------------------------------------------------------------

class UserProfile(BaseModel):
    """Public shopper profile schema for authenticated demo accounts."""
    id: str
    username: str
    display_name: str
    persona_description: str
    created_at: str

class DemoPersonaPublic(BaseModel):
    """Public metadata for demonstration evaluation personas."""
    id: str
    username: str
    display_name: str
    tag: str
    persona_description: str

class DemoLoginRequest(BaseModel):
    """Payload for whitelisted one-click demo persona authentication."""
    persona: str = Field(..., description="Whitelisted demo persona username (e.g. demo_gamer)")

class LoginRequest(BaseModel):
    """Login credentials submission."""
    username: str
    password: str

class LoginResponse(BaseModel):
    """Successful authentication response."""
    user: UserProfile
    session_token: str
    message: str = "Authenticated successfully"

class OrderItemDetail(BaseModel):
    """Itemized product in an order."""
    product_id: str
    name: str
    category: str
    image_url: str
    quantity: int
    reference_price: float
    simulated_price: float
    savings: float
    line_total: float

class OrderDetail(BaseModel):
    """Itemized past order with provenance metadata."""
    id: str
    user_id: str
    created_at: str
    status: str = "completed_simulated"
    provenance: str = "synthetic_demonstration"
    currency: str = "USD"
    total_amount: float
    total_savings: float
    items: list[OrderItemDetail]

class CreateOrderRequest(BaseModel):
    """Payload for completing a simulated checkout while signed in."""
    items: list[dict]
    applied_discounts: dict[str, float] = Field(default_factory=dict)

