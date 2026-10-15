import { X, ShieldCheck, Cpu, Lock, CheckCircle2, AlertCircle } from 'lucide-react';

interface TransparencyModalProps {
  isOpen: boolean;
  onClose: () => void;
  geminiConfigured?: boolean;
}

export function TransparencyModal({
  isOpen,
  onClose,
  geminiConfigured = false,
}: TransparencyModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="flex min-h-full items-center justify-center p-4 text-center sm:p-0">
        <div className="relative transform overflow-hidden rounded-2xl bg-white text-left shadow-2xl transition-all sm:my-8 sm:w-full sm:max-w-2xl border border-slate-200">
          {/* Header */}
          <div className="bg-slate-900 px-6 py-5 text-white flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                <ShieldCheck className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <h3 className="text-base font-bold leading-6 text-white">
                  How Recommendations & Offers Work
                </h3>
                <p className="text-xs text-slate-400 font-mono">
                  FairCart AI Ethical Commerce Protocol
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
              aria-label="Close transparency disclosure"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content Body */}
          <div className="p-6 space-y-5 text-xs text-slate-600 leading-relaxed max-h-[75vh] overflow-y-auto">
            {/* Core Pillars */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
                <div className="flex items-center space-x-1.5 font-bold text-slate-900 text-xs">
                  <Cpu className="w-4 h-4 text-indigo-600" />
                  <span>Dual Engines</span>
                </div>
                <p className="text-[11px] text-slate-500">
                  Relevance (Engine A) and economic incentives (Engine B) are evaluated as separate, inspectable stages.
                </p>
              </div>

              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
                <div className="flex items-center space-x-1.5 font-bold text-slate-900 text-xs">
                  <Lock className="w-4 h-4 text-emerald-600" />
                  <span>Zero Price Hikes</span>
                </div>
                <p className="text-[11px] text-slate-500">
                  FairCart AI never inflates reference prices or uses dynamic surge pricing. Offers only reduce prices.
                </p>
              </div>

              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
                <div className="flex items-center space-x-1.5 font-bold text-slate-900 text-xs">
                  <CheckCircle2 className="w-4 h-4 text-blue-600" />
                  <span>No Tracking</span>
                </div>
                <p className="text-[11px] text-slate-500">
                  Zero invasive profiling, zero third-party surveillance cookies. Context derives from your explicit filter.
                </p>
              </div>
            </div>

            {/* Factual Decision Pipeline Explanation */}
            <div className="space-y-3">
              <h4 className="font-bold text-slate-900 text-sm border-b border-slate-100 pb-1.5">
                1. Recommendation Selection (Engine A)
              </h4>
              <p>
                When you add products to your cart, Engine A evaluates candidate accessories from our SQLite catalogue. Recommendations are chosen purely based on factual technical compatibility, shared physical attributes, complementary relationships, and your explicitly chosen Shopping Intent filter (e.g. Productivity, Gaming, Study). If no eligible in-stock match exists, no recommendation is shown.
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="font-bold text-slate-900 text-sm border-b border-slate-100 pb-1.5">
                2. Margin-Preserving Incentives (Engine B)
              </h4>
              <p>
                In traditional retail, blanket promotional discounts often erode merchant profit margins. In FairCart AI, Engine B tests each candidate mathematically. A discount is granted <strong>only if</strong> the combined basket satisfies the merchant's gross margin safety floor (minimum 20%). If the basket margin would fall below the threshold, the complementary product is recommended at its standard reference price with the label <em>"Standard price · No discount applied"</em>.
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="font-bold text-slate-900 text-sm border-b border-slate-100 pb-1.5">
                3. The Role of Google Gemini AI
              </h4>
              <div className="bg-indigo-50/70 border border-indigo-200/80 rounded-xl p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-indigo-900">
                    Natural Language Explanations Only
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    geminiConfigured
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                      : 'bg-slate-200 text-slate-700'
                  }`}>
                    {geminiConfigured ? 'Gemini 2.5 Flash Active' : 'Deterministic Fallback Active'}
                  </span>
                </div>
                <p className="text-[11px] text-indigo-950/80 leading-relaxed">
                  Google Gemini 2.5 Flash is used exclusively to translate technical catalogue attributes into natural, clear sentences explaining why an accessory pairs with your cart.
                </p>
                <div className="flex items-start space-x-2 text-[11px] text-indigo-900 font-medium">
                  <AlertCircle className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Strict AI Firewall:</strong> Gemini has zero access or authority to set prices, calculate discounts, override margins, or invent scarcity claims. All financial values are calculated deterministically in integer cents by the backend.
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="font-bold text-slate-900 text-sm border-b border-slate-100 pb-1.5">
                4. Data & Privacy Guarantee
              </h4>
              <p>
                FairCart AI stores your active cart, selected shopping intent, and dismissed recommendations locally in your browser's <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-800 font-mono">localStorage</code>. Zero personal identifiable information (PII) is gathered or transmitted. Resetting your cart clears this state immediately.
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="bg-slate-50 px-6 py-4 flex items-center justify-between border-t border-slate-200">
            <span className="text-[11px] text-slate-500 font-medium">
              Devpost "Build With AI: Basics" Transparency Standard
            </span>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-slate-900"
            >
              Understood
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
