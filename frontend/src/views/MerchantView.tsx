import { BarChart3, Sliders, Database, TrendingUp, Tag, Info, Lock } from 'lucide-react';
import { Product } from '../types.ts';

interface MerchantViewProps {
  products: Product[];
}

export function MerchantView({ products }: MerchantViewProps) {
  // Compute basic catalog metrics from loaded products
  const totalProducts = products.length;
  const totalPrice = products.reduce((sum, p) => sum + p.reference_price, 0);
  const avgPrice = totalProducts > 0 ? totalPrice / totalProducts : 0;
  const minPrice = totalProducts > 0 ? Math.min(...products.map((p) => p.reference_price)) : 0;
  const maxPrice = totalProducts > 0 ? Math.max(...products.map((p) => p.reference_price)) : 0;

  // Group by category
  const categoryCounts = products.reduce<{ [cat: string]: number }>((acc, p) => {
    acc[p.category] = (acc[p.category] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6 pb-16">
      {/* Restrained Merchant Header */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/90 shadow-sm space-y-3">
        <div className="inline-flex items-center space-x-2 bg-indigo-50 text-indigo-700 px-3 py-1 rounded-full text-xs font-semibold border border-indigo-200">
          <Sliders className="w-3.5 h-3.5" />
          <span>Merchant Intelligence Preview</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
          Merchant Intelligence & Policy Console
        </h1>
        <p className="text-sm text-slate-600 leading-relaxed max-w-2xl">
          Monitor catalogue inventory, margin baselines, and configure ethical incentive parameters. Full real-time telemetry and the 3-policy simulation (No Discount vs. Blanket 15% vs. FairCart AI) will activate in Milestone 4.
        </p>
      </div>

      {/* Live Catalogue Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4.5 rounded-xl border border-slate-200/90 shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Catalogue Size</span>
            <Database className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">{totalProducts} Products</div>
          <p className="text-[11px] text-slate-500">Seeded deterministically in SQLite</p>
        </div>

        <div className="bg-white p-4.5 rounded-xl border border-slate-200/90 shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Average Price</span>
            <Tag className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">${avgPrice.toFixed(2)}</div>
          <p className="text-[11px] text-slate-500">Across all catalog categories</p>
        </div>

        <div className="bg-white p-4.5 rounded-xl border border-slate-200/90 shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Price Range</span>
            <TrendingUp className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">
            ${minPrice.toFixed(0)} - ${maxPrice.toFixed(0)}
          </div>
          <p className="text-[11px] text-slate-500">From accessories to mechanical keyboards</p>
        </div>

        <div className="bg-white p-4.5 rounded-xl border border-slate-200/90 shadow-sm space-y-1.5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Categories</span>
            <BarChart3 className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 font-mono">
            {Object.keys(categoryCounts).length} Distinct
          </div>
          <p className="text-[11px] text-slate-500">Keyboards, Audio, Workspace & more</p>
        </div>
      </div>

      {/* Category Breakdown & Policy Sliders Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Breakdown Table */}
        <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
            <Database className="w-4 h-4 text-indigo-600" />
            <span>Catalogue Category Inventory</span>
          </h3>
          <div className="divide-y divide-slate-100">
            {Object.entries(categoryCounts).map(([cat, count]) => (
              <div key={cat} className="py-2 flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700">{cat}</span>
                <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-mono font-bold">
                  {count} {count === 1 ? 'item' : 'items'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Policy Sliders (Milestone 4 Preview) */}
        <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-sm space-y-4 relative">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
              <Sliders className="w-4 h-4 text-indigo-600" />
              <span>Policy Thresholds (Milestone 4 Preview)</span>
            </h3>
            <span className="inline-flex items-center space-x-1 text-[11px] bg-amber-50 text-amber-800 font-semibold px-2 py-0.5 rounded-full border border-amber-200">
              <Lock className="w-3 h-3 text-amber-600" />
              <span>Preview</span>
            </span>
          </div>

          <div className="space-y-4 opacity-80 pointer-events-none select-none">
            {/* Margin Floor Slider */}
            <div>
              <div className="flex justify-between text-xs mb-1 font-semibold text-slate-700">
                <span>Minimum Basket Margin Floor</span>
                <span className="font-mono text-indigo-600 font-bold">25.0%</span>
              </div>
              <input
                type="range"
                min="10"
                max="50"
                value="25"
                readOnly
                className="w-full accent-indigo-600 h-1.5 bg-slate-200 rounded-lg cursor-not-allowed"
              />
              <p className="text-[10px] text-slate-500 mt-0.5">
                Engine B will reject any incentive candidate yielding margin below this floor.
              </p>
            </div>

            {/* Discount Cap Slider */}
            <div>
              <div className="flex justify-between text-xs mb-1 font-semibold text-slate-700">
                <span>Maximum Allowed Discount Cap</span>
                <span className="font-mono text-indigo-600 font-bold">20.0%</span>
              </div>
              <input
                type="range"
                min="5"
                max="30"
                value="20"
                readOnly
                className="w-full accent-indigo-600 h-1.5 bg-slate-200 rounded-lg cursor-not-allowed"
              />
              <p className="text-[10px] text-slate-500 mt-0.5">
                Upper bound on single-item discount percentage.
              </p>
            </div>
          </div>

          <div className="bg-slate-50 rounded-lg p-3 border border-slate-200 text-xs text-slate-600 flex items-start space-x-2">
            <Info className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
            <p className="text-[11px] leading-relaxed">
              <strong>Milestone Sequence Note:</strong> You are currently reviewing Milestone 2. Policy tuning, real-time telemetry graphs, and the 100-basket 3-policy simulation are scheduled for <strong>Milestone 4</strong>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
