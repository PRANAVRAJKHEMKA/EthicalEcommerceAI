import { useEffect } from 'react';
import { X, Plus, Package, Sparkles, Tag, ShieldCheck } from 'lucide-react';
import { Product, RecommendationItem } from '../types.ts';

interface ProductDetailModalProps {
  product: Product | null;
  isOpen: boolean;
  onClose: () => void;
  onAddToCart: (
    product: Product,
    customPrice?: number,
    discountPct?: number,
    condition?: string
  ) => void;
  eligibleOffer?: RecommendationItem;
  cartQuantity?: number;
}

export function ProductDetailModal({
  product,
  isOpen,
  onClose,
  onAddToCart,
  eligibleOffer,
  cartQuantity = 0,
}: ProductDetailModalProps) {
  // Handle ESC key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !product) return null;

  const hasOffer = eligibleOffer?.is_offered ?? false;
  const finalPrice = hasOffer ? eligibleOffer!.final_price : product.reference_price;
  const discountPct = hasOffer ? Math.round(eligibleOffer!.discount_percentage * 100) : 0;
  const savings = hasOffer ? eligibleOffer!.savings : 0;

  const handleAdd = () => {
    if (hasOffer) {
      onAddToCart(
        product,
        eligibleOffer!.final_price,
        eligibleOffer!.discount_percentage,
        eligibleOffer!.conditions
      );
    } else {
      onAddToCart(product);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="product-detail-title"
    >
      <div
        className="bg-white rounded-2xl max-w-2xl w-full overflow-hidden shadow-2xl border border-slate-200 relative animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 p-2 rounded-full bg-white/80 hover:bg-white text-slate-500 hover:text-slate-800 shadow-sm border border-slate-200 transition-colors cursor-pointer"
          aria-label="Close product details"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="grid grid-cols-1 sm:grid-cols-2">
          {/* Product Image */}
          <div className="relative h-64 sm:h-full bg-slate-100 overflow-hidden min-h-[260px]">
            <img
              src={product.image_url}
              alt={product.name}
              className="w-full h-full object-cover object-center"
              onError={(e) => {
                e.currentTarget.src =
                  'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80';
              }}
            />

            {/* Badges */}
            <div className="absolute top-3 left-3 flex flex-col gap-1.5">
              <span className="text-[10px] font-bold tracking-wider uppercase bg-white/95 backdrop-blur-sm text-slate-700 px-2.5 py-1 rounded shadow-sm border border-slate-200/80">
                {product.category}
              </span>
              {product.subcategory && (
                <span className="text-[10px] font-medium bg-slate-900/80 text-white px-2 py-0.5 rounded backdrop-blur-sm">
                  {product.subcategory}
                </span>
              )}
            </div>

            {hasOffer && (
              <div className="absolute top-3 right-12 sm:right-3">
                <span className="inline-flex items-center space-x-1 text-[11px] font-bold bg-emerald-600 text-white px-2.5 py-1 rounded-full shadow-sm">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{discountPct}% Bundle Offer</span>
                </span>
              </div>
            )}
          </div>

          {/* Product Info & Action */}
          <div className="p-6 flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="text-[11px] text-indigo-600 font-semibold uppercase tracking-wider flex items-center space-x-1">
                <Tag className="w-3.5 h-3.5" />
                <span>Verified Catalogue Item · ID: {product.id}</span>
              </div>

              <h2 id="product-detail-title" className="text-xl font-bold text-slate-900 leading-snug">
                {product.name}
              </h2>

              <p className="text-xs text-slate-600 leading-relaxed">
                {product.description}
              </p>

              {/* Use Case Tags */}
              {product.use_cases && product.use_cases.length > 0 && (
                <div className="pt-1">
                  <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                    Recommended For
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {product.use_cases.map((uc) => (
                      <span
                        key={uc}
                        className="bg-indigo-50 text-indigo-700 border border-indigo-200 text-[10px] font-medium px-2 py-0.5 rounded-md"
                      >
                        {uc}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Stock and Margin Safety Indicator */}
              <div className="pt-1 flex items-center justify-between text-xs text-slate-500 border-t border-slate-100">
                <span className="inline-flex items-center space-x-1.5">
                  <Package className="w-3.5 h-3.5 text-slate-400" />
                  <span>{product.inventory} units available</span>
                </span>
                <span className="inline-flex items-center space-x-1 text-emerald-700 font-medium text-[11px]">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Price Ceiling Guaranteed</span>
                </span>
              </div>
            </div>

            {/* Pricing & Cart Action */}
            <div className="pt-3 border-t border-slate-100 space-y-3">
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-semibold">
                    {hasOffer ? 'Eligible Bundle Price' : 'Standard Reference Price'}
                  </span>
                  <div className="flex items-baseline space-x-2">
                    <span className="text-2xl font-extrabold text-slate-900 font-mono">
                      ${finalPrice.toFixed(2)}
                    </span>
                    {hasOffer && (
                      <>
                        <span className="text-xs text-slate-400 line-through font-mono">
                          ${product.reference_price.toFixed(2)}
                        </span>
                        <span className="text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                          Save ${savings.toFixed(2)}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {cartQuantity > 0 && (
                  <span className="text-xs text-indigo-700 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded-full font-semibold">
                    {cartQuantity} in cart
                  </span>
                )}
              </div>

              {hasOffer && (
                <p className="text-[11px] text-indigo-700 bg-indigo-50/70 p-2 rounded-lg border border-indigo-100 leading-tight">
                  <span className="font-semibold">Offer Condition:</span> {eligibleOffer!.conditions}
                </p>
              )}

              <button
                onClick={handleAdd}
                className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-sm hover:shadow transition-all flex items-center justify-center space-x-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>
                  {hasOffer ? `Add with ${discountPct}% Bundle Discount` : `Add to Cart${cartQuantity > 0 ? ` (${cartQuantity})` : ''}`}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
