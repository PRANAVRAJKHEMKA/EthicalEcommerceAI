import { useState, useEffect } from 'react';
import { X, Package, Clock, ShieldCheck, Tag, Loader2, Sparkles } from 'lucide-react';
import { OrderDetail, UserProfile } from '../types.ts';
import { fetchUserOrders } from '../api.ts';

interface OrderHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile;
}

export function OrderHistoryModal({ isOpen, onClose, user }: OrderHistoryModalProps) {
  const [orders, setOrders] = useState<OrderDetail[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      setErrorMessage(null);
      fetchUserOrders()
        .then((data) => {
          setOrders(data);
        })
        .catch((err: any) => {
          setErrorMessage(err.message || 'Failed to load order history.');
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [isOpen, user.id]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="flex min-h-screen items-center justify-center p-4">
        <div
          className="relative w-full max-w-2xl rounded-2xl bg-white p-6 md:p-8 shadow-2xl transition-all border border-slate-100 max-h-[90vh] flex flex-col"
          role="dialog"
          aria-modal="true"
        >
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute right-4 top-4 rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Header */}
          <div className="flex items-center gap-3 mb-3 shrink-0">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
              <Package className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900">Order History</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium">
                  {user.display_name}
                </span>
              </div>
              <p className="text-xs text-slate-500 font-mono">Account ID: {user.username}</p>
            </div>
          </div>

          {/* Persona & Recommendation Anchor Callout */}
          <div className="mb-4 p-3 rounded-xl bg-amber-50/70 border border-amber-200/80 text-xs text-amber-900 shrink-0">
            <div className="flex items-start gap-2">
              <Sparkles className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-amber-950">Recommendation Engine Integration:</span>{' '}
                These past orders act as authenticated historical order anchors (
                <code className="font-mono text-[11px] bg-amber-100 px-1 py-0.5 rounded text-amber-900">O</code>
                ) in FairCart AI&apos;s candidate generation pool (
                <code className="font-mono text-[11px] bg-amber-100 px-1 py-0.5 rounded text-amber-900">
                  A = B ∪ V ∪ S ∪ O
                </code>
                ). Suggestions in the catalog are tailored to this persona without leaking across sessions.
              </div>
            </div>
          </div>

          {/* Content Body */}
          <div className="overflow-y-auto pr-1 flex-1 space-y-4">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                <Loader2 className="h-8 w-8 animate-spin mb-2 text-indigo-600" />
                <p className="text-sm">Loading verified order history...</p>
              </div>
            ) : errorMessage ? (
              <div className="rounded-lg bg-rose-50 p-4 text-xs text-rose-700 border border-rose-200">
                {errorMessage}
              </div>
            ) : orders.length === 0 ? (
              <div className="text-center py-12 text-slate-400">
                <Package className="h-10 w-10 mx-auto mb-2 text-slate-300" />
                <p className="text-sm font-medium text-slate-600">No past orders found</p>
                <p className="text-xs text-slate-400 mt-1">
                  Complete a simulated checkout while signed in to record a new verified order.
                </p>
              </div>
            ) : (
              orders.map((order) => (
                <div
                  key={order.id}
                  className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all"
                >
                  {/* Order Top Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-800">{order.id}</span>
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-200">
                        <ShieldCheck className="h-3 w-3" />
                        {order.status}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
                        {order.provenance}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 text-[11px] text-slate-500">
                      <Clock className="h-3.5 w-3.5 text-slate-400" />
                      <span>{new Date(order.created_at).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}</span>
                    </div>
                  </div>

                  {/* Items list */}
                  <div className="divide-y divide-slate-100">
                    {order.items.map((item, idx) => (
                      <div key={`${order.id}-${item.product_id}-${idx}`} className="py-2.5 flex items-center justify-between gap-3 text-xs">
                        <div className="flex items-center gap-2.5 min-w-0">
                          {item.image_url ? (
                            <img
                              src={item.image_url}
                              alt={item.name}
                              className="h-10 w-10 rounded-lg object-cover bg-slate-100 border border-slate-200 shrink-0"
                            />
                          ) : (
                            <div className="h-10 w-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400 shrink-0">
                              <Package className="h-5 w-5" />
                            </div>
                          )}
                          <div className="min-w-0">
                            <p className="font-semibold text-slate-800 truncate">{item.name}</p>
                            <p className="text-[11px] text-slate-400">
                              Qty: {item.quantity} • {item.category}
                            </p>
                          </div>
                        </div>

                        <div className="text-right shrink-0">
                          <p className="font-semibold text-slate-900">${item.line_total.toFixed(2)}</p>
                          {item.savings > 0 && (
                            <p className="text-[11px] text-emerald-600 font-medium">
                              Saved ${(item.savings * item.quantity).toFixed(2)}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Order Footer Totals */}
                  <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                    <div className="text-slate-500 text-[11px]">
                      {order.total_savings > 0 ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-medium">
                          <Tag className="h-3 w-3" />
                          Total Order Savings: ${order.total_savings.toFixed(2)}
                        </span>
                      ) : (
                        <span>Standard reference pricing</span>
                      )}
                    </div>
                    <div className="text-right">
                      <span className="text-slate-500 text-[11px] mr-1">Paid Total:</span>
                      <span className="font-bold text-slate-900 text-sm">
                        ${order.total_amount.toFixed(2)} {order.currency}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer note */}
          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400 shrink-0">
            <span>Verified Persona Orders: {orders.length}</span>
            <span>Zero Cross-Account Leakage Guaranteed</span>
          </div>
        </div>
      </div>
    </div>
  );
}
