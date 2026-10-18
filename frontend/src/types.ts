export interface Product {
  id: string;
  name: string;
  category: string;
  subcategory?: string;
  description: string;
  reference_price: number;
  cogs: number;
  inventory: number;
  complementary_ids: string[];
  tags?: string[];
  use_cases?: string[];
  image_url: string;
}

export interface CartItem {
  product: Product;
  quantity: number;
  discountedPrice?: number;
  appliedDiscountPct?: number;
  appliedCondition?: string;
}

export interface HealthStatus {
  status: string;
  catalog_items_loaded: number;
  database: string;
  gemini_configured: boolean;
  version: string;
}

export interface CartItemInput {
  product_id: string;
  quantity: number;
}

export interface DecisionRequest {
  session_id?: string;
  user_id?: string;
  cart_items: CartItemInput[];
  applied_discounts?: Record<string, number>;
  shopping_context?: string;
  dwell_time_seconds?: number;
  margin_floor?: number;
  discount_cap?: number;
  viewed_product_ids?: string[];
  hovered_product_ids?: string[];
  saved_cart_product_ids?: string[];
  historical_order_product_ids?: string[];
  search_query?: string;
}

export interface UserProfile {
  id: string;
  username: string;
  display_name: string;
  persona_description: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  user: UserProfile;
  session_token: string;
}

export interface OrderItemDetail {
  product_id: string;
  name: string;
  category: string;
  image_url: string;
  quantity: number;
  reference_price: number;
  simulated_price: number;
  savings: number;
  line_total: number;
}

export interface OrderDetail {
  id: string;
  user_id: string;
  created_at: string;
  status: string;
  provenance: string;
  currency: string;
  total_amount: number;
  total_savings: number;
  items: OrderItemDetail[];
}

export interface CreateOrderRequest {
  items: { product_id: string; quantity: number }[];
  applied_discounts?: Record<string, number>;
}

export interface DemoPersona {
  id: string;
  username: string;
  display_name: string;
  tag: string;
  persona_description: string;
}

export interface RecommendationItem {
  product_id: string;
  name: string;
  category: string;
  subcategory?: string;
  tags?: string[];
  use_cases?: string[];
  reference_price: number;
  cogs?: number;
  inventory: number;
  image_url: string;
  affinity_score: number;
  compatibility_reason: string;
  association_lift?: number;
  association_confidence?: number;
  is_multi_item_match?: boolean;
  is_offered: boolean;
  tier: string;
  discount_percentage: number;
  final_price: number;
  savings: number;
  currency: string;
  conditions: string;
  basket_gross_margin: number;
  decision_reason: string;
  recommendation_source?: string;
  provenance_label?: string;
}

export type RecommendationResponse = RecommendationItem;

export interface IncentiveResponse {
  is_offered: boolean;
  tier: string;
  discount_percentage: number;
  reference_price: number;
  final_price: number;
  savings: number;
  currency: string;
  conditions: string;
}

export interface BasketQuoteItem {
  product_id: string;
  name: string;
  quantity: number;
  reference_price: number;
  unit_price: number;
  discount_percentage: number;
  savings: number;
  line_total: number;
  applied_condition: string;
}

export interface BasketQuote {
  items: BasketQuoteItem[];
  standard_subtotal: number;
  final_subtotal: number;
  total_savings: number;
  basket_gross_margin: number;
}

export interface QuoteRequest {
  cart_items: CartItemInput[];
  applied_discounts?: Record<string, number>;
}

export interface PassportPolicyChecks {
  margin_floor_passed: boolean;
  discount_cap_passed: boolean;
  bundle_rule_passed: boolean;
}

export interface PassportMerchantMetrics {
  basket_revenue: number;
  basket_cogs: number;
  gross_profit: number;
  margin_delta_vs_baseline: number;
  status: string;
}

export interface PassportScenario {
  scenario_id: 'no_discount' | 'faircart_approved' | 'aggressive_alternative';
  label: string;
  discount_percentage: number;
  candidate_price: number;
  candidate_savings: number;
  basket_subtotal: number;
  basket_savings: number;
  basket_gross_margin: number;
  is_approved: boolean;
  rejection_reason?: string | null;
  policy_checks: PassportPolicyChecks;
  shopper_explanation: string;
  merchant_explanation: string;
  merchant_metrics?: PassportMerchantMetrics | null;
}

export interface FairDealPassport {
  passport_id: string;
  cart_snapshot_hash: string;
  generated_at: string;
  candidate_product_id: string;
  candidate_product_name: string;
  candidate_reference_price: number;
  active_margin_floor: number;
  active_discount_cap: number;
  selected_scenario_id: string;
  scenarios: PassportScenario[];
  macro_simulation_summary?: Record<string, string | number> | null;
  explanation_source: string;
}

export interface DealPassportRequest {
  session_id?: string;
  cart_items: CartItemInput[];
  candidate_product_id: string;
  candidate_discount_pct?: number;
  alternative_discount_pct?: number;
  applied_discounts?: Record<string, number>;
  margin_floor?: number;
  discount_cap?: number;
  shopping_context?: string;
  view_mode?: 'shopper' | 'merchant';
}

