import { CheckCircle2, X, ShoppingBag, ShieldCheck } from 'lucide-react';
import { CartItem } from '../types.ts';

interface CheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  cart: CartItem[];
  onCompleteOrder: () => void;
}

export function CheckoutModal({
  isOpen,
  onClose,
  cart,
  onCompleteOrder,
}: CheckoutModalProps) {
  if (!isOpen) return null;

  const subtotal = cart.reduce((sum, item) => sum + item.product.reference_price * item.quantity, 0);
  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
  const orderId = `FC-${Math.floor(100000 + Math.random() * 900000)}`;
  const orderTimestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

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
          <div className="bg-emerald-600 px-6 py-5 text-white flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <CheckCircle2 className="w-6 h-6 text-emerald-200" />
              <div>
                <h3 className="text-base font-bold leading-6">Demo Order Simulated</h3>
                <p className="text-xs text-emerald-100">Order ID: #{orderId} · {orderTimestamp}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-emerald-100 hover:text-white p-1 rounded-lg hover:bg-emerald-700/50 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6 space-y-5">
            {/* Safe Demo Notice Banner */}
            <div className="flex items-start space-x-2.5 bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-xs text-emerald-900">
              <ShieldCheck className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
              <p>
                <strong>Zero Payment Collected:</strong> FairCart AI operates with zero payment collection. This checkout confirms the simulated cart state for demonstration and testing.
              </p>
            </div>

            {/* Receipt Item Breakdown */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Order Items ({totalItems})
              </h4>
              <div className="max-h-56 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-lg">
                {cart.map((item) => (
                  <div key={item.product.id} className="p-3 flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2.5 min-w-0 pr-2">
                      <ShoppingBag className="w-4 h-4 text-slate-400 shrink-0" />
                      <div className="truncate">
                        <span className="font-semibold text-slate-900">{item.product.name}</span>
                        <span className="text-slate-400 ml-1.5">x{item.quantity}</span>
                      </div>
                    </div>
                    <span className="font-mono font-semibold text-slate-800 shrink-0">
                      ${(item.product.reference_price * item.quantity).toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Cost Summary Table */}
            <div className="bg-slate-50 rounded-lg p-3.5 space-y-2 text-xs border border-slate-200">
              <div className="flex justify-between text-slate-600">
                <span>Items Subtotal</span>
                <span className="font-mono">${subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Shipping (Standard Ground)</span>
                <span className="text-emerald-600 font-semibold">$0.00 (Demo Free)</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Estimated Sales Tax</span>
                <span className="font-mono">$0.00</span>
              </div>
              <div className="border-t border-slate-200 pt-2 flex justify-between font-bold text-sm text-slate-900">
                <span>Total Simulated Value</span>
                <span className="font-mono text-base text-indigo-700">${subtotal.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* Modal Actions */}
          <div className="bg-slate-50 px-6 py-4 flex items-center justify-end space-x-3 border-t border-slate-200">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 rounded-lg transition-colors"
            >
              Keep Cart
            </button>
            <button
              onClick={handleFinish}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
            >
              Complete & Reset Cart
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
