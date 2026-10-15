import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  Product,
  CartItem,
  HealthStatus,
  DecisionResponse,
  RecommendationItem,
  ItemExplanation,
  UserProfile,
} from './types.ts';
import {
  fetchHealth,
  fetchCatalog,
  fetchDecision,
  fetchExplanation,
  recordSessionEvent,
  clearSessionEvents,
  fetchCurrentUser,
  logoutUser,
  createSimulatedOrder,
} from './api.ts';
import { Header } from './components/Header.tsx';
import { CartDrawer } from './components/CartDrawer.tsx';
import { CheckoutModal } from './components/CheckoutModal.tsx';
import { TransparencyModal } from './components/TransparencyModal.tsx';
import { LoginModal } from './components/LoginModal.tsx';
import { OrderHistoryModal } from './components/OrderHistoryModal.tsx';
import { StorefrontView } from './views/StorefrontView.tsx';
import { MerchantView } from './views/MerchantView.tsx';

// Helpers to load user-scoped cart and viewed items
function loadUserCart(userId?: string): CartItem[] {
  if (typeof window === 'undefined') return [];
  try {
    const key = `faircart_cart_${userId || 'guest'}`;
    const saved = localStorage.getItem(key);
    if (saved) return JSON.parse(saved);
    if (!userId) {
      const legacy = localStorage.getItem('faircart_cart');
      if (legacy) return JSON.parse(legacy);
    }
    return [];
  } catch {
    return [];
  }
}

