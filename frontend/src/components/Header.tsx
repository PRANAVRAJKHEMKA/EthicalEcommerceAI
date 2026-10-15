import { ShoppingCart, ShieldCheck, HelpCircle } from 'lucide-react';
import { HealthStatus } from '../types.ts';

interface HeaderProps {
  activeTab: 'store' | 'merchant';
  setActiveTab: (tab: 'store' | 'merchant') => void;
  cartCount: number;
  openCart: () => void;
  health: HealthStatus | null;
  loadingHealth: boolean;
  onOpenTransparency?: () => void;
}

export function Header({
  activeTab,
  setActiveTab,
  cartCount,
  openCart,
  health,
  loadingHealth,
  onOpenTransparency,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white/95 backdrop-blur-md sticky top-0 z-40 shadow-xs">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-14 sm:h-16 flex items-center justify-between">
        {/* Brand & Ethical Engine Pill */}
        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={() => setActiveTab('store')}
            className="flex items-baseline cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded p-1 -m-1"
            aria-label="FairCart AI Home"
          >
            <span className="text-base sm:text-lg font-black tracking-tight text-slate-900">
              FairCart <span className="text-indigo-600">AI</span>
            </span>
          </button>

          {onOpenTransparency && (
            <button
              onClick={onOpenTransparency}
              className="hidden md:inline-flex items-center space-x-1 text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold px-2 py-0.5 rounded-md border border-slate-200 transition-colors cursor-pointer"
              title="Click to view How Recommendations & Offers Work"
            >
              <ShieldCheck className="w-3 h-3 text-emerald-600" />
              <span>Ethical Engine</span>
              <HelpCircle className="w-2.5 h-2.5 text-slate-400 ml-0.5" />
            </button>
          )}
        </div>

        {/* Right Controls: Switcher + Health + Cart */}
        <div className="flex items-center space-x-1.5 sm:space-x-3 shrink-0">
          {/* View Switcher Tabs */}
          <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200">
            <button
              onClick={() => setActiveTab('store')}
              className={`px-2 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold rounded-md transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                activeTab === 'store'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span className="sm:hidden">Store</span>
              <span className="hidden sm:inline">Shop Store</span>
            </button>
            <button
              onClick={() => setActiveTab('merchant')}
              className={`px-2 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold rounded-md transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                activeTab === 'merchant'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span className="sm:hidden">Console</span>
              <span className="hidden sm:inline">Merchant Console</span>
            </button>
          </div>

          {/* Health Pill (Desktop only) */}
          <div className="hidden lg:flex items-center space-x-2 text-xs py-1 px-2.5 rounded-lg bg-slate-50 border border-slate-200">
            <span
              className={`h-2 w-2 rounded-full ${
                health && health.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-400'
              }`}
            />
            <span className="text-slate-600 font-medium">
              {loadingHealth
                ? 'Connecting...'
                : health
                ? `FastAPI (${health.catalog_items_loaded} items)`
                : 'API Offline'}
            </span>
          </div>

          {/* Cart Button */}
          <button
            onClick={openCart}
            className="relative inline-flex items-center space-x-1 bg-indigo-600 hover:bg-indigo-700 text-white p-1.5 sm:px-3 sm:py-1.5 rounded-lg text-xs font-semibold transition-colors shadow-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 shrink-0"
            aria-label="Open cart"
          >
            <ShoppingCart className="w-4 h-4 shrink-0" />
            <span className="hidden sm:inline">Cart</span>
            {cartCount > 0 && (
              <span className="inline-flex items-center justify-center bg-white text-indigo-700 text-[10px] font-bold rounded-full h-4 min-w-4 px-1 ml-0.5">
                {cartCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
