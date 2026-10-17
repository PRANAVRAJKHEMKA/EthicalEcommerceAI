import { useState, useEffect, useMemo } from 'react';
import {
  Scale,
  ShieldCheck,
  AlertTriangle,
  Check,
  RefreshCw,
  Info,
} from 'lucide-react';
import { Product, FairDealPassport } from '../types.ts';
import { fetchDealPassport } from '../api.ts';

interface MerchantDealPassportInspectorProps {
  products: Product[];
  marginFloor: number;
  discountCap: number;
}

const PRESETS = [
  {
    id: 'mouse_and_stand',
    label: 'Precision Mouse ($65) + Monitor Stand ($55) — Illustrative Benchmark',
    cartProductIds: ['item-003'],
    candidateProductId: 'item-005',
    candidateDiscountPct: 0.10,
    alternativeDiscountPct: 0.15,
  },
  {
    id: 'keyboard_and_mat',
    label: 'Mechanical Keyboard ($120) + Desk Mat ($30)',
    cartProductIds: ['item-001'],
    candidateProductId: 'item-004',
    candidateDiscountPct: 0.10,
    alternativeDiscountPct: 0.20,
  },
  {
    id: 'stream_deck_and_mic',
    label: 'Streaming Console ($150) + Studio Boom Arm ($85)',
    cartProductIds: ['item-009'],
    candidateProductId: 'item-011',
    candidateDiscountPct: 0.10,
    alternativeDiscountPct: 0.20,
  },
];

