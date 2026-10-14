import { useState, useEffect } from 'react';
import { HealthStatus } from './types.ts';

export default function App() {
  const [activeTab, setActiveTab] = useState<'store' | 'merchant'>('store');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/v1/health')
      .then((res) => res.json())
      .then((data: HealthStatus) => {
        setHealth(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      {/* Top Navigation */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-xl font-bold tracking-tight text-slate-900">
              FairCart <span className="text-emerald-600">AI</span>
            </span>
            <span className="hidden sm:inline-block text-xs bg-emerald-50 text-emerald-700 font-medium px-2.5 py-0.5 rounded-full border border-emerald-200">
              Ethical Commerce Engine
            </span>
          </div>

          {/* View Switcher Navigation */}
          <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => setActiveTab('store')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                activeTab === 'store'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Shop Store
            </button>
            <button
              onClick={() => setActiveTab('merchant')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                activeTab === 'merchant'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Merchant Console
            </button>
          </div>

          {/* Backend Status Badge */}
          <div className="flex items-center space-x-2 text-xs">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                health && health.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-400'
              }`}
            />
            <span className="text-slate-600 font-mono">
              {loading
                ? 'Connecting API...'
                : health
                ? `DB Ready (${health.catalog_items_loaded} items)`
                : 'API Offline'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-6">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                {activeTab === 'store' ? 'Storefront Scaffold' : 'Merchant Console Scaffold'}
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                Milestone 1 — Foundation & Health Operational
              </p>
            </div>
            <span className="text-xs font-mono bg-slate-100 text-slate-700 px-3 py-1 rounded-md border border-slate-200">
              Devpost Build With AI: Basics
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Database Engine
              </span>
              <p className="text-lg font-bold text-slate-800 mt-1">
                SQLite Embedded
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Sub-millisecond query latency; zero cloud dependencies.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Catalog Items Loaded
              </span>
              <p className="text-lg font-bold text-slate-800 mt-1">
                {health ? `${health.catalog_items_loaded} Products` : '20 Seeded in DB'}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Realistic wholesale COGS and base reference prices.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Next Stage
              </span>
              <p className="text-lg font-bold text-indigo-600 mt-1">
                Milestone 2
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Catalog API, interactive cart drawer, and recommendation card.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
