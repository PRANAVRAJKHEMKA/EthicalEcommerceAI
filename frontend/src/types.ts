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
}

export interface HealthStatus {
  status: string;
  catalog_items_loaded: number;
  database: string;
  gemini_configured: boolean;
  version: string;
}