function loadUserViewedIds(userId?: string): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const key = `faircart_viewed_ids_${userId || 'guest'}`;
    const saved = localStorage.getItem(key);
    if (saved) return JSON.parse(saved);
    if (!userId) {
      const legacy = localStorage.getItem('faircart_viewed_ids');
      if (legacy) return JSON.parse(legacy);
    }
    return [];
  } catch {
    return [];
  }
}

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

  // Authenticated demo user state
  const [user, setUser] = useState<UserProfile | null>(null);

  // Anonymous session ID persisted to sessionStorage (cleared on tab close)
  const [sessionId] = useState<string>(() => {
    if (typeof window === 'undefined') return 'sess-shopper';
    try {
      const existing = sessionStorage.getItem('faircart_session_id');
      if (existing) return existing;
      const newId = `sess-${Math.random().toString(36).substring(2, 10)}`;
      sessionStorage.setItem('faircart_session_id', newId);
      return newId;
    } catch {
      return 'sess-shopper';
    }
  });

  // Cart state persisted to user-scoped localStorage
  const [cart, setCart] = useState<CartItem[]>(() => loadUserCart());

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
  const [isTransparencyOpen, setIsTransparencyOpen] = useState(false);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [isOrderHistoryOpen, setIsOrderHistoryOpen] = useState(false);

  // Decision Engine state
  const [decision, setDecision] = useState<DecisionResponse | null>(null);

  // AI & Deterministic Explanations state
  const [explanations, setExplanations] = useState<Record<string, ItemExplanation>>({});
  const [isAiGenerated, setIsAiGenerated] = useState(false);

  // Dismissed recommendation IDs persisted to localStorage
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(() => {
    if (typeof window === 'undefined') return new Set();
    try {
      const saved = localStorage.getItem('faircart_dismissed_ids');
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });

  // Viewed product IDs persisted to user-scoped localStorage
  const [viewedProductIds, setViewedProductIds] = useState<string[]>(() => loadUserViewedIds());

  const [decisionRevision, setDecisionRevision] = useState(0);
  const triggerDecisionFetch = useCallback(() => {
    setDecisionRevision((r) => r + 1);
  }, []);

  const hoverDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Incremental sequence ID guard to prevent stale asynchronous decision responses from overwriting newer recommendations
  const decisionRequestIdRef = useRef<number>(0);

  // Restore authenticated session on initial mount
  useEffect(() => {
    fetchCurrentUser()
      .then((existingUser) => {
        if (existingUser) {
          setUser(existingUser);
          const savedCart = loadUserCart(existingUser.id);
          if (savedCart.length > 0) {
            setCart(savedCart);
          }
          setViewedProductIds(loadUserViewedIds(existingUser.id));
        }
      })
      .catch(() => {});
  }, []);

  const handleLoginSuccess = (loggedInUser: UserProfile) => {
    setUser(loggedInUser);
    const existingUserCart = loadUserCart(loggedInUser.id);
    if (existingUserCart.length > 0) {
      setCart(existingUserCart);
    } else if (cart.length > 0) {
      // Migrate current guest cart items to newly signed in account
      setCart(cart);
    }
    setViewedProductIds(loadUserViewedIds(loggedInUser.id));
    triggerDecisionFetch();
  };

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch (e) {
      console.error('Logout error:', e);
    }
    setUser(null);
    setCart(loadUserCart());
    setViewedProductIds(loadUserViewedIds());
    triggerDecisionFetch();
  };

  const handleViewProduct = useCallback(
    async (productId: string) => {
      const episodeId = `view-${productId}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      try {
        await recordSessionEvent({
          session_id: sessionId,
          event_type: 'product_view',
          product_id: productId,
          shopping_context: shoppingContext,
          event_id: episodeId,
          timestamp: new Date().toISOString(),
        });
      } catch (e) {
        console.error('Failed to record product_view event:', e);
      }

      setViewedProductIds((prev) => {
        const next = [productId, ...prev.filter((id) => id !== productId)].slice(0, 10);
        return next;
      });
      triggerDecisionFetch();
    },
    [sessionId, shoppingContext, triggerDecisionFetch]
  );

  const handleProductHover = useCallback(
    async (productId: string, durationMs: number, episodeId: string) => {
      try {
        await recordSessionEvent({
          session_id: sessionId,
          event_type: 'product_hover',
          product_id: productId,
          shopping_context: shoppingContext,
          event_id: episodeId,
          timestamp: new Date().toISOString(),
          metadata: { dwell_ms: durationMs },
        });
      } catch (e) {
        console.error('Failed to record product_hover event:', e);
      }

      if (hoverDebounceRef.current) {
        clearTimeout(hoverDebounceRef.current);
      }
      hoverDebounceRef.current = setTimeout(() => {
        triggerDecisionFetch();
      }, 350);
    },
    [sessionId, shoppingContext, triggerDecisionFetch]
  );

  const handleProductFocus = useCallback(
    async (productId: string, episodeId: string) => {
      try {
        await recordSessionEvent({
          session_id: sessionId,
          event_type: 'product_focus',
          product_id: productId,
          shopping_context: shoppingContext,
          event_id: episodeId,
          timestamp: new Date().toISOString(),
        });
      } catch (e) {
        console.error('Failed to record product_focus event:', e);
      }

      if (hoverDebounceRef.current) {
        clearTimeout(hoverDebounceRef.current);
      }
      hoverDebounceRef.current = setTimeout(() => {
        triggerDecisionFetch();
      }, 350);
    },
    [sessionId, shoppingContext, triggerDecisionFetch]
  );

  // Save dismissedIds to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(
        'faircart_dismissed_ids',
        JSON.stringify(Array.from(dismissedIds))
      );
    } catch (e) {
      console.error('Failed to save dismissed IDs to localStorage', e);
    }
  }, [dismissedIds]);

  // Save user-scoped cart to localStorage
  useEffect(() => {
    try {
      const key = `faircart_cart_${user?.id || 'guest'}`;
      localStorage.setItem(key, JSON.stringify(cart));
    } catch (e) {
      console.error('Failed to save cart to localStorage', e);
    }
  }, [cart, user?.id]);

  // Save user-scoped viewedProductIds to localStorage
  useEffect(() => {
    try {
      const key = `faircart_viewed_ids_${user?.id || 'guest'}`;
      localStorage.setItem(key, JSON.stringify(viewedProductIds));
    } catch (e) {
      console.error('Failed to save viewed IDs to localStorage', e);
    }
  }, [viewedProductIds, user?.id]);

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

  // Reset session handler for demonstration and testing cold-start fallback
  const handleResetSession = useCallback(async () => {
    setCart([]);
    setDismissedIds(new Set());
    setViewedProductIds([]);
    try {
      const cartKey = `faircart_cart_${user?.id || 'guest'}`;
      const viewedKey = `faircart_viewed_ids_${user?.id || 'guest'}`;
      localStorage.removeItem(cartKey);
      localStorage.removeItem(viewedKey);
      localStorage.removeItem('faircart_dismissed_ids');
    } catch (e) {
      console.error('Failed to clear storage:', e);
    }
    try {
      await clearSessionEvents(sessionId);
    } catch (e) {
      console.error('Failed to clear session events:', e);
    }
    triggerDecisionFetch();
  }, [sessionId, user?.id, triggerDecisionFetch]);

  // Query Decision Engine whenever cart contents, shoppingContext, viewedProductIds, user, or revision change
  // Guards against race conditions by discarding stale asynchronous responses
  useEffect(() => {
    let isMounted = true;
    const currentRequestId = ++decisionRequestIdRef.current;

    const appliedDiscounts: Record<string, number> = {};
    cart.forEach((i) => {
      if (i.appliedDiscountPct && i.appliedDiscountPct > 0) {
        appliedDiscounts[i.product.id] = i.appliedDiscountPct;
      }
    });

    fetchDecision({
      session_id: sessionId,
      user_id: user?.id,
      cart_items: cart.map((i) => ({
        product_id: i.product.id,
        quantity: i.quantity,
      })),
      applied_discounts: appliedDiscounts,
      shopping_context: shoppingContext,
      viewed_product_ids: viewedProductIds,
      dwell_time_seconds: 30,
      margin_floor: 0.20,
      discount_cap: 0.20,
    })
      .then((data) => {
        if (isMounted && currentRequestId === decisionRequestIdRef.current) {
          setDecision(data);
        }
      })
      .catch((err) => {
        console.error('Decision pipeline error:', err);
        if (isMounted && currentRequestId === decisionRequestIdRef.current) {
          setDecision(null);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [cart, shoppingContext, viewedProductIds, sessionId, user?.id, decisionRevision]);

  // Revalidate cart bundle discounts against latest backend decision
  // Automatically revokes discounts if prerequisite items are removed
  useEffect(() => {
    if (!decision) return;
    setCart((prev) => {
      let changed = false;
      const next = prev.map((item) => {
        if (item.appliedDiscountPct && item.appliedDiscountPct > 0) {
          const offer = decision.eligible_offers_by_product_id?.[item.product.id];
          if (!offer || !offer.is_offered) {
            changed = true;
            return {
              ...item,
              discountedPrice: undefined,
              appliedDiscountPct: undefined,
              appliedCondition: undefined,
            };
          } else if (item.discountedPrice !== offer.final_price) {
            changed = true;
            return {
              ...item,
              discountedPrice: offer.final_price,
              appliedDiscountPct: offer.discount_percentage,
              appliedCondition: offer.conditions,
            };
          }
        }
        return item;
      });
      return changed ? next : prev;
    });
  }, [decision]);

  // Fetch AI / natural-language explanations when recommendations change
  useEffect(() => {
    if (!decision || decision.recommendations.length === 0) {
      setExplanations({});
      setIsAiGenerated(false);
      return;
    }

    let isMounted = true;
    const candidateIds = decision.recommendations.map((r) => r.product_id);
    const cartIds = cart.map((i) => i.product.id);

    fetchExplanation({
      session_id: decision.session_id,
      shopping_context: shoppingContext,
      cart_product_ids: cartIds,
      candidate_product_ids: candidateIds,
    })
      .then((data) => {
        if (isMounted) {
          setExplanations(data.explanations || {});
          setIsAiGenerated(data.ai_generated || false);
        }
      })
      .catch((err) => {
        console.warn('Asynchronous explanation fetch note:', err);
      });

    return () => {
      isMounted = false;
    };
  }, [decision, shoppingContext, cart]);

  // Cart operations
  const handleAddToCart = (
    product: Product,
    customPrice?: number,
    discountPct?: number,
    condition?: string
  ) => {
    recordSessionEvent({
      session_id: sessionId,
      event_type: 'cart_item_added',
      product_id: product.id,
      shopping_context: shoppingContext,
    }).catch(() => {});

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
    recordSessionEvent({
      session_id: sessionId,
      event_type: 'cart_item_removed',
      product_id: productId,
      shopping_context: shoppingContext,
    }).catch(() => {});

    setCart((prev) => prev.filter((item) => item.product.id !== productId));
  };

  const handleClearCart = () => {
    setCart([]);
    setDismissedIds(new Set());
    clearSessionEvents(sessionId).catch(() => {});
  };

  const handleCompleteOrder = async () => {
    recordSessionEvent({
      session_id: sessionId,
      event_type: 'simulated_purchase_completed',
      shopping_context: shoppingContext,
      metadata: { total_items: cart.length },
    }).catch(() => {});

    // If authenticated, persist the completed simulated order to the database
    if (user && cart.length > 0) {
      try {
        const appliedDiscounts: Record<string, number> = {};
        cart.forEach((i) => {
          if (i.appliedDiscountPct && i.appliedDiscountPct > 0) {
            appliedDiscounts[i.product.id] = i.appliedDiscountPct;
          }
        });
        await createSimulatedOrder({
          items: cart.map((i) => ({ product_id: i.product.id, quantity: i.quantity })),
          applied_discounts: appliedDiscounts,
        });
      } catch (e) {
        console.error('Failed to persist simulated order:', e);
      }
    }

    setCart([]);
    setDismissedIds(new Set());
    clearSessionEvents(sessionId).catch(() => {});
    triggerDecisionFetch();
  };

  // Handle accepting a complementary recommendation
  const handleAcceptRecommendation = (rec: RecommendationItem) => {
    recordSessionEvent({
      session_id: sessionId,
      event_type: 'recommendation_accepted',
      product_id: rec.product_id,
      shopping_context: shoppingContext,
    }).catch(() => {});

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

  const handleSelectShoppingContext = (ctx: string) => {
    setShoppingContext(ctx);
    recordSessionEvent({
      session_id: sessionId,
      event_type: 'context_selected',
      shopping_context: ctx,
    }).catch(() => {});
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
          onOpenTransparency={() => setIsTransparencyOpen(true)}
          user={user}
          onOpenLogin={() => setIsLoginOpen(true)}
          onOpenOrderHistory={() => setIsOrderHistoryOpen(true)}
          onLogout={handleLogout}
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
              onSelectShoppingContext={handleSelectShoppingContext}
              explanations={explanations}
              isAiGenerated={isAiGenerated}
              onOpenTransparency={() => setIsTransparencyOpen(true)}
              onViewProduct={handleViewProduct}
              onResetSession={handleResetSession}
              onHoverProduct={handleProductHover}
              onFocusProduct={handleProductFocus}
            />
          ) : (
            <MerchantView products={products} health={health} />
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
        explanations={explanations}
        isAiGenerated={isAiGenerated}
      />

      {/* Simulated Checkout Modal */}
      <CheckoutModal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        cart={cart}
        onCompleteOrder={handleCompleteOrder}
        basketQuote={decision?.cart_quote}
      />

      {/* Transparency & AI Firewall Modal */}
      <TransparencyModal
        isOpen={isTransparencyOpen}
        onClose={() => setIsTransparencyOpen(false)}
        geminiConfigured={health?.gemini_configured ?? false}
      />

      {/* Demo Account Authentication Modal */}
      <LoginModal
        isOpen={isLoginOpen}
        onClose={() => setIsLoginOpen(false)}
        onLoginSuccess={handleLoginSuccess}
      />

      {/* User Order History Modal */}
      {user && (
        <OrderHistoryModal
          isOpen={isOrderHistoryOpen}
          onClose={() => setIsOrderHistoryOpen(false)}
          user={user}
        />
      )}

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
