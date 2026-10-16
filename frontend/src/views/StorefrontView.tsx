import { useState, useMemo } from 'react';
import { Search, AlertCircle, RefreshCw, Layers, ShieldCheck, Cpu, Compass, Sparkles, HelpCircle } from 'lucide-react';
import { Product, RecommendationItem, ItemExplanation } from '../types.ts';
import { ProductCard } from '../components/ProductCard.tsx';
import { RecommendationCard } from '../components/RecommendationCard.tsx';
import { ProductDetailModal } from '../components/ProductDetailModal.tsx';

interface StorefrontViewProps {
  products: Product[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onAddToCart: (
    product: Product,
    customPrice?: number,
    discountPct?: number,
    condition?: string
  ) => void;
  cartQuantities: { [productId: string]: number };
  recommendations: RecommendationItem[];
  eligibleOffersByProductId: Record<string, RecommendationItem>;
  onAcceptRecommendation: (rec: RecommendationItem) => void;
  onDismissRecommendation: (productId: string) => void;
  dismissedIds: Set<string>;
  shoppingContext: string;
  onSelectShoppingContext: (context: string) => void;
  explanations?: Record<string, ItemExplanation>;
  isAiGenerated?: boolean;
  onOpenTransparency?: () => void;
  onViewProduct?: (productId: string) => void;
  onResetSession?: () => void;
  onHoverProduct?: (productId: string, durationMs: number, episodeId: string) => void;
  onFocusProduct?: (productId: string, episodeId: string) => void;
  isUpdating?: boolean;
}

const SHOPPING_CONTEXTS = [
  { id: 'all', label: 'All Setups' },
  { id: 'productivity', label: 'Productivity' },
  { id: 'gaming', label: 'Gaming' },
  { id: 'study', label: 'Study & Remote' },
  { id: 'travel', label: 'Travel Ready' },
  { id: 'wellness', label: 'Ergonomics' },
];

export function StorefrontView({
  products,
  loading,
  error,
  onRetry,
  onAddToCart,
  cartQuantities,
  recommendations,
  eligibleOffersByProductId,
  onAcceptRecommendation,
  onDismissRecommendation,
  dismissedIds,
  shoppingContext,
  onSelectShoppingContext,
  explanations,
  isAiGenerated,
  onOpenTransparency,
  onViewProduct,
  onResetSession,
  onHoverProduct,
  onFocusProduct,
  isUpdating,
}: StorefrontViewProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedDetailProduct, setSelectedDetailProduct] = useState<Product | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  const handleOpenDetail = (product: Product) => {
    setSelectedDetailProduct(product);
    setIsDetailOpen(true);
    onViewProduct?.(product.id);
  };

  // Extract distinct categories dynamically from the catalog
  const categories = useMemo(() => {
    const set = new Set<string>();
    products.forEach((p) => set.add(p.category));
    return ['All', ...Array.from(set).sort()];
  }, [products]);

