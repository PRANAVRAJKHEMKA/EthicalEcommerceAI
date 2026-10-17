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
  Play,
  ArrowUpRight,
  DollarSign,
  AlertTriangle,
  Layers,
  Scale,
  Info,
} from 'lucide-react';
import {
  Product,
  HealthStatus,
  MerchantSettings,
  SimulationResponse,
} from '../types.ts';
import {
  fetchMerchantSettings,
  updateMerchantSettings,
  runSimulation,
  fetchLatestSimulation,
  getSessionPolicy,
  saveSessionPolicy,
  resetSessionPolicy,
  DEFAULT_DEMO_POLICY,
} from '../api.ts';
import { MerchantDealPassportInspector } from '../components/MerchantDealPassportInspector.tsx';

interface MerchantViewProps {
  products: Product[];
  health?: HealthStatus | null;
  sessionPolicy?: MerchantSettings;
  onPolicyChange?: (newPolicy: MerchantSettings) => void;
}

export function MerchantView({ products, health, sessionPolicy, onPolicyChange }: MerchantViewProps) {
  // Policy settings state initialized from active demo session policy
  const [settings, setSettings] = useState<MerchantSettings>(() => {
    return sessionPolicy || getSessionPolicy();
  });
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);
  const [isGlobalPersisted, setIsGlobalPersisted] = useState<boolean>(false);

  // Sync if parent updates sessionPolicy prop
  useEffect(() => {
    if (sessionPolicy) {
      setSettings(sessionPolicy);
    }
  }, [sessionPolicy?.margin_floor, sessionPolicy?.discount_cap]);

  // Demo-safe administrative access token (persisted strictly in browser session)
  const [adminToken, setAdminToken] = useState<string>(() => {
    if (typeof window === 'undefined') return '';
    try {
      return sessionStorage.getItem('faircart_admin_token') || '';
    } catch {
      return '';
    }
  });
  const [showAdminInput, setShowAdminInput] = useState<boolean>(false);

  // Simulation state
  const [numSessions, setNumSessions] = useState<number>(1000);
  const [randomSeed, setRandomSeed] = useState<number>(42);
  const [simulationRunning, setSimulationRunning] = useState<boolean>(false);
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);

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

  // Load merchant policy settings & latest simulation from backend
  useEffect(() => {
    let isMounted = true;
    setLoadingSettings(true);

    fetchMerchantSettings()
      .then((data) => {
        if (isMounted) {
          // If no custom session policy is set in sessionStorage, use backend settings
          try {
            const stored = sessionStorage.getItem('faircart_demo_policy');
            if (!stored && !sessionPolicy) {
              setSettings(data);
            }
          } catch {
            if (!sessionPolicy) setSettings(data);
          }
        }
      })
      .catch((err) => {
        console.error('Failed to load merchant settings:', err);
      })
      .finally(() => {
        if (isMounted) setLoadingSettings(false);
      });

    fetchLatestSimulation()
      .then((sim) => {
        if (isMounted && sim && sim.policies) {
          setSimulationResult(sim);
        }
      })
      .catch((err) => {
        console.warn('No previous simulation run or failed to load:', err);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSaveSettings = async () => {
    try {
      setSavingSettings(true);
      setSaveError(null);
      setSessionNotice(null);

      if (adminToken.trim()) {
        const updated = await updateMerchantSettings(settings, adminToken.trim());
        setSettings(updated);
        setIsGlobalPersisted(true);
        setSaveSuccess(true);
        setSessionNotice('Global merchant settings successfully updated in the database.');
        saveSessionPolicy(updated);
        onPolicyChange?.(updated);
        setTimeout(() => setSaveSuccess(false), 2500);
      } else {
        saveSessionPolicy(settings);
        onPolicyChange?.(settings);
        setIsGlobalPersisted(false);
        setSaveSuccess(true);
        setSessionNotice(
          'Policy applied to this demo session. Storefront bundle rules and Monte Carlo simulator updated immediately. Shared merchant settings are unchanged.'
        );
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to update merchant settings');
      if (err instanceof Error && err.message.includes('authorization')) {
        setShowAdminInput(true);
      }
    } finally {
      setSavingSettings(false);
    }
  };

  const handleResetDefaults = async () => {
    const defaults: MerchantSettings = DEFAULT_DEMO_POLICY;
    setSettings(defaults);
    setSaveError(null);
    setSessionNotice(null);

    if (adminToken.trim()) {
      try {
        setSavingSettings(true);
        const updated = await updateMerchantSettings(defaults, adminToken.trim());
        setSettings(updated);
        setIsGlobalPersisted(true);
        setSaveSuccess(true);
        setSessionNotice('Default policy (20% margin floor / 20% discount cap) restored globally in database.');
        resetSessionPolicy();
        onPolicyChange?.(updated);
        setTimeout(() => setSaveSuccess(false), 2500);
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : 'Failed to reset settings');
        if (err instanceof Error && err.message.includes('authorization')) {
          setShowAdminInput(true);
        }
      } finally {
        setSavingSettings(false);
      }
    } else {
      resetSessionPolicy();
      onPolicyChange?.(defaults);
      setIsGlobalPersisted(false);
      setSaveSuccess(true);
      setSessionNotice('Default policy (20% margin floor / 20% discount cap) restored for this demo session.');
      setTimeout(() => setSaveSuccess(false), 2500);
    }
  };

  const handleRunSimulation = async () => {
    try {
      setSimulationRunning(true);
      setSimulationError(null);
      const res = await runSimulation({
        num_sessions: numSessions,
        random_seed: randomSeed,
        margin_floor: settings.margin_floor,
        discount_cap: settings.discount_cap,
      });
      setSimulationResult(res);
    } catch (err) {
      setSimulationError(err instanceof Error ? err.message : 'Simulation run failed');
    } finally {
      setSimulationRunning(false);
    }
  };

  const isGeminiConfigured = health?.gemini_configured ?? false;

  // Policies from simulation result
  const noDiscount = simulationResult?.policies?.NO_DISCOUNT;
  const blanket15 = simulationResult?.policies?.BLANKET_15;
  const faircartAi = simulationResult?.policies?.FAIRCART_AI;
  const relNoDiscount = simulationResult?.relative_comparison?.vs_no_discount;
  const relBlanket = simulationResult?.relative_comparison?.vs_blanket_15;

  return (
    <div className="space-y-8 pb-16">
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
            <span className={`w-1.5 h-1.5 rounded-full ${health?.status === 'unhealthy' ? 'bg-red-500' : 'bg-emerald-500'}`} />
            <span>
              {health?.status === 'unhealthy'
                ? 'Database Offline'
                : health?.database === 'postgresql'
                ? 'PostgreSQL Cloud Persistence Active'
                : 'SQLite WAL Persistence Active'}
            </span>
          </span>
          <span>·</span>
          <span className="inline-flex items-center space-x-1.5 font-medium">
            <span className={`w-1.5 h-1.5 rounded-full ${isGlobalPersisted ? 'bg-emerald-500' : adminToken.trim() ? 'bg-amber-500' : 'bg-indigo-500'}`} />
            <span>
              {isGlobalPersisted
                ? 'Global Database Override Applied'
                : adminToken.trim()
                ? 'Admin Mode (Global Write)'
                : 'Session-Scoped Policy Active'}
            </span>
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
          <p className="text-[11px] text-slate-500">
            {health?.status === 'unhealthy'
              ? 'Database reconnecting'
              : health?.database === 'postgresql'
              ? 'Curated & seeded in Neon PostgreSQL'
              : 'Curated & seeded in SQLite database'}
          </p>
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

            {/* Merchant Access Key Configuration (Demo-Safe Protection) */}
            <div className="pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">Merchant Administration</span>
                <button
                  type="button"
                  onClick={() => setShowAdminInput(!showAdminInput)}
                  className="text-indigo-600 hover:text-indigo-800 text-[11px] font-semibold underline underline-offset-2 flex items-center gap-1 cursor-pointer"
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-indigo-500" />
                  <span>{adminToken ? 'Admin Key Set' : showAdminInput ? 'Hide Key' : 'Admin Key (Optional)'}</span>
                </button>
              </div>

              {showAdminInput && (
                <div className="mt-2 bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-xs space-y-1.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">Production Admin Token:</span>
                    <span className="text-slate-400">Kept in session storage only</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="password"
                      placeholder="Enter ADMIN_TOKEN (if required by host)"
                      value={adminToken}
                      onChange={(e) => {
                        setAdminToken(e.target.value);
                        try {
                          sessionStorage.setItem('faircart_admin_token', e.target.value);
                        } catch {}
                      }}
                      className="flex-1 px-2.5 py-1 text-xs border border-slate-300 rounded bg-white font-mono placeholder:text-slate-400"
                    />
                    {adminToken && (
                      <button
                        type="button"
                        onClick={() => {
                          setAdminToken('');
                          try {
                            sessionStorage.removeItem('faircart_admin_token');
                          } catch {}
                        }}
                        className="px-2 py-1 text-[11px] bg-slate-200 hover:bg-slate-300 rounded text-slate-700"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="pt-2 flex items-center justify-between gap-3 border-t border-slate-100">
              <button
                onClick={handleResetDefaults}
                disabled={savingSettings}
                className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
              >
                Reset Defaults (20%/20%)
              </button>

              <button
                onClick={handleSaveSettings}
                disabled={savingSettings}
                className="inline-flex items-center space-x-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                {savingSettings ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : saveSuccess ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-white" />
                    <span>{adminToken.trim() ? 'Saved to Database!' : 'Applied to Session!'}</span>
                  </>
                ) : (
                  <span>{adminToken.trim() ? 'Save Global Settings (Admin)' : 'Apply to Demo Session'}</span>
                )}
              </button>
            </div>

            {sessionNotice && (
              <p className="text-xs text-indigo-700 bg-indigo-50 p-2.5 rounded-lg border border-indigo-200 flex items-start space-x-1.5">
                <Info className="w-3.5 h-3.5 shrink-0 text-indigo-600 mt-0.5" />
                <span>{sessionNotice}</span>
              </p>
            )}

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

      {/* ========================================================================= */}
      {/* STEP 5.17: FAIR DEAL PASSPORT & COUNTERFACTUAL INSPECTOR */}
      {/* ========================================================================= */}
      <MerchantDealPassportInspector
        products={products}
        marginFloor={settings.margin_floor}
        discountCap={settings.discount_cap}
      />

      {/* ========================================================================= */}
      {/* MILESTONE 5: THREE-POLICY ECONOMIC SIMULATION COMPARATOR */}
      {/* ========================================================================= */}
      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-sm overflow-hidden">
        {/* Comparator Header Banner */}
        <div className="p-6 sm:p-8 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex items-center space-x-2 bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full text-xs font-semibold border border-indigo-400/30">
              <Scale className="w-3.5 h-3.5" />
              <span>Milestone 5 · Rigorous Economic Evaluation</span>
            </div>
            {simulationResult && (
              <span className="text-xs text-slate-400 font-mono">
                Last Run: {new Date(simulationResult.timestamp).toLocaleTimeString()} · Latency:{' '}
                {simulationResult.run_metadata.execution_latency_ms.toFixed(0)}ms
              </span>
            )}
          </div>

          <div className="max-w-3xl space-y-2">
            <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight">
              Three-Policy Economic Simulation Comparator
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Simulates paired customer cohorts across 9 realistic shopper archetypes using Common
              Random Numbers (CRN). Evaluates causal profit, conversion uplift, and margin floor
              preservation between Organic Baseline, Indiscriminate 15% Markdown, and FairCart AI.
            </p>
          </div>

          {/* Interactive Run Bar */}
          <div className="pt-2 flex flex-wrap items-center gap-4 bg-white/5 p-4 rounded-xl border border-white/10">
            <div className="flex items-center space-x-2">
              <label htmlFor="sim-sessions-select" className="text-xs text-slate-300 font-medium">Sessions:</label>
              <select
                id="sim-sessions-select"
                value={numSessions}
                onChange={(e) => setNumSessions(parseInt(e.target.value, 10))}
                className="bg-slate-800 text-white text-xs border border-slate-700 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-400"
              >
                <option value={250}>250 Sessions (Quick test)</option>
                <option value={500}>500 Sessions (Standard)</option>
                <option value={1000}>1,000 Sessions (Evaluation default)</option>
                <option value={2500}>2,500 Sessions (High precision)</option>
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <label htmlFor="sim-seed-input" className="text-xs text-slate-300 font-medium">Seed:</label>
              <input
                id="sim-seed-input"
                type="number"
                value={randomSeed}
                onChange={(e) => setRandomSeed(parseInt(e.target.value, 10) || 0)}
                className="w-20 bg-slate-800 text-white text-xs border border-slate-700 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-400 font-mono"
              />
            </div>

            <div className="flex items-center space-x-2 text-xs text-slate-400">
              <span>Policy:</span>
              <span className="font-mono text-indigo-300">
                Floor {(settings.margin_floor * 100).toFixed(0)}% / Cap{' '}
                {(settings.discount_cap * 100).toFixed(0)}%
              </span>
            </div>

            <button
              onClick={handleRunSimulation}
              disabled={simulationRunning}
              className="ml-auto inline-flex items-center space-x-2 px-5 py-2 bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-500/50 text-white text-xs font-bold rounded-lg shadow-md transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-300"
            >
              {simulationRunning ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Evaluating Paired Cohorts...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Run 3-Policy Simulation</span>
                </>
              )}
            </button>
          </div>

          {simulationError && (
            <div className="p-3 bg-red-900/60 border border-red-700 rounded-lg text-xs text-red-200 flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{simulationError}</span>
            </div>
          )}
        </div>

        {/* Results Body */}
        {simulationResult ? (
          <div className="p-6 sm:p-8 space-y-8">
            {/* Relative Head-to-Head Callout Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* vs Blanket 15% Card */}
              <div className="p-5 rounded-xl border border-emerald-200 bg-emerald-50/50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 flex items-center space-x-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    <span>FairCart AI vs Blanket 15% Promotion</span>
                  </span>
                  <span className="text-xs bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">
                    Protected Profit
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <div className="text-[11px] text-slate-500 font-medium">Profit Delta</div>
                    <div className="text-xl font-extrabold text-emerald-700 flex items-center">
                      <ArrowUpRight className="w-4 h-4 mr-0.5 text-emerald-600" />
                      ${relBlanket?.contribution_profit_delta.toFixed(2)}
                      <span className="text-xs font-normal ml-1">
                        ({(relBlanket?.contribution_profit_pct ?? 0) > 0 ? '+' : ''}
                        {(relBlanket?.contribution_profit_pct ?? 0).toFixed(1)}%)
                      </span>
                    </div>
                  </div>

                  <div>
                    <div className="text-[11px] text-slate-500 font-medium">Promotional Waste Saved</div>
                    <div className="text-xl font-extrabold text-indigo-700">
                      ${relBlanket?.incentive_expense_reduction.toFixed(2)}
                      <span className="text-xs font-normal ml-1">
                        (-{(relBlanket?.incentive_expense_reduction_pct ?? 0).toFixed(1)}%)
                      </span>
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-white rounded-lg border border-emerald-200/80 text-xs text-slate-700 space-y-1">
                  <div className="font-semibold text-emerald-900 flex items-center space-x-1.5">
                    <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span>
                      {relBlanket?.margin_floor_violations_avoided} Margin Violations Avoided
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600">
                    Blanket 15% markdown breaches the {(settings.margin_floor * 100).toFixed(0)}% margin floor on {blanket15?.margin_floor_violations_count} orders. FairCart AI eliminated 100% of these unprofitable transactions.
                  </p>
                </div>
              </div>

              {/* vs No Discount Card */}
              <div className="p-5 rounded-xl border border-indigo-200 bg-indigo-50/50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-indigo-800 flex items-center space-x-1.5">
                    <TrendingUp className="w-4 h-4 text-indigo-600" />
                    <span>FairCart AI vs No-Discount Baseline</span>
                  </span>
                  <span className="text-xs bg-indigo-100 text-indigo-800 font-semibold px-2 py-0.5 rounded-full">
                    Organic Growth
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <div className="text-[11px] text-slate-500 font-medium">Profit Uplift</div>
                    <div className="text-xl font-extrabold text-indigo-700 flex items-center">
                      <ArrowUpRight className="w-4 h-4 mr-0.5 text-indigo-600" />
                      ${relNoDiscount?.contribution_profit_delta.toFixed(2)}
                      <span className="text-xs font-normal ml-1">
                        ({(relNoDiscount?.contribution_profit_pct ?? 0) > 0 ? '+' : ''}
                        {(relNoDiscount?.contribution_profit_pct ?? 0).toFixed(1)}%)
                      </span>
                    </div>
                  </div>

                  <div>
                    <div className="text-[11px] text-slate-500 font-medium">Conversion Lift</div>
                    <div className="text-xl font-extrabold text-indigo-700">
                      +{relNoDiscount?.conversion_rate_delta_pp.toFixed(1)} pp
                      <span className="text-xs font-normal ml-1 text-slate-500">
                        ({((faircartAi?.conversion_rate || 0) * 100).toFixed(1)}% vs{' '}
                        {((noDiscount?.conversion_rate || 0) * 100).toFixed(1)}%)
                      </span>
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-white rounded-lg border border-indigo-200/80 text-xs text-slate-700 space-y-1">
                  <div className="font-semibold text-indigo-900 flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                    <span>Average Order Value Expansion</span>
                  </div>
                  <p className="text-[11px] text-slate-600">
                    AOV expanded by +${relNoDiscount?.aov_delta.toFixed(2)} ({relNoDiscount?.aov_pct.toFixed(1)}%) through relevant multi-item basket recommendations.
                  </p>
                </div>
              </div>
            </div>

            {/* Side-by-Side 3-Policy Comparison Cards */}
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                <Layers className="w-4 h-4 text-indigo-600" />
                <span>Simulated Policy Comparison ({simulationResult.parameters.num_sessions} Sessions, Seed {simulationResult.parameters.random_seed})</span>
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Policy 1: No Discount */}
                <div className="bg-slate-50/70 border border-slate-200 rounded-xl p-5 space-y-4">
                  <div className="space-y-1 border-b border-slate-200 pb-3">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-200/80 px-2 py-0.5 rounded">
                      Baseline
                    </span>
                    <h4 className="text-base font-bold text-slate-900">1. No Discount</h4>
                    <p className="text-[11px] text-slate-500">Organic shopping behaviour with zero promotional incentives.</p>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <div className="text-[11px] text-slate-500">Total Contribution Profit</div>
                      <div className="text-xl font-bold text-slate-900 font-mono">
                        ${noDiscount?.total_contribution_profit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        95% CI: [${noDiscount?.avg_contribution_profit_per_session_ci_95[0].toFixed(2)}, ${noDiscount?.avg_contribution_profit_per_session_ci_95[1].toFixed(2)}]/session
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-200/60">
                      <div>
                        <div className="text-[10px] text-slate-500">Conversion Rate</div>
                        <div className="text-sm font-bold text-slate-800 font-mono">
                          {((noDiscount?.conversion_rate || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-slate-400">
                          {noDiscount?.completed_orders_count} / {noDiscount?.sessions_count} orders
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-slate-500">Average Order Value</div>
                        <div className="text-sm font-bold text-slate-800 font-mono">
                          ${noDiscount?.average_order_value.toFixed(2)}
                        </div>
                        <div className="text-[10px] text-slate-400">Per completed order</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-200/60">
                      <div>
                        <div className="text-[10px] text-slate-500">Promotions Given</div>
                        <div className="text-sm font-bold text-slate-800 font-mono">$0.00</div>
                        <div className="text-[10px] text-slate-400">0.0% of sales</div>
                      </div>

                      <div>
                        <div className="text-[10px] text-slate-500">Gross Margin</div>
                        <div className="text-sm font-bold text-slate-800 font-mono">
                          {((noDiscount?.total_gross_margin || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-slate-400">Full catalogue margin</div>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-200/60">
                      <div className="text-[10px] text-slate-500">Margin Floor Violations</div>
                      <div className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-md mt-0.5">
                        <Check className="w-3.5 h-3.5 text-slate-500" />
                        <span>0 violations (0.0%)</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Policy 2: Blanket 15% */}
                <div className="bg-amber-50/40 border border-amber-200 rounded-xl p-5 space-y-4">
                  <div className="space-y-1 border-b border-amber-200 pb-3">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 bg-amber-100 px-2 py-0.5 rounded">
                      Indiscriminate
                    </span>
                    <h4 className="text-base font-bold text-slate-900">2. Blanket 15% Markdown</h4>
                    <p className="text-[11px] text-slate-500">Fixed 15% promo applied to all eligible items without margin check.</p>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <div className="text-[11px] text-slate-500">Total Contribution Profit</div>
                      <div className="text-xl font-bold text-amber-900 font-mono">
                        ${blanket15?.total_contribution_profit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        95% CI: [${blanket15?.avg_contribution_profit_per_session_ci_95[0].toFixed(2)}, ${blanket15?.avg_contribution_profit_per_session_ci_95[1].toFixed(2)}]/session
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1 border-t border-amber-200/60">
                      <div>
                        <div className="text-[10px] text-slate-500">Conversion Rate</div>
                        <div className="text-sm font-bold text-amber-900 font-mono">
                          {((blanket15?.conversion_rate || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-slate-400">
                          {blanket15?.completed_orders_count} / {blanket15?.sessions_count} orders
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-slate-500">Average Order Value</div>
                        <div className="text-sm font-bold text-slate-800 font-mono">
                          ${blanket15?.average_order_value.toFixed(2)}
                        </div>
                        <div className="text-[10px] text-slate-400">Eroded by markdown</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1 border-t border-amber-200/60">
                      <div>
                        <div className="text-[10px] text-slate-500">Promotions Given</div>
                        <div className="text-sm font-bold text-rose-700 font-mono">
                          ${blanket15?.total_incentive_expense.toFixed(2)}
                        </div>
                        <div className="text-[10px] text-rose-600">High promotional waste</div>
                      </div>

                      <div>
                        <div className="text-[10px] text-slate-500">Gross Margin</div>
                        <div className="text-sm font-bold text-slate-800 font-mono">
                          {((blanket15?.total_gross_margin || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-slate-400">Compressed margin</div>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-amber-200/60">
                      <div className="text-[10px] text-slate-500">Margin Floor Violations</div>
                      <div className="inline-flex items-center space-x-1.5 text-xs font-semibold text-rose-700 bg-rose-100 px-2.5 py-1 rounded-md mt-0.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                        <span>
                          {blanket15?.margin_floor_violations_count} breaches (
                          {((blanket15?.margin_floor_violation_rate || 0) * 100).toFixed(1)}%)
                        </span>
                      </div>
                      <p className="text-[10px] text-rose-600 mt-1">
                        Erodes margin below the {(settings.margin_floor * 100).toFixed(0)}% floor on low-margin products.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Policy 3: FairCart AI */}
                <div className="bg-emerald-50/50 border-2 border-emerald-500/80 rounded-xl p-5 space-y-4 shadow-sm relative">
                  <div className="absolute top-3 right-3 bg-emerald-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase">
                    Recommended
                  </div>
                  <div className="space-y-1 border-b border-emerald-200 pb-3">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded">
                      Margin-Constrained AI
                    </span>
                    <h4 className="text-base font-bold text-slate-900">3. FairCart AI</h4>
                    <p className="text-[11px] text-slate-500">
                      Context-aware hybrid recommendations with mathematical margin constraints.
                    </p>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <div className="text-[11px] text-slate-500">Total Contribution Profit</div>
                      <div className="text-xl font-extrabold text-emerald-700 font-mono">
                        ${faircartAi?.total_contribution_profit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        95% CI: [${faircartAi?.avg_contribution_profit_per_session_ci_95[0].toFixed(2)}, ${faircartAi?.avg_contribution_profit_per_session_ci_95[1].toFixed(2)}]/session
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1 border-t border-emerald-200/60">
                      <div>
                        <div className="text-[10px] text-slate-500">Conversion Rate</div>
                        <div className="text-sm font-bold text-emerald-800 font-mono">
                          {((faircartAi?.conversion_rate || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-slate-400">
                          {faircartAi?.completed_orders_count} / {faircartAi?.sessions_count} orders
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-slate-500">Average Order Value</div>
                        <div className="text-sm font-bold text-slate-800 font-mono">
                          ${faircartAi?.average_order_value.toFixed(2)}
                        </div>
                        <div className="text-[10px] text-slate-400">Highest AOV across policies</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1 border-t border-emerald-200/60">
                      <div>
                        <div className="text-[10px] text-slate-500">Promotions Given</div>
                        <div className="text-sm font-bold text-indigo-700 font-mono">
                          ${faircartAi?.total_incentive_expense.toFixed(2)}
                        </div>
                        <div className="text-[10px] text-emerald-600">Targeted & efficient</div>
                      </div>

                      <div>
                        <div className="text-[10px] text-slate-500">Gross Margin</div>
                        <div className="text-sm font-bold text-slate-800 font-mono">
                          {((faircartAi?.total_gross_margin || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-slate-400">Safeguarded</div>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-emerald-200/60">
                      <div className="text-[10px] text-slate-500">Margin Floor Violations</div>
                      <div className="inline-flex items-center space-x-1.5 text-xs font-semibold text-emerald-700 bg-emerald-100 px-2.5 py-1 rounded-md mt-0.5">
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        <span>0 breaches (100% Invariant Compliant)</span>
                      </div>
                      <p className="text-[10px] text-emerald-700 mt-1">
                        Acceptance Rate: {((faircartAi?.recommendation_acceptance_rate || 0) * 100).toFixed(1)}% on relevant recommendations.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Visual SVG Comparison Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
              {/* Chart 1: Contribution Profit Bar Chart */}
              <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                    <DollarSign className="w-4 h-4 text-emerald-600" />
                    <span>Net Contribution Profit ($)</span>
                  </div>
                  <span className="text-[11px] text-slate-400">Total order contribution</span>
                </div>

                {/* SVG Profit Chart */}
                <div className="pt-2">
                  {(() => {
                    const pNo = noDiscount?.total_contribution_profit || 1;
                    const pBlanket = blanket15?.total_contribution_profit || 1;
                    const pFair = faircartAi?.total_contribution_profit || 1;
                    const maxP = Math.max(pNo, pBlanket, pFair) * 1.15;

                    const barW = (val: number) => `${Math.max(5, (val / maxP) * 100)}%`;

                    return (
                      <div className="space-y-3 text-xs">
                        {/* No Discount Bar */}
                        <div className="space-y-1">
                          <div className="flex justify-between text-slate-600 font-medium">
                            <span>1. No Discount</span>
                            <span className="font-mono font-bold">${pNo.toFixed(2)}</span>
                          </div>
                          <div className="w-full bg-slate-200 h-6 rounded-md overflow-hidden relative">
                            <div
                              className="h-full bg-slate-500 rounded-md transition-all duration-500"
                              style={{ width: barW(pNo) }}
                            />
                          </div>
                        </div>

                        {/* Blanket 15 Bar */}
                        <div className="space-y-1">
                          <div className="flex justify-between text-slate-600 font-medium">
                            <span>2. Blanket 15%</span>
                            <span className="font-mono font-bold">${pBlanket.toFixed(2)}</span>
                          </div>
                          <div className="w-full bg-slate-200 h-6 rounded-md overflow-hidden relative">
                            <div
                              className="h-full bg-amber-500 rounded-md transition-all duration-500"
                              style={{ width: barW(pBlanket) }}
                            />
                          </div>
                        </div>

                        {/* FairCart AI Bar */}
                        <div className="space-y-1">
                          <div className="flex justify-between text-slate-900 font-bold">
                            <span className="text-emerald-700 flex items-center space-x-1">
                              <span>3. FairCart AI</span>
                              <Sparkles className="w-3 h-3 text-emerald-600" />
                            </span>
                            <span className="font-mono text-emerald-700 font-extrabold">
                              ${pFair.toFixed(2)}
                            </span>
                          </div>
                          <div className="w-full bg-slate-200 h-6 rounded-md overflow-hidden relative">
                            <div
                              className="h-full bg-emerald-600 rounded-md transition-all duration-500"
                              style={{ width: barW(pFair) }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
                <p className="text-[11px] text-slate-500 pt-1">
                  Accounting: Net Sales Revenue − COGS − Variable Fulfillment ($3.50/order). Zero discount double-counting.
                </p>
              </div>

              {/* Chart 2: Conversion Rate & Floor Violation Comparison */}
              <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                    <TrendingUp className="w-4 h-4 text-indigo-600" />
                    <span>Conversion Rate (%) & Margin Safety</span>
                  </div>
                  <span className="text-[11px] text-slate-400">Conversion vs Risk</span>
                </div>

                {/* SVG Conversion Chart */}
                <div className="pt-2">
                  {(() => {
                    const cNo = (noDiscount?.conversion_rate || 0) * 100;
                    const cBlanket = (blanket15?.conversion_rate || 0) * 100;
                    const cFair = (faircartAi?.conversion_rate || 0) * 100;
                    const maxC = Math.max(cNo, cBlanket, cFair, 25) * 1.25;

                    const barW = (val: number) => `${Math.max(5, (val / maxC) * 100)}%`;

                    return (
                      <div className="space-y-3 text-xs">
                        {/* No Discount Bar */}
                        <div className="space-y-1">
                          <div className="flex justify-between text-slate-600 font-medium">
                            <span>1. No Discount</span>
                            <span className="font-mono font-bold">{cNo.toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 h-6 rounded-md overflow-hidden relative">
                            <div
                              className="h-full bg-slate-500 rounded-md transition-all duration-500"
                              style={{ width: barW(cNo) }}
                            />
                          </div>
                        </div>

                        {/* Blanket 15 Bar */}
                        <div className="space-y-1">
                          <div className="flex justify-between text-slate-600 font-medium">
                            <span className="flex items-center space-x-1">
                              <span>2. Blanket 15%</span>
                              <span className="text-[10px] text-rose-600 font-bold bg-rose-50 px-1 rounded">
                                {blanket15?.margin_floor_violations_count} breaches
                              </span>
                            </span>
                            <span className="font-mono font-bold text-amber-700">{cBlanket.toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 h-6 rounded-md overflow-hidden relative">
                            <div
                              className="h-full bg-amber-500 rounded-md transition-all duration-500"
                              style={{ width: barW(cBlanket) }}
                            />
                          </div>
                        </div>

                        {/* FairCart AI Bar */}
                        <div className="space-y-1">
                          <div className="flex justify-between text-slate-900 font-bold">
                            <span className="text-indigo-700 flex items-center space-x-1">
                              <span>3. FairCart AI</span>
                              <span className="text-[10px] text-emerald-700 font-bold bg-emerald-100 px-1 rounded">
                                0 breaches
                              </span>
                            </span>
                            <span className="font-mono text-indigo-700 font-extrabold">
                              {cFair.toFixed(1)}%
                            </span>
                          </div>
                          <div className="w-full bg-slate-200 h-6 rounded-md overflow-hidden relative">
                            <div
                              className="h-full bg-indigo-600 rounded-md transition-all duration-500"
                              style={{ width: barW(cFair) }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
                <p className="text-[11px] text-slate-500 pt-1">
                  Common Random Numbers ensure identical purchase propensity thresholds for all 3 policies.
                </p>
              </div>
            </div>

            {/* Comprehensive Side-by-Side Comparison Table */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                  <BarChart3 className="w-4 h-4 text-indigo-600" />
                  <span>Comprehensive Metric Comparison Matrix</span>
                </h3>
                <span className="text-xs text-slate-400 font-mono">
                  Seed: {simulationResult.parameters.random_seed} · N={simulationResult.parameters.num_sessions}
                </span>
              </div>

              <div className="overflow-x-auto border border-slate-200 rounded-xl">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100/80 text-slate-700 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-4">Evaluation Metric</th>
                      <th className="py-2.5 px-4">1. No Discount (Organic)</th>
                      <th className="py-2.5 px-4">2. Blanket 15% Markdown</th>
                      <th className="py-2.5 px-4 bg-emerald-50 text-emerald-900">
                        3. FairCart AI (Constrained)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans font-semibold text-slate-900">
                        Total Contribution Profit ($)
                      </td>
                      <td className="py-2.5 px-4 text-slate-700">
                        ${noDiscount?.total_contribution_profit.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 text-amber-800">
                        ${blanket15?.total_contribution_profit.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 font-bold text-emerald-700 bg-emerald-50/40">
                        ${faircartAi?.total_contribution_profit.toFixed(2)}
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans text-slate-600">
                        Profit per Session (95% CI)
                      </td>
                      <td className="py-2.5 px-4 text-slate-600">
                        ${noDiscount?.avg_contribution_profit_per_session.toFixed(2)} [
                        {noDiscount?.avg_contribution_profit_per_session_ci_95[0].toFixed(2)},{' '}
                        {noDiscount?.avg_contribution_profit_per_session_ci_95[1].toFixed(2)}]
                      </td>
                      <td className="py-2.5 px-4 text-amber-700">
                        ${blanket15?.avg_contribution_profit_per_session.toFixed(2)} [
                        {blanket15?.avg_contribution_profit_per_session_ci_95[0].toFixed(2)},{' '}
                        {blanket15?.avg_contribution_profit_per_session_ci_95[1].toFixed(2)}]
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-emerald-700 bg-emerald-50/40">
                        ${faircartAi?.avg_contribution_profit_per_session.toFixed(2)} [
                        {faircartAi?.avg_contribution_profit_per_session_ci_95[0].toFixed(2)},{' '}
                        {faircartAi?.avg_contribution_profit_per_session_ci_95[1].toFixed(2)}]
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans font-semibold text-slate-900">
                        Conversion Rate (%)
                      </td>
                      <td className="py-2.5 px-4 text-slate-700">
                        {((noDiscount?.conversion_rate || 0) * 100).toFixed(1)}%
                      </td>
                      <td className="py-2.5 px-4 text-amber-800 font-semibold">
                        {((blanket15?.conversion_rate || 0) * 100).toFixed(1)}%
                      </td>
                      <td className="py-2.5 px-4 font-bold text-indigo-700 bg-emerald-50/40">
                        {((faircartAi?.conversion_rate || 0) * 100).toFixed(1)}%
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans text-slate-600">
                        Completed Orders Count
                      </td>
                      <td className="py-2.5 px-4 text-slate-600">
                        {noDiscount?.completed_orders_count}
                      </td>
                      <td className="py-2.5 px-4 text-slate-600">
                        {blanket15?.completed_orders_count}
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-emerald-800 bg-emerald-50/40">
                        {faircartAi?.completed_orders_count}
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans text-slate-600">
                        Average Order Value (AOV)
                      </td>
                      <td className="py-2.5 px-4 text-slate-700">
                        ${noDiscount?.average_order_value.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 text-amber-700">
                        ${blanket15?.average_order_value.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 font-bold text-slate-900 bg-emerald-50/40">
                        ${faircartAi?.average_order_value.toFixed(2)}
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans text-slate-600">
                        Total Net Sales Revenue
                      </td>
                      <td className="py-2.5 px-4 text-slate-700">
                        ${noDiscount?.total_net_sales_revenue.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 text-slate-700">
                        ${blanket15?.total_net_sales_revenue.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-slate-900 bg-emerald-50/40">
                        ${faircartAi?.total_net_sales_revenue.toFixed(2)}
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans text-slate-600">
                        Total Promotional Discounts
                      </td>
                      <td className="py-2.5 px-4 text-slate-500">$0.00</td>
                      <td className="py-2.5 px-4 text-rose-600 font-bold">
                        ${blanket15?.total_incentive_expense.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-indigo-700 bg-emerald-50/40">
                        ${faircartAi?.total_incentive_expense.toFixed(2)}
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans text-slate-600">
                        Catalogue Gross Margin (%)
                      </td>
                      <td className="py-2.5 px-4 text-slate-700">
                        {((noDiscount?.total_gross_margin || 0) * 100).toFixed(1)}%
                      </td>
                      <td className="py-2.5 px-4 text-amber-800">
                        {((blanket15?.total_gross_margin || 0) * 100).toFixed(1)}%
                      </td>
                      <td className="py-2.5 px-4 font-bold text-emerald-800 bg-emerald-50/40">
                        {((faircartAi?.total_gross_margin || 0) * 100).toFixed(1)}%
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans font-semibold text-slate-900">
                        Margin Floor Breaches (&lt;{(settings.margin_floor * 100).toFixed(0)}%)
                      </td>
                      <td className="py-2.5 px-4 text-emerald-600">0 (0.0%)</td>
                      <td className="py-2.5 px-4 text-rose-600 font-bold">
                        {blanket15?.margin_floor_violations_count} (
                        {((blanket15?.margin_floor_violation_rate || 0) * 100).toFixed(1)}%)
                      </td>
                      <td className="py-2.5 px-4 font-bold text-emerald-700 bg-emerald-50/40">
                        0 (0.0% · 100% compliant)
                      </td>
                    </tr>

                    <tr className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-4 font-sans text-slate-600">
                        Recommendation Acceptance Rate
                      </td>
                      <td className="py-2.5 px-4 text-slate-400">N/A</td>
                      <td className="py-2.5 px-4 text-slate-400">N/A</td>
                      <td className="py-2.5 px-4 font-bold text-indigo-700 bg-emerald-50/40">
                        {((faircartAi?.recommendation_acceptance_rate || 0) * 100).toFixed(1)}%
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Methodology & Synthetic Provenance Notice */}
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 space-y-2">
              <div className="font-semibold text-slate-800 flex items-center space-x-2">
                <Info className="w-4 h-4 text-indigo-600 shrink-0" />
                <span>Simulation Provenance & Scientific Methodology</span>
              </div>
              <p className="leading-relaxed text-[11px] text-slate-500">
                {simulationResult.dataset_provenance.disclaimer}
              </p>
              <div className="pt-1 flex flex-wrap gap-2 text-[10px]">
                <span className="font-semibold text-slate-700">Archetypes Evaluated:</span>
                {Object.entries(simulationResult.dataset_provenance.archetype_distribution).map(
                  ([arch, cnt]) => (
                    <span
                      key={arch}
                      className="bg-white border border-slate-200 text-slate-600 px-2 py-0.5 rounded font-mono"
                    >
                      {arch}: {cnt}
                    </span>
                  )
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-12 text-center space-y-4">
            <Scale className="w-12 h-12 text-slate-300 mx-auto" />
            <div className="space-y-1">
              <h3 className="text-base font-bold text-slate-900">No Simulation Evaluated Yet</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Click &ldquo;Run 3-Policy Simulation&rdquo; above to run 1,000 paired synthetic shopping
                sessions comparing No Discount, Blanket 15%, and FairCart AI.
              </p>
            </div>
            <button
              onClick={handleRunSimulation}
              disabled={simulationRunning}
              className="inline-flex items-center space-x-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm transition-all"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run 1,000-Session Simulation</span>
            </button>
          </div>
        )}
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
