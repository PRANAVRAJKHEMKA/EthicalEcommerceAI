import React, { useState, useEffect } from 'react';
import {
  Cpu,
  TrendingUp,
  AlertTriangle,
  ShieldCheck,
  RefreshCw,
  Play,
  ArrowUpRight,
  PackageCheck,
  BarChart2,
  Lock,
  Link as LinkIcon,
  Zap,
} from 'lucide-react';
import {
  InventoryItem,
  DemandForecastRecord,
  InventoryAlert,
  BatchOptimizationResult,
  ExternalConnectorConfig,
  DecisionTraceSnapshot,
} from '../types.ts';
import {
  fetchTwinInventory,
  fetchTwinInventoryAlerts,
  fetchTwinForecasts,
  runBatchOptimization,
  fetchConnectors,
  configureConnector,
  syncConnector,
  disconnectConnector,
  fetchTwinTrace,
} from '../api.ts';

export function DecisionTwinConsole() {
  const [activeSubTab, setActiveSubTab] = useState<'simulator' | 'inventory' | 'forecasts' | 'alerts' | 'connectors' | 'trace'>('simulator');

  // Inventory state
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loadingInventory, setLoadingInventory] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('all');

  // Forecasts state
  const [forecasts, setForecasts] = useState<DemandForecastRecord[]>([]);
  const [horizonDays, setHorizonDays] = useState<number>(14);
  const [loadingForecasts, setLoadingForecasts] = useState(false);

  // Alerts state
  const [alerts, setAlerts] = useState<InventoryAlert[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState(false);

  // Batch Simulator state
  const [batchSessionsCount, setBatchSessionsCount] = useState<number>(20);
  const [batchMarginFloor, setBatchMarginFloor] = useState<number>(0.20);
  const [batchDiscountCap, setBatchDiscountCap] = useState<number>(0.20);
  const [runningBatch, setRunningBatch] = useState(false);
  const [batchResult, setBatchResult] = useState<BatchOptimizationResult | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);

  // Connectors state
  const [connectors, setConnectors] = useState<ExternalConnectorConfig[]>([]);
  const [loadingConnectors, setLoadingConnectors] = useState(false);
  const [syncingProvider, setSyncingProvider] = useState<string | null>(null);
  const [connectorMsg, setConnectorMsg] = useState<{ provider: string; msg: string; isError?: boolean } | null>(null);

  // GA4 / Shopify modal or inline config
  const [configProvider, setConfigProvider] = useState<string | null>(null);
  const [ga4PropId, setGa4PropId] = useState('');
  const [ga4Email, setGa4Email] = useState('');
  const [shopifyDomain, setShopifyDomain] = useState('');
  const [shopifyToken, setShopifyToken] = useState('');
  const [configuring, setConfiguring] = useState(false);

  // Trace Inspector state
  const [traceIdInput, setTraceIdInput] = useState('');
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [traceData, setTraceData] = useState<DecisionTraceSnapshot | null>(null);
  const [traceError, setTraceError] = useState<string | null>(null);

  // Initial loads
  useEffect(() => {
    loadInventory();
    loadAlerts();
    loadForecasts(horizonDays);
    loadConnectors();
  }, []);

  async function loadInventory() {
    setLoadingInventory(true);
    try {
      const data = await fetchTwinInventory('primary_storefront', categoryFilter);
      setInventory(data);
    } catch (err: unknown) {
      console.error('Failed to load inventory:', err);
    } finally {
      setLoadingInventory(false);
    }
  }

  async function loadAlerts() {
    setLoadingAlerts(true);
    try {
      const data = await fetchTwinInventoryAlerts('primary_storefront');
      setAlerts(data);
    } catch (err: unknown) {
      console.error('Failed to load alerts:', err);
    } finally {
      setLoadingAlerts(false);
    }
  }

  async function loadForecasts(h: number) {
    setLoadingForecasts(true);
    try {
      const data = await fetchTwinForecasts('primary_storefront', h);
      setForecasts(data);
    } catch (err: unknown) {
      console.error('Failed to load forecasts:', err);
    } finally {
      setLoadingForecasts(false);
    }
  }

  async function loadConnectors() {
    setLoadingConnectors(true);
    try {
      const data = await fetchConnectors();
      setConnectors(data);
    } catch (err: unknown) {
      console.error('Failed to load connectors:', err);
    } finally {
      setLoadingConnectors(false);
    }
  }

  async function handleRunBatch() {
    setRunningBatch(true);
    setBatchError(null);
    try {
      // Generate synthetic sessions competing for stock
      const sessions = Array.from({ length: batchSessionsCount }, (_, i) => ({
        session_id: `sess_twin_demo_${i + 1}`,
        cart_items: [
          {
            product_id: i % 3 === 0 ? 'item-001' : (i % 3 === 1 ? 'item-003' : 'item-002'),
            quantity: 1,
          },
        ],
        dwell_time_seconds: 20 + (i * 15) % 180,
      }));

      const res = await runBatchOptimization({
        sessions,
        storefront_id: 'primary_storefront',
        margin_floor: batchMarginFloor,
        discount_cap: batchDiscountCap,
      });
      setBatchResult(res);
      // Refresh inventory to reflect shadow analysis
      loadInventory();
      loadAlerts();
    } catch (err: unknown) {
      setBatchError(err instanceof Error ? err.message : 'Batch simulation failed');
    } finally {
      setRunningBatch(false);
    }
  }

  async function handleSync(provider: string) {
    setSyncingProvider(provider);
    setConnectorMsg(null);
    try {
      const res = await syncConnector(provider, 'primary_storefront');
      setConnectorMsg({
        provider,
        msg: `Sync complete: Ingested ${res.records_ingested} records. ${res.details}`,
      });
      loadConnectors();
    } catch (err: unknown) {
      setConnectorMsg({
        provider,
        msg: err instanceof Error ? err.message : 'Sync failed',
        isError: true,
      });
    } finally {
      setSyncingProvider(null);
    }
  }

  async function handleDisconnect(provider: string) {
    if (!confirm(`Are you sure you want to disconnect ${provider} and erase its encrypted credentials?`)) return;
    try {
      await disconnectConnector(provider);
      loadConnectors();
    } catch (err: unknown) {
      alert(`Disconnect failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }

  async function handleConfigureSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!configProvider) return;
    setConfiguring(true);
    try {
      const creds: Record<string, string> = {};
      if (configProvider === 'google_analytics_4') {
        creds.property_id = ga4PropId;
        creds.client_email = ga4Email;
      } else {
        creds.shop_url = shopifyDomain;
        creds.access_token = shopifyToken;
      }

      await configureConnector({
        provider: configProvider,
        credentials: creds,
      });

      setConfigProvider(null);
      setGa4PropId('');
      setGa4Email('');
      setShopifyDomain('');
      setShopifyToken('');
      loadConnectors();
    } catch (err: unknown) {
      alert(`Configuration error: ${err instanceof Error ? err.message : 'Failed to configure'}`);
    } finally {
      setConfiguring(false);
    }
  }

  async function handleInspectTrace(id: string) {
    if (!id.trim()) return;
    setLoadingTrace(true);
    setTraceError(null);
    try {
      const data = await fetchTwinTrace(id.trim());
      setTraceData(data);
      setActiveSubTab('trace');
    } catch (err: unknown) {
      setTraceError(err instanceof Error ? err.message : 'Trace not found');
      setTraceData(null);
    } finally {
      setLoadingTrace(false);
    }
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-slate-100 shadow-2xl mt-8">
      {/* Console Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-400">
              <Cpu className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold tracking-tight text-white">FairCart Decision Twin</h2>
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-500/30">
                  Dual ATP & Causal Intent Active
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-0.5">
                Predictive demand horizons, Available-To-Promise inventory allocation, and scarcity shadow pricing ($\lambda_i$)
              </p>
            </div>
          </div>
        </div>

        {/* Quick KPI Strip */}
        <div className="flex items-center gap-3 text-xs bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5">
          <div className="px-3 border-r border-slate-800">
            <span className="text-slate-400 block">Inventory Monitored</span>
            <span className="font-semibold text-slate-200 text-sm">{inventory.length} SKUs</span>
          </div>
          <div className="px-3 border-r border-slate-800">
            <span className="text-slate-400 block">Active Alerts</span>
            <span className={`font-semibold text-sm ${alerts.filter(a => a.severity === 'CRITICAL').length > 0 ? 'text-amber-400' : 'text-slate-200'}`}>
              {alerts.length} ({alerts.filter(a => a.severity === 'CRITICAL').length} critical)
            </span>
          </div>
          <div className="px-3">
            <span className="text-slate-400 block">Scarcity Guard</span>
            <span className="font-semibold text-teal-400 text-sm">$\lambda_i$ Bounded</span>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex flex-wrap items-center gap-2 mt-6 border-b border-slate-800 pb-3 text-sm">
        <button
          onClick={() => setActiveSubTab('simulator')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg font-medium transition-colors ${
            activeSubTab === 'simulator'
              ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Play className="w-4 h-4" />
          Multi-Shopper Profit Allocator
        </button>
        <button
          onClick={() => setActiveSubTab('inventory')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg font-medium transition-colors ${
            activeSubTab === 'inventory'
              ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <PackageCheck className="w-4 h-4" />
          Real-Time ATP & $\lambda_i$ Matrix
        </button>
        <button
          onClick={() => setActiveSubTab('forecasts')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg font-medium transition-colors ${
            activeSubTab === 'forecasts'
              ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <BarChart2 className="w-4 h-4" />
          Demand Forecasts & Intervals
        </button>
        <button
          onClick={() => setActiveSubTab('alerts')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg font-medium transition-colors relative ${
            activeSubTab === 'alerts'
              ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          Advisory & Restock Alerts
          {alerts.length > 0 && (
            <span className="ml-1 px-1.5 py-0.2 text-[10px] bg-amber-500/20 text-amber-300 rounded-full border border-amber-500/30">
              {alerts.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveSubTab('connectors')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg font-medium transition-colors ${
            activeSubTab === 'connectors'
              ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <LinkIcon className="w-4 h-4" />
          Analytics Connectors
        </button>
        <button
          onClick={() => setActiveSubTab('trace')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-lg font-medium transition-colors ${
            activeSubTab === 'trace'
              ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          Trace Audit Inspector
        </button>
      </div>

      {/* SUB-TAB 1: MULTI-SHOPPER PROFIT ALLOCATOR */}
      {activeSubTab === 'simulator' && (
        <div className="mt-6 space-y-6">
          <div className="bg-slate-950/40 border border-slate-800/80 rounded-xl p-5">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-teal-400" />
              Batch Profit Allocation Optimizer: Twin vs. Naive Greedy
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Simulates concurrent shoppers competing for constrained Available-To-Promise (ATP) stock.
              The Decision Twin suppresses discounts on scarce items (scarcity shadow price $\lambda_i$ &gt; 0) to reserve them for full-margin organic buyers,
              while a naive greedy allocator depletes inventory prematurely with heavy discounting.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 pt-4 border-t border-slate-800/60">
              <div>
                <label className="text-xs text-slate-300 font-medium block">Competing Sessions (N)</label>
                <select
                  value={batchSessionsCount}
                  onChange={(e) => setBatchSessionsCount(Number(e.target.value))}
                  className="mt-1.5 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"
                >
                  <option value={10}>10 Shoppers (Light Traffic)</option>
                  <option value={20}>20 Shoppers (Constrained Surge)</option>
                  <option value={50}>50 Shoppers (High Demand Peak)</option>
                  <option value={100}>100 Shoppers (Flash Sale Load)</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-300 font-medium block">
                  Gross Margin Floor ({Math.round(batchMarginFloor * 100)}%)
                </label>
                <input
                  type="range"
                  min="0.10"
                  max="0.50"
                  step="0.01"
                  value={batchMarginFloor}
                  onChange={(e) => setBatchMarginFloor(Number(e.target.value))}
                  className="mt-2 w-full accent-teal-400"
                />
              </div>
              <div>
                <label className="text-xs text-slate-300 font-medium block">
                  Discount Cap ({Math.round(batchDiscountCap * 100)}%)
                </label>
                <input
                  type="range"
                  min="0.05"
                  max="0.30"
                  step="0.01"
                  value={batchDiscountCap}
                  onChange={(e) => setBatchDiscountCap(Number(e.target.value))}
                  className="mt-2 w-full accent-teal-400"
                />
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <button
                onClick={handleRunBatch}
                disabled={runningBatch}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 font-semibold text-sm transition-all disabled:opacity-50"
              >
                {runningBatch ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                {runningBatch ? 'Solving Allocation...' : 'Run Decision Twin Batch Optimization'}
              </button>

              <span className="text-xs text-slate-400">
                Non-destructive shadow allocation; does not decrement physical inventory.
              </span>
            </div>

            {batchError && (
              <div className="mt-4 p-3 bg-rose-950/40 border border-rose-800 rounded-lg text-rose-300 text-xs">
                {batchError}
              </div>
            )}
          </div>

          {/* Results Display */}
          {batchResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-950/80 border border-teal-500/30 rounded-xl p-4">
                  <span className="text-xs text-slate-400 uppercase tracking-wider block">Decision Twin Profit</span>
                  <div className="text-2xl font-bold text-teal-300 mt-1">
                    ${batchResult.aggregate_projected_profit.toFixed(2)}
                  </div>
                  <span className="text-xs text-emerald-400 flex items-center gap-1 mt-1 font-medium">
                    <ArrowUpRight className="w-3.5 h-3.5" />
                    +{batchResult.projected_profit_lift_pct}% vs. Greedy
                  </span>
                </div>

                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
                  <span className="text-xs text-slate-400 uppercase tracking-wider block">Naive Greedy Baseline</span>
                  <div className="text-2xl font-bold text-slate-300 mt-1">
                    ${batchResult.baseline_greedy_profit.toFixed(2)}
                  </div>
                  <span className="text-xs text-rose-400 mt-1 block">Suffers stockout leakage</span>
                </div>

                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
                  <span className="text-xs text-slate-400 uppercase tracking-wider block">Scarce Units Protected</span>
                  <div className="text-2xl font-bold text-amber-300 mt-1">
                    {batchResult.inventory_saved_units} Units
                  </div>
                  <span className="text-xs text-slate-400 mt-1 block">Preserved for full margin</span>
                </div>

                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4">
                  <span className="text-xs text-slate-400 uppercase tracking-wider block">Stockout Prevention</span>
                  <div className="text-2xl font-bold text-emerald-400 mt-1">
                    {Math.round(batchResult.stockout_prevention_rate * 100)}%
                  </div>
                  <span className="text-xs text-slate-400 mt-1 block">{batchResult.execution_latency_ms}ms runtime</span>
                </div>
              </div>

              {/* Allocation Breakdown */}
              <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-5">
                <h4 className="text-sm font-semibold text-white mb-3">
                  Optimal Offer Allocation Breakdown ({batchResult.allocations.length} sessions evaluated)
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 uppercase font-medium">
                        <th className="py-2 px-3">Session</th>
                        <th className="py-2 px-3">Product</th>
                        <th className="py-2 px-3">Twin Action</th>
                        <th className="py-2 px-3">Final Price</th>
                        <th className="py-2 px-3">Discount</th>
                        <th className="py-2 px-3">$\lambda_i$ Scarcity</th>
                        <th className="py-2 px-3">Expected Profit</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {batchResult.allocations.slice(0, 10).map((row, idx) => (
                        <tr key={idx} className="hover:bg-slate-900/50">
                          <td className="py-2 px-3 text-slate-400">{row.session_id}</td>
                          <td className="py-2 px-3 font-sans text-slate-200">{row.product_name}</td>
                          <td className="py-2 px-3">
                            <span className={`px-2 py-0.5 rounded text-[11px] ${
                              row.action.includes('NO_OFFER')
                                ? 'bg-slate-800 text-slate-300'
                                : 'bg-teal-950 text-teal-300 border border-teal-500/30'
                            }`}>
                              {row.action}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-slate-200">${row.price.toFixed(2)}</td>
                          <td className="py-2 px-3 text-amber-300">{Math.round(row.discount_pct * 100)}%</td>
                          <td className="py-2 px-3 text-teal-400">${row.scarcity_lambda.toFixed(2)}</td>
                          <td className="py-2 px-3 font-semibold text-emerald-400">${row.expected_profit.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {batchResult.allocations.length > 10 && (
                    <p className="text-center text-[11px] text-slate-500 mt-2 font-sans">
                      Showing first 10 of {batchResult.allocations.length} sessions. All {batchResult.allocations.length} preserved in shadow audit.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 2: REAL-TIME ATP & SCARCITY MATRIX */}
      {activeSubTab === 'inventory' && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400">Filter Category:</span>
              <select
                value={categoryFilter}
                onChange={(e) => {
                  setCategoryFilter(e.target.value);
                  loadInventory();
                }}
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200"
              >
                <option value="all">All Categories</option>
                <option value="Electronics">Electronics</option>
                <option value="Accessories">Accessories</option>
                <option value="Ergonomics">Ergonomics</option>
                <option value="Audio">Audio</option>
              </select>
            </div>
            <button
              onClick={loadInventory}
              disabled={loadingInventory}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingInventory ? 'animate-spin' : ''}`} />
              Refresh ATP
            </button>
          </div>

          <div className="bg-slate-950/40 border border-slate-800 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase font-medium bg-slate-950/80">
                    <th className="py-2.5 px-3">SKU</th>
                    <th className="py-2.5 px-3">Product Name</th>
                    <th className="py-2.5 px-3">Category</th>
                    <th className="py-2.5 px-3">On Hand</th>
                    <th className="py-2.5 px-3">Reserved</th>
                    <th className="py-2.5 px-3 font-semibold text-white">ATP Stock</th>
                    <th className="py-2.5 px-3">Buffer</th>
                    <th className="py-2.5 px-3 text-teal-400 font-semibold">Shadow Price ($\lambda_i$)</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {inventory.map((item) => (
                    <tr key={item.sku} className="hover:bg-slate-900/50">
                      <td className="py-2.5 px-3 text-slate-400">{item.sku}</td>
                      <td className="py-2.5 px-3 font-sans text-slate-200 font-medium">{item.product_name}</td>
                      <td className="py-2.5 px-3 font-sans text-slate-400">{item.category}</td>
                      <td className="py-2.5 px-3">{item.on_hand}</td>
                      <td className="py-2.5 px-3 text-slate-400">{item.reserved}</td>
                      <td className="py-2.5 px-3 font-bold text-white text-sm">{item.atp}</td>
                      <td className="py-2.5 px-3 text-slate-400">{item.safety_stock}</td>
                      <td className="py-2.5 px-3 font-semibold text-teal-400">
                        {item.scarcity_lambda > 0 ? `$${item.scarcity_lambda.toFixed(2)}` : '$0.00'}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-sans font-semibold ${
                          item.stock_status === 'CRITICAL_STOCKOUT_RISK'
                            ? 'bg-rose-950 text-rose-300 border border-rose-500/40'
                            : item.stock_status === 'LOW_STOCK'
                            ? 'bg-amber-950 text-amber-300 border border-amber-500/40'
                            : item.stock_status === 'OVERSTOCKED'
                            ? 'bg-indigo-950 text-indigo-300 border border-indigo-500/40'
                            : 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'
                        }`}>
                          {item.stock_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 3: DEMAND FORECASTS & INTERVALS */}
      {activeSubTab === 'forecasts' && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Forecast Horizon:</span>
              {[7, 14, 30].map((h) => (
                <button
                  key={h}
                  onClick={() => {
                    setHorizonDays(h);
                    loadForecasts(h);
                  }}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold ${
                    horizonDays === h
                      ? 'bg-teal-500 text-slate-950'
                      : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {h}-Day Horizon
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              {loadingForecasts && <RefreshCw className="w-3.5 h-3.5 animate-spin text-teal-400" />}
              <span className="text-xs text-slate-400">
                Conformal Residual Intervals (95% Coverage)
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {forecasts.slice(0, 6).map((fc) => (
              <div key={fc.sku} className="bg-slate-950/60 border border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-slate-400">{fc.sku}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-teal-300 font-mono">
                    {fc.method}
                  </span>
                </div>
                <div className="mt-3">
                  <span className="text-xs text-slate-400 block">{horizonDays}-Day Point Demand</span>
                  <div className="text-2xl font-bold text-white mt-0.5">
                    {fc.point_forecast} <span className="text-sm font-normal text-slate-400">units</span>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-slate-800 text-xs flex justify-between text-slate-300">
                  <span>95% Interval:</span>
                  <span className="font-mono text-teal-400">[{fc.lower_bound} — {fc.upper_bound}]</span>
                </div>

                <div className="mt-2 text-[11px] text-slate-400 flex justify-between">
                  <span>WAPE: {(fc.wape * 100).toFixed(1)}%</span>
                  <span>MASE: {fc.mase.toFixed(2)}</span>
                  <span>Bias: {fc.forecast_bias > 0 ? `+${fc.forecast_bias}%` : `${fc.forecast_bias}%`}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SUB-TAB 4: ADVISORY & RESTOCK ALERTS */}
      {activeSubTab === 'alerts' && (
        <div className="mt-6 space-y-3">
          <div className="flex justify-between items-center pb-1">
            <span className="text-xs text-slate-400">Proactive inventory health and stockout protection</span>
            <button
              onClick={loadAlerts}
              disabled={loadingAlerts}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingAlerts ? 'animate-spin' : ''}`} />
              Refresh Alerts
            </button>
          </div>
          {alerts.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm bg-slate-950/40 rounded-xl border border-slate-800">
              No active inventory alerts. All catalog SKUs maintain healthy ATP buffers.
            </div>
          ) : (
            alerts.map((alt) => (
              <div
                key={alt.alert_id}
                className={`p-4 rounded-xl border flex items-start gap-3.5 ${
                  alt.severity === 'CRITICAL'
                    ? 'bg-rose-950/30 border-rose-500/40 text-rose-200'
                    : alt.severity === 'WARNING'
                    ? 'bg-amber-950/30 border-amber-500/40 text-amber-200'
                    : 'bg-indigo-950/30 border-indigo-500/40 text-indigo-200'
                }`}
              >
                <AlertTriangle className={`w-5 h-5 shrink-0 mt-0.5 ${
                  alt.severity === 'CRITICAL' ? 'text-rose-400' : alt.severity === 'WARNING' ? 'text-amber-400' : 'text-indigo-400'
                }`} />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm text-white">
                      {alt.product_name} ({alt.sku})
                    </span>
                    <span className="text-[11px] font-mono opacity-80">
                      {alt.days_of_supply_remaining} Days Supply Left
                    </span>
                  </div>
                  <p className="text-xs mt-1 opacity-90">{alt.description}</p>
                  <div className="mt-2 text-xs font-medium text-white flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-teal-400" />
                    <span>Suggested Action: {alt.suggested_action}</span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* SUB-TAB 5: ANALYTICS CONNECTORS */}
      {activeSubTab === 'connectors' && (
        <div className="mt-6 space-y-6">
          <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <LinkIcon className="w-5 h-5 text-teal-400" />
                  External Analytics & Commerce Connectors
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Connect Google Analytics 4 and Shopify Admin to automatically ingest funnel traffic, checkout drops, and order lines.
                  Credentials are encrypted at rest with Fernet authenticated encryption (AES-128-CBC with HMAC-SHA256). Truthful connectivity: unconfigured connectors do not claim fake syncs.
                </p>
              </div>
              <button
                onClick={loadConnectors}
                disabled={loadingConnectors}
                className="self-start sm:self-auto flex items-center gap-1.5 text-xs text-slate-400 hover:text-white bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingConnectors ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">
              {/* GA4 Card */}
              {connectors.find(c => c.provider === 'google_analytics_4') && (() => {
                const ga = connectors.find(c => c.provider === 'google_analytics_4')!;
                const isConn = ga.status === 'connected';
                return (
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white text-sm">Google Analytics 4</span>
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                          isConn ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'
                        }`}>
                          {ga.status.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        Ingests e-commerce funnel events (`view_item`, `add_to_cart`, `purchase`).
                      </p>
                      <div className="mt-3 text-xs space-y-1 text-slate-300">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Account:</span>
                          <span className="font-mono text-slate-200">{ga.masked_account_id || 'Not configured'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Scope:</span>
                          <span className="font-mono text-[11px] text-teal-400">analytics.readonly</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Last Sync:</span>
                          <span className="text-slate-200">{ga.last_sync_at ? new Date(ga.last_sync_at).toLocaleString() : 'Never'}</span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-5 pt-3 border-t border-slate-800 flex items-center gap-2">
                      {isConn ? (
                        <>
                          <button
                            onClick={() => handleSync('google_analytics_4')}
                            disabled={syncingProvider === 'google_analytics_4'}
                            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-500/20 text-teal-300 border border-teal-500/40 text-xs font-semibold hover:bg-teal-500/30 transition-all"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${syncingProvider === 'google_analytics_4' ? 'animate-spin' : ''}`} />
                            Sync Traffic
                          </button>
                          <button
                            onClick={() => handleDisconnect('google_analytics_4')}
                            className="px-3 py-1.5 rounded-lg bg-rose-950/40 text-rose-300 border border-rose-800 text-xs font-semibold hover:bg-rose-900/50"
                          >
                            Disconnect
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => setConfigProvider('google_analytics_4')}
                          className="w-full px-3 py-2 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 text-xs font-semibold"
                        >
                          Configure GA4 Credentials
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* Shopify Card */}
              {connectors.find(c => c.provider === 'shopify') && (() => {
                const shp = connectors.find(c => c.provider === 'shopify')!;
                const isConn = shp.status === 'connected';
                return (
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white text-sm">Shopify Admin API</span>
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                          isConn ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'
                        }`}>
                          {shp.status.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        Ingests itemized orders, wholesale COGS, and refunds across storefronts.
                      </p>
                      <div className="mt-3 text-xs space-y-1 text-slate-300">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Storefront:</span>
                          <span className="font-mono text-slate-200">{shp.masked_account_id || 'Not configured'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Scopes:</span>
                          <span className="font-mono text-[11px] text-teal-400">read_orders, read_products</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Last Sync:</span>
                          <span className="text-slate-200">{shp.last_sync_at ? new Date(shp.last_sync_at).toLocaleString() : 'Never'}</span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-5 pt-3 border-t border-slate-800 flex items-center gap-2">
                      {isConn ? (
                        <>
                          <button
                            onClick={() => handleSync('shopify')}
                            disabled={syncingProvider === 'shopify'}
                            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-500/20 text-teal-300 border border-teal-500/40 text-xs font-semibold hover:bg-teal-500/30 transition-all"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${syncingProvider === 'shopify' ? 'animate-spin' : ''}`} />
                            Sync Orders
                          </button>
                          <button
                            onClick={() => handleDisconnect('shopify')}
                            className="px-3 py-1.5 rounded-lg bg-rose-950/40 text-rose-300 border border-rose-800 text-xs font-semibold hover:bg-rose-900/50"
                          >
                            Disconnect
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => setConfigProvider('shopify')}
                          className="w-full px-3 py-2 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 text-xs font-semibold"
                        >
                          Configure Shopify Store
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>

            {connectorMsg && (
              <div className={`mt-4 p-3 rounded-lg text-xs ${
                connectorMsg.isError ? 'bg-rose-950/40 border border-rose-800 text-rose-300' : 'bg-teal-950/40 border border-teal-800 text-teal-300'
              }`}>
                {connectorMsg.msg}
              </div>
            )}
          </div>

          {/* Configuration Modal / Inline Form */}
          {configProvider && (
            <div className="bg-slate-950 border border-teal-500/40 rounded-xl p-5 shadow-2xl">
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <Lock className="w-4 h-4 text-teal-400" />
                Configure {configProvider === 'google_analytics_4' ? 'Google Analytics 4' : 'Shopify Admin'}
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                Keys are encrypted server-side with Fernet authenticated encryption (AES-128-CBC with HMAC-SHA256) before storage.
              </p>

              <form onSubmit={handleConfigureSubmit} className="mt-4 space-y-3">
                {configProvider === 'google_analytics_4' ? (
                  <>
                    <div>
                      <label className="text-xs text-slate-300 font-medium block">GA4 Property ID</label>
                      <input
                        type="text"
                        placeholder="e.g. properties/123456789 or 123456789"
                        value={ga4PropId}
                        onChange={(e) => setGa4PropId(e.target.value)}
                        required
                        className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-300 font-medium block">Service Account Email</label>
                      <input
                        type="email"
                        placeholder="analytics-reader@project.iam.gserviceaccount.com"
                        value={ga4Email}
                        onChange={(e) => setGa4Email(e.target.value)}
                        required
                        className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <label className="text-xs text-slate-300 font-medium block">Shopify Store Domain</label>
                      <input
                        type="text"
                        placeholder="mystore.myshopify.com"
                        value={shopifyDomain}
                        onChange={(e) => setShopifyDomain(e.target.value)}
                        required
                        className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-300 font-medium block">Admin API Access Token</label>
                      <input
                        type="password"
                        placeholder="shpat_..."
                        value={shopifyToken}
                        onChange={(e) => setShopifyToken(e.target.value)}
                        required
                        className="mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
                      />
                    </div>
                  </>
                )}

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setConfigProvider(null)}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={configuring}
                    className="px-4 py-1.5 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 text-xs font-bold"
                  >
                    {configuring ? 'Validating & Encrypting...' : 'Save Encrypted Credentials'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 6: TRACE AUDIT INSPECTOR */}
      {activeSubTab === 'trace' && (
        <div className="mt-6 space-y-5">
          <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-5">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-teal-400" />
              Auditable Decision Trace Inspector
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Look up any cryptographic trace snapshot to audit continuous Markov intent posteriors,
              scarcity shadow price $\lambda_i$, candidate valuation breakdown, and why counterfactual offers were rejected.
            </p>

            <div className="mt-4 flex gap-2">
              <input
                type="text"
                placeholder="Enter trace ID (e.g. trc_abc123...)"
                value={traceIdInput}
                onChange={(e) => setTraceIdInput(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white"
              />
              <button
                onClick={() => handleInspectTrace(traceIdInput)}
                disabled={loadingTrace || !traceIdInput.trim()}
                className="px-4 py-2 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 text-xs font-bold disabled:opacity-50"
              >
                {loadingTrace ? 'Fetching...' : 'Inspect Trace'}
              </button>
            </div>

            {traceError && (
              <div className="mt-3 p-3 bg-rose-950/40 border border-rose-800 text-rose-300 text-xs rounded-lg">
                {traceError}
              </div>
            )}
          </div>

          {/* Trace Detail View */}
          {traceData && (
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 space-y-4 font-sans">
              <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-800 gap-2">
                <div>
                  <span className="text-xs text-slate-400 font-mono">Trace ID: {traceData.trace_id}</span>
                  <div className="text-sm font-bold text-white mt-0.5">
                    Session: <span className="font-mono text-teal-300">{traceData.session_id}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 font-mono">
                    Intent State: <strong className="text-teal-300">{traceData.intent_state}</strong>
                  </span>
                  <span className="px-2.5 py-1 rounded bg-slate-800 text-teal-400 font-mono">
                    $\lambda_i = ${traceData.scarcity_lambda.toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Utility Formula */}
              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg font-mono text-xs text-teal-300">
                <span className="text-slate-400 block mb-1 font-sans text-[11px]">Active Utility Objective:</span>
                {traceData.utility_formula}
              </div>

              {/* Candidates Evaluated Table */}
              <div>
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Action Candidates Evaluated ({traceData.candidates_evaluated.length})
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 uppercase">
                        <th className="py-2 px-2">Action</th>
                        <th className="py-2 px-2">Ref Price</th>
                        <th className="py-2 px-2">Offered</th>
                        <th className="py-2 px-2">Margin %</th>
                        <th className="py-2 px-2">P(Conv)</th>
                        <th className="py-2 px-2">Scarcity Pen.</th>
                        <th className="py-2 px-2">Status</th>
                        <th className="py-2 px-2">Reason / Note</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {traceData.candidates_evaluated.map((c, i) => (
                        <tr key={i} className={c.candidate_id === traceData.chosen_action?.candidate_id ? 'bg-teal-950/30' : ''}>
                          <td className="py-2 px-2 text-slate-200 font-bold">{c.action_type}</td>
                          <td className="py-2 px-2">${c.reference_price.toFixed(2)}</td>
                          <td className="py-2 px-2 text-teal-300">${c.offered_price.toFixed(2)}</td>
                          <td className="py-2 px-2">{(c.gross_margin_pct * 100).toFixed(1)}%</td>
                          <td className="py-2 px-2">{(c.expected_conversion * 100).toFixed(1)}%</td>
                          <td className="py-2 px-2 text-amber-300">${c.scarcity_penalty.toFixed(2)}</td>
                          <td className="py-2 px-2">
                            {c.candidate_id === traceData.chosen_action?.candidate_id ? (
                              <span className="text-emerald-400 font-sans font-bold">★ CHOSEN</span>
                            ) : c.margin_floor_passed ? (
                              <span className="text-slate-400">Suboptimal</span>
                            ) : (
                              <span className="text-rose-400 font-bold">REJECTED</span>
                            )}
                          </td>
                          <td className="py-2 px-2 font-sans text-slate-400 text-[11px]">
                            {c.rejection_reason || 'Constraint passed; optimal utility'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Redacted Shopper View */}
              <div className="pt-3 border-t border-slate-800">
                <span className="text-xs text-slate-400 block mb-1">
                  Redacted Consumer Fair Deal Passport Representation (Zero COGS or Shadow Costs Disclosed):
                </span>
                <pre className="p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs font-mono text-slate-300 overflow-x-auto">
                  {JSON.stringify(traceData.redacted_shopper_view, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
