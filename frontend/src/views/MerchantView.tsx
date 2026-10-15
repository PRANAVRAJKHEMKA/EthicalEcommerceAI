import { useState, useEffect } from 'react';
import {
  BarChart3,
  Sliders,
  Database,
  TrendingUp,
  Tag,
  ShieldCheck,
  Cpu,
  Sparkles,
  Check,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { Product, HealthStatus, MerchantSettings } from '../types.ts';
import { fetchMerchantSettings, updateMerchantSettings } from '../api.ts';

interface MerchantViewProps {
  products: Product[];
  health?: HealthStatus | null;
}

export function MerchantView({ products, health }: MerchantViewProps) {
  // Policy settings state
  const [settings, setSettings] = useState<MerchantSettings>({
    margin_floor: 0.20,
    discount_cap: 0.20,
  });
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Compute live catalogue metrics
  const totalProducts = products.length;
  const totalPrice = products.reduce((sum, p) => sum + p.reference_price, 0);
  const totalCogs = products.reduce((sum, p) => sum + p.cogs, 0);
  const avgPrice = totalProducts > 0 ? totalPrice / totalProducts : 0;
  const avgMargin = totalPrice > 0 ? ((totalPrice - totalCogs) / totalPrice) * 100 : 0;
  const minPrice = totalProducts > 0 ? Math.min(...products.map((p) => p.reference_price)) : 0;
  const maxPrice = totalProducts > 0 ? Math.max(...products.map((p) => p.reference_price)) : 0;

  // Group by category
  const categoryCounts = products.reduce<{ [cat: string]: number }>((acc, p) => {
    acc[p.category] = (acc[p.category] || 0) + 1;
    return acc;
  }, {});

  // Load merchant policy settings from backend SQLite
  useEffect(() => {
    let isMounted = true;
    setLoadingSettings(true);
    fetchMerchantSettings()
      .then((data) => {
        if (isMounted) {
          setSettings(data);
        }
      })
      .catch((err) => {
        console.error('Failed to load merchant settings:', err);
      })
      .finally(() => {
        if (isMounted) setLoadingSettings(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSaveSettings = async () => {
    try {
      setSavingSettings(true);
      setSaveError(null);
      await updateMerchantSettings(settings);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to update merchant settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const handleResetDefaults = async () => {
    const defaults: MerchantSettings = { margin_floor: 0.20, discount_cap: 0.20 };
    setSettings(defaults);
    try {
      setSavingSettings(true);
      await updateMerchantSettings(defaults);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to reset settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const isGeminiConfigured = health?.gemini_configured ?? false;

  return (
    <div className="space-y-6 pb-16">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/90 shadow-sm space-y-3">
        <div className="inline-flex items-center space-x-2 bg-indigo-50 text-indigo-700 px-3 py-1 rounded-full text-xs font-semibold border border-indigo-200">
          <Sliders className="w-3.5 h-3.5" />
          <span>Merchant Policy & Intelligence Console</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
          Merchant Economics & Decision Guardrails
        </h1>
        <p className="text-sm text-slate-600 leading-relaxed max-w-3xl">
          Configure real-time gross margin floors and promotional discount caps. FairCart AI enforces these parameters synchronously on every basket evaluation, preventing predatory discounts while ensuring customer transparency.
        </p>

        <div className="pt-1 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="inline-flex items-center space-x-1.5 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>SQLite WAL Persistence Active</span>
          </span>
          <span>·</span>
          <span className="inline-flex items-center space-x-1.5 font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
            <span>Mathematical Margin Invariants Enforced</span>
          </span>
          <span>·</span>
          <span className="inline-flex items-center space-x-1.5 font-medium">
            <Cpu className="w-3.5 h-3.5 text-indigo-600" />
            <span>Sub-25ms Synchronous Decision SLA</span>
          </span>
        </div>
      </div>

      {/* Live Catalogue Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4.5 rounded-xl border border-slate-200/90 shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Catalogue Items</span>
            <Database className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">{totalProducts} Products</div>
          <p className="text-[11px] text-slate-500">Curated & seeded in SQLite database</p>
        </div>

        <div className="bg-white p-4.5 rounded-xl border border-slate-200/90 shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Average Margin</span>
            <TrendingUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-emerald-700 font-mono">{avgMargin.toFixed(1)}%</div>
          <p className="text-[11px] text-slate-500">Catalogue-wide baseline gross margin</p>
        </div>

        <div className="bg-white p-4.5 rounded-xl border border-slate-200/90 shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Price Range</span>
            <Tag className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">
            ${minPrice.toFixed(0)} - ${maxPrice.toFixed(0)}
          </div>
          <p className="text-[11px] text-slate-500">Average reference price: ${avgPrice.toFixed(2)}</p>
        </div>

        <div className="bg-white p-4.5 rounded-xl border border-slate-200/90 shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Categories</span>
            <BarChart3 className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">
            {Object.keys(categoryCounts).length} Distinct
          </div>
          <p className="text-[11px] text-slate-500">Cross-category complementary mesh</p>
        </div>
      </div>

      {/* Main Control Grid: Policy Sliders & AI Service Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Interactive Policy Sliders */}
        <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Sliders className="w-4 h-4 text-indigo-600" />
              <h3 className="text-sm font-bold text-slate-900">
                Live Economic Policy Sliders
              </h3>
            </div>
            <span className="text-[11px] bg-emerald-50 text-emerald-700 font-semibold px-2 py-0.5 rounded-full border border-emerald-200 flex items-center space-x-1">
              {loadingSettings ? (
                <>
                  <RefreshCw className="w-3 h-3 animate-spin text-slate-500" />
                  <span className="text-slate-600">Loading...</span>
                </>
              ) : (
                <span>Active Controls</span>
              )}
            </span>
          </div>

          <div className="space-y-4 pt-1">
            {/* Margin Floor Slider */}
            <div>
              <div className="flex justify-between text-xs mb-1 font-semibold text-slate-700">
                <span>Minimum Basket Gross Margin Floor</span>
                <span className="font-mono text-indigo-600 font-bold">
                  {(settings.margin_floor * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="10"
                max="50"
                step="1"
                value={Math.round(settings.margin_floor * 100)}
                onChange={(e) =>
                  setSettings({ ...settings, margin_floor: parseFloat(e.target.value) / 100.0 })
                }
                className="w-full accent-indigo-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Engine B rejects any discount proposal if the resulting basket gross margin would drop below this floor.
              </p>
            </div>

            {/* Discount Cap Slider */}
            <div>
              <div className="flex justify-between text-xs mb-1 font-semibold text-slate-700">
                <span>Maximum Allowed Discount Cap</span>
                <span className="font-mono text-indigo-600 font-bold">
                  {(settings.discount_cap * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="5"
                max="35"
                step="1"
                value={Math.round(settings.discount_cap * 100)}
                onChange={(e) =>
                  setSettings({ ...settings, discount_cap: parseFloat(e.target.value) / 100.0 })
                }
                className="w-full accent-indigo-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Hard ceiling on any single complementary product discount, preventing predatory price destruction.
              </p>
            </div>

            {/* Actions */}
            <div className="pt-2 flex items-center justify-between gap-3 border-t border-slate-100">
              <button
                onClick={handleResetDefaults}
                disabled={savingSettings}
                className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
              >
                Reset Defaults (20%/20%)
              </button>

              <button
                onClick={handleSaveSettings}
                disabled={savingSettings}
                className="inline-flex items-center space-x-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {savingSettings ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : saveSuccess ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-white" />
                    <span>Saved to SQLite!</span>
                  </>
                ) : (
                  <span>Apply Policy Changes</span>
                )}
              </button>
            </div>

            {saveError && (
              <p className="text-xs text-red-600 bg-red-50 p-2 rounded-lg border border-red-200 flex items-center space-x-1.5">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 text-red-500" />
                <span>{saveError}</span>
              </p>
            )}
          </div>
        </div>

        {/* Gemini AI Explanation Service Status */}
        <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-sm space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  AI Explanation Service Telemetry
                </h3>
              </div>
              <span
                className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${
                  isGeminiConfigured
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-indigo-50 text-indigo-800 border-indigo-200'
                }`}
              >
                {isGeminiConfigured ? 'Gemini 2.5 Flash Online' : 'Deterministic Fallback Active'}
              </span>
            </div>

            <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2 text-xs">
              <div className="flex justify-between items-center text-slate-600">
                <span>Natural Language Service:</span>
                <span className="font-semibold text-slate-800">
                  {isGeminiConfigured ? 'Google Gemini 2.5 Flash' : 'Attribute-Grounded Fallback Engine'}
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Endpoint Architecture:</span>
                <span className="font-mono text-indigo-700">POST /api/v1/explanation</span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Financial Boundary:</span>
                <span className="font-semibold text-emerald-700">Read-Only Ground Truth (Immutability Verified)</span>
              </div>
              <div className="flex justify-between items-center text-slate-600">
                <span>Fallback Timeout SLA:</span>
                <span className="font-mono text-slate-800">&lt; 3,500ms (Fail-Safe Sub-2ms)</span>
              </div>
            </div>

            <p className="text-[11px] text-slate-500 leading-relaxed">
              FairCart AI enforces a strict architectural boundary: Gemini translates verified catalogue attributes and offer conditions into plain-language customer explanations. It has zero capability to alter pricing, override margins, or invent scarcity claims.
            </p>
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
            <span>Decision latency: sub-25ms synchronous</span>
            <span>Zero personal data recorded</span>
          </div>
        </div>
      </div>

      {/* Category Breakdown Table */}
      <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-sm space-y-3">
        <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
          <Database className="w-4 h-4 text-indigo-600" />
          <span>Curated Catalogue Inventory Breakdown</span>
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 pt-1">
          {Object.entries(categoryCounts).map(([cat, count]) => (
            <div
              key={cat}
              className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg flex items-center justify-between text-xs"
            >
              <span className="font-semibold text-slate-700">{cat}</span>
              <span className="bg-white border border-slate-200 text-indigo-700 px-2 py-0.5 rounded font-mono font-bold text-[11px]">
                {count} {count === 1 ? 'item' : 'items'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
