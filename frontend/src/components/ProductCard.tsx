import { useState } from 'react';
import { Plus, Check, Package } from 'lucide-react';
import { Product } from '../types.ts';

interface ProductCardProps {
  product: Product;
  onAddToCart: (product: Product) => void;
  cartQuantity: number;
}

export function ProductCard({ product, onAddToCart, cartQuantity }: ProductCardProps) {
  const [justAdded, setJustAdded] = useState(false);

  const handleAdd = () => {
    onAddToCart(product);
    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 900);
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between">
      <div>
        {/* Product Image */}
        <div className="relative aspect-video w-full bg-slate-100 overflow-hidden">
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={(e) => {
              // Fallback to placeholder if image fails to load
              e.currentTarget.src =
                'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80';
            }}
          />
          <div className="absolute top-2.5 left-2.5">
            <span className="text-[11px] font-semibold tracking-wide uppercase bg-white/90 backdrop-blur-sm text-slate-800 px-2 py-0.5 rounded shadow-sm border border-slate-200/50">
              {product.category}
            </span>
          </div>
        </div>

        {/* Product Details */}
        <div className="p-4">
          <h3 className="font-semibold text-slate-900 text-base leading-snug line-clamp-1">
            {product.name}
          </h3>
          <p className="text-xs text-slate-500 mt-1.5 line-clamp-2 leading-relaxed">
            {product.description}
          </p>

          <div className="flex items-center space-x-1.5 mt-3 text-xs text-slate-500 font-medium">
            <Package className="w-3.5 h-3.5 text-slate-400" />
            <span>{product.inventory} in stock</span>
          </div>
        </div>
      </div>

      {/* Pricing & Add to Cart Footer */}
      <div className="p-4 pt-0 border-t border-slate-100 mt-2 flex items-center justify-between">
        <div>
          <span className="text-xs text-slate-400 block font-medium">Reference Price</span>
          <span className="text-lg font-bold text-slate-900">
            ${product.reference_price.toFixed(2)}
          </span>
        </div>

        <button
          onClick={handleAdd}
          className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
            justAdded
              ? 'bg-emerald-600 text-white'
              : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm'
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
              <span>Add{cartQuantity > 0 ? ` (${cartQuantity})` : ''}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
