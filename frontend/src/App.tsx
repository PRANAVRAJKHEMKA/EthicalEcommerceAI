import { useState, useEffect, useMemo, useCallback } from 'react';
import { Product, CartItem, HealthStatus } from './types.ts';
import { fetchHealth, fetchCatalog } from './api.ts';
import { Header } from './components/Header.tsx';
import { CartDrawer } from './components/CartDrawer.tsx';
import { CheckoutModal } from './components/CheckoutModal.tsx';
import { StorefrontView } from './views/StorefrontView.tsx';
import { MerchantView } from './views/MerchantView.tsx';

export default function App() {
  const [activeTab, setActiveTab] = useState<'store' | 'merchant'>('store');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);

  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);

  const [cart, setCart] = useState<CartItem[]>([]);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);

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

  // Cart operations
  const handleAddToCart = (product: Product) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.product.id === product.id);
      if (existing) {
        return prev.map((item) =>
          item.product.id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [...prev, { product, quantity: 1 }];
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
  };

  const handleCompleteOrder = () => {
    setCart([]);
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
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 flex flex-col justify-between">
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
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
          {activeTab === 'store' ? (
            <StorefrontView
              products={products}
              loading={loadingProducts}
              error={productsError}
              onRetry={loadProducts}
              onAddToCart={handleAddToCart}
              cartQuantities={cartQuantities}
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
      />

      {/* Simulated Checkout Modal */}
      <CheckoutModal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        cart={cart}
        onCompleteOrder={handleCompleteOrder}
      />

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 mt-12 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-800">FairCart AI</span>
            <span>·</span>
            <span>Devpost "Build With AI: Basics"</span>
          </div>
          <div className="text-slate-400">
            Explainable, Margin-Preserving E-Commerce · Sub-25ms Local Decisions · Powered by Gemini
          </div>
        </div>
      </footer>
    </div>
  );
}
