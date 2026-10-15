import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Product,
  CartItem,
  HealthStatus,
  DecisionResponse,
  RecommendationItem,
} from './types.ts';
import { fetchHealth, fetchCatalog, fetchDecision } from './api.ts';
import { Header } from './components/Header.tsx';
import { CartDrawer } from './components/CartDrawer.tsx';
import { CheckoutModal } from './components/CheckoutModal.tsx';
import { StorefrontView } from './views/StorefrontView.tsx';
import { MerchantView } from './views/MerchantView.tsx';

export default function App() {
  const [activeTab, setActiveTabState] = useState<'store' | 'merchant'>(() => {
    return typeof window !== 'undefined' && window.location.hash === '#merchant'
      ? 'merchant'
      : 'store';
  });

  const setActiveTab = (tab: 'store' | 'merchant') => {
    setActiveTabState(tab);
    if (typeof window !== 'undefined') {
      window.location.hash = tab === 'merchant' ? '#merchant' : '#store';
    }
  };

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);

  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);

  // Cart state persisted to localStorage
  const [cart, setCart] = useState<CartItem[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const saved = localStorage.getItem('faircart_cart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Shopping Intent Context persisted to localStorage
  const [shoppingContext, setShoppingContext] = useState<string>(() => {
    if (typeof window === 'undefined') return 'all';
    try {
      return localStorage.getItem('faircart_shopping_context') || 'all';
    } catch {
      return 'all';
    }
  });

  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);

  // Decision Engine state
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  // Save cart to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('faircart_cart', JSON.stringify(cart));
    } catch (e) {
      console.error('Failed to save cart to localStorage', e);
    }
  }, [cart]);

  // Save shoppingContext to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('faircart_shopping_context', shoppingContext);
    } catch (e) {
      console.error('Failed to save shopping context to localStorage', e);
    }
  }, [shoppingContext]);

  // Load health check on mount
  const checkHealth = useCallback(async () => {
    try {
      setLoadingHealth(true);
      const data = await fetchHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  // Load catalogue products on mount or retry
  const loadProducts = useCallback(async () => {
    try {
      setLoadingProducts(true);
      setProductsError(null);
      const data = await fetchCatalog();
      setProducts(data);
    } catch (err) {
      setProductsError(
        err instanceof Error ? err.message : 'Unable to connect to the catalogue service.'
      );
    } finally {
      setLoadingProducts(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    loadProducts();
  }, [checkHealth, loadProducts]);

  // Query Decision Engine whenever cart contents or shoppingContext change
  useEffect(() => {
    if (cart.length === 0) {
      setDecision(null);
      return;
    }

    let isMounted = true;

    const appliedDiscounts: Record<string, number> = {};
    cart.forEach((i) => {
      if (i.appliedDiscountPct && i.appliedDiscountPct > 0) {
        appliedDiscounts[i.product.id] = i.appliedDiscountPct;
      }
    });

    fetchDecision({
      session_id: 'sess-shopper',
      cart_items: cart.map((i) => ({
        product_id: i.product.id,
        quantity: i.quantity,
      })),
      applied_discounts: appliedDiscounts,
      shopping_context: shoppingContext,
      dwell_time_seconds: 30,
      margin_floor: 0.20,
      discount_cap: 0.20,
    })
      .then((data) => {
        if (isMounted) {
          setDecision(data);
        }
      })
      .catch((err) => {
        console.error('Decision pipeline error:', err);
        if (isMounted) {
          setDecision(null);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [cart, shoppingContext]);

  // Cart operations
  const handleAddToCart = (
    product: Product,
    customPrice?: number,
    discountPct?: number,
    condition?: string
  ) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.product.id === product.id);
      if (existing) {
        return prev.map((item) =>
          item.product.id === product.id
            ? {
                ...item,
                quantity: item.quantity + 1,
                discountedPrice: customPrice ?? item.discountedPrice,
                appliedDiscountPct: discountPct ?? item.appliedDiscountPct,
                appliedCondition: condition ?? item.appliedCondition,
              }
            : item
        );
      }
      return [
        ...prev,
        {
          product,
          quantity: 1,
          discountedPrice: customPrice,
          appliedDiscountPct: discountPct,
          appliedCondition: condition,
        },
      ];
    });
  };

  const handleUpdateQuantity = (productId: string, delta: number) => {
    setCart((prev) =>
      prev
        .map((item) => {
          if (item.product.id === productId) {
            const nextQuantity = item.quantity + delta;
            return nextQuantity > 0 ? { ...item, quantity: nextQuantity } : null;
          }
          return item;
        })
        .filter((item): item is CartItem => item !== null)
    );
  };

  const handleRemoveItem = (productId: string) => {
    setCart((prev) => prev.filter((item) => item.product.id !== productId));
  };

  const handleClearCart = () => {
    setCart([]);
    setDismissedIds(new Set());
  };

  const handleCompleteOrder = () => {
    setCart([]);
    setDismissedIds(new Set());
  };

  // Handle accepting a complementary recommendation
  const handleAcceptRecommendation = (rec: RecommendationItem) => {
    const productObj = products.find((p) => p.id === rec.product_id) || {
      id: rec.product_id,
      name: rec.name,
      category: rec.category,
      subcategory: rec.subcategory,
      description: rec.compatibility_reason,
      reference_price: rec.reference_price,
      cogs: rec.cogs ?? Math.round(rec.reference_price * 0.5 * 100) / 100,
      inventory: rec.inventory,
      complementary_ids: [],
      image_url: rec.image_url,
    };

    handleAddToCart(
      productObj,
      rec.is_offered ? rec.final_price : undefined,
      rec.is_offered ? rec.discount_percentage : undefined,
      rec.is_offered ? rec.conditions : undefined
    );
  };

  const handleDismissRecommendation = (productId: string) => {
    setDismissedIds((prev) => new Set([...prev, productId]));
  };

  // Fast lookup of cart quantities by product id
  const cartQuantities = useMemo(() => {
    const map: { [productId: string]: number } = {};
    cart.forEach((item) => {
      map[item.product.id] = item.quantity;
    });
    return map;
  }, [cart]);

  const totalCartCount = useMemo(
    () => cart.reduce((sum, item) => sum + item.quantity, 0),
    [cart]
  );

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 flex flex-col justify-between overflow-x-hidden">
      <div>
        {/* Navigation Header */}
        <Header
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          cartCount={totalCartCount}
          openCart={() => setIsCartOpen(true)}
          health={health}
          loadingHealth={loadingHealth}
        />

        {/* Main Application Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 sm:pt-8 w-full min-w-0">
          {activeTab === 'store' ? (
            <StorefrontView
              products={products}
              loading={loadingProducts}
              error={productsError}
              onRetry={loadProducts}
              onAddToCart={handleAddToCart}
              cartQuantities={cartQuantities}
              recommendations={decision?.recommendations || []}
              eligibleOffersByProductId={decision?.eligible_offers_by_product_id || {}}
              onAcceptRecommendation={handleAcceptRecommendation}
              onDismissRecommendation={handleDismissRecommendation}
              dismissedIds={dismissedIds}
              shoppingContext={shoppingContext}
              onSelectShoppingContext={setShoppingContext}
            />
          ) : (
            <MerchantView products={products} />
          )}
        </main>
      </div>

      {/* Slide-out Cart Drawer */}
      <CartDrawer
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cart={cart}
        onUpdateQuantity={handleUpdateQuantity}
        onRemoveItem={handleRemoveItem}
        onClearCart={handleClearCart}
        onOpenCheckout={() => {
          setIsCartOpen(false);
          setIsCheckoutOpen(true);
        }}
        recommendations={decision?.recommendations || []}
        onAcceptRecommendation={handleAcceptRecommendation}
        onDismissRecommendation={handleDismissRecommendation}
        dismissedIds={dismissedIds}
        basketQuote={decision?.cart_quote}
      />

      {/* Simulated Checkout Modal */}
      <CheckoutModal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        cart={cart}
        onCompleteOrder={handleCompleteOrder}
        basketQuote={decision?.cart_quote}
      />

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 mt-12 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2.5">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-800">FairCart AI</span>
            <span>·</span>
            <span>Devpost "Build With AI: Basics"</span>
          </div>
          <div className="text-slate-400 text-center sm:text-right">
            Explainable, Margin-Preserving E-Commerce · Sub-25ms Local Decisions · Powered by Gemini
          </div>
        </div>
      </footer>
    </div>
  );
}
