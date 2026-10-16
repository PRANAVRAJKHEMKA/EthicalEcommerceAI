import { CheckCircle2, X, ShoppingBag, ShieldCheck, Tag, RefreshCw } from 'lucide-react';
import { CartItem, BasketQuote } from '../types.ts';
import { isQuoteAlignedWithCart } from './CartDrawer.tsx';

interface CheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  cart: CartItem[];
  onCompleteOrder: () => void;
  basketQuote?: BasketQuote | null;
  isQuoteUpdating?: boolean;
  marginFloor?: number;
}

export function CheckoutModal({
  isOpen,
  onClose,
  cart,
  onCompleteOrder,
  basketQuote,
  isQuoteUpdating,
  marginFloor,
}: CheckoutModalProps) {
  if (!isOpen) return null;

  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

  // Quote alignment check to prevent stale quotes from rendering in receipt
  const isAligned = isQuoteAlignedWithCart(basketQuote, cart);
  const activeQuote = isAligned ? basketQuote : null;
  const isPending = Boolean(isQuoteUpdating || (!isAligned && cart.length > 0));

  // Authoritative totals from backend quote when aligned, fallback to client line totals
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

  const totalCogs = cart.reduce((sum, item) => sum + item.product.cogs * item.quantity, 0);
  const clientGrossMargin = subtotal > 0 ? (subtotal - totalCogs) / subtotal : 0.0;
  const displayedMargin = activeQuote ? activeQuote.basket_gross_margin : clientGrossMargin;
  const hasActiveDiscount = totalSavings > 0.005;
  const activeFloor = marginFloor ?? 0.20;

  const orderId = `FC-${Math.floor(100000 + Math.random() * 900000)}`;
  const orderTimestamp = new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  const handleFinish = () => {
    onCompleteOrder();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="flex min-h-full items-center justify-center p-4 text-center sm:p-0">
        <div className="relative transform overflow-hidden rounded-2xl bg-white text-left shadow-2xl transition-all sm:my-8 sm:w-full sm:max-w-lg border border-slate-200">
          {/* Modal Header */}
          <div className="bg-slate-900 px-6 py-5 text-white flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold leading-6 text-white">Demo Order Confirmed</h3>
                <p className="text-xs text-slate-400 font-mono">
                  Order ID: #{orderId} · {orderTimestamp}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
              aria-label="Close order receipt"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6 space-y-5">
            {/* Safe Demo Notice Banner */}
            <div className="flex items-start space-x-2.5 bg-emerald-50/80 border border-emerald-200 rounded-xl p-3 text-xs text-emerald-900">
              <ShieldCheck className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
              <p>
                <strong>Zero Payment Collected:</strong> FairCart AI operates with zero payment collection. This checkout confirms the simulated cart state for demonstration and testing.
              </p>
            </div>

            {/* Receipt Item Breakdown */}
            <div>
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                Order Items ({totalItems})
              </h4>
              <div className="max-h-56 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-xl">
                {cart.map((item) => {
                  const quoteItem = activeQuote?.items.find((qi) => qi.product_id === item.product.id);
                  const unitPrice = quoteItem ? quoteItem.unit_price : (item.discountedPrice ?? item.product.reference_price);
                  const lineTotal = quoteItem ? quoteItem.line_total : unitPrice * item.quantity;
                  const isDiscounted = quoteItem
                    ? quoteItem.discount_percentage > 0
                    : (item.discountedPrice !== undefined && item.discountedPrice < item.product.reference_price);

                  return (
                    <div
                      key={item.product.id}
                      className="p-3 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center space-x-2.5 min-w-0 pr-2">
                        <ShoppingBag className="w-4 h-4 text-slate-400 shrink-0" />
                        <div className="truncate">
                          <div className="flex items-center space-x-1.5">
                            <span className="font-semibold text-slate-900 truncate">
                              {item.product.name}
                            </span>
                            <span className="text-slate-400 text-[11px]">x{item.quantity}</span>
                            {isDiscounted && (
                              <span className="text-[10px] text-emerald-700 font-semibold bg-emerald-50 px-1 py-0.2 rounded border border-emerald-200">
                                Bundle Deal
                              </span>
                            )}
                          </div>
                          {isDiscounted && (item.appliedCondition || quoteItem?.applied_condition) && (
                            <p className="text-[10px] text-indigo-700 font-medium truncate mt-0.5">
                              {item.appliedCondition || quoteItem?.applied_condition}
                            </p>
                          )}
                          {!isDiscounted && (
                            (item.appliedCondition && item.appliedCondition.includes('·')) ||
                            (quoteItem?.applied_condition && quoteItem.applied_condition.includes('·') && !quoteItem.applied_condition.includes('No discount applied'))
                          ) && (
                            <p className="text-[10px] text-amber-700 font-medium truncate mt-0.5">
                              ⚠️ {quoteItem?.applied_condition || item.appliedCondition}
                            </p>
                          )}
                        </div>
                      </div>
                      <span className="font-mono font-semibold text-slate-800 shrink-0">
                        ${lineTotal.toFixed(2)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Cost Summary Table */}
            <div className="bg-slate-50 rounded-xl p-4 space-y-2 text-xs border border-slate-200">
              <div className="flex justify-between text-slate-600">
                <span>Items Subtotal</span>
                <span className="font-mono font-semibold text-slate-900">
                  ${standardSubtotal.toFixed(2)}
                </span>
              </div>
              {totalSavings > 0.005 && (
                <div className="flex justify-between text-emerald-700 font-medium">
                  <span className="flex items-center space-x-1">
                    <Tag className="w-3.5 h-3.5" />
                    <span>FairCart Bundle Savings</span>
                  </span>
                  <span className="font-mono font-bold">-${totalSavings.toFixed(2)}</span>
                </div>
              )}
              <div className="flex justify-between text-slate-600">
                <span>Shipping (Standard Ground)</span>
                <span className="text-emerald-700 font-semibold">$0.00 (Demo Free)</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Estimated Sales Tax</span>
                <span className="font-mono">$0.00</span>
              </div>
              <div className="border-t border-slate-200 pt-2 flex justify-between font-bold text-sm text-slate-900">
                <span>Total Simulated Value</span>
                <span className="font-mono text-base text-indigo-700">
                  ${subtotal.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between text-[11px] text-slate-500 font-mono pt-1 border-t border-slate-200/50">
                <span>{hasActiveDiscount ? 'Verified Bundle Margin' : 'Catalogue Base Margin'}</span>
                <span className={`font-semibold ${hasActiveDiscount ? 'text-indigo-700' : 'text-slate-700'}`}>
                  {(displayedMargin * 100).toFixed(1)}%
                  {hasActiveDiscount && ` (Floor: ${(activeFloor * 100).toFixed(0)}%)`}
                </span>
              </div>

              {isPending && (
                <div className="flex items-center space-x-1.5 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 font-medium">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin shrink-0 text-amber-600" />
                  <span>Revalidating authoritative quote. Please wait before confirming order...</span>
                </div>
              )}
            </div>
          </div>

          {/* Modal Actions */}
          <div className="bg-slate-50 px-6 py-4 flex items-center justify-end space-x-3 border-t border-slate-200">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400"
            >
              Keep Cart
            </button>
            <button
              onClick={handleFinish}
              disabled={isPending || cart.length === 0}
              className={`px-4 py-2 font-semibold rounded-lg shadow-sm transition-colors text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                isPending || cart.length === 0
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer'
              }`}
            >
              {isPending ? 'Updating Quote...' : 'Complete & Reset Cart'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