export interface DecisionResponse {
  request_id: string;
  session_id: string;
  shopping_context: string;
  decision: 'OFFER_APPLIED' | 'NO_OFFER';
  recommendations: RecommendationItem[];
  recommendation: RecommendationItem | null;
  incentive: IncentiveResponse | null;
  cart_quote?: BasketQuote | null;
  eligible_offers_by_product_id: Record<string, RecommendationItem>;
  deterministic_explanation: string;
  decision_reason: string;
  basket_gross_margin: number;
  fallback_applied: boolean;
  deal_passport?: FairDealPassport | null;
  execution_latency_ms: number;
}

export interface ExplanationRequest {
  session_id?: string;
  shopping_context?: string;
  cart_product_ids: string[];
  candidate_product_ids: string[];
}

export interface ItemExplanation {
  product_id: string;
  explanation: string;
  factual_signals: string[];
  source: 'gemini' | 'deterministic_fallback';
}

export interface ExplanationResponse {
  session_id: string;
  shopping_context: string;
  explanations: Record<string, ItemExplanation>;
  ai_generated: boolean;
  fallback_applied: boolean;
  fallback_reason?: string | null;
  execution_latency_ms: number;
}

export interface MerchantSettings {
  margin_floor: number;
  discount_cap: number;
}

export interface SessionEventCreate {
  session_id: string;
  event_type: string;
  product_id?: string;
  shopping_context?: string;
  metadata?: Record<string, unknown>;
  event_id?: string;
  timestamp?: string;
}

