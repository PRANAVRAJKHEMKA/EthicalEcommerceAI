import { useState, useMemo } from 'react';
import { Search, Sparkles, AlertCircle, RefreshCw, Layers } from 'lucide-react';
import { Product } from '../types.ts';
import { ProductCard } from '../components/ProductCard.tsx';

interface StorefrontViewProps {
  products: Product[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onAddToCart: (product: Product) => void;
  cartQuantities: { [productId: string]: number };
}

export function StorefrontView({
  products,
  loading,
  error,
  onRetry,
  onAddToCart,
  cartQuantities,
}: StorefrontViewProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');

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

  return (
    <div className="space-y-8 pb-16">
      {/* Hero / Value Proposition Banner */}
      <section className="bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-8 sm:p-10 text-white shadow-xl relative overflow-hidden border border-slate-800">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center space-x-2 bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full text-xs font-semibold backdrop-blur-md border border-indigo-500/30">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Devpost "Build With AI: Basics" Project</span>
          </div>

          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight leading-tight">
            Curated Desk Tech with <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-300">
              Ethical AI Decisions
            </span>
          </h1>

          <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
            Browse our 20-product catalogue backed by SQLite. As you add items to your cart, FairCart AI evaluates margin safety and merchant economics without artificial countdowns or fake scarcity.
          </p>

          <div className="pt-2 flex flex-wrap gap-2 text-xs font-medium text-slate-300">
            <span className="bg-slate-800/80 px-3 py-1 rounded-lg border border-slate-700">
              ✓ 20 Local SQLite Items
            </span>
            <span className="bg-slate-800/80 px-3 py-1 rounded-lg border border-slate-700">
              ✓ Sub-25ms Local Decision Engine
            </span>
            <span className="bg-slate-800/80 px-3 py-1 rounded-lg border border-slate-700">
              ✓ Zero Dark Patterns
            </span>
          </div>
        </div>

        {/* Decorative background glow */}
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
      </section>

      {/* Catalog Search & Filter Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-2 md:pb-0 scrollbar-none">
          <Layers className="w-4 h-4 text-slate-400 mr-1 shrink-0" />
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all ${
                selectedCategory === cat
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
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
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="bg-white rounded-xl border border-slate-200 p-4 space-y-4 animate-pulse"
            >
              <div className="aspect-video bg-slate-200 rounded-lg w-full" />
              <div className="space-y-2">
                <div className="h-4 bg-slate-200 rounded w-3/4" />
                <div className="h-3 bg-slate-100 rounded w-full" />
                <div className="h-3 bg-slate-100 rounded w-2/3" />
              </div>
              <div className="pt-4 border-t border-slate-100 flex justify-between items-center">
                <div className="h-5 bg-slate-200 rounded w-16" />
                <div className="h-8 bg-slate-200 rounded w-20" />
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
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-lg"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredProducts.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onAddToCart={onAddToCart}
                  cartQuantity={cartQuantities[product.id] || 0}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
