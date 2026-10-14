export interface Product {
  id: string;
  name: string;
  category: string;
  description: string;
  reference_price: number;
  cogs: number;
  inventory: number;
  complementary_ids: string[];
  image_url: string;
}

export interface CartItem {
  product: Product;
  quantity: number;
  discountedPrice?: number;
  appliedDiscountPct?: number;
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
  dwell_time_seconds?: number;
  margin_floor?: number;
  discount_cap?: number;
}

export interface RecommendationResponse {
  product_id: string;
  name: string;
  category: string;
  reference_price: number;
  affinity_score: number;
  compatibility_reason: string;
  image_url: string;
}

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

export interface DecisionResponse {
  request_id: string;
  session_id: string;
  decision: 'OFFER_APPLIED' | 'NO_OFFER';
  recommendation: RecommendationResponse | null;
  incentive: IncentiveResponse | null;
  deterministic_explanation: string;
  decision_reason: string;
  basket_gross_margin: number;
  fallback_applied: boolean;
  execution_latency_ms: number;
}
