import { X, Trash2, Plus, Minus, ShoppingBag, ArrowRight, RotateCcw, ShieldCheck, Tag, Sparkles } from 'lucide-react';
import { CartItem, RecommendationItem, BasketQuote, ItemExplanation } from '../types.ts';
import { RecommendationCard } from './RecommendationCard.tsx';

interface CartDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  cart: CartItem[];
  onUpdateQuantity: (productId: string, delta: number) => void;
  onRemoveItem: (productId: string) => void;
  onClearCart: () => void;
  onOpenCheckout: () => void;
  recommendations: RecommendationItem[];
  onAcceptRecommendation: (rec: RecommendationItem) => void;
  onDismissRecommendation: (productId: string) => void;
  dismissedIds: Set<string>;
  basketQuote?: BasketQuote | null;
  explanations?: Record<string, ItemExplanation>;
  isAiGenerated?: boolean;
}

export function CartDrawer({
  isOpen,
  onClose,
  cart,
  onUpdateQuantity,
  onRemoveItem,
  onClearCart,
  onOpenCheckout,
  recommendations,
  onAcceptRecommendation,
  onDismissRecommendation,
  dismissedIds,
  basketQuote,
  explanations,
  isAiGenerated,
}: CartDrawerProps) {
  if (!isOpen) return null;

  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

  // Authoritative totals from backend quote when available, fallback to client calculation
  const subtotal = basketQuote
    ? basketQuote.final_subtotal
    : cart.reduce((sum, item) => {
        const price = item.discountedPrice ?? item.product.reference_price;
        return sum + price * item.quantity;
      }, 0);

  const standardSubtotal = basketQuote
    ? basketQuote.standard_subtotal
    : cart.reduce(
        (sum, item) => sum + item.product.reference_price * item.quantity,
        0
      );

  const totalSavings = basketQuote
    ? basketQuote.total_savings
    : Math.max(0, standardSubtotal - subtotal);

  // Filter recommendations: not dismissed and not already in cart
  const activeRecommendations = recommendations.filter(
    (rec) =>
      !dismissedIds.has(rec.product_id) &&
      !cart.some((item) => item.product.id === rec.product_id)
  );

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col">
          {/* Drawer Header */}
          <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-white">
            <div className="flex items-center space-x-2">
              <ShoppingBag className="w-5 h-5 text-indigo-600" />
              <h2 className="text-base font-bold text-slate-900">Your Cart</h2>
              <span className="text-xs bg-indigo-50 text-indigo-700 font-semibold px-2 py-0.5 rounded-full border border-indigo-200">
                {totalItems} {totalItems === 1 ? 'item' : 'items'}
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
              aria-label="Close cart"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {cart.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-4">
                <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                  <ShoppingBag className="w-7 h-7" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-800 text-sm">Your cart is empty</h3>
                  <p className="text-xs text-slate-500 mt-1 max-w-xs leading-relaxed">
                    Explore our 32 curated tech accessories and peripherals to experience FairCart AI.
                  </p>
                </div>
                <button
                  onClick={onClose}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  Browse Catalogue
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="divide-y divide-slate-100">
                  {cart.map((item) => {
                    const unitPrice = item.discountedPrice ?? item.product.reference_price;
                    const lineTotal = unitPrice * item.quantity;
                    const hasDiscount =
                      item.discountedPrice !== undefined &&
                      item.discountedPrice < item.product.reference_price;

                    return (
                      <div key={item.product.id} className="py-3.5 flex items-start space-x-3">
                        {/* Fixed Aspect Thumbnail */}
                        <img
                          src={item.product.image_url}
                          alt={item.product.name}
                          className="w-16 h-16 rounded-lg object-cover bg-slate-100 border border-slate-200 shrink-0"
                          onError={(e) => {
                            e.currentTarget.src =
                              'https://images.unsplash.com/photo-1526738549149-8e07eca6c147?auto=format&fit=crop&w=600&q=80';
                          }}
                        />

                        {/* Info & Controls */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between">
                            <h4 className="text-xs font-semibold text-slate-900 truncate pr-2">
                              {item.product.name}
                            </h4>
                            <button
                              onClick={() => onRemoveItem(item.product.id)}
                              className="text-slate-400 hover:text-red-500 p-0.5 transition-colors focus:outline-none focus:ring-2 focus:ring-red-400 rounded"
                              aria-label={`Remove ${item.product.name}`}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          <div className="flex items-center space-x-1.5 mt-0.5">
                            {hasDiscount ? (
                              <>
                                <span className="text-xs font-bold text-emerald-700 font-mono">
                                  ${unitPrice.toFixed(2)}
                                </span>
                                <span className="text-[11px] text-slate-400 line-through font-mono">
                                  ${item.product.reference_price.toFixed(2)}
                                </span>
                                <span className="inline-flex items-center px-1 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800">
                                  Bundle
                                </span>
                              </>
                            ) : (
                              <span className="text-[11px] text-slate-500 font-mono">
                                ${item.product.reference_price.toFixed(2)} each · {item.product.category}
                              </span>
                            )}
                          </div>

                          {/* Applied bundle condition note */}
                          {hasDiscount && item.appliedCondition && (
                            <p className="text-[10px] text-indigo-700 font-medium truncate mt-0.5">
                              {item.appliedCondition}
                            </p>
                          )}

                          <div className="flex items-center justify-between mt-2">
                            {/* Quantity Controls */}
                            <div className="flex items-center border border-slate-200 rounded-md overflow-hidden bg-slate-50">
                              <button
                                onClick={() => onUpdateQuantity(item.product.id, -1)}
                                className="p-1 hover:bg-slate-200 text-slate-600 transition-colors focus:outline-none"
                                aria-label="Decrease quantity"
                              >
                                <Minus className="w-3 h-3" />
                              </button>
                              <span className="px-2 text-xs font-semibold text-slate-800 font-mono">
                                {item.quantity}
                              </span>
                              <button
                                onClick={() => onUpdateQuantity(item.product.id, 1)}
                                className="p-1 hover:bg-slate-200 text-slate-600 transition-colors focus:outline-none"
                                aria-label="Increase quantity"
                              >
                                <Plus className="w-3 h-3" />
                              </button>
                            </div>

                            {/* Line Subtotal */}
                            <span className="text-xs font-bold text-slate-900 font-mono">
                              ${lineTotal.toFixed(2)}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* FairCart Recommendations Section Inside Drawer */}
                {activeRecommendations.length > 0 && (
                  <div className="pt-3 border-t border-slate-100 space-y-2.5">
                    <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-800">
                      <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Recommended Complements</span>
                    </div>

                    <div className="space-y-3">
                      {activeRecommendations.slice(0, 3).map((rec) => {
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
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Drawer Footer */}
          {cart.length > 0 && (
            <div className="p-5 border-t border-slate-200 bg-slate-50/80 space-y-3">
              {/* Subtotal & Savings Breakdown */}
              <div className="space-y-1">
                {totalSavings > 0.005 && (
                  <div className="flex items-center justify-between text-xs text-emerald-700">
                    <span className="flex items-center space-x-1 font-medium">
                      <Tag className="w-3 h-3" />
                      <span>Bundle Discount Applied</span>
                    </span>
                    <span className="font-mono font-bold">-${totalSavings.toFixed(2)}</span>
                  </div>
                )}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-600 font-medium">Cart Subtotal</span>
                  <span className="text-lg font-bold text-slate-900 font-mono">
                    ${subtotal.toFixed(2)}
                  </span>
                </div>
                {basketQuote && (
                  <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                    <span>Verified Gross Margin</span>
                    <span className="font-semibold text-indigo-700">
                      {(basketQuote.basket_gross_margin * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>

              {/* Ethical Commerce Trust Banner */}
              <div className="flex items-center space-x-2 text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg px-2.5 py-1.5 font-medium">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>FairCart AI guarantees transparent pricing and no artificial countdowns.</span>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2 pt-1">
                <button
                  onClick={onOpenCheckout}
                  className="w-full flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 px-4 rounded-lg shadow-sm transition-colors text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
                >
                  <span>Simulate Checkout</span>
                  <ArrowRight className="w-4 h-4" />
                </button>

                <button
                  onClick={onClearCart}
                  className="w-full flex items-center justify-center space-x-1.5 text-xs text-slate-500 hover:text-slate-800 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-300 rounded"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset Cart</span>
                </button>
              </div>

              <p className="text-[10px] text-center text-slate-400">
                Demo Mode · Zero payment collected
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
