"""FairCart AI — Decision Twin Schemas & Data Contracts

Authoritative schemas for:
- Available-To-Promise (ATP) inventory & scarcity shadow prices (lambda_i)
- Multi-horizon demand forecasts & prediction intervals
- Auditable inventory alerts (stockout, excess, markdown)
- Continuous recency-weighted Markov shopper intent
- Multi-shopper batch optimization & shadow profit allocation
- Traceable decision audit records with redacted public views
- Authorized external analytics connectors (GA4 & Shopify)
"""

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, field_validator


class InventoryItem(BaseModel):
    """Inventory snapshot and Available-To-Promise (ATP) tracking for a SKU."""
    sku: str = Field(..., description="Unique SKU / Product Identifier")
    product_name: str = Field(..., description="Display product name")
    category: str = Field(..., description="Top-level product category")
    storefront_id: str = Field(default="primary_storefront", description="Storefront or warehouse partition")
    on_hand: int = Field(..., ge=0, description="Physical units in stock")
    reserved: int = Field(default=0, ge=0, description="Units committed to pending orders")
    safety_stock: int = Field(default=10, ge=0, description="Buffer stock threshold")
    incoming: int = Field(default=0, ge=0, description="Units on inbound replenishment POs")
    lead_time_days: int = Field(default=7, ge=1, description="Supplier lead time in days")
    atp: int = Field(..., ge=0, description="Available-To-Promise: max(0, on_hand - reserved)")
    scarcity_lambda: float = Field(default=0.0, ge=0.0, description="Shadow price opportunity cost in USD per unit")
    stock_status: str = Field(default="HEALTHY", description="HEALTHY, LOW_STOCK, CRITICAL_STOCKOUT_RISK, OVERSTOCKED")
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DemandForecastRecord(BaseModel):
    """Predictive demand forecast for a SKU over a specific forward horizon."""
    sku: str
    storefront_id: str = "primary_storefront"
    horizon_days: int = Field(..., description="Forecast horizon in days (e.g. 7, 14, 30)")
    forecast_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())
    point_forecast: float = Field(..., ge=0.0, description="Expected unit demand over the horizon")
    lower_bound: float = Field(..., ge=0.0, description="Lower prediction interval bound (conformal / residual)")
    upper_bound: float = Field(..., ge=0.0, description="Upper prediction interval bound")
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.99, description="Statistical coverage level")
    method: str = Field(..., description="Model: hist_gradient_boosting, croston_intermittent, seasonal_naive")
    wape: float = Field(default=0.0, ge=0.0, description="Weighted Absolute Percentage Error on test backtest")
    mase: float = Field(default=0.0, ge=0.0, description="Mean Absolute Scaled Error relative to naive baseline")
    forecast_bias: float = Field(default=0.0, description="Signed percentage forecast bias")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InventoryAlert(BaseModel):
    """Auditable stockout, excess, or replenishment alert for merchants."""
    alert_id: str
    sku: str
    product_name: str
    severity: str = Field(..., description="CRITICAL, WARNING, INFO")
    alert_type: str = Field(..., description="STOCKOUT_RISK, EXCESS_INVENTORY, REPLENISHMENT_RECOMMENDED, MARKDOWN_CANDIDATE")
    description: str
    suggested_action: str
    days_of_supply_remaining: float
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ShopperIntentState(BaseModel):
    """Continuous recency-weighted Markov shopper intent model."""
    session_id: str
    current_state: str = Field(..., description="DISCOVERY, PRODUCT_COMPARISON, PURCHASE_CONSIDERATION, CART_COMPLETION, REPLENISHMENT")
    state_probabilities: dict[str, float] = Field(default_factory=dict)
    intent_score: float = Field(..., ge=0.0, le=1.0, description="Estimated purchase likelihood")
    decayed_dwell_seconds: float = Field(default=0.0, ge=0.0)
    transition_entropy: float = Field(default=0.0, ge=0.0, description="State uncertainty measure")
    top_category_affinity: str = "general"
    price_sensitivity_estimate: float = Field(default=1.0, ge=0.1, le=5.0)


