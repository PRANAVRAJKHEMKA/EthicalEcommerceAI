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
  cart_items: CartItemInput[];
  applied_discounts?: Record<string, number>;
  shopping_context?: string;
  dwell_time_seconds?: number;
  margin_floor?: number;
  discount_cap?: number;
  viewed_product_ids?: string[];
  saved_cart_product_ids?: string[];
  historical_order_product_ids?: string[];
  search_query?: string;
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