export interface SessionEvent {
  id: string;
  session_id: string;
  event_type: string;
  product_id: string;
  shopping_context: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface SimulationRequest {
  num_sessions?: number;
  random_seed?: number;
  margin_floor?: number;
  discount_cap?: number;
}

export interface PolicyMetrics {
  policy_id: string;
  policy_name: string;
  description: string;
  sessions_count: number;
  completed_orders_count: number;
  conversion_rate: number;
  conversion_rate_ci_95: [number, number];
  average_order_value: number;
  total_gross_sales: number;
  total_net_sales_revenue: number;
  total_incentive_expense: number;
  total_cogs: number;
  total_contribution_profit: number;
  avg_contribution_profit_per_session: number;
  avg_contribution_profit_per_session_ci_95: [number, number];
  avg_contribution_profit_per_order: number;
  total_gross_margin: number;
  order_avg_gross_margin: number;
  margin_floor_violations_count: number;
  margin_floor_violation_rate: number;
  recommendations_surfaced_count: number;
  recommendations_accepted_count: number;
  recommendation_acceptance_rate: number;
}

export interface SimulationResponse {
  simulation_id: string;
  timestamp: string;
  version: string;
  parameters: {
    num_sessions: number;
    random_seed: number;
    margin_floor: number;
    discount_cap: number;
    variable_fulfillment_cost_per_order: number;
  };
  active_merchant_settings: {
    margin_floor: number;
    discount_cap: number;
  };
  policies: Record<string, PolicyMetrics>;
  relative_comparison: {
    vs_no_discount: {
      contribution_profit_delta: number;
      contribution_profit_pct: number;
      conversion_rate_delta_pp: number;
      aov_delta: number;
      aov_pct: number;
    };
    vs_blanket_15: {
      contribution_profit_delta: number;
      contribution_profit_pct: number;
      incentive_expense_reduction: number;
      incentive_expense_reduction_pct: number;
      margin_floor_violations_avoided: number;
      gross_margin_delta_pp: number;
    };
  };
  dataset_provenance: {
    methodology: string;
    disclaimer: string;
    archetype_distribution: Record<string, number>;
    total_catalog_products: number;
  };
  run_metadata: {
    execution_latency_ms: number;
    recommender_mode: string;
    optimizer_margin_floor: number;
    optimizer_discount_cap: number;
  };
}

export interface FunnelStageMetrics {
  product_views: number;
  searches_submitted: number;
  recommendation_impressions: number;
  recommendation_clicks: number;
  cart_adds: number;
  cart_removes: number;
  offer_exposures: number;
  offer_acceptances: number;
  offer_rejections: number;
  checkouts_started: number;
  demo_orders_completed: number;
  actual_orders_completed: number;
}

export interface FunnelConversionRates {
  recommendation_ctr: number;
  offer_acceptance_rate: number;
  checkout_completion_rate: number;
  view_to_order_rate: number;
}

export interface FunnelMetricsResponse {
  time_window_hours: number;
  total_events: number;
  funnel_stages: FunnelStageMetrics;
  conversion_rates: FunnelConversionRates;
  provenance_breakdown: Record<string, number>;
  storefront_breakdown: Record<string, number>;
  is_small_sample: boolean;
  tracking_completeness: string;
  methodology_disclaimer: string;
  recent_events: Array<{
    id: string;
    session_id: string;
    event_type: string;
    product_id: string;
    shopping_context: string;
    provenance: string;
    storefront_id: string;
    timestamp: string;
  }>;
}

export interface UpliftDecileMetric {
  decile: number;
  treated_count: number;
  control_count: number;
  treated_conversions: number;
  control_conversions: number;
  treated_conversion_rate: number;
  control_conversion_rate: number;
  incremental_uplift: number;
  cumulative_qini: number;
}

export interface UpliftModelMetrics {
  model_name: string;
  auuc: number;
  qini_coefficient: number;
  normalized_qini: number;
  sample_size_train: number;
  sample_size_test: number;
  treated_proportion: number;
  control_proportion: number;
}

export interface UpliftStrategyComparison {
  strategy_id: string;
  strategy_name: string;
  description: string;
  targeted_percentage: number;
  expected_conversion_rate: number;
  relative_lift_vs_baseline: number;
  modeled_incentive_cost: number;
}

export interface UpliftEvaluationResponse {
  dataset_name: string;
  dataset_provenance: string;
  features_used: string[];
  outcome_evaluated: string;
  treatment_column: string;
  train_samples: number;
  test_samples: number;
  models: Record<string, UpliftModelMetrics>;
  decile_breakdown: UpliftDecileMetric[];
  strategy_comparison: UpliftStrategyComparison[];
  methodology_disclaimer: string;
  real_dataset_status: string;
}

// ==============================================================================
// MULTI-STORE PROFIT INTELLIGENCE TYPES (Step 5.20)
// ==============================================================================

export interface CSVValidationIssue {
  row: number;
  column: string;
  message: string;
  sample_value?: string;
}

export interface CSVValidationResponse {
  valid: boolean;
  import_type: 'orders' | 'traffic';
  filename: string;
  total_rows: number;
  accepted_rows: number;
  rejected_rows: number;
  errors: CSVValidationIssue[];
  preview_rows: Record<string, any>[];
  detected_storefronts: string[];
  detected_currencies: string[];
  detected_channels: string[];
  summary_metrics: Record<string, any>;
}

export interface CSVImportRequest {
  import_type: 'orders' | 'traffic';
  csv_content: string;
  filename?: string;
  storefront_override?: string;
}

export interface CSVImportResponse {
  batch_id: string;
  status: 'completed' | 'partial' | 'failed';
  import_type: string;
  storefront_id: string;
  filename: string;
  total_rows: number;
  accepted_rows: number;
  rejected_rows: number;
  errors: CSVValidationIssue[];
  message: string;
}

export interface StorefrontPerformanceMetric {
  storefront_id: string;
  storefront_name: string;
  currency: string;
  unique_sessions: number;
  product_views: number;
  recommendation_impressions: number;
  recommendation_clicks: number;
  cart_adds: number;
  checkouts_started: number;
  distinct_orders: number;
  units_sold: number;
  gross_revenue: number;
  discount_amount: number;
  refund_amount: number;
  net_revenue: number;
  cogs: number;
  gross_profit: number;
  gross_margin_pct: number;
  aov: number;
  conversion_rate: number;
  recommendation_ctr: number;
  discount_share_pct: number;
  refund_rate_pct: number;
  data_quality_flags: string[];
}

export interface ChannelPerformanceMetric {
  channel: string;
  channel_label: string;
  currency: string;
  unique_sessions: number;
  attributed_orders: number;
  gross_revenue: number;
  discount_amount: number;
  net_revenue: number;
  cogs: number;
  gross_profit: number;
  gross_margin_pct: number;
  aov: number;
  conversion_rate: number;
  attribution_note: string;
}

export interface CategoryProfitabilityMetric {
  category: string;
  units_sold: number;
  gross_revenue: number;
  discount_amount: number;
  net_revenue: number;
  cogs: number;
  gross_profit: number;
  gross_margin_pct: number;
}

export interface DiscountingDiagnostic {
  severity: 'alert' | 'warning' | 'info';
  storefront_id: string;
  storefront_name: string;
  metric: string;
  detail: string;
}

export interface MultiStoreAggregatedTotals {
  currency: string;
  total_storefronts: number;
  total_distinct_orders: number;
  total_unique_sessions: number;
  gross_revenue: number;
  discount_amount: number;
  refund_amount: number;
  net_revenue: number;
  cogs: number;
  gross_profit: number;
  gross_margin_pct: number;
  overall_aov: number;
  overall_conversion_rate: number;
}

export interface MultiStoreProfitResponse {
  date_range_start?: string;
  date_range_end?: string;
  selected_currency: string;
  currencies_available: string[];
  total_storefronts: number;
  total_batches_imported: number;
  aggregated_totals: MultiStoreAggregatedTotals;
  storefronts: StorefrontPerformanceMetric[];
  channels: ChannelPerformanceMetric[];
  category_profitability: CategoryProfitabilityMetric[];
  discounting_diagnostics: DiscountingDiagnostic[];
  methodology_disclaimer: string;
  data_provenance: string;
}

export interface ImportBatchRecord {
  id: string;
  storefront_id: string;
  import_type: string;
  filename: string;
  schema_version: string;
  status: string;
  total_rows: number;
  accepted_rows: number;
  rejected_rows: number;
  errors: CSVValidationIssue[];
  imported_at: string;
}
