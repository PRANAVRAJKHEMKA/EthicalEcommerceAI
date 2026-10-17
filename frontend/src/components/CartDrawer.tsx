import { X, Trash2, Plus, Minus, ShoppingBag, ArrowRight, RotateCcw, ShieldCheck, Tag, Sparkles, RefreshCw } from 'lucide-react';
import { CartItem, RecommendationItem, BasketQuote, ItemExplanation } from '../types.ts';
import { RecommendationCard } from './RecommendationCard.tsx';

/**
 * Validates whether an asynchronous backend basket quote exactly corresponds
 * to the current client cart contents and quantities.
 */
export function isQuoteAlignedWithCart(
  quote: BasketQuote | null | undefined,
  cart: CartItem[]
): boolean {
  if (!quote || !quote.items) return false;
  if (cart.length === 0) return quote.items.length === 0;
  if (quote.items.length !== cart.length) return false;

  const quoteMap = new Map<string, number>();
  for (const item of quote.items) {
    quoteMap.set(item.product_id, (quoteMap.get(item.product_id) || 0) + item.quantity);
  }

  for (const cartItem of cart) {
    const quoteQty = quoteMap.get(cartItem.product.id);
    if (quoteQty !== cartItem.quantity) {
      return false;
    }
  }
  return true;
}

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
  isQuoteUpdating?: boolean;
  marginFloor?: number;
  onOpenPassport?: (rec: RecommendationItem) => void;
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
  isQuoteUpdating,
  marginFloor,
  onOpenPassport,
}: CartDrawerProps) {
  if (!isOpen) return null;

  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

  // Quote alignment verification: discard stale quotes from previous cart states
  const isAligned = isQuoteAlignedWithCart(basketQuote, cart);
  const activeQuote = isAligned ? basketQuote : null;
  const isPending = Boolean(isQuoteUpdating || (!isAligned && cart.length > 0));

  // Authoritative totals: use aligned backend quote when available, fallback to client line totals
  const subtotal = activeQuote
    ? activeQuote.final_subtotal
    : cart.reduce((sum, item) => {
        const price = item.discountedPrice ?? item.product.reference_price;
        return sum + price * item.quantity;
      }, 0);

  const standardSubtotal = activeQuote
    ? activeQuote.standard_subtotal
    : cart.reduce(
        (sum, item) => sum + item.product.reference_price * item.quantity,
        0
      );

  const totalSavings = activeQuote
    ? activeQuote.total_savings
    : Math.max(0, standardSubtotal - subtotal);

  // Margin calculation: use authoritative backend margin when aligned, or compute exact client baseline
  const totalCogs = cart.reduce((sum, item) => sum + item.product.cogs * item.quantity, 0);
  const clientGrossMargin = subtotal > 0 ? (subtotal - totalCogs) / subtotal : 0.0;
  const displayedMargin = activeQuote ? activeQuote.basket_gross_margin : clientGrossMargin;
  const hasActiveDiscount = totalSavings > 0.005;
  const activeFloor = marginFloor ?? 0.20;
  const isBelowFloor = displayedMargin < activeFloor;

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
                    Explore our curated everyday essentials, culinary staples, and desk tech to experience FairCart AI.
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
                    const quoteItem = activeQuote?.items.find((qi) => qi.product_id === item.product.id);
                    const unitPrice = quoteItem ? quoteItem.unit_price : (item.discountedPrice ?? item.product.reference_price);
                    const lineTotal = quoteItem ? quoteItem.line_total : unitPrice * item.quantity;
                    const hasDiscount = quoteItem
                      ? quoteItem.discount_percentage > 0
                      : (item.discountedPrice !== undefined && item.discountedPrice < item.product.reference_price);

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
                                {onOpenPassport && (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      onOpenPassport({
                                        product_id: item.product.id,
                                        name: item.product.name,
                                        category: item.product.category,
                                        reference_price: item.product.reference_price,
                                        is_offered: true,
                                        discount_percentage: item.appliedDiscountPct ?? 0,
                                        final_price: unitPrice,
                                        savings: Math.max(0, item.product.reference_price - unitPrice),
                                        currency: 'USD',
                                        tier: 'Bundle',
                                        conditions: item.appliedCondition || 'Active bundle offer',
                                        basket_gross_margin: displayedMargin,
                                        decision_reason: item.appliedCondition || 'Active bundle offer',
                                        affinity_score: 1.0,
                                        compatibility_reason: item.product.description,
                                        inventory: item.product.inventory,
                                        image_url: item.product.image_url,
                                      })
                                    }
                                    className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition-colors"
                                    title="View Fair Deal Passport explanation"
                                  >
                                    Deal Passport
                                  </button>
                                )}
                              </>
                            ) : (
                              <span className="text-[11px] text-slate-500 font-mono">
                                ${item.product.reference_price.toFixed(2)} each · {item.product.category}
                              </span>
                            )}
                          </div>

                          {/* Applied bundle condition note or revocation warning */}
                          {hasDiscount && (item.appliedCondition || quoteItem?.applied_condition) && (
                            <p className="text-[10px] text-indigo-700 font-medium truncate mt-0.5">
                              {item.appliedCondition || quoteItem?.applied_condition}
                            </p>
                          )}
                          {!hasDiscount && (
                            (item.appliedCondition && item.appliedCondition.includes('·')) ||
                            (quoteItem?.applied_condition && quoteItem.applied_condition.includes('·') && !quoteItem.applied_condition.includes('No discount applied'))
                          ) && (
                            <p className="text-[10px] text-amber-700 font-medium truncate mt-0.5 flex items-center gap-1">
                              <span>⚠️ {quoteItem?.applied_condition || item.appliedCondition}</span>
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
                            onOpenPassport={onOpenPassport}
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
              <div className="space-y-1.5">
                {/* Pending Revalidation Status */}
                {isPending && (
                  <div className="flex items-center space-x-1.5 text-[11px] text-amber-700 bg-amber-50 border border-amber-200/80 rounded px-2.5 py-1 font-medium animate-pulse">
                    <RefreshCw className="w-3 h-3 animate-spin shrink-0 text-amber-600" />
                    <span>Revalidating authoritative quote & policy floor...</span>
                  </div>
                )}

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

                {/* Margin Transparency & Floor Compliance */}
                <div className="pt-1 border-t border-slate-200/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-slate-500">
                      {hasActiveDiscount ? 'Verified Bundle Margin' : 'Catalogue Base Margin'}
                    </span>
                    <span className={`font-semibold ${hasActiveDiscount ? 'text-indigo-700' : 'text-slate-700'}`}>
                      {(displayedMargin * 100).toFixed(1)}%
                    </span>
                  </div>

                  {!hasActiveDiscount && isBelowFloor && (
                    <div className="text-[10px] text-amber-800 bg-amber-50 border border-amber-200/80 rounded px-2 py-1 leading-snug">
                      Catalogue base margin ({(displayedMargin * 100).toFixed(1)}%) is below active{' '}
                      {(activeFloor * 100).toFixed(0)}% floor. Discounts cannot be applied because catalogue prices cannot be raised.
                    </div>
                  )}

                  {hasActiveDiscount && (
                    <div className="text-[10px] text-emerald-800 bg-emerald-50 border border-emerald-200/80 rounded px-2 py-0.5 font-medium">
                      Guaranteed: Bundle discount satisfies merchant {(activeFloor * 100).toFixed(0)}% margin floor.
                    </div>
                  )}
                </div>
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
                  disabled={isPending || cart.length === 0}
                  className={`w-full flex items-center justify-center space-x-2 font-semibold py-2.5 px-4 rounded-lg shadow-sm transition-colors text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 ${
                    isPending || cart.length === 0
                      ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                      : 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer'
                  }`}
                  title={isPending ? 'Please wait while quote revalidates' : 'Simulate Checkout'}
                >
                  <span>{isPending ? 'Updating Quote...' : 'Simulate Checkout'}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>

                <button
                  onClick={onClearCart}
                  className="w-full flex items-center justify-center space-x-1.5 text-xs text-slate-500 hover:text-slate-800 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-300 rounded cursor-pointer"
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
