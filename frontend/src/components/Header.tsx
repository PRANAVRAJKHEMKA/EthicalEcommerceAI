import { ShoppingCart } from 'lucide-react';
import { HealthStatus } from '../types.ts';

interface HeaderProps {
  activeTab: 'store' | 'merchant';
  setActiveTab: (tab: 'store' | 'merchant') => void;
  cartCount: number;
  openCart: () => void;
  health: HealthStatus | null;
  loadingHealth: boolean;
}

export function Header({
  activeTab,
  setActiveTab,
  cartCount,
  openCart,
  health,
  loadingHealth,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white/95 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand & Tagline */}
        <div className="flex items-center space-x-3">
          <div className="flex items-baseline space-x-1 cursor-pointer" onClick={() => setActiveTab('store')}>
            <span className="text-xl font-black tracking-tight text-slate-900">
              FairCart <span className="text-emerald-600">AI</span>
            </span>
          </div>
          <span className="hidden md:inline-flex items-center text-xs bg-emerald-50 text-emerald-800 font-semibold px-2.5 py-0.5 rounded-full border border-emerald-200">
            Ethical Commerce
          </span>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
          <button
            onClick={() => setActiveTab('store')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
              activeTab === 'store'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Shop Store
          </button>
          <button
            onClick={() => setActiveTab('merchant')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
              activeTab === 'merchant'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Merchant Console
          </button>
        </div>

        {/* Action Controls: Status Pill & Cart Trigger */}
        <div className="flex items-center space-x-4">
          {/* Health Pill */}
          <div className="hidden sm:flex items-center space-x-2 text-xs py-1 px-2.5 rounded-md bg-slate-50 border border-slate-200">
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
            className="relative flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white px-3.5 py-2 rounded-lg text-sm font-semibold transition-colors shadow-sm"
            aria-label="Open Cart"
          >
            <ShoppingCart className="w-4 h-4" />
            <span className="hidden sm:inline">Cart</span>
            {cartCount > 0 && (
              <span className="inline-flex items-center justify-center bg-white text-indigo-700 text-xs font-bold rounded-full h-5 min-w-5 px-1 ml-1">
                {cartCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