class DecisionCandidate(BaseModel):
    """Evaluated action candidate with utility, margin, and scarcity penalty."""
    action_type: str = Field(..., description="NO_OFFER, BUNDLE_DISCOUNT, ITEM_DISCOUNT, ALTERNATIVE_SUBSTITUTE")
    candidate_id: str = Field(..., description="SKU or bundle action identifier")
    product_name: str
    reference_price: float
    offered_price: float
    discount_pct: float
    cogs: float
    gross_margin_pct: float
    expected_conversion: float
    scarcity_penalty: float = Field(default=0.0, description="lambda_i * quantity opportunity cost in USD")
    net_expected_profit: float = Field(..., description="Expected profit after discount and scarcity penalty")
    margin_floor_passed: bool
    rejection_reason: str | None = None


class DecisionTraceSnapshot(BaseModel):
    """Comprehensive, auditable snapshot of a Decision Twin offer calculation."""
    trace_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str
    storefront_id: str = "primary_storefront"
    intent_state: str
    candidates_evaluated: list[DecisionCandidate] = Field(default_factory=list)
    chosen_action: DecisionCandidate | None = None
    scarcity_lambda: float = 0.0
    utility_formula: str = "V(s,a) = P(conv|s,a)*(R - C) - P(conv|s,0)*(R_0 - C) - k - lambda*q"
    constraints_applied: dict[str, Any] = Field(default_factory=dict)
    redacted_shopper_view: dict[str, Any] = Field(default_factory=dict, description="Redacted view omitting internal COGS and shadow costs")


class BatchShopperSession(BaseModel):
    """Input session for multi-shopper batch optimization."""
    session_id: str
    user_id: str | None = None
    cart_items: list[dict[str, Any]] = Field(default_factory=list)
    shopping_context: str = "all"
    viewed_product_ids: list[str] = Field(default_factory=list)
    dwell_time_seconds: int = 30
    applied_discounts: dict[str, float] = Field(default_factory=dict)


class BatchOptimizationRequest(BaseModel):
    """Request payload for multi-shopper batch profit allocation."""
    sessions: list[BatchShopperSession] = Field(..., min_length=1)
    storefront_id: str = "primary_storefront"
    margin_floor: float = Field(default=0.20, ge=0.0, le=1.0)
    discount_cap: float = Field(default=0.20, ge=0.0, le=0.50)


class BatchOptimizationResult(BaseModel):
    """Result of multi-shopper profit allocation with scarcity constraints."""
    total_sessions_evaluated: int
    inventory_constrained_skus: list[str] = Field(default_factory=list)
    allocations: list[dict[str, Any]] = Field(default_factory=list)
    aggregate_projected_profit: float
    baseline_greedy_profit: float
    projected_profit_lift_pct: float
    inventory_saved_units: int
    stockout_prevention_rate: float
    execution_latency_ms: float
    disclaimer: str = "Simulation results reflect offline causal optimization against constrained Available-To-Promise inventory."


class ExternalConnectorConfig(BaseModel):
    """Configuration and connection health of an external analytics connector."""
    provider: str = Field(..., description="google_analytics_4 or shopify")
    merchant_id: str = "usr_demo_merchant"
    status: str = Field(default="unconfigured", description="unconfigured, connected, error")
    masked_account_id: str | None = None
    last_sync_at: str | None = None
    sync_frequency_hours: int = 24
    read_only_scopes: list[str] = Field(default_factory=list)
    audit_log: list[dict[str, Any]] = Field(default_factory=list)


class ConnectorConfigureRequest(BaseModel):
    """Credential configuration payload for an external connector."""
    provider: str
    credentials: dict[str, str] = Field(..., description="Encrypted on server before write")
    merchant_id: str = "usr_demo_merchant"


class ConnectorSyncResult(BaseModel):
    """Execution outcome of a connector synchronization cycle."""
    provider: str
    status: str
    records_ingested: int
    synced_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: str
