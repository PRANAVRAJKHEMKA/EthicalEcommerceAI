import { useState, useEffect } from 'react';
import {
  Activity,
  Layers,
  ShieldCheck,
  RefreshCw,
  Info,
  CheckCircle2,
  BarChart2,
  AlertTriangle,
  ShoppingBag,
  Eye,
  MousePointerClick,
  Percent,
} from 'lucide-react';
import {
  FunnelMetricsResponse,
  UpliftEvaluationResponse,
} from '../types.ts';
import {
  fetchFunnelAnalytics,
  fetchUpliftEvaluation,
  triggerUpliftEvaluation,
} from '../api.ts';

export function TransactionOutcomeLedger() {
  const [activeTab, setActiveTab] = useState<'funnel' | 'uplift'>('funnel');
  const [timeWindow, setTimeWindow] = useState<number>(24);

  // Funnel State
  const [funnelData, setFunnelData] = useState<FunnelMetricsResponse | null>(null);
  const [loadingFunnel, setLoadingFunnel] = useState<boolean>(false);
  const [funnelError, setFunnelError] = useState<string | null>(null);

  // Uplift State
  const [upliftData, setUpliftData] = useState<UpliftEvaluationResponse | null>(null);
  const [loadingUplift, setLoadingUplift] = useState<boolean>(false);
  const [upliftOutcome, setUpliftOutcome] = useState<'conversion' | 'visit'>('conversion');
  const [upliftError, setUpliftError] = useState<string | null>(null);

  // Load Funnel Data
  const loadFunnel = async (hours: number) => {
    try {
      setLoadingFunnel(true);
      setFunnelError(null);
      const data = await fetchFunnelAnalytics(hours);
      setFunnelData(data);
    } catch (err) {
      setFunnelError(err instanceof Error ? err.message : 'Failed to load funnel analytics');
    } finally {
      setLoadingFunnel(false);
    }
  };

  // Load Uplift Data
  const loadUplift = async (outcome: string) => {
    try {
      setLoadingUplift(true);
      setUpliftError(null);
      const data = await fetchUpliftEvaluation(outcome);
      setUpliftData(data);
    } catch (err) {
      setUpliftError(err instanceof Error ? err.message : 'Failed to load uplift evaluation');
    } finally {
      setLoadingUplift(false);
    }
  };

  const handleRerunUplift = async () => {
    try {
      setLoadingUplift(true);
      setUpliftError(null);
      const data = await triggerUpliftEvaluation(upliftOutcome);
      setUpliftData(data);
    } catch (err) {
      setUpliftError(err instanceof Error ? err.message : 'Failed to evaluate uplift models');
    } finally {
      setLoadingUplift(false);
    }
  };

  useEffect(() => {
    loadFunnel(timeWindow);
    loadUplift(upliftOutcome);
  }, []);

  const stages = funnelData?.funnel_stages;
  const rates = funnelData?.conversion_rates;

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden space-y-0">
      {/* Header Banner */}
      <div className="p-6 sm:p-8 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex items-center space-x-2 bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full text-xs font-semibold border border-indigo-400/30">
            <Activity className="w-3.5 h-3.5" />
            <span>Step 5.19 · Transaction Outcome Intelligence & Uplift Lab</span>
          </div>

          <div className="flex items-center space-x-2 bg-slate-800/80 p-1 rounded-lg border border-slate-700/60 text-xs">
            <button
              onClick={() => setActiveTab('funnel')}
              className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                activeTab === 'funnel'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              First-Party Funnel Ledger
            </button>
            <button
              onClick={() => setActiveTab('uplift')}
              className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                activeTab === 'uplift'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Offline Uplift Lab (T-Learner)
            </button>
          </div>
        </div>

        <div className="max-w-3xl space-y-2">
          <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight">
            {activeTab === 'funnel'
              ? 'Observed Commerce Funnel & Event Outcome Ledger'
              : 'Two-Model T-Learner Causal Uplift Laboratory'}
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            {activeTab === 'funnel'
              ? 'Tracks what happens after FairCart recommendations and offers are presented. Analyzes impressions, acceptances, and demo completions with zero PII and strict provenance separation.'
              : 'Investigates which shoppers are likely to change their purchasing behavior because of an incentive. Evaluates held-out Qini curves and compares causal targeting against indiscriminate discounting.'}
          </p>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="p-6 sm:p-8 space-y-6">
        {/* ========================================================================= */}
        {/* TAB 1: FIRST-PARTY COMMERCE FUNNEL LEDGER */}
        {/* ========================================================================= */}
        {activeTab === 'funnel' && (
          <div className="space-y-6">
            {/* Control & Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200">
              <div className="flex items-center space-x-3 text-xs">
                <span className="font-semibold text-slate-700">Time Window:</span>
                {[
                  { label: 'Past 24 Hours', hours: 24 },
                  { label: 'Past 7 Days', hours: 168 },
                  { label: 'All Recorded', hours: 720 },
                ].map((w) => (
                  <button
                    key={w.hours}
                    onClick={() => {
                      setTimeWindow(w.hours);
                      loadFunnel(w.hours);
                    }}
                    className={`px-3 py-1 rounded-lg border text-xs font-medium cursor-pointer transition-all ${
                      timeWindow === w.hours
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-bold'
                        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {w.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={() => loadFunnel(timeWindow)}
                  disabled={loadingFunnel}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingFunnel ? 'animate-spin' : ''}`} />
                  <span>Refresh Ledger</span>
                </button>
              </div>
            </div>

            {funnelError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />
                <span>{funnelError}</span>
              </div>
            )}

            {/* Funnel Stage Progression Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-[10px] uppercase font-bold tracking-wider">1. Views</span>
                  <Eye className="w-3.5 h-3.5 text-indigo-600" />
                </div>
                <div className="text-xl font-bold font-mono text-slate-900">{stages?.product_views ?? 0}</div>
                <div className="text-[10px] text-slate-400">Browsing intent</div>
              </div>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-[10px] uppercase font-bold tracking-wider">2. Rec Shown</span>
                  <Layers className="w-3.5 h-3.5 text-indigo-600" />
                </div>
                <div className="text-xl font-bold font-mono text-slate-900">{stages?.recommendation_impressions ?? 0}</div>
                <div className="text-[10px] text-slate-400">Impressions</div>
              </div>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-[10px] uppercase font-bold tracking-wider">3. Rec Clicks</span>
                  <MousePointerClick className="w-3.5 h-3.5 text-emerald-600" />
                </div>
                <div className="text-xl font-bold font-mono text-emerald-700">{stages?.recommendation_clicks ?? 0}</div>
                <div className="text-[10px] text-emerald-600 font-semibold">
                  CTR: {((rates?.recommendation_ctr ?? 0) * 100).toFixed(1)}%
                </div>
              </div>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-[10px] uppercase font-bold tracking-wider">4. Cart Adds</span>
                  <ShoppingBag className="w-3.5 h-3.5 text-indigo-600" />
                </div>
                <div className="text-xl font-bold font-mono text-slate-900">{stages?.cart_adds ?? 0}</div>
                <div className="text-[10px] text-slate-400">Active baskets</div>
              </div>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                <div className="flex items-center justify-between text-slate-500">
                  <span className="text-[10px] uppercase font-bold tracking-wider">5. Offer Takes</span>
                  <Percent className="w-3.5 h-3.5 text-amber-600" />
                </div>
                <div className="text-xl font-bold font-mono text-amber-700">{stages?.offer_acceptances ?? 0}</div>
                <div className="text-[10px] text-amber-600 font-semibold">
                  Accept: {((rates?.offer_acceptance_rate ?? 0) * 100).toFixed(1)}%
                </div>
              </div>

              <div className="p-4 bg-indigo-50/70 border border-indigo-200 rounded-xl space-y-1">
                <div className="flex items-center justify-between text-indigo-700">
                  <span className="text-[10px] uppercase font-bold tracking-wider">6. Demo Orders</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-indigo-600" />
                </div>
                <div className="text-xl font-bold font-mono text-indigo-900">{stages?.demo_orders_completed ?? 0}</div>
                <div className="text-[10px] text-indigo-700 font-semibold">
                  Conv: {((rates?.checkout_completion_rate ?? 0) * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Data Source & Sample Size Notice */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-2 text-slate-800 font-semibold">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>Provenance & Privacy Boundary</span>
                </div>
                <div className="flex items-center space-x-2 text-[11px]">
                  <span className="px-2 py-0.5 rounded bg-white border border-slate-200 font-mono text-slate-700">
                    Total Events: {funnelData?.total_events ?? 0}
                  </span>
                  {funnelData?.is_small_sample ? (
                    <span className="px-2 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-800 font-medium flex items-center space-x-1">
                      <AlertTriangle className="w-3 h-3 text-amber-600" />
                      <span>Small Sample (&lt;30 events)</span>
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-800 font-medium">
                      Sample Size Verified
                    </span>
                  )}
                </div>
              </div>

              <p className="text-[11px] text-slate-500 leading-relaxed">
                {funnelData?.methodology_disclaimer ||
                  'First-party outcome ledger tracks observed events within the demo storefront. Demo orders represent interactive customer simulation in a sandbox environment, strictly distinguished from paid live transactions. Zero personal data (PII) is stored.'}
              </p>

              <div className="pt-1 flex flex-wrap gap-2 text-[10px] text-slate-600">
                <span className="font-semibold text-slate-700">Data Sources:</span>
                {funnelData?.provenance_breakdown &&
                  Object.entries(funnelData.provenance_breakdown).map(([prov, cnt]) => (
                    <span key={prov} className="bg-white border border-slate-200 px-2 py-0.5 rounded font-mono">
                      {prov}: {cnt}
                    </span>
                  ))}
              </div>
            </div>

            {/* Recent Event Stream Table */}
            {funnelData?.recent_events && funnelData.recent_events.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                  <Activity className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Recent Event Stream (Authoritative Audit Trail)</span>
                </h3>
                <div className="overflow-x-auto border border-slate-200 rounded-xl">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
                      <tr>
                        <th className="py-2 px-3 font-semibold">Event ID</th>
                        <th className="py-2 px-3 font-semibold">Event Type</th>
                        <th className="py-2 px-3 font-semibold">Product</th>
                        <th className="py-2 px-3 font-semibold">Context</th>
                        <th className="py-2 px-3 font-semibold">Provenance</th>
                        <th className="py-2 px-3 font-semibold text-right">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                      {funnelData.recent_events.map((evt) => (
                        <tr key={evt.id} className="hover:bg-slate-50/50">
                          <td className="py-2 px-3 text-slate-500">{evt.id}</td>
                          <td className="py-2 px-3 font-semibold text-indigo-700">{evt.event_type}</td>
                          <td className="py-2 px-3 text-slate-700">{evt.product_id || '—'}</td>
                          <td className="py-2 px-3 text-slate-500">{evt.shopping_context}</td>
                          <td className="py-2 px-3">
                            <span className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded text-[10px]">
                              {evt.provenance}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right text-slate-400">
                            {new Date(evt.timestamp).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: OFFLINE UPLIFT LAB (T-LEARNER & QINI BENCHMARK) */}
        {/* ========================================================================= */}
        {activeTab === 'uplift' && (
          <div className="space-y-6">
            {/* Control & Outcome Selector Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200">
              <div className="flex items-center space-x-3 text-xs">
                <span className="font-semibold text-slate-700">Target Outcome:</span>
                {[
                  { label: 'Conversion (Purchase Intent)', value: 'conversion' },
                  { label: 'Site Visit (Traffic Engagement)', value: 'visit' },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setUpliftOutcome(opt.value as 'conversion' | 'visit');
                      loadUplift(opt.value);
                    }}
                    className={`px-3 py-1 rounded-lg border text-xs font-medium cursor-pointer transition-all ${
                      upliftOutcome === opt.value
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-bold'
                        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={handleRerunUplift}
                  disabled={loadingUplift}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingUplift ? 'animate-spin' : ''}`} />
                  <span>Re-evaluate Uplift Models</span>
                </button>
              </div>
            </div>

            {upliftError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />
                <span>{upliftError}</span>
              </div>
            )}

            {/* Model Benchmark Performance Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {upliftData?.models?.t_learner && (
                <div className="p-4 bg-emerald-50/50 border border-emerald-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-900">
                      Two-Model T-Learner
                    </span>
                    <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full">
                      Causal Uplift
                    </span>
                  </div>
                  <div className="flex items-baseline space-x-2">
                    <span className="text-2xl font-bold font-mono text-emerald-700">
                      {upliftData.models.t_learner.normalized_qini.toFixed(3)}
                    </span>
                    <span className="text-xs text-slate-500">Normalized Qini</span>
                  </div>
                  <div className="text-[11px] text-slate-600 space-y-0.5 pt-1 border-t border-emerald-100">
                    <div className="flex justify-between">
                      <span>AUUC Score:</span>
                      <span className="font-mono font-semibold">{upliftData.models.t_learner.auuc.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Qini Coefficient:</span>
                      <span className="font-mono font-semibold text-emerald-700">
                        {upliftData.models.t_learner.qini_coefficient.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {upliftData?.models?.propensity_baseline && (
                <div className="p-4 bg-amber-50/40 border border-amber-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-amber-900">
                      Conversion Propensity
                    </span>
                    <span className="text-[10px] bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full">
                      Non-Causal
                    </span>
                  </div>
                  <div className="flex items-baseline space-x-2">
                    <span className="text-2xl font-bold font-mono text-amber-700">
                      {upliftData.models.propensity_baseline.normalized_qini.toFixed(3)}
                    </span>
                    <span className="text-xs text-slate-500">Normalized Qini</span>
                  </div>
                  <div className="text-[11px] text-slate-600 space-y-0.5 pt-1 border-t border-amber-100">
                    <div className="flex justify-between">
                      <span>AUUC Score:</span>
                      <span className="font-mono font-semibold">{upliftData.models.propensity_baseline.auuc.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Pitfall:</span>
                      <span className="text-amber-800 font-medium">Targets sure-things</span>
                    </div>
                  </div>
                </div>
              )}

              {upliftData?.models?.random_baseline && (
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-700">
                      Random Baseline
                    </span>
                    <span className="text-[10px] bg-slate-200 text-slate-700 font-bold px-2 py-0.5 rounded-full">
                      Uniform Baseline
                    </span>
                  </div>
                  <div className="flex items-baseline space-x-2">
                    <span className="text-2xl font-bold font-mono text-slate-600">
                      0.000
                    </span>
                    <span className="text-xs text-slate-500">Normalized Qini</span>
                  </div>
                  <div className="text-[11px] text-slate-600 space-y-0.5 pt-1 border-t border-slate-200">
                    <div className="flex justify-between">
                      <span>AUUC Score:</span>
                      <span className="font-mono font-semibold">{upliftData.models.random_baseline.auuc.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Targeting Strategy:</span>
                      <span className="text-slate-600">Random allocation</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Three-Strategy Counterfactual Comparison */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                <BarChart2 className="w-3.5 h-3.5 text-indigo-600" />
                <span>Macro Incentive Strategy Comparison (Synthetic Held-Out Test Set)</span>
              </h3>
              <div className="overflow-x-auto border border-slate-200 rounded-xl">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600">
                    <tr>
                      <th className="py-2.5 px-4 font-semibold">Strategy</th>
                      <th className="py-2.5 px-4 font-semibold">Targeted %</th>
                      <th className="py-2.5 px-4 font-semibold">Modeled Conversion</th>
                      <th className="py-2.5 px-4 font-semibold">Relative Lift</th>
                      <th className="py-2.5 px-4 font-semibold">Subsidy Eligibility Index (%)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                    {upliftData?.strategy_comparison?.map((strat) => (
                      <tr
                        key={strat.strategy_id}
                        className={
                          strat.strategy_id === 'uplift_targeted'
                            ? 'bg-emerald-50/40 hover:bg-emerald-50/60 font-semibold'
                            : 'hover:bg-slate-50/50'
                        }
                      >
                        <td className="py-2.5 px-4 font-sans text-slate-900">
                          <div className="font-bold">{strat.strategy_name}</div>
                          <div className="text-[10px] text-slate-500 font-normal">{strat.description}</div>
                        </td>
                        <td className="py-2.5 px-4 text-slate-700">{strat.targeted_percentage.toFixed(1)}%</td>
                        <td className="py-2.5 px-4 text-slate-900 font-bold">
                          {(strat.expected_conversion_rate * 100).toFixed(1)}%
                        </td>
                        <td className="py-2.5 px-4">
                          <span
                            className={
                              strat.relative_lift_vs_baseline > 0
                                ? 'text-emerald-700 font-bold'
                                : 'text-slate-400'
                            }
                          >
                            {strat.relative_lift_vs_baseline > 0 ? '+' : ''}
                            {strat.relative_lift_vs_baseline.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-slate-700">{strat.modeled_incentive_cost.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Decile Uplift Breakdown Table */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-600" />
                <span>T-Learner Decile Uplift Breakdown (Decile 1 = Top Predicted Uplift)</span>
              </h3>
              <div className="overflow-x-auto border border-slate-200 rounded-xl">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600">
                    <tr>
                      <th className="py-2 px-3 font-semibold">Decile</th>
                      <th className="py-2 px-3 font-semibold">Treated N</th>
                      <th className="py-2 px-3 font-semibold">Ctrl N</th>
                      <th className="py-2 px-3 font-semibold">Treated Conv %</th>
                      <th className="py-2 px-3 font-semibold">Ctrl Conv %</th>
                      <th className="py-2 px-3 font-semibold">Incremental Uplift</th>
                      <th className="py-2 px-3 font-semibold text-right">Cumulative Qini</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                    {upliftData?.decile_breakdown?.map((d) => (
                      <tr key={d.decile} className="hover:bg-slate-50/50">
                        <td className="py-2 px-3 font-bold text-slate-800">D{d.decile}</td>
                        <td className="py-2 px-3 text-slate-600">{d.treated_count}</td>
                        <td className="py-2 px-3 text-slate-600">{d.control_count}</td>
                        <td className="py-2 px-3 text-slate-700">{(d.treated_conversion_rate * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3 text-slate-700">{(d.control_conversion_rate * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3">
                          <span
                            className={
                              d.incremental_uplift > 0
                                ? 'text-emerald-700 font-bold'
                                : d.incremental_uplift < 0
                                ? 'text-rose-600 font-medium'
                                : 'text-slate-400'
                            }
                          >
                            {d.incremental_uplift > 0 ? '+' : ''}
                            {(d.incremental_uplift * 100).toFixed(1)} pp
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right font-bold text-slate-900">{d.cumulative_qini.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Scientific Provenance & Architecture Notice */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-2">
              <div className="flex items-center space-x-2 text-slate-800 font-semibold">
                <Info className="w-4 h-4 text-indigo-600 shrink-0" />
                <span>Dataset Provenance & Scientific Methodology</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                {upliftData?.methodology_disclaimer}
              </p>
              <div className="pt-1 flex flex-wrap gap-2 text-[10px] text-slate-600">
                <span className="font-semibold text-slate-700">Dataset:</span>
                <span className="bg-white border border-slate-200 px-2 py-0.5 rounded font-mono">
                  {upliftData?.dataset_name} ({upliftData?.dataset_provenance})
                </span>
                <span className="font-semibold text-slate-700">Status:</span>
                <span className="bg-white border border-slate-200 px-2 py-0.5 rounded font-mono text-indigo-700">
                  {upliftData?.real_dataset_status}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
