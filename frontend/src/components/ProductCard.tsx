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
    <div className="bg-white rounded-xl border border-slate-200/90 overflow-hidden shadow-sm hover:shadow-md hover:border-slate-300 transition-all duration-200 flex flex-col justify-between group">
      <div>
        {/* Fixed Aspect Image Container */}
        <div className="relative h-44 w-full bg-slate-100 overflow-hidden">
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={(e) => {
              // Graceful fallback to neutral tech photo if external URL fails
              e.currentTarget.src =
                'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80';
            }}
          />
          <div className="absolute top-2.5 left-2.5">
            <span className="text-[10px] font-semibold tracking-wider uppercase bg-white/95 backdrop-blur-sm text-slate-700 px-2 py-0.5 rounded shadow-sm border border-slate-200/80">
              {product.category}
            </span>
          </div>
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
      <div className="p-4 pt-3 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
        <div>
          <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-semibold">
            Price
          </span>
          <span className="text-base font-bold text-slate-900 font-mono">
            ${product.reference_price.toFixed(2)}
          </span>
        </div>

        <button
          onClick={handleAdd}
          className={`inline-flex items-center justify-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 transition-all ${
            justAdded
              ? 'bg-emerald-600 text-white'
              : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm hover:shadow'
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
