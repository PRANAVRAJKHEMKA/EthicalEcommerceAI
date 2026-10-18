import { useState, useEffect } from 'react';
import {
  Store,
  TrendingUp,
  DollarSign,
  UploadCloud,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Info,
  ShieldCheck,
  Percent,
  Layers,
  Database,
  Trash2,
  FileText,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import {
  MultiStoreProfitResponse,
  CSVValidationResponse,
  ImportBatchRecord,
} from '../types.ts';
import {
  fetchMultiStoreProfit,
  fetchMultiStoreBatches,
  previewMultiStoreCSV,
  importMultiStoreCSV,
  seedMultiStoreDemoData,
  clearMultiStoreData,
  demoLoginUser,
} from '../api.ts';

export function MultiStoreProfitIntelligence() {
  const [activeTab, setActiveTab] = useState<'storefronts' | 'channels' | 'categories' | 'ingestion' | 'batches'>('storefronts');
  const [profitData, setProfitData] = useState<MultiStoreProfitResponse | null>(null);
  const [batches, setBatches] = useState<ImportBatchRecord[]>([]);
  const [selectedCurrency, setSelectedCurrency] = useState<string>('USD');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Ingestion form state
  const [importType, setImportType] = useState<'orders' | 'traffic'>('orders');
  const [csvContent, setCsvContent] = useState<string>('');
  const [filename, setFilename] = useState<string>('orders.csv');
  const [storefrontOverride, setStorefrontOverride] = useState<string>('');
  const [validating, setValidating] = useState<boolean>(false);
  const [validationResult, setValidationResult] = useState<CSVValidationResponse | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [importing, setImporting] = useState<boolean>(false);
  const [seedingDemo, setSeedingDemo] = useState<boolean>(false);
  const [clearing, setClearing] = useState<boolean>(false);
  const [nonConfidentialAffirmed, setNonConfidentialAffirmed] = useState<boolean>(false);

  // Load metrics from backend
  const loadData = async (curr?: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchMultiStoreProfit(undefined, curr || selectedCurrency);
      setProfitData(data);
      if (data.selected_currency) {
        setSelectedCurrency(data.selected_currency);
      }
      const bList = await fetchMultiStoreBatches(20);
      setBatches(bList);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load multi-store data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCurrencyChange = (curr: string) => {
    setSelectedCurrency(curr);
    loadData(curr);
  };

  // Seed demo data handler
  const handleSeedDemo = async () => {
    try {
      setSeedingDemo(true);
      setError(null);
      const res = await seedMultiStoreDemoData();
      setSuccessMessage(res.message);
      await loadData();
      setTimeout(() => setSuccessMessage(null), 6000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to seed multi-store demo data');
    } finally {
      setSeedingDemo(false);
    }
  };

  // Clear data handler
  const handleClearData = async () => {
    if (!window.confirm('Are you sure you want to clear all imported multi-store data? This action cannot be undone.')) {
      return;
    }
    try {
      setClearing(true);
      setError(null);
      const res = await clearMultiStoreData();
      setSuccessMessage(res.message);
      await loadData();
      setTimeout(() => setSuccessMessage(null), 6000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear multi-store data');
    } finally {
      setClearing(false);
    }
  };

  // File upload handler
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFilename(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      setCsvContent(text);
      setValidationResult(null);
      setValidationError(null);
    };
    reader.readAsText(file);
  };

  // Validate CSV
  const handleValidate = async () => {
    if (!csvContent.trim()) {
      setValidationError('Please select or paste CSV content before validating.');
      return;
    }
    try {
      setValidating(true);
      setValidationError(null);
      const res = await previewMultiStoreCSV({
        import_type: importType,
        csv_content: csvContent,
        filename,
        storefront_override: storefrontOverride.trim() || undefined,
      });
      setValidationResult(res);
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : 'CSV validation failed');
    } finally {
      setValidating(false);
    }
  };

  // Confirm Import
  const handleConfirmImport = async () => {
    if (!csvContent.trim()) return;
    try {
      setImporting(true);
      setError(null);
      const res = await importMultiStoreCSV({
        import_type: importType,
        csv_content: csvContent,
        filename,
        storefront_override: storefrontOverride.trim() || undefined,
      });
      setSuccessMessage(res.message);
      setCsvContent('');
      setValidationResult(null);
      setActiveTab('storefronts');
      await loadData();
      setTimeout(() => setSuccessMessage(null), 6000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  // Helper formatting functions
  const fmtCurrency = (val: number, curr: string = selectedCurrency) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: curr,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(val);
  };

  const fmtPercent = (val: number) => `${val.toFixed(1)}%`;

  const getMarginBadgeClass = (pct: number) => {
    if (pct >= 40.0) return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    if (pct >= 25.0) return 'bg-amber-100 text-amber-800 border-amber-200';
    return 'bg-red-100 text-red-800 border-red-200';
  };

  const totals = profitData?.aggregated_totals;
  const storefronts = profitData?.storefronts || [];
  const channels = profitData?.channels || [];
  const categories = profitData?.category_profitability || [];
  const diagnostics = profitData?.discounting_diagnostics || [];

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden space-y-0">
      {/* Header Banner */}
      <div className="p-6 sm:p-8 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center space-x-2 bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full text-xs font-semibold border border-indigo-400/30">
              <Store className="w-3.5 h-3.5" />
              <span>Step 5.20 · Multi-Store Profit Intelligence</span>
            </div>
            <div className="inline-flex items-center space-x-1.5 bg-amber-500/20 text-amber-300 px-2.5 py-1 rounded-full text-[11px] font-semibold border border-amber-400/30">
              <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
              <span>Shared Demo Sandbox · Synthetic Data Only</span>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {profitData && profitData.currencies_available.length > 1 && (
              <div className="flex items-center space-x-1 bg-white/10 px-2.5 py-1 rounded-lg text-xs">
                <span className="text-slate-400">Currency:</span>
                <select
                  value={selectedCurrency}
                  onChange={(e) => handleCurrencyChange(e.target.value)}
                  className="bg-transparent text-white font-bold focus:outline-none"
                >
                  {profitData.currencies_available.map((c) => (
                    <option key={c} value={c} className="bg-slate-900 text-white">
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <button
              onClick={() => loadData()}
              disabled={loading}
              className="p-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors cursor-pointer"
              title="Refresh Analytics"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        <div className="max-w-3xl space-y-2">
          <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight">
            Multi-Storefront Profit Intelligence & Comparative Auditing
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            Ingest order lines and traffic event datasets across all owned commerce properties.
            Authoritatively compares net gross profit, conversion rates, markdown subsidies,
            and observational channel attribution without leaking PII.
          </p>
        </div>

        {/* Global Toolbar */}
        <div className="pt-2 flex flex-wrap items-center justify-between gap-3 bg-white/5 p-3 sm:p-4 rounded-xl border border-white/10">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-400">Stores active:</span>
            <span className="font-mono font-bold text-white bg-slate-800 px-2 py-0.5 rounded">
              {profitData?.total_storefronts ?? 0}
            </span>
            <span className="text-slate-400 ml-2">Total batches:</span>
            <span className="font-mono font-bold text-white bg-slate-800 px-2 py-0.5 rounded">
              {profitData?.total_batches_imported ?? 0}
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleSeedDemo}
              disabled={seedingDemo || loading}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-700/50 text-white text-xs font-semibold rounded-lg shadow-sm transition-all cursor-pointer"
            >
              <Database className="w-3.5 h-3.5" />
              <span>{seedingDemo ? 'Seeding Fixtures...' : 'Seed Demo Fixture (3 Stores)'}</span>
            </button>

            <button
              onClick={() => setActiveTab('ingestion')}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold rounded-lg border border-white/20 transition-all cursor-pointer"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>Import CSV</span>
            </button>

            {(storefronts.length > 0 || batches.length > 0) && (
              <button
                onClick={handleClearData}
                disabled={clearing}
                className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer"
                title="Clear all imported data"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Feedback Alerts */}
        {error && (
          <div className="p-3 bg-red-900/60 border border-red-700 rounded-lg text-xs text-red-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{error}</span>
            </div>
            {(error.includes('Merchant authentication required') || error.includes('Customer session tokens') || error.includes('401') || error.includes('403')) && (
              <button
                onClick={async () => {
                  try {
                    await demoLoginUser('demo_merchant');
                    setError(null);
                    setSuccessMessage('Successfully authenticated as FairCart Merchant (demo_merchant).');
                    await loadData();
                    setTimeout(() => setSuccessMessage(null), 5000);
                  } catch (e: any) {
                    setError(e.message || 'Failed to authenticate demo merchant');
                  }
                }}
                className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-medium text-[11px] transition-colors cursor-pointer"
              >
                Sign in as Demo Merchant
              </button>
            )}
          </div>
        )}
        {successMessage && (
          <div className="p-3 bg-emerald-900/60 border border-emerald-700 rounded-lg text-xs text-emerald-200 flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}
      </div>

      {/* Aggregated KPI Summary Row */}
      {totals && totals.total_storefronts > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-slate-200 border-b border-slate-200 text-slate-900">
          <div className="bg-white p-5 space-y-1">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Combined Net Revenue</span>
              <DollarSign className="w-3.5 h-3.5 text-indigo-600" />
            </div>
            <div className="text-xl sm:text-2xl font-black text-slate-900">
              {fmtCurrency(totals.net_revenue, totals.currency)}
            </div>
            <div className="text-[11px] text-slate-500">
              Gross: {fmtCurrency(totals.gross_revenue, totals.currency)}
            </div>
          </div>

          <div className="bg-white p-5 space-y-1">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Gross Profit & Margin</span>
              <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div className="text-xl sm:text-2xl font-black text-emerald-700">
              {fmtCurrency(totals.gross_profit, totals.currency)}
            </div>
            <div className="text-[11px] font-semibold text-emerald-700">
              {fmtPercent(totals.gross_margin_pct)} Combined Margin
            </div>
          </div>

          <div className="bg-white p-5 space-y-1">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Orders & Conversion</span>
              <Percent className="w-3.5 h-3.5 text-indigo-600" />
            </div>
            <div className="text-xl sm:text-2xl font-black text-slate-900">
              {totals.total_distinct_orders}{' '}
              <span className="text-xs font-normal text-slate-500">orders</span>
            </div>
            <div className="text-[11px] text-slate-500">
              {fmtPercent(totals.overall_conversion_rate * 100)} Conv · AOV{' '}
              {fmtCurrency(totals.overall_aov, totals.currency)}
            </div>
          </div>

          <div className="bg-white p-5 space-y-1">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Discounts & Refunds</span>
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            </div>
            <div className="text-xl sm:text-2xl font-black text-slate-900">
              {fmtCurrency(totals.discount_amount + totals.refund_amount, totals.currency)}
            </div>
            <div className="text-[11px] text-slate-500">
              Discounts {fmtCurrency(totals.discount_amount, totals.currency)} · Refunds{' '}
              {fmtCurrency(totals.refund_amount, totals.currency)}
            </div>
          </div>
        </div>
      )}

      {/* Diagnostic Callout Banners */}
      {diagnostics.length > 0 && (
        <div className="p-4 sm:p-6 bg-slate-50 border-b border-slate-200 space-y-2">
          <div className="text-xs font-bold text-slate-700 flex items-center space-x-1.5 uppercase tracking-wider">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>Multi-Store Diagnostic Warnings ({diagnostics.length})</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            {diagnostics.map((d, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg border text-xs space-y-1 ${
                  d.severity === 'alert'
                    ? 'bg-red-50 border-red-200 text-red-900'
                    : d.severity === 'warning'
                    ? 'bg-amber-50 border-amber-200 text-amber-900'
                    : 'bg-blue-50 border-blue-200 text-blue-900'
                }`}
              >
                <div className="flex items-center justify-between font-bold">
                  <span>{d.storefront_name} ({d.storefront_id})</span>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-white/80 border">
                    {d.metric}
                  </span>
                </div>
                <p className="text-[11px] leading-relaxed opacity-90">{d.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="px-6 sm:px-8 border-b border-slate-200 bg-white flex items-center space-x-6 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('storefronts')}
          className={`py-4 border-b-2 transition-all cursor-pointer flex items-center space-x-1.5 ${
            activeTab === 'storefronts'
              ? 'border-indigo-600 text-indigo-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Store className="w-3.5 h-3.5" />
          <span>Storefront Comparison ({storefronts.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('channels')}
          className={`py-4 border-b-2 transition-all cursor-pointer flex items-center space-x-1.5 ${
            activeTab === 'channels'
              ? 'border-indigo-600 text-indigo-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Channel Attribution ({channels.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('categories')}
          className={`py-4 border-b-2 transition-all cursor-pointer flex items-center space-x-1.5 ${
            activeTab === 'categories'
              ? 'border-indigo-600 text-indigo-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Category Margins ({categories.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('ingestion')}
          className={`py-4 border-b-2 transition-all cursor-pointer flex items-center space-x-1.5 ${
            activeTab === 'ingestion'
              ? 'border-indigo-600 text-indigo-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <UploadCloud className="w-3.5 h-3.5" />
          <span>CSV Ingestion Hub</span>
        </button>

        <button
          onClick={() => setActiveTab('batches')}
          className={`py-4 border-b-2 transition-all cursor-pointer flex items-center space-x-1.5 ${
            activeTab === 'batches'
              ? 'border-indigo-600 text-indigo-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Import Audit Log ({batches.length})</span>
        </button>
      </div>

      {/* Tab 1: Storefront Comparison */}
      {activeTab === 'storefronts' && (
        <div className="p-6 sm:p-8 space-y-6">
          {storefronts.length === 0 ? (
            <div className="text-center py-12 space-y-4">
              <Store className="w-12 h-12 text-slate-300 mx-auto" />
              <div className="space-y-1">
                <h3 className="text-base font-bold text-slate-800">No Storefronts Imported Yet</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  Click &ldquo;Seed Demo Fixture&rdquo; above to immediately load 3 benchmark stores (Tech, Living, Pantry)
                  or use the CSV Ingestion Hub to upload your own order lines.
                </p>
              </div>
              <button
                onClick={handleSeedDemo}
                disabled={seedingDemo}
                className="inline-flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm"
              >
                <Database className="w-3.5 h-3.5" />
                <span>Seed 3-Store Demo Dataset</span>
              </button>
            </div>
          ) : (
            <>
              {/* Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {storefronts.map((s) => (
                  <div
                    key={s.storefront_id}
                    className="p-5 rounded-xl border border-slate-200 bg-white shadow-xs space-y-4 hover:border-indigo-300 transition-all"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-slate-900">{s.storefront_name}</h4>
                        <span className="text-[10px] font-mono text-slate-400">{s.storefront_id}</span>
                      </div>
                      <span
                        className={`text-xs font-extrabold px-2 py-0.5 rounded-full border ${getMarginBadgeClass(
                          s.gross_margin_pct
                        )}`}
                      >
                        {fmtPercent(s.gross_margin_pct)} Margin
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-xs pt-1">
                      <div>
                        <span className="text-slate-400 block text-[10px]">Net Revenue</span>
                        <span className="font-extrabold text-slate-800">
                          {fmtCurrency(s.net_revenue, s.currency)}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Gross Profit</span>
                        <span className="font-extrabold text-emerald-700">
                          {fmtCurrency(s.gross_profit, s.currency)}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Distinct Orders</span>
                        <span className="font-extrabold text-slate-800">
                          {s.distinct_orders}{' '}
                          <span className="text-[10px] font-normal text-slate-400">
                            ({s.units_sold} units)
                          </span>
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Conversion Rate</span>
                        <span className="font-extrabold text-indigo-700">
                          {fmtPercent(s.conversion_rate * 100)}
                        </span>
                      </div>
                    </div>

                    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100 text-[11px] space-y-1">
                      <div className="flex justify-between text-slate-600">
                        <span>Discount Subsidies:</span>
                        <span className="font-medium text-slate-800">
                          {fmtCurrency(s.discount_amount, s.currency)} ({fmtPercent(s.discount_share_pct)})
                        </span>
                      </div>
                      <div className="flex justify-between text-slate-600">
                        <span>Customer Refunds:</span>
                        <span className="font-medium text-slate-800">
                          {fmtCurrency(s.refund_amount, s.currency)} ({fmtPercent(s.refund_rate_pct)})
                        </span>
                      </div>
                    </div>

                    {s.data_quality_flags.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {s.data_quality_flags.map((flag, idx) => (
                          <span
                            key={idx}
                            className="bg-amber-50 text-amber-800 border border-amber-200 text-[10px] px-2 py-0.5 rounded font-medium flex items-center space-x-1"
                          >
                            <Info className="w-2.5 h-2.5 text-amber-600" />
                            <span>{flag}</span>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Comprehensive Storefront Comparison Table */}
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
                    <tr>
                      <th className="p-3">Storefront</th>
                      <th className="p-3">Sessions</th>
                      <th className="p-3">Orders</th>
                      <th className="p-3">Conv. Rate</th>
                      <th className="p-3">Gross Sales</th>
                      <th className="p-3">Discounts</th>
                      <th className="p-3">Refunds</th>
                      <th className="p-3">Net Revenue</th>
                      <th className="p-3">COGS</th>
                      <th className="p-3">Gross Profit</th>
                      <th className="p-3">Margin %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {storefronts.map((s) => (
                      <tr key={s.storefront_id} className="hover:bg-slate-50/80">
                        <td className="p-3 font-semibold text-slate-900">
                          <div>{s.storefront_name}</div>
                          <div className="text-[10px] text-slate-400 font-mono">{s.storefront_id}</div>
                        </td>
                        <td className="p-3 font-mono text-slate-700">{s.unique_sessions}</td>
                        <td className="p-3 font-mono text-slate-900 font-bold">{s.distinct_orders}</td>
                        <td className="p-3 font-mono text-indigo-700 font-semibold">
                          {fmtPercent(s.conversion_rate * 100)}
                        </td>
                        <td className="p-3 font-mono text-slate-500">
                          {fmtCurrency(s.gross_revenue, s.currency)}
                        </td>
                        <td className="p-3 font-mono text-amber-700">
                          -{fmtCurrency(s.discount_amount, s.currency)}
                        </td>
                        <td className="p-3 font-mono text-red-600">
                          -{fmtCurrency(s.refund_amount, s.currency)}
                        </td>
                        <td className="p-3 font-mono font-bold text-slate-900">
                          {fmtCurrency(s.net_revenue, s.currency)}
                        </td>
                        <td className="p-3 font-mono text-slate-500">{fmtCurrency(s.cogs, s.currency)}</td>
                        <td className="p-3 font-mono font-bold text-emerald-700">
                          {fmtCurrency(s.gross_profit, s.currency)}
                        </td>
                        <td className="p-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getMarginBadgeClass(
                              s.gross_margin_pct
                            )}`}
                          >
                            {fmtPercent(s.gross_margin_pct)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Tab 2: Acquisition Channel Attribution */}
      {activeTab === 'channels' && (
        <div className="p-6 sm:p-8 space-y-6">
          <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl flex items-start space-x-3 text-xs text-indigo-900">
            <Info className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold">Observational Channel Attribution Notice</span>
              <p className="text-[11px] text-indigo-800 leading-relaxed">
                Attributed revenue reflects touchpoint association recorded during traffic ingestion.
                Association does <strong>not</strong> prove incremental causation. To evaluate whether promotions
                caused transactions that would not have occurred otherwise, inspect the offline Uplift Evaluation Laboratory.
              </p>
            </div>
          </div>

          {channels.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs">
              No acquisition channel events recorded. Import traffic data or seed the demo fixture.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
                  <tr>
                    <th className="p-3">Acquisition Channel</th>
                    <th className="p-3">Sessions</th>
                    <th className="p-3">Attributed Orders</th>
                    <th className="p-3">Conv. Rate</th>
                    <th className="p-3">Net Revenue</th>
                    <th className="p-3">Gross Profit</th>
                    <th className="p-3">Margin %</th>
                    <th className="p-3">AOV</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {channels.map((ch) => (
                    <tr key={ch.channel} className="hover:bg-slate-50/80">
                      <td className="p-3 font-semibold text-slate-900">
                        <div>{ch.channel_label}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{ch.channel}</div>
                      </td>
                      <td className="p-3 font-mono text-slate-700">{ch.unique_sessions}</td>
                      <td className="p-3 font-mono font-bold text-slate-900">{ch.attributed_orders}</td>
                      <td className="p-3 font-mono font-semibold text-indigo-700">
                        {fmtPercent(ch.conversion_rate * 100)}
                      </td>
                      <td className="p-3 font-mono font-bold text-slate-900">
                        {fmtCurrency(ch.net_revenue, ch.currency)}
                      </td>
                      <td className="p-3 font-mono font-bold text-emerald-700">
                        {fmtCurrency(ch.gross_profit, ch.currency)}
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getMarginBadgeClass(
                            ch.gross_margin_pct
                          )}`}
                        >
                          {fmtPercent(ch.gross_margin_pct)}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-slate-700">{fmtCurrency(ch.aov, ch.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Curated Catalogue Category Profitability */}
      {activeTab === 'categories' && (
        <div className="p-6 sm:p-8 space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
              <Database className="w-4 h-4 text-indigo-600" />
              <span>Category Margin Performance across Imported Stores</span>
            </h3>
            <span className="text-xs text-slate-500 font-mono">
              Active Currency: {selectedCurrency}
            </span>
          </div>

          {categories.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs">
              No category sales lines recorded for the selected currency.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
                  <tr>
                    <th className="p-3">Category</th>
                    <th className="p-3">Units Sold</th>
                    <th className="p-3">Gross Sales</th>
                    <th className="p-3">Discounts</th>
                    <th className="p-3">Net Revenue</th>
                    <th className="p-3">COGS</th>
                    <th className="p-3">Gross Profit</th>
                    <th className="p-3">Gross Margin %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {categories.map((c) => (
                    <tr key={c.category} className="hover:bg-slate-50/80">
                      <td className="p-3 font-semibold text-slate-900 capitalize">{c.category}</td>
                      <td className="p-3 font-mono text-slate-700">{c.units_sold}</td>
                      <td className="p-3 font-mono text-slate-500">{fmtCurrency(c.gross_revenue)}</td>
                      <td className="p-3 font-mono text-amber-700">-{fmtCurrency(c.discount_amount)}</td>
                      <td className="p-3 font-mono font-bold text-slate-900">{fmtCurrency(c.net_revenue)}</td>
                      <td className="p-3 font-mono text-slate-500">{fmtCurrency(c.cogs)}</td>
                      <td className="p-3 font-mono font-bold text-emerald-700">
                        {fmtCurrency(c.gross_profit)}
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getMarginBadgeClass(
                            c.gross_margin_pct
                          )}`}
                        >
                          {fmtPercent(c.gross_margin_pct)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: CSV Ingestion Hub */}
      {activeTab === 'ingestion' && (
        <div className="p-6 sm:p-8 space-y-6">
          <div className="max-w-2xl space-y-1">
            <h3 className="text-base font-bold text-slate-900">CSV Data Ingestion Hub</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Upload storefront sales order lines or traffic funnel events. The engine performs strict pre-flight
              validation, verifies non-negative financial values, guarantees distinct order grouping, and strictly
              rejects PII headers.
            </p>
          </div>

          {/* Configuration Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Dataset Type</label>
              <select
                value={importType}
                onChange={(e) => {
                  setImportType(e.target.value as 'orders' | 'traffic');
                  setValidationResult(null);
                }}
                className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="orders">Storefront Order Lines (Sales)</option>
                <option value="traffic">Traffic & Funnel Events</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Storefront ID (Optional Override)
              </label>
              <input
                type="text"
                placeholder="e.g. store-gamma-pantry"
                value={storefrontOverride}
                onChange={(e) => setStorefrontOverride(e.target.value)}
                className="w-full text-xs border border-slate-300 rounded-lg p-2 bg-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Upload File (.csv)</label>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={handleFileUpload}
                className="w-full text-xs text-slate-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer"
              />
            </div>
          </div>

          {/* Raw CSV Text Area */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-700">CSV Content</label>
              <span className="text-[11px] text-slate-400 font-mono">
                {csvContent.length} bytes · {csvContent.split('\n').filter(Boolean).length} rows
              </span>
            </div>
            <textarea
              rows={8}
              value={csvContent}
              onChange={(e) => {
                setCsvContent(e.target.value);
                setValidationResult(null);
                setValidationError(null);
              }}
              placeholder={
                importType === 'orders'
                  ? 'storefront_id,order_id,order_timestamp,product_id,quantity,gross_line_revenue,discount_amount,refund_amount,cogs_amount,attribution_channel,currency\nstore-alpha-tech,ord-101,2026-10-15T10:00:00Z,item-001,1,149.00,0.00,0.00,65.00,organic_search,USD'
                  : 'event_id,event_timestamp,session_id,storefront_id,event_type,acquisition_channel,product_id,order_id\nevt-101,2026-10-15T09:50:00Z,sess-101,store-alpha-tech,product_view,organic_search,item-001,'
              }
              className="w-full p-3 font-mono text-xs border border-slate-300 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Format Reference Pill */}
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-600 flex items-start space-x-2">
            <HelpCircle className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-semibold text-slate-700">Expected Column Headers:</span>
              <p className="font-mono text-[10px] text-slate-500">
                {importType === 'orders'
                  ? 'Required: order_id, product_id, gross_line_revenue | Optional: storefront_id, order_timestamp, quantity, discount_amount, refund_amount, cogs_amount, attribution_channel, currency'
                  : 'Required: event_id, session_id, event_type | Optional: storefront_id, event_timestamp, acquisition_channel, product_id, order_id'}
              </p>
            </div>
          </div>

          {/* Demonstration Sandbox Notice & Privacy Guarantee */}
          <div className="p-3 bg-amber-50/80 border border-amber-200/90 rounded-lg text-[11px] text-amber-900 flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold text-amber-950">Demonstration Sandbox & Privacy Guarantee:</span>
              <p className="text-[11px] text-amber-800 leading-relaxed">
                You are operating in the shared FairCart Demonstration Merchant environment. All data imported here is scoped to the shared demo tenant (<code>usr_demo_merchant</code>) and is visible across the shared demo environment; <strong>it is not private to an individual visitor</strong>. <strong>Do not upload confidential, proprietary, or personal business datasets.</strong> Synthetic or anonymized CSVs only. Zero-PII policy is strictly enforced: files containing customer names, emails, phones, or credit cards are automatically rejected.
              </p>
              <label className="flex items-start space-x-2 text-xs text-amber-950 cursor-pointer pt-1 font-medium">
                <input
                  type="checkbox"
                  checked={nonConfidentialAffirmed}
                  onChange={(e) => setNonConfidentialAffirmed(e.target.checked)}
                  className="mt-0.5 rounded border-amber-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span>I affirm this dataset contains synthetic or non-confidential demonstration data only, and understand it is visible in the shared demo sandbox.</span>
              </label>
            </div>
          </div>

          {/* Validation Feedback & Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              onClick={handleValidate}
              disabled={validating || !csvContent.trim()}
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-lg shadow-sm transition-all cursor-pointer"
            >
              {validating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <FileSpreadsheet className="w-3.5 h-3.5" />}
              <span>{validating ? 'Validating Schema...' : 'Validate CSV Preview'}</span>
            </button>

            {validationResult?.valid && (
              <button
                onClick={handleConfirmImport}
                disabled={importing || !nonConfidentialAffirmed}
                className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300 text-white text-xs font-semibold rounded-lg shadow-sm transition-all cursor-pointer"
                title={!nonConfidentialAffirmed ? 'Please affirm that this is non-confidential demonstration data' : undefined}
              >
                {importing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                <span>
                  {importing
                    ? 'Persisting Records...'
                    : `Confirm & Ingest ${validationResult.accepted_rows} Records`}
                </span>
              </button>
            )}
          </div>

          {validationError && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-lg flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          {/* Validation Report Card */}
          {validationResult && (
            <div
              className={`p-5 rounded-xl border text-xs space-y-4 ${
                validationResult.valid ? 'bg-emerald-50/60 border-emerald-200' : 'bg-red-50/60 border-red-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold flex items-center space-x-2">
                  {validationResult.valid ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span className="text-emerald-900">Pre-Flight Validation Succeeded</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-4 h-4 text-red-600" />
                      <span className="text-red-900">Pre-Flight Validation Failed</span>
                    </>
                  )}
                </span>
                <span className="font-mono text-[11px] text-slate-500">
                  {validationResult.accepted_rows} accepted · {validationResult.rejected_rows} rejected
                </span>
              </div>

              {/* Summary Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-white p-3 rounded-lg border border-slate-200/80">
                <div>
                  <span className="text-[10px] text-slate-400 block">Detected Stores</span>
                  <span className="font-mono font-bold text-slate-800">
                    {validationResult.detected_storefronts.join(', ') || 'default'}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Currencies</span>
                  <span className="font-mono font-bold text-slate-800">
                    {validationResult.detected_currencies.join(', ') || 'USD'}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Est. Net Revenue</span>
                  <span className="font-mono font-bold text-slate-800">
                    ${validationResult.summary_metrics?.estimated_net_revenue ?? '—'}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Est. Margin</span>
                  <span className="font-mono font-bold text-emerald-700">
                    {validationResult.summary_metrics?.estimated_gross_margin_pct != null
                      ? `${validationResult.summary_metrics.estimated_gross_margin_pct}%`
                      : '—'}
                  </span>
                </div>
              </div>

              {/* Row Errors */}
              {validationResult.errors.length > 0 && (
                <div className="space-y-1">
                  <span className="font-bold text-red-900 block">Validation Issues:</span>
                  <div className="max-h-40 overflow-y-auto space-y-1 bg-white p-2.5 rounded-lg border border-red-200">
                    {validationResult.errors.map((err, idx) => (
                      <div key={idx} className="text-[11px] text-red-700 font-mono">
                        Row {err.row} [{err.column}]: {err.message}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Import Audit Batches Log */}
      {activeTab === 'batches' && (
        <div className="p-6 sm:p-8 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
              <FileText className="w-4 h-4 text-indigo-600" />
              <span>Multi-Store Ingestion Audit Trail</span>
            </h3>
            <span className="text-xs text-slate-400 font-mono">Immutable ingestion logs</span>
          </div>

          {batches.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs">
              No import batches recorded. Upload a CSV file or seed demo data.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
                  <tr>
                    <th className="p-3">Batch ID</th>
                    <th className="p-3">Storefront</th>
                    <th className="p-3">Type</th>
                    <th className="p-3">Filename</th>
                    <th className="p-3">Accepted</th>
                    <th className="p-3">Rejected</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Imported At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {batches.map((b) => (
                    <tr key={b.id} className="hover:bg-slate-50/80">
                      <td className="p-3 font-mono text-indigo-700 font-semibold">{b.id}</td>
                      <td className="p-3 font-semibold text-slate-900">{b.storefront_id}</td>
                      <td className="p-3 font-mono uppercase text-slate-600">{b.import_type}</td>
                      <td className="p-3 text-slate-600 font-mono text-[11px]">{b.filename}</td>
                      <td className="p-3 font-mono text-emerald-700 font-bold">{b.accepted_rows}</td>
                      <td className="p-3 font-mono text-red-600">{b.rejected_rows}</td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            b.status === 'completed' || b.status === 'success'
                              ? 'bg-emerald-100 text-emerald-800'
                              : b.status === 'partial'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {b.status}
                        </span>
                      </td>
                      <td className="p-3 text-slate-400 font-mono text-[10px]">
                        {new Date(b.imported_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Methodology & Safety Footer */}
      <div className="p-4 bg-slate-50 border-t border-slate-200 text-[11px] text-slate-500 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>
            {profitData?.methodology_disclaimer ||
              'Multi-Store Profit Intelligence strictly isolates currencies and enforces integer-cent financial calculations.'}
          </span>
        </div>
        <span className="font-mono text-slate-400">Step 5.20 Verified</span>
      </div>
    </div>
  );
}
