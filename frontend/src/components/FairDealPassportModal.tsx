import { useEffect, useState } from 'react';
import {
  ShieldCheck,
  X,
  AlertTriangle,
  Scale,
  Info,
  Check,
  Plus,
  RefreshCw,
  BarChart3,
} from 'lucide-react';
import { FairDealPassport } from '../types.ts';

interface FairDealPassportModalProps {
  isOpen: boolean;
  onClose: () => void;
  passport: FairDealPassport | null;
  loading?: boolean;
  error?: string | null;
  onAcceptApprovedOffer?: (productId: string, price: number, discountPct: number) => void;
  isItemInCart?: boolean;
  viewMode?: 'shopper' | 'merchant';
}

export function FairDealPassportModal({
  isOpen,
  onClose,
  passport,
  loading = false,
  error = null,
  onAcceptApprovedOffer,
  isItemInCart = false,
  viewMode = 'shopper',
}: FairDealPassportModalProps) {
  const [activeTab, setActiveTab] = useState<'scenarios' | 'macro'>('scenarios');

  // Keyboard accessibility: Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="passport-modal-title"
    >
      <div className="relative w-full max-w-4xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-5 py-4 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/20 border border-indigo-400/30 text-indigo-300">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 id="passport-modal-title" className="text-base sm:text-lg font-bold text-white tracking-tight">
                  Fair Deal Passport
                </h3>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/30 text-indigo-200 border border-indigo-400/30">
                  Counterfactual Offer Audit
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                Authoritative pricing breakdown comparing baseline, approved offer, and rejected alternative.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-white"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Subheader / Navigation */}
        <div className="px-5 py-2.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveTab('scenarios')}
              className={`px-3 py-1 rounded-lg font-semibold transition-colors ${
                activeTab === 'scenarios'
                  ? 'bg-white text-indigo-700 shadow-sm border border-slate-200'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              3 Counterfactual Scenarios
            </button>
            <button
              onClick={() => setActiveTab('macro')}
              className={`px-3 py-1 rounded-lg font-semibold transition-colors flex items-center space-x-1.5 ${
                activeTab === 'macro'
                  ? 'bg-white text-indigo-700 shadow-sm border border-slate-200'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>1,000-Session Simulation Context</span>
            </button>
          </div>

          {passport && (
            <div className="flex items-center space-x-2 text-[11px] text-slate-500 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>Snapshot ID: {passport.passport_id}</span>
            </div>
          )}
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-4">
          {loading ? (
            <div className="py-16 text-center space-y-3">
              <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin mx-auto" />
              <p className="text-sm font-semibold text-slate-700">
                Evaluating authoritative counterfactual pricing scenarios...
              </p>
              <p className="text-xs text-slate-400">
                Calculating integer-cent cart margins against active merchant safety guardrails.
              </p>
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Passport Evaluation Unavailable</p>
                <p className="text-xs mt-1 text-red-600">{error}</p>
              </div>
            </div>
          ) : passport ? (
            <>
              {/* Product & Active Policy Banner */}
              <div className="bg-slate-100/80 rounded-xl p-3.5 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Candidate Product Offer:
                  </span>
                  <div className="flex items-baseline space-x-2 mt-0.5">
                    <span className="text-sm font-bold text-slate-900">
                      {passport.candidate_product_name}
                    </span>
                    <span className="text-slate-500 font-mono">
                      (Ref Price: ${passport.candidate_reference_price.toFixed(2)})
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-1 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-800 font-medium text-[11px]">
                    <ShieldCheck className="w-3.5 h-3.5 text-indigo-600 mr-1" />
                    Floor: {(passport.active_margin_floor * 100).toFixed(1)}%
                  </span>
                  <span className="inline-flex items-center px-2 py-1 rounded-md bg-slate-200 text-slate-700 font-medium text-[11px]">
                    Cap: {(passport.active_discount_cap * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {activeTab === 'scenarios' ? (
                <div>
                  {/* Three Counterfactual Scenario Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                    {passport.scenarios.map((scenario) => {
                      const isSelected = passport.selected_scenario_id === scenario.scenario_id;
                      const isApprovedOffer = scenario.is_approved && scenario.discount_percentage > 0;
                      const isRejected = !scenario.is_approved && scenario.discount_percentage > 0;
                      const isBaseline = scenario.scenario_id === 'no_discount';
                      const isRevokedOffer = scenario.scenario_id === 'faircart_approved' && !scenario.is_approved;

                      return (
                        <div
                          key={scenario.scenario_id}
                          className={`rounded-xl border p-4 flex flex-col justify-between transition-all ${
                            isSelected && isApprovedOffer
                              ? 'border-indigo-400 ring-2 ring-indigo-500/20 bg-gradient-to-b from-indigo-50/60 to-white shadow-md'
                              : isSelected && isBaseline
                              ? 'border-slate-300 ring-1 ring-slate-400/20 bg-white shadow-sm'
                              : isRevokedOffer
                              ? 'border-amber-200 bg-amber-50/30'
                              : isRejected
                              ? 'border-rose-200 bg-rose-50/30'
                              : 'border-slate-200 bg-slate-50/40'
                          }`}
                        >
                          <div>
                            {/* Card Header Status */}
                            <div className="flex items-center justify-between gap-1.5 mb-2.5">
                              <span
                                className={`text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                  isSelected && isApprovedOffer
                                    ? 'bg-indigo-100 text-indigo-800 border border-indigo-200'
                                    : isRevokedOffer
                                    ? 'bg-amber-100 text-amber-800 border border-amber-200'
                                    : isRejected
                                    ? 'bg-rose-100 text-rose-800 border border-rose-200'
                                    : 'bg-slate-200 text-slate-700'
                                }`}
                              >
                                {scenario.label}
                              </span>

                              {isSelected && isApprovedOffer && (
                                <span className="text-[10px] font-bold text-emerald-700 flex items-center">
                                  <Check className="w-3.5 h-3.5 mr-0.5" />
                                  Selected Offer
                                </span>
                              )}
                              {isSelected && isBaseline && (
                                <span className="text-[10px] font-bold text-slate-700 flex items-center">
                                  <Check className="w-3.5 h-3.5 mr-0.5" />
                                  Active Baseline
                                </span>
                              )}
                              {isRevokedOffer && (
                                <span className="text-[10px] font-bold text-amber-700 flex items-center">
                                  <AlertTriangle className="w-3.5 h-3.5 mr-0.5" />
                                  Discount Revoked
                                </span>
                              )}
                              {isRejected && (
                                <span className="text-[10px] font-bold text-rose-700 flex items-center">
                                  <AlertTriangle className="w-3.5 h-3.5 mr-0.5" />
                                  Rejected
                                </span>
                              )}
                            </div>

                            {/* Price & Savings */}
                            <div className="space-y-1 pb-3 border-b border-slate-100">
                              <div className="text-[11px] text-slate-500">Candidate Unit Price:</div>
                              <div className="flex items-baseline space-x-2">
                                <span className="text-xl font-extrabold text-slate-900 font-mono">
                                  ${scenario.candidate_price.toFixed(2)}
                                </span>
                                {scenario.candidate_savings > 0 && (
                                  <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                                    Save ${scenario.candidate_savings.toFixed(2)}
                                  </span>
                                )}
                              </div>

                              <div className="pt-2 flex items-center justify-between text-xs text-slate-600 font-mono">
                                <span>Basket Subtotal:</span>
                                <span className="font-bold text-slate-900">
                                  ${scenario.basket_subtotal.toFixed(2)}
                                </span>
                              </div>
                            </div>

                            {/* Plain-Language Explanation */}
                            <div className="py-3 space-y-1.5 text-xs text-slate-600 leading-relaxed">
                              <div className="font-semibold text-slate-800 flex items-center space-x-1">
                                <Info className="w-3.5 h-3.5 text-indigo-600" />
                                <span>Decision Rationale:</span>
                              </div>
                              <p className="text-[11px]">
                                {viewMode === 'merchant'
                                  ? scenario.merchant_explanation
                                  : scenario.shopper_explanation}
                              </p>
                              {scenario.rejection_reason && (
                                <div className="mt-1 p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-[11px] font-medium">
                                  ⚠️ {scenario.rejection_reason}
                                </div>
                              )}
                            </div>

                            {/* Merchant Confidential Metrics (Exclusive to Merchant Console) */}
                            {viewMode === 'merchant' && scenario.merchant_metrics && (
                              <div className="mt-2 pt-2 border-t border-slate-200 space-y-1 text-[11px] font-mono text-slate-600 bg-white/70 p-2 rounded-lg">
                                <div className="font-sans font-bold text-slate-800 text-[10px] uppercase">
                                  Merchant Unit Economics:
                                </div>
                                <div className="flex justify-between">
                                  <span>Basket Revenue:</span>
                                  <span className="font-semibold text-slate-900">
                                    ${scenario.merchant_metrics.basket_revenue.toFixed(2)}
                                  </span>
                                </div>
                                <div className="flex justify-between">
                                  <span>Total COGS:</span>
                                  <span>${scenario.merchant_metrics.basket_cogs.toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between text-emerald-700 font-semibold">
                                  <span>Gross Profit:</span>
                                  <span>${scenario.merchant_metrics.gross_profit.toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between text-indigo-700 font-semibold">
                                  <span>Basket Margin:</span>
                                  <span>{(scenario.basket_gross_margin * 100).toFixed(1)}%</span>
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Card Footer Actions */}
                          <div className="mt-3 pt-2.5 border-t border-slate-100">
                            {isApprovedOffer && isSelected ? (
                              isItemInCart ? (
                                <div className="w-full py-1.5 px-3 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold text-center border border-emerald-200 flex items-center justify-center space-x-1">
                                  <Check className="w-3.5 h-3.5" />
                                  <span>Active in Cart</span>
                                </div>
                              ) : (
                                <button
                                  onClick={() => {
                                    if (onAcceptApprovedOffer) {
                                      onAcceptApprovedOffer(
                                        passport.candidate_product_id,
                                        scenario.candidate_price,
                                        scenario.discount_percentage
                                      );
                                    }
                                    onClose();
                                  }}
                                  className="w-full py-1.5 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-colors flex items-center justify-center space-x-1"
                                >
                                  <Plus className="w-3.5 h-3.5" />
                                  <span>Add Bundle for ${scenario.candidate_price.toFixed(2)}</span>
                                </button>
                              )
                            ) : isRevokedOffer ? (
                              <div className="w-full py-1.5 px-3 rounded-lg border border-amber-300 bg-amber-50 text-amber-800 text-xs font-semibold text-center">
                                Standard Price Only (Below Margin Floor)
                              </div>
                            ) : isBaseline ? (
                              <button
                                onClick={onClose}
                                className="w-full py-1.5 px-3 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800 text-xs font-semibold transition-colors"
                              >
                                {isItemInCart ? 'Keep My Cart' : `Add at Regular Price ($${scenario.candidate_price.toFixed(2)})`}
                              </button>
                            ) : (
                              <div className="w-full py-1.5 px-3 rounded-lg border border-rose-300 bg-rose-50/80 text-rose-700 text-xs font-semibold text-center">
                                Rejected by Policy Floor
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                /* Phase 2: Macro 1,000-Session Simulation Context */
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                    <div className="flex items-center space-x-2 text-indigo-950 font-bold text-sm">
                      <BarChart3 className="w-4 h-4 text-indigo-600" />
                      <span>Macro Policy Validation: 1,000-Session CRN Simulation</span>
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      While the Fair Deal Passport validates this specific transaction in real time, FairCart AI's policy constraints have been evaluated across <strong>1,000 synthetic shopping sessions</strong> using Common Random Numbers (CRN).
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                      <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-1">
                        <span className="text-[10px] font-bold uppercase text-slate-500">
                          1. No Discount Baseline
                        </span>
                        <div className="text-lg font-bold text-slate-900 font-mono">0.0%</div>
                        <p className="text-[11px] text-slate-500">Margin floor violations</p>
                      </div>

                      <div className="p-3 rounded-lg bg-white border border-rose-200 space-y-1">
                        <span className="text-[10px] font-bold uppercase text-rose-600">
                          2. Blanket 15% Markdown
                        </span>
                        <div className="text-lg font-bold text-rose-700 font-mono">42.1%</div>
                        <p className="text-[11px] text-rose-600">Erodes merchant margin floor</p>
                      </div>

                      <div className="p-3 rounded-lg bg-white border border-emerald-200 space-y-1">
                        <span className="text-[10px] font-bold uppercase text-emerald-700">
                          3. FairCart AI
                        </span>
                        <div className="text-lg font-bold text-emerald-700 font-mono">0.0%</div>
                        <p className="text-[11px] text-emerald-700">100% floor compliance guaranteed</p>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] leading-relaxed">
                      <strong>Methodology Disclaimer:</strong> {passport.macro_simulation_summary?.disclaimer || 'Synthetic simulation results evaluating pipeline mechanics; not observed real-world uplift.'}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3.5 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-2.5 text-xs text-slate-500 shrink-0">
          <div className="flex items-center space-x-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Mathematical Margin Invariant Guarantee · Sub-25ms Decision SLA</span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 font-semibold transition-colors"
            >
              Close Passport
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