export function MerchantDealPassportInspector({
  products,
  marginFloor,
  discountCap,
}: MerchantDealPassportInspectorProps) {
  const [selectedPresetId, setSelectedPresetId] = useState<string>('mouse_and_stand');
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>('item-005');
  const [alternativePct, setAlternativePct] = useState<number>(0.15);
  const [passport, setPassport] = useState<FairDealPassport | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const activePreset = useMemo(() => {
    return PRESETS.find((p) => p.id === selectedPresetId) || PRESETS[0];
  }, [selectedPresetId]);

  // Load Passport when preset, candidate, marginFloor, or discountCap changes
  useEffect(() => {
    let isCancelled = false;
    const controller = new AbortController();

    async function loadPassport() {
      setLoading(true);
      setError(null);
      try {
        const cartItems = activePreset.cartProductIds.map((id) => ({
          product_id: id,
          quantity: 1,
        }));

        const res = await fetchDealPassport(
          {
            cart_items: cartItems,
            candidate_product_id: selectedCandidateId,
            alternative_discount_pct: alternativePct,
            margin_floor: marginFloor,
            discount_cap: discountCap,
            view_mode: 'merchant',
          },
          controller.signal
        );

        if (!isCancelled) {
          setPassport(res);
        }
      } catch (err: any) {
        if (!isCancelled && err.name !== 'AbortError') {
          setError(err.message || 'Failed to generate Fair Deal Passport');
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadPassport();

    return () => {
      isCancelled = true;
      controller.abort();
    };
  }, [activePreset, selectedCandidateId, alternativePct, marginFloor, discountCap]);

  return (
    <div className="bg-white rounded-xl border border-slate-200/90 shadow-sm p-5 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-700">
            <Scale className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
                Fair Deal Passport & Counterfactual Inspector
              </h3>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                Authoritative Engine
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Inspect integer-cent unit economics, gross margins, and guardrail decisions across 3 counterfactual pricing scenarios.
            </p>
          </div>
        </div>

        {/* Live Active Parameters Badge */}
        <div className="flex items-center gap-2 text-xs">
          <span className="inline-flex items-center px-2 py-1 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-800 font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-600 mr-1" />
            Floor: {(marginFloor * 100).toFixed(1)}%
          </span>
          <span className="inline-flex items-center px-2 py-1 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-medium">
            Cap: {(discountCap * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Preset & Candidate Selectors */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-slate-50/70 p-3 rounded-xl border border-slate-200/80 text-xs">
        <div>
          <label className="block text-[11px] font-semibold text-slate-700 mb-1">
            Cart Scenario Preset:
          </label>
          <select
            value={selectedPresetId}
            onChange={(e) => {
              const pId = e.target.value;
              setSelectedPresetId(pId);
              const p = PRESETS.find((pr) => pr.id === pId);
              if (p) {
                setSelectedCandidateId(p.candidateProductId);
                setAlternativePct(p.alternativeDiscountPct);
              }
            }}
            className="w-full text-xs rounded-lg border border-slate-300 bg-white py-1.5 px-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-semibold text-slate-700 mb-1">
            Candidate Accessory / Add-on:
          </label>
          <select
            value={selectedCandidateId}
            onChange={(e) => setSelectedCandidateId(e.target.value)}
            className="w-full text-xs rounded-lg border border-slate-300 bg-white py-1.5 px-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {products.map((prod) => (
              <option key={prod.id} value={prod.id}>
                {prod.name} (${prod.reference_price.toFixed(2)})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-semibold text-slate-700 mb-1">
            Aggressive Counterfactual Markdown:
          </label>
          <select
            value={alternativePct}
            onChange={(e) => setAlternativePct(parseFloat(e.target.value))}
            className="w-full text-xs rounded-lg border border-slate-300 bg-white py-1.5 px-2.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value={0.12}>12% Markdown</option>
            <option value={0.15}>15% Markdown (Standard Stress Test)</option>
            <option value={0.20}>20% Markdown (Max Cap Stress Test)</option>
            <option value={0.25}>25% Markdown (Cap Breach Test)</option>
          </select>
        </div>
      </div>

      {/* Live Passport Content */}
      {loading ? (
        <div className="py-12 text-center space-y-2">
          <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin mx-auto" />
          <p className="text-xs font-semibold text-slate-600">
            Evaluating integer-cent scenario economics across active policy constraints...
          </p>
        </div>
      ) : error ? (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
          <span>{error}</span>
        </div>
      ) : passport ? (
        <div className="space-y-3">
          {/* 3 Counterfactual Scenario Columns */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {passport.scenarios.map((scenario) => {
              const isSelected = scenario.scenario_id === 'faircart_approved';
              const isRejected = !scenario.is_approved && scenario.discount_percentage > 0;
              const m = scenario.merchant_metrics;

              return (
                <div
                  key={scenario.scenario_id}
                  className={`rounded-xl border p-4 flex flex-col justify-between ${
                    isSelected
                      ? 'border-indigo-400 ring-2 ring-indigo-500/20 bg-gradient-to-b from-indigo-50/50 to-white'
                      : isRejected
                      ? 'border-rose-300 bg-rose-50/40'
                      : 'border-slate-200 bg-slate-50/50'
                  }`}
                >
                  <div className="space-y-3">
                    {/* Header */}
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                          isSelected
                            ? 'bg-indigo-100 text-indigo-800 border border-indigo-200'
                            : isRejected
                            ? 'bg-rose-100 text-rose-800 border border-rose-200'
                            : 'bg-slate-200 text-slate-700'
                        }`}
                      >
                        {scenario.label}
                      </span>

                      <span
                        className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${
                          scenario.is_approved
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {scenario.is_approved ? 'PASS' : 'REJECTED'}
                      </span>
                    </div>

                    {/* Badge: Actual Quote vs Simulation */}
                    <div className="text-[10px] font-medium text-slate-500 flex items-center space-x-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                      <span>
                        {scenario.scenario_id === 'aggressive_alternative'
                          ? 'Simulated Counterfactual'
                          : 'Authoritative Quote Calculation'}
                      </span>
                    </div>

                    {/* Financial Metrics Grid */}
                    <div className="bg-white p-3 rounded-lg border border-slate-200/90 space-y-1.5 font-mono text-xs">
                      <div className="flex justify-between text-slate-600">
                        <span>Candidate Price:</span>
                        <span className="font-bold text-slate-900">
                          ${scenario.candidate_price.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex justify-between text-slate-600">
                        <span>Customer Savings:</span>
                        <span className="text-emerald-700 font-semibold">
                          ${scenario.candidate_savings.toFixed(2)} ({Math.round(scenario.discount_percentage * 100)}%)
                        </span>
                      </div>
                      <div className="border-t border-slate-100 pt-1 flex justify-between text-slate-700">
                        <span>Basket Revenue:</span>
                        <span className="font-bold text-slate-900">
                          ${scenario.basket_subtotal.toFixed(2)}
                        </span>
                      </div>
                      {m && (
                        <>
                          <div className="flex justify-between text-slate-500">
                            <span>Supplier COGS:</span>
                            <span>${m.basket_cogs.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-emerald-700 font-semibold">
                            <span>Gross Profit:</span>
                            <span>${m.gross_profit.toFixed(2)}</span>
                          </div>
                        </>
                      )}
                      <div className="border-t border-slate-100 pt-1 flex justify-between font-bold">
                        <span className="text-slate-700">Basket Margin:</span>
                        <span
                          className={
                            scenario.policy_checks.margin_floor_passed
                              ? 'text-emerald-700'
                              : 'text-rose-700'
                          }
                        >
                          {(scenario.basket_gross_margin * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>

                    {/* Policy Invariant Checks */}
                    <div className="space-y-1 text-[11px]">
                      <div className="font-semibold text-slate-700 text-[10px] uppercase tracking-wider">
                        Guardrail Verifications:
                      </div>
                      <div className="flex items-center justify-between text-slate-600">
                        <span>Margin Floor (≥{(marginFloor * 100).toFixed(1)}%):</span>
                        {scenario.policy_checks.margin_floor_passed ? (
                          <span className="text-emerald-700 font-semibold flex items-center">
                            <Check className="w-3 h-3 mr-0.5" /> Pass
                          </span>
                        ) : (
                          <span className="text-rose-700 font-semibold flex items-center">
                            <AlertTriangle className="w-3 h-3 mr-0.5" /> Breach
                          </span>
                        )}
                      </div>
                      <div className="flex items-center justify-between text-slate-600">
                        <span>Discount Cap (≤{(discountCap * 100).toFixed(0)}%):</span>
                        {scenario.policy_checks.discount_cap_passed ? (
                          <span className="text-emerald-700 font-semibold flex items-center">
                            <Check className="w-3 h-3 mr-0.5" /> Pass
                          </span>
                        ) : (
                          <span className="text-rose-700 font-semibold flex items-center">
                            <AlertTriangle className="w-3 h-3 mr-0.5" /> Exceeded
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Explanation */}
                    <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-600 leading-relaxed">
                      <p>{scenario.merchant_explanation}</p>
                      {scenario.rejection_reason && (
                        <div className="mt-1.5 p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-[10px] font-semibold">
                          ⚠️ {scenario.rejection_reason}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Micro-to-Macro Context Footer */}
          <div className="p-3 rounded-lg bg-indigo-50/70 border border-indigo-100 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-indigo-900">
            <div className="flex items-center space-x-1.5">
              <Info className="w-4 h-4 text-indigo-600 shrink-0" />
              <span>
                <strong>Reactivity Note:</strong> Adjust the Minimum Gross Margin Floor slider above to observe how counterfactual alternatives are dynamically approved or rejected.
              </span>
            </div>
            <span className="text-[11px] font-mono text-indigo-700 shrink-0">
              Deterministic Invariant Verification
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
