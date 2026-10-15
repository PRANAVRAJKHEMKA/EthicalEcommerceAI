import { useState } from 'react';
import { Plus, Check, Package, Sparkles } from 'lucide-react';
import { Product, RecommendationItem } from '../types.ts';

interface ProductCardProps {
  product: Product;
  onAddToCart: (
    product: Product,
    customPrice?: number,
    discountPct?: number,
    condition?: string
  ) => void;
  cartQuantity: number;
  eligibleOffer?: RecommendationItem;
}

export function ProductCard({
  product,
  onAddToCart,
  cartQuantity,
  eligibleOffer,
}: ProductCardProps) {
  const [justAdded, setJustAdded] = useState(false);

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
    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 900);
  };

  return (
    <div className={`bg-white rounded-xl border overflow-hidden shadow-sm hover:shadow-md transition-all duration-200 flex flex-col justify-between group ${
      hasOffer ? 'border-indigo-300 ring-1 ring-indigo-200/50' : 'border-slate-200/90 hover:border-slate-300'
    }`}>
      <div>
        {/* Fixed Aspect Image Container */}
        <div className="relative h-44 w-full bg-slate-100 overflow-hidden">
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={(e) => {
              e.currentTarget.src =
                'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80';
            }}
          />

          {/* Category Pill */}
          <div className="absolute top-2.5 left-2.5">
            <span className="text-[10px] font-semibold tracking-wider uppercase bg-white/95 backdrop-blur-sm text-slate-700 px-2 py-0.5 rounded shadow-sm border border-slate-200/80">
              {product.category}
            </span>
          </div>

          {/* Contextual Offer Badge on Product Card */}
          {hasOffer && (
            <div className="absolute top-2.5 right-2.5">
              <span className="inline-flex items-center space-x-1 text-[10px] font-bold bg-emerald-600 text-white px-2 py-0.5 rounded shadow-sm">
                <Sparkles className="w-3 h-3" />
                <span>{discountPct}% Bundle Deal</span>
              </span>
            </div>
          )}
        </div>

        {/* Product Details */}
        <div className="p-4">
          <h3 className="font-semibold text-slate-900 text-sm leading-snug line-clamp-1 group-hover:text-indigo-600 transition-colors">
            {product.name}
          </h3>
          <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed h-8">
            {product.description}
          </p>

          <div className="flex items-center space-x-1.5 mt-3 text-xs text-slate-500 font-medium">
            <Package className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span>{product.inventory} in stock</span>
          </div>
        </div>
      </div>

      {/* Pricing & Add to Cart Action */}
      <div className={`p-4 pt-3 border-t flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
        hasOffer ? 'bg-indigo-50/40 border-indigo-100' : 'bg-slate-50/50 border-slate-100'
      }`}>
        <div className="min-w-0">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-semibold">
            {hasOffer ? 'Bundle Offer' : 'Standard Price'}
          </span>
          <div className="flex items-baseline space-x-1.5">
            <span className="text-base font-bold text-slate-900 font-mono">
              ${finalPrice.toFixed(2)}
            </span>
            {hasOffer && (
              <>
                <span className="text-xs text-slate-400 line-through font-mono">
                  ${product.reference_price.toFixed(2)}
                </span>
                <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1 rounded">
                  Save ${savings.toFixed(2)}
                </span>
              </>
            )}
          </div>
          {hasOffer && (
            <span className="text-[10px] text-indigo-700 font-medium block truncate mt-0.5">
              {eligibleOffer!.conditions}
            </span>
          )}
        </div>

        <button
          onClick={handleAdd}
          className={`inline-flex items-center justify-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 transition-all shrink-0 ${
            justAdded
              ? 'bg-emerald-600 text-white'
              : hasOffer
              ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm hover:shadow'
              : 'bg-slate-900 hover:bg-slate-800 text-white shadow-sm'
          }`}
          aria-label={`Add ${product.name} to cart`}
        >
          {justAdded ? (
            <>
              <Check className="w-3.5 h-3.5" />
              <span>Added</span>
            </>
          ) : (
            <>
              <Plus className="w-3.5 h-3.5" />
              <span>{hasOffer ? 'Add Bundle' : `Add${cartQuantity > 0 ? ` (${cartQuantity})` : ''}`}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