  // Filter products by category and search term
  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      const matchesCategory =
        selectedCategory === 'All' || product.category === selectedCategory;
      const matchesSearch =
        product.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        product.description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [products, selectedCategory, searchQuery]);

  // Filter recommendations: must not be dismissed, must not be currently in cart
  const activeRecommendations = useMemo(() => {
    return recommendations.filter(
      (r) => !dismissedIds.has(r.product_id) && !(cartQuantities[r.product_id] > 0)
    );
  }, [recommendations, dismissedIds, cartQuantities]);

  return (
    <div className="w-full min-w-0 space-y-6 pb-16">
      {/* Restrained, Premium Value Proposition Banner */}
      <section className="bg-white rounded-2xl p-5 sm:p-8 border border-slate-200/90 shadow-sm w-full min-w-0">
        <div className="max-w-3xl space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center space-x-2 bg-slate-100 text-slate-700 px-3 py-1 rounded-full text-xs font-semibold border border-slate-200">
              <Cpu className="w-3.5 h-3.5 text-indigo-600" />
              <span>Devpost "Build With AI: Basics" Project</span>
            </div>
            {onOpenTransparency && (
              <button
                onClick={onOpenTransparency}
                className="inline-flex items-center space-x-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-xs font-semibold border border-indigo-200 transition-colors cursor-pointer"
              >
                <HelpCircle className="w-3.5 h-3.5" />
                <span>How Offers & AI Work</span>
              </button>
            )}
          </div>

          <h1 className="text-xl sm:text-3xl font-extrabold tracking-tight text-slate-900 leading-tight">
            Curated Desk Tech with Transparent Commerce
          </h1>

          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed max-w-2xl">
            Explore 32 productivity tools, creator peripherals, and desk essentials backed by a deterministic SQLite catalogue. As you shop, FairCart AI balances customer savings with real merchant margin safety.
          </p>

          <div className="pt-1 flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-slate-500">
            <span className="inline-flex items-center space-x-1.5 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>32 Local SQLite Items</span>
            </span>
            <span className="hidden sm:inline">·</span>
            <span className="inline-flex items-center space-x-1.5 font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Zero Dark Patterns</span>
            </span>
            <span className="hidden sm:inline">·</span>
            <span className="inline-flex items-center space-x-1.5 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
              <span>Sub-25ms Decision Guardrails</span>
            </span>
          </div>
        </div>
      </section>

      {/* Inspectable Shopping Intent / Context Selector */}
      <section className="bg-slate-100/80 rounded-xl p-3 sm:p-4 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <Compass className="w-4 h-4 text-indigo-600 shrink-0" />
          <div>
            <h3 className="text-xs font-bold text-slate-900">Shopping Intent / Use Case Context:</h3>
            <p className="text-[11px] text-slate-500">
              Select your primary setup goal to align candidate recommendations (No invasive tracking).
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {SHOPPING_CONTEXTS.map((ctx) => (
            <button
              key={ctx.id}
              onClick={() => onSelectShoppingContext(ctx.id)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                shoppingContext === ctx.id
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200'
              }`}
            >
              {ctx.label}
            </button>
          ))}
        </div>
      </section>

      {/* Multi-Candidate Recommendation Section (Surfaced on empty basket and active cart) */}
      {activeRecommendations.length > 0 && (
        <section className="space-y-3 pt-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              <h2 className="text-sm font-bold text-slate-900">
                {activeRecommendations[0]?.provenance_label || 'Tailored Recommendations'}
                <span className="ml-2 font-normal text-xs text-slate-500">
                  ({activeRecommendations.length} {activeRecommendations.some((r) => r.is_offered) ? 'tailored bundle offers' : 'discovery picks'})
                </span>
                {isUpdating && (
                  <span className="ml-2 inline-flex items-center space-x-1 text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200/80 rounded-full px-2 py-0.5 animate-pulse">
                    <RefreshCw className="w-2.5 h-2.5 animate-spin" />
                    <span>Refreshing...</span>
                  </span>
                )}
              </h2>
            </div>
            <div className="flex items-center space-x-3">
              {onResetSession && (
                <button
                  onClick={onResetSession}
                  className="text-xs text-slate-500 hover:text-slate-800 underline underline-offset-2 flex items-center gap-1"
                  title="Clear viewed history and cart to reset session to cold-start discovery"
                >
                  <RefreshCw className="w-3 h-3" />
                  Reset Session
                </button>
              )}
              <span className="text-xs text-slate-400 font-mono hidden sm:inline">
                {activeRecommendations.some((r) => r.is_offered)
                  ? 'Margin-Verified Offers'
                  : 'Standard Reference Pricing'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeRecommendations.map((rec) => {
              const expObj = explanations ? explanations[rec.product_id] : undefined;
              return (
                <RecommendationCard
                  key={rec.product_id}
                  recommendation={rec}
                  onAccept={onAcceptRecommendation}
                  onDismiss={onDismissRecommendation}
                  isAdded={false}
                  explanationText={expObj?.explanation}
                  factualSignals={expObj?.factual_signals}
                  isAiGenerated={Boolean(isAiGenerated && expObj?.source === 'gemini')}
                />
              );
            })}
          </div>
        </section>
      )}

      {/* Catalog Search & Category Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 w-full min-w-0">
        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 w-full min-w-0 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <Layers className="w-4 h-4 text-slate-400 mr-1 shrink-0 hidden sm:inline" />
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 ${
                selectedCategory === cat
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-slate-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-64 shrink-0">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search 32 products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 shadow-sm transition-all"
            aria-label="Search catalog"
          />
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center space-y-3">
          <div className="inline-flex p-3 rounded-full bg-red-100 text-red-600">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-red-900">Failed to load catalogue</h3>
            <p className="text-xs text-red-700 mt-1">{error}</p>
          </div>
          <button
            onClick={onRetry}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-red-500"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton Grid */}
      {loading && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="bg-white rounded-xl border border-slate-200 p-4 space-y-3 animate-pulse"
            >
              <div className="h-44 bg-slate-200 rounded-lg w-full" />
              <div className="space-y-2">
                <div className="h-4 bg-slate-200 rounded w-3/4" />
                <div className="h-3 bg-slate-100 rounded w-full" />
                <div className="h-3 bg-slate-100 rounded w-2/3" />
              </div>
              <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
                <div className="h-4 bg-slate-200 rounded w-16" />
                <div className="h-7 bg-slate-200 rounded w-16" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Product Grid */}
      {!loading && !error && (
        <>
          {filteredProducts.length === 0 ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-3">
              <Search className="w-8 h-8 text-slate-300 mx-auto" />
              <h3 className="text-sm font-bold text-slate-800">No matching products found</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                No products match "{searchQuery}" in category "{selectedCategory}". Try clearing your filters.
              </p>
              <button
                onClick={() => {
                  setSelectedCategory('All');
                  setSearchQuery('');
                }}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-lg hover:bg-slate-800 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-900"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
              {filteredProducts.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onAddToCart={onAddToCart}
                  cartQuantity={cartQuantities[product.id] || 0}
                  eligibleOffer={eligibleOffersByProductId[product.id]}
                  onView={() => handleOpenDetail(product)}
                  onHover={onHoverProduct}
                  onFocus={onFocusProduct}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Deliberate Product Detail Modal */}
      <ProductDetailModal
        product={selectedDetailProduct}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        onAddToCart={onAddToCart}
        eligibleOffer={selectedDetailProduct ? eligibleOffersByProductId[selectedDetailProduct.id] : undefined}
        cartQuantity={selectedDetailProduct ? (cartQuantities[selectedDetailProduct.id] || 0) : 0}
      />
    </div>
  );
}
