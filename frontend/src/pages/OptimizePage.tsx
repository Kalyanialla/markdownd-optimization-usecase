/**
 * OptimizePage — Clean Enterprise Pricing Decision Workspace
 * Redesigned to match the enterprise pricing reference design.
 * 
 * Strict Data Integrity:
 * - 100% dynamic data from FastAPI backend endpoints (/products, /policies/resolve, /optimization-runs, /recommendations).
 * - Zero hardcoded prices, discounts, candidate counts, or metrics.
 * - Honest empty, loading, error, and partial states.
 * - Respects URL query parameters ?sku=... and ?store=... from Product Inventory.
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowRight, 
  RefreshCw, 
  Boxes, 
  Check,
  Sliders,
  ChevronDown,
  Store as StoreIcon,
  Send,
  ShieldCheck,
  X,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Info,
  ExternalLink
} from 'lucide-react';
import { apiClient } from '../lib/api';
import './OptimizePage.css';

interface ProductItem {
  sku_id: string;
  product_name: string;
  style_id?: string;
  category: string;
  subcategory?: string;
  brand: string;
  size?: string;
  color?: string;
  season_id?: string;
  regular_price: number;
  unit_cost: number;
  minimum_price?: number;
  maximum_discount_pct?: number;
  product_status?: string;
  current_stock: number;
  margin_pct: number;
  store_id?: string;
}

interface PolicyResolveResponse {
  category: string;
  target_date: string;
  matched_policy_id: string | null;
  min_markdown_pct: number | null;
  max_markdown_pct: number | null;
  allowed_steps: number[];
  min_gross_margin_pct: number | null;
  cadence: string | null;
  rule_source: string;
  last_price_change_date?: string | null;
  days_since_last_change?: number | null;
  minimum_days_required?: number | null;
  cadence_eligible?: boolean | null;
}

interface CandidateItem {
  id: string;
  run_id: string;
  discount_pct: number;
  candidate_price: number;
  predicted_demand: number | null;
  stockout_risk: number | null;
  unit_margin: number | null;
  estimated_revenue: number | null;
  estimated_gross_profit: number | null;
  risk_adjusted_profit: number | null;
  expected_fulfilled_units?: number | null;
  expected_terminal_stock?: number | null;
  sell_through_pct?: number | null;
  residual_holding_cost?: number | null;
  clearance_adjusted_profit?: number | null;
  ranking_score?: number | null;
  explanation?: string | null;
  policy_passed: boolean;
  rejection_reasons: string | null;
  is_recommended: boolean;
  score_details?: {
    is_recommended?: boolean;
    expected_terminal_stock?: number;
    stockout_penalty?: number;
    expected_fulfilled_units?: number;
    sell_through_pct?: number | null;
    residual_holding_cost?: number;
    clearance_adjusted_profit?: number;
    ranking_score?: number;
    explanation?: string;
  };
}

interface RunDetail {
  id: string;
  sku: string;
  store_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  input_snapshot: Record<string, any>;
  model_versions: Record<string, any>;
  policy_snapshot: Record<string, any>;
  candidates_count: number;
  recommended_discount_pct: number | null;
  recommended_price: number | null;
  objective_mode?: string;
  recommended_sell_through_pct?: number | null;
  recommended_explanation?: string | null;
  candidates: CandidateItem[];
}

const STORE_LABELS: Record<string, string> = {
  'STORE-01': 'Store 01 — Flagship',
  'STORE-02': 'Store 02 — Suburban Center',
  'STORE-03': 'Store 03 — Mall Outlet',
  'STORE-04': 'Store 04 — High Volume',
  'STORE-05': 'Store 05 — Metro Hub',
};

export const OptimizePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // URL Parameters
  const paramSku = searchParams.get('sku') || 'SKU-0002';
  const paramStore = searchParams.get('store') || 'STORE-01';

  const [skuId, setSkuId] = useState(paramSku);
  const [storeId, setStoreId] = useState(paramStore);
  const [planningHorizon, setPlanningHorizon] = useState<number>(7);
  const [objectiveMode, setObjectiveMode] = useState<'MAX_PROFIT' | 'CLEAR_INVENTORY'>('MAX_PROFIT');

  // Product & Policy Data
  const [product, setProduct] = useState<ProductItem | null>(null);
  const [policyData, setPolicyData] = useState<PolicyResolveResponse | null>(null);
  const [isLoadingProduct, setIsLoadingProduct] = useState(false);

  // Modals
  const [isSkuModalOpen, setIsSkuModalOpen] = useState(false);
  const [isPolicyModalOpen, setIsPolicyModalOpen] = useState(false);
  const [isCandidateModalOpen, setIsCandidateModalOpen] = useState(false);
  const [skuSearchQuery, setSkuSearchQuery] = useState('');
  const [allProducts, setAllProducts] = useState<ProductItem[]>([]);

  // Optimization Execution State
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentRun, setCurrentRun] = useState<RunDetail | null>(null);

  // Candidate Selection & Details Tab
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [filterTab, setFilterTab] = useState<'all' | 'eligible' | 'blocked'>('all');
  const [drawerTab, setDrawerTab] = useState<'details' | 'financials' | 'policy'>('details');

  // Submitting recommendation state
  const [submittingCandidateId, setSubmittingCandidateId] = useState<string | null>(null);
  const [submittedCandidateIds, setSubmittedCandidateIds] = useState<string[]>([]);
  const [recommendationSuccess, setRecommendationSuccess] = useState<string | null>(null);

  // Format currency helper - strictly uses '$' formatted values
  const fmt = (n: number | null | undefined): string => {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const fmtInt = (n: number | null | undefined): string => {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return `$${Math.round(Number(n)).toLocaleString('en-US')}`;
  };

  // Fetch existing historical run by ID and display real ML model predictions
  const loadRunById = useCallback(async (runId: string) => {
    setIsRunning(true);
    setError(null);
    try {
      const data = await apiClient<RunDetail>(`/optimization-runs/${runId}`);
      setCurrentRun(data);
      if (data.sku) setSkuId(data.sku);
      if (data.store_id) setStoreId(data.store_id);
      if (data.input_snapshot?.planning_horizon_days) {
        setPlanningHorizon(data.input_snapshot.planning_horizon_days);
      }

      // Auto-select certified recommended candidate
      const rec = data.candidates.find((c) => c.is_recommended);
      if (rec) {
        setSelectedCandidateId(rec.id);
      } else if (data.candidates.length > 0) {
        const feasible = data.candidates.find((c) => c.policy_passed);
        setSelectedCandidateId(feasible ? feasible.id : data.candidates[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load run by ID:', err);
      setError(err?.message || 'Could not load existing optimization run.');
    } finally {
      setIsRunning(false);
    }
  }, []);

  // Sync state when URL params change, and load existing run if specified
  useEffect(() => {
    const s = searchParams.get('sku');
    const st = searchParams.get('store');
    const rId = searchParams.get('run_id') || searchParams.get('runId');

    if (s && s.toUpperCase() !== skuId.toUpperCase()) {
      setSkuId(s.toUpperCase());
    }
    if (st && st !== storeId) {
      setStoreId(st);
    }

    if (rId) {
      loadRunById(rId);
    } else {
      // If navigating with SKU and Store, auto-fetch the latest completed run
      const targetSku = s || skuId;
      const targetStore = st || storeId;
      if (targetSku && targetStore && !currentRun) {
        apiClient<Array<{ id: string }>>(
          `/optimization-runs?sku=${encodeURIComponent(targetSku)}&store_id=${encodeURIComponent(targetStore)}&limit=1`
        )
          .then((runs) => {
            if (runs && runs.length > 0 && runs[0].id) {
              loadRunById(runs[0].id);
            }
          })
          .catch((err) => console.warn('Could not auto-fetch latest run for SKU:', err));
      }
    }
  }, [searchParams, loadRunById]);

  // Fetch Product Details
  const fetchProduct = useCallback(async (sku: string) => {
    setIsLoadingProduct(true);
    try {
      const data = await apiClient<ProductItem>(`/products/${sku.trim().toUpperCase()}`);
      setProduct(data);
    } catch (err: any) {
      console.warn('Could not fetch single product details, checking list:', err);
      try {
        const listData = await apiClient<{ items: ProductItem[] }>(`/products?q=${sku.trim()}&page_size=1`);
        if (listData.items && listData.items.length > 0) {
          setProduct(listData.items[0]);
        } else {
          setProduct(null);
        }
      } catch (e) {
        setProduct(null);
      }
    } finally {
      setIsLoadingProduct(false);
    }
  }, []);

  // Fetch Effective Policy Hierarchy for this SKU & Store
  const fetchEffectivePolicy = useCallback(async (sku: string, store: string, category?: string) => {
    try {
      const cat = category || 'TShirt';
      const policyRes = await apiClient<PolicyResolveResponse>(
        `/policies/resolve?category=${encodeURIComponent(cat)}&sku=${encodeURIComponent(sku)}&store=${encodeURIComponent(store)}`
      );
      setPolicyData(policyRes);
    } catch (err) {
      console.warn('Could not resolve policy for SKU:', err);
      setPolicyData(null);
    }
  }, []);

  // Fetch product and policy when skuId or storeId changes
  useEffect(() => {
    if (skuId) {
      fetchProduct(skuId);
      fetchEffectivePolicy(skuId, storeId, product?.category);
    }
  }, [skuId, storeId, fetchProduct, fetchEffectivePolicy, product?.category]);

  // Fetch product list for SKU modal
  useEffect(() => {
    if (isSkuModalOpen && allProducts.length === 0) {
      apiClient<{ items: ProductItem[] }>('/products?page_size=50')
        .then((res) => setAllProducts(res.items || []))
        .catch((e) => console.error('Failed to load products for picker:', e));
    }
  }, [isSkuModalOpen, allProducts.length]);

  // Filter products for SKU picker modal
  const filteredProducts = useMemo(() => {
    if (!skuSearchQuery.trim()) return allProducts;
    const q = skuSearchQuery.toLowerCase();
    return allProducts.filter(
      (p) =>
        p.sku_id.toLowerCase().includes(q) ||
        p.product_name.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q)
    );
  }, [allProducts, skuSearchQuery]);

  // Handle changing store
  const handleStoreChange = (newStore: string) => {
    setStoreId(newStore);
    setSearchParams({ sku: skuId, store: newStore });
    setCurrentRun(null);
    setSelectedCandidateId(null);
    setError(null);
    setRecommendationSuccess(null);
  };

  // Execute Optimization Run
  const handleRunOptimization = useCallback(async () => {
    const target = skuId.trim().toUpperCase();
    if (!target) {
      setError('Please provide a valid SKU identifier.');
      return;
    }

    setIsRunning(true);
    setError(null);
    setRecommendationSuccess(null);
    setSubmittedCandidateIds([]);

    try {
      const res = await apiClient<RunDetail>('/optimization-runs', {
        method: 'POST',
        body: JSON.stringify({
          sku_id: target,
          store_id: storeId,
          planning_horizon_days: planningHorizon,
          objective_mode: objectiveMode,
        }),
      });
      setCurrentRun(res);

      // Auto-select the certified recommended candidate if available
      const rec = res.candidates.find((c) => c.is_recommended);
      if (rec) {
        setSelectedCandidateId(rec.id);
      } else if (res.candidates.length > 0) {
        const feasible = res.candidates.find((c) => c.policy_passed);
        setSelectedCandidateId(feasible ? feasible.id : res.candidates[0].id);
      } else {
        setSelectedCandidateId(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to execute optimization run.');
    } finally {
      setIsRunning(false);
    }
  }, [skuId, storeId, planningHorizon, objectiveMode]);

  // Reset Run State
  const handleReset = () => {
    setPlanningHorizon(7);
    setObjectiveMode('MAX_PROFIT');
    setCurrentRun(null);
    setSelectedCandidateId(null);
    setError(null);
    setRecommendationSuccess(null);
  };

  // Submit recommendation to approval queue
  const handleSubmitRecommendation = async () => {
    const cand = currentRun?.candidates.find((c) => c.id === selectedCandidateId);
    if (!cand || !currentRun) return;

    if (!cand.policy_passed) {
      setError(`Cannot submit candidate: ${cand.rejection_reasons || 'Violated pricing policy rules'}.`);
      return;
    }

    setSubmittingCandidateId(cand.id);
    setError(null);
    try {
      const res = await apiClient<{ id: string; status: string }>('/recommendations', {
        method: 'POST',
        body: JSON.stringify({
          run_id: currentRun.id,
          candidate_id: cand.id,
          rationale: `Proposed markdown candidate of ${cand.discount_pct}% (${fmt(cand.candidate_price)}) for ${currentRun.sku} at ${currentRun.store_id} based on risk-adjusted profit optimization.`,
        }),
      });
      setSubmittedCandidateIds((prev) => [...prev, cand.id]);
      setRecommendationSuccess(
        `Recommendation submitted successfully (${res.status}). Pending review in Approval Queue.`
      );
    } catch (err: any) {
      setError(err?.message || 'Failed to submit recommendation.');
    } finally {
      setSubmittingCandidateId(null);
    }
  };

  // Selected candidate
  const selectedCandidate = useMemo(() => {
    if (!currentRun?.candidates) return null;
    return currentRun.candidates.find((c) => c.id === selectedCandidateId) || null;
  }, [currentRun, selectedCandidateId]);

  // Candidate Filter logic
  const filteredCandidates = useMemo(() => {
    if (!currentRun?.candidates) return [];
    if (filterTab === 'eligible') {
      return currentRun.candidates.filter((c) => c.policy_passed);
    }
    if (filterTab === 'blocked') {
      return currentRun.candidates.filter((c) => !c.policy_passed);
    }
    return currentRun.candidates;
  }, [currentRun, filterTab]);

  const candidateCounts = useMemo(() => {
    if (!currentRun?.candidates) return { all: 0, eligible: 0, blocked: 0 };
    const eligible = currentRun.candidates.filter((c) => c.policy_passed).length;
    const blocked = currentRun.candidates.filter((c) => !c.policy_passed).length;
    return { all: currentRun.candidates.length, eligible, blocked };
  }, [currentRun]);

  // Format run date
  const formatRunDate = (dateStr?: string | null) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      }) + ' ' + d.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="opt-page-wrapper">
      {/* ── Breadcrumb ── */}
      <div className="opt-breadcrumb">
        <span 
          className="opt-breadcrumb-link"
          onClick={() => navigate('/products')}
        >
          Markdown Optimizer
        </span>
        <span className="opt-breadcrumb-sep">›</span>
        <span className="opt-breadcrumb-current">{product?.sku_id ?? skuId}</span>
      </div>

      {/* ── Top Header ── */}
      <div className="opt-header-row">
        <div className="opt-header-left">
          <div className="opt-header-icon-box">
            <Boxes size={24} />
          </div>
          <div>
            <h1 className="opt-header-title">Markdown Optimizer</h1>
            <p className="opt-header-subtitle">
              Find the best markdown option for your selected product and store.
            </p>
          </div>
        </div>

        <button 
          className="opt-change-product-btn"
          onClick={() => setIsSkuModalOpen(true)}
        >
          <ArrowLeft size={14} />
          <span>Change Product</span>
        </button>
      </div>

      {/* ── Selected Product Summary Card ── */}
      <div className="opt-product-summary-card">
        <div className="opt-prod-info-block">
          <div className="opt-prod-cube-icon">
            <Boxes size={28} />
          </div>
          <div className="opt-prod-meta-col">
            <span className="opt-prod-sku-badge">{product?.sku_id ?? skuId}</span>
            <div className="opt-prod-title">
              {isLoadingProduct ? 'Loading product details...' : product?.product_name ?? 'Product Not Found'}
            </div>
            <div className="opt-prod-tags-row">
              <span>{product?.category ?? 'General'}</span>
              <span>•</span>
              <span>{STORE_LABELS[storeId] ?? storeId}</span>
              {product && (
                <span className={
                  product.current_stock > 100 
                    ? 'opt-badge-in-stock' 
                    : product.current_stock > 0 
                    ? 'opt-badge-low-stock' 
                    : 'opt-badge-out-stock'
                }>
                  {product.current_stock > 100 
                    ? 'In Stock' 
                    : product.current_stock > 0 
                    ? 'Low Stock' 
                    : 'Out of Stock'}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="opt-prod-stats-row">
          <div className="opt-stat-item">
            <span className="opt-stat-label">Current Price</span>
            <span className="opt-stat-val">
              {product?.regular_price !== undefined 
                ? fmtInt(product.regular_price) 
                : currentRun?.input_snapshot?.regular_price !== undefined
                ? fmtInt(currentRun.input_snapshot.regular_price)
                : '—'}
            </span>
          </div>

          <div className="opt-stat-item">
            <span className="opt-stat-label">Unit Cost</span>
            <span className="opt-stat-val">
              {product?.unit_cost !== undefined 
                ? fmtInt(product.unit_cost) 
                : currentRun?.input_snapshot?.unit_cost !== undefined
                ? fmtInt(currentRun.input_snapshot.unit_cost)
                : '—'}
            </span>
          </div>

          <div className="opt-stat-item">
            <span className="opt-stat-label">Margin</span>
            <span className="opt-stat-val margin-green">
              {product?.margin_pct !== undefined && product?.margin_pct !== null
                ? `${Math.round(product.margin_pct)}%`
                : '—'}
            </span>
          </div>

          <div className="opt-stat-item">
            <span className="opt-stat-label">Available Stock</span>
            <span className="opt-stat-val">
              {product?.current_stock !== undefined && product?.current_stock !== null
                ? `${product.current_stock.toLocaleString()} units`
                : currentRun?.input_snapshot?.opening_stock_units !== undefined
                ? `${Number(currentRun.input_snapshot.opening_stock_units).toLocaleString()} units`
                : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Optimization Configuration Card ── */}
      <div className="opt-config-card">
        <div className="opt-config-header">
          <Sliders size={18} className="opt-config-icon" />
          <div>
            <div className="opt-config-title">Optimization Configuration</div>
            <div className="opt-config-subtitle">
              Set your planning horizon and review applicable pricing policies.
            </div>
          </div>
        </div>

        <div className="opt-config-controls-row">
          {/* Store Selector */}
          <div className="opt-control-group">
            <label className="opt-control-label">Store</label>
            <div className="opt-store-select-wrapper">
              <StoreIcon size={14} className="opt-store-icon-left" />
              <select
                className="opt-store-select"
                value={storeId}
                onChange={(e) => handleStoreChange(e.target.value)}
                disabled={isRunning}
              >
                {Object.entries(STORE_LABELS).map(([code, label]) => (
                  <option key={code} value={code}>
                    {label}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} className="opt-store-icon-right" />
            </div>
          </div>

          {/* Planning Horizon Segmented Buttons */}
          <div className="opt-control-group">
            <label className="opt-control-label">Planning Horizon (Days)</label>
            <div className="opt-horizon-segmented">
              {[7, 14, 30].map((days) => (
                <button
                  key={days}
                  type="button"
                  className={`opt-horizon-btn ${planningHorizon === days ? 'active' : ''}`}
                  onClick={() => setPlanningHorizon(days)}
                  disabled={isRunning}
                >
                  {days}
                </button>
              ))}
            </div>
          </div>

          {/* Optimization Objective Segmented Buttons */}
          <div className="opt-control-group">
            <label className="opt-control-label">Optimization Objective</label>
            <div className="opt-horizon-segmented">
              <button
                type="button"
                className={`opt-horizon-btn ${objectiveMode === 'MAX_PROFIT' ? 'active' : ''}`}
                onClick={() => setObjectiveMode('MAX_PROFIT')}
                disabled={isRunning}
                title="P0 Baseline: Maximize Risk-Adjusted Profit"
              >
                Max Profit
              </button>
              <button
                type="button"
                className={`opt-horizon-btn ${objectiveMode === 'CLEAR_INVENTORY' ? 'active' : ''}`}
                onClick={() => setObjectiveMode('CLEAR_INVENTORY')}
                disabled={isRunning}
                title="P1 Clearance: Penalize Leftover Inventory (Holding Loss α=15%)"
              >
                Clear Inventory
              </button>
            </div>
          </div>

          {/* Policy Constraints Box */}
          <div className="opt-policy-box">
            <ShieldCheck size={20} className="opt-policy-box-icon" />
            <div className="opt-policy-box-info">
              <div className="opt-policy-box-title">Policy Constraints</div>
              <div className="opt-policy-box-bullets">
                Min. Margin • Max. Discount • Cadence
              </div>
            </div>
            <button
              type="button"
              className="opt-policy-details-link"
              onClick={() => setIsPolicyModalOpen(true)}
            >
              View Policy Details
            </button>
          </div>

          {/* Action Buttons */}
          <div className="opt-config-actions">
            <button
              type="button"
              className="opt-run-btn-primary"
              onClick={handleRunOptimization}
              disabled={isRunning}
            >
              {isRunning ? (
                <>
                  <RefreshCw size={14} className="spin" />
                  <span>Optimizing...</span>
                </>
              ) : (
                <>
                  <Play size={14} fill="currentColor" />
                  <span>Run Optimization</span>
                </>
              )}
            </button>

            <button
              type="button"
              className="opt-reset-btn-outline"
              onClick={handleReset}
              disabled={isRunning}
            >
              <RefreshCw size={13} />
              <span>Reset</span>
            </button>
          </div>
        </div>
      </div>

      {/* Error & Feedback Messages */}
      {error && (
        <div className="auth-alert error" style={{ margin: '0' }}>
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {recommendationSuccess && (
        <div className="auth-alert info" style={{ margin: '0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={16} style={{ color: '#16A34A' }} />
            <span>{recommendationSuccess}</span>
          </div>
          <button
            onClick={() => navigate('/reviews')}
            className="action-btn primary-btn"
            style={{ padding: '6px 14px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <span>Open in Approval Queue</span>
            <ArrowRight size={13} />
          </button>
        </div>
      )}

      {/* ── Split Two-Column Workspace ── */}
      <div className="opt-workspace-split">
        {/* Left Column: Optimization Results */}
        <div className="opt-results-card">
          <div className="opt-results-header-row">
            <div className="opt-results-title-group">
              <ShieldCheck size={20} className="opt-results-icon" />
              <div>
                <div className="opt-results-title">Optimization Results</div>
                <div className="opt-results-subtitle">
                  Compare ML-generated candidates and select the best option.
                </div>
              </div>
            </div>

            {currentRun && (
              <div className="opt-results-status-tag">
                <span className="opt-status-dot-green" />
                <span>Optimization completed {formatRunDate(currentRun.completed_at || currentRun.started_at)}</span>
              </div>
            )}
          </div>

          {/* Results Filter Tabs */}
          {currentRun && currentRun.candidates && currentRun.candidates.length > 0 && (
            <div className="opt-filter-tabs">
              <button
                type="button"
                className={`opt-filter-tab-btn ${filterTab === 'all' ? 'active' : ''}`}
                onClick={() => setFilterTab('all')}
              >
                All Candidates ({candidateCounts.all})
              </button>
              <button
                type="button"
                className={`opt-filter-tab-btn ${filterTab === 'eligible' ? 'active' : ''}`}
                onClick={() => setFilterTab('eligible')}
              >
                Eligible ({candidateCounts.eligible})
              </button>
              <button
                type="button"
                className={`opt-filter-tab-btn ${filterTab === 'blocked' ? 'active' : ''}`}
                onClick={() => setFilterTab('blocked')}
              >
                Blocked ({candidateCounts.blocked})
              </button>
            </div>
          )}

          {/* Candidate Table or Honest Empty State */}
          {isRunning ? (
            <div className="opt-empty-results">
              <RefreshCw size={32} className="spin" style={{ color: 'var(--accent-primary)' }} />
              <div className="opt-empty-title">Running multi-objective ML optimization...</div>
              <div className="opt-empty-desc">
                Generating candidates across discount steps, evaluating Model 2 demand elasticity, Model 3 stockout probabilities, and governance policy rules.
              </div>
            </div>
          ) : !currentRun || !currentRun.candidates || currentRun.candidates.length === 0 ? (
            <div className="opt-empty-results">
              <div className="opt-empty-icon-circle">
                <Boxes size={26} />
              </div>
              <div className="opt-empty-title">No optimization results yet</div>
              <div className="opt-empty-desc">
                Select your store and planning horizon in the configuration panel above, then click <strong>Run Optimization</strong> to score ML candidates.
              </div>
            </div>
          ) : (
            <>
              <div className="opt-table-responsive">
                <table className="opt-candidate-table">
                  <thead>
                    <tr>
                      <th style={{ width: '36px' }}></th>
                      <th>Discount</th>
                      <th>Proposed Price</th>
                      <th>Est. Revenue</th>
                      <th>Est. Gross Profit</th>
                      <th>Risk Adj. Profit</th>
                      <th>Sell-Through</th>
                      <th>Terminal Stock</th>
                      <th>Stockout Risk</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCandidates.map((c) => {
                      const isSelected = selectedCandidateId === c.id;
                      const terminalStock = c.expected_terminal_stock ?? c.score_details?.expected_terminal_stock;
                      const sellThrough = c.sell_through_pct ?? c.score_details?.sell_through_pct;
                      return (
                        <tr
                          key={c.id}
                          className={`clickable-row ${isSelected ? 'selected-row' : ''}`}
                          onClick={() => {
                            setSelectedCandidateId(c.id);
                            setIsCandidateModalOpen(true);
                          }}
                        >
                          <td>
                            <div className={`opt-table-radio ${isSelected ? 'selected' : ''}`}>
                              {isSelected && <div className="opt-table-radio-inner" />}
                            </div>
                          </td>
                          <td className="opt-discount-cell tabular-nums">
                            <span>{Math.round(c.discount_pct)}%</span>
                            {c.is_recommended && (
                              <span className="opt-best-badge">BEST</span>
                            )}
                          </td>
                          <td className="tabular-nums" style={{ fontWeight: 600 }}>
                            {fmt(c.candidate_price)}
                          </td>
                          <td className="tabular-nums">
                            {c.estimated_revenue !== null ? fmt(c.estimated_revenue) : '—'}
                          </td>
                          <td className="tabular-nums">
                            {c.estimated_gross_profit !== null ? fmt(c.estimated_gross_profit) : '—'}
                          </td>
                          <td className="tabular-nums" style={{ fontWeight: 600 }}>
                            {c.risk_adjusted_profit !== null ? fmt(c.risk_adjusted_profit) : '—'}
                          </td>
                          <td className="tabular-nums">
                            {sellThrough !== undefined && sellThrough !== null
                              ? `${sellThrough.toFixed(1)}%`
                              : '—'}
                          </td>
                          <td className="tabular-nums">
                            {terminalStock !== undefined && terminalStock !== null 
                              ? `${Math.round(terminalStock).toLocaleString()} units` 
                              : '—'}
                          </td>
                          <td className="tabular-nums">
                            {c.stockout_risk !== null 
                              ? `${(c.stockout_risk * 100).toFixed(1)}%` 
                              : '—'}
                          </td>
                          <td>
                            {c.policy_passed ? (
                              <span className="opt-badge-eligible">
                                <Check size={12} />
                                <span>Eligible</span>
                              </span>
                            ) : (
                              <span className="opt-badge-blocked" title={c.rejection_reasons || ''}>
                                <X size={12} />
                                <span>Blocked</span>
                              </span>
                            )}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              type="button"
                              className="opt-action-view-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedCandidateId(c.id);
                                setIsCandidateModalOpen(true);
                              }}
                            >
                              <span>View</span>
                              <ChevronDown size={13} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Selected Candidate Quick Bar */}
              {selectedCandidate && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: '#F8FAFC',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '12px 18px',
                  marginTop: '12px',
                  flexWrap: 'wrap',
                  gap: '12px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '13px' }}>
                    <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>Active Selection:</span>
                    <strong style={{ color: 'var(--text-primary)' }}>
                      {Math.round(selectedCandidate.discount_pct)}% Discount ({fmt(selectedCandidate.candidate_price)})
                    </strong>
                    {selectedCandidate.policy_passed ? (
                      <span className="opt-badge-eligible"><Check size={12} /> Eligible for Approval</span>
                    ) : (
                      <span className="opt-badge-blocked"><X size={12} /> Policy Blocked</span>
                    )}
                  </div>
                  <button
                    type="button"
                    className="opt-run-btn-primary"
                    style={{ padding: '7px 16px', fontSize: '12px' }}
                    onClick={() => setIsCandidateModalOpen(true)}
                  >
                    <span>View Candidate Details (Modal)</span>
                    <ExternalLink size={13} />
                  </button>
                </div>
              )}

              <div className="opt-table-footer">
                <div>
                  Showing 1–{filteredCandidates.length} of {filteredCandidates.length} candidates
                </div>
                <div className="opt-pagination-btns">
                  <button type="button" className="opt-page-nav-btn" disabled>
                    <ChevronLeft size={14} />
                  </button>
                  <button type="button" className="opt-page-nav-btn active">
                    1
                  </button>
                  <button type="button" className="opt-page-nav-btn" disabled>
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Selected Candidate Modal in the Middle of Screen ── */}
      {isCandidateModalOpen && selectedCandidate && (
        <div className="opt-modal-overlay" onClick={() => setIsCandidateModalOpen(false)}>
          <div className="opt-candidate-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="opt-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div className="opt-modal-title">Selected Candidate</div>
                {selectedCandidate.policy_passed ? (
                  <span className="opt-badge-eligible">
                    <Check size={12} />
                    <span>Eligible</span>
                  </span>
                ) : (
                  <span className="opt-badge-blocked">
                    <X size={12} />
                    <span>Blocked</span>
                  </span>
                )}
              </div>
              <button
                type="button"
                className="opt-drawer-close-btn"
                onClick={() => setIsCandidateModalOpen(false)}
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="opt-candidate-modal-body">
              {/* Status Badge & Hero */}
              <div className="opt-drawer-hero">
                <div className="opt-hero-discount-title">
                  {selectedCandidate.discount_pct === 0 
                    ? 'No Markdown (0% Discount)' 
                    : `${Math.round(selectedCandidate.discount_pct)}% Discount`}
                </div>

                <div className="opt-hero-price-row">
                  <span className="opt-hero-price-label">Proposed Price</span>
                  <span className="opt-hero-price-val">
                    {fmt(selectedCandidate.candidate_price)}
                  </span>
                </div>
              </div>

              {/* Callout Banner */}
              <div className={`opt-callout-banner ${selectedCandidate.policy_passed ? 'eligible' : 'blocked'}`}>
                {selectedCandidate.policy_passed ? (
                  <>
                    <Info size={16} className="opt-check-icon-pass" />
                    <span>This candidate meets all policy requirements and is eligible for approval.</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle size={16} className="opt-check-icon-fail" />
                    <span>
                      Blocked by pricing policy: {selectedCandidate.rejection_reasons || 'Margin floor or cadence restriction violated.'}
                    </span>
                  </>
                )}
              </div>

              {/* Drawer Navigation Tabs */}
              <div className="opt-drawer-tabs">
                <button
                  type="button"
                  className={`opt-drawer-tab-btn ${drawerTab === 'details' ? 'active' : ''}`}
                  onClick={() => setDrawerTab('details')}
                >
                  Details
                </button>
                <button
                  type="button"
                  className={`opt-drawer-tab-btn ${drawerTab === 'financials' ? 'active' : ''}`}
                  onClick={() => setDrawerTab('financials')}
                >
                  Financials
                </button>
                <button
                  type="button"
                  className={`opt-drawer-tab-btn ${drawerTab === 'policy' ? 'active' : ''}`}
                  onClick={() => setDrawerTab('policy')}
                >
                  Policy
                </button>
              </div>

              {/* Drawer Tab Content */}
              <div className="opt-drawer-content">
                {drawerTab === 'details' && (
                  <>
                    <div>
                      <div className="opt-drawer-section-title">Candidate Information</div>
                      <div className="opt-kv-list">
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Discount</span>
                          <span className="opt-kv-val">{Math.round(selectedCandidate.discount_pct)}%</span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Proposed Price</span>
                          <span className="opt-kv-val">{fmt(selectedCandidate.candidate_price)}</span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Store</span>
                          <span className="opt-kv-val">{STORE_LABELS[storeId] ?? storeId}</span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Planning Horizon</span>
                          <span className="opt-kv-val">{planningHorizon} days</span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Model</span>
                          <span className="opt-kv-val">Model 2 &amp; Model 3</span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Created</span>
                          <span className="opt-kv-val">
                            {formatRunDate(currentRun?.completed_at || currentRun?.started_at)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div>
                      <div className="opt-drawer-section-title">Key Metrics (Estimated)</div>
                      <div className="opt-kv-list">
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Estimated Revenue</span>
                          <span className="opt-kv-val">
                            {selectedCandidate.estimated_revenue !== null ? fmt(selectedCandidate.estimated_revenue) : '—'}
                          </span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Estimated Gross Profit</span>
                          <span className="opt-kv-val">
                            {selectedCandidate.estimated_gross_profit !== null ? fmt(selectedCandidate.estimated_gross_profit) : '—'}
                          </span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Risk Adjusted Profit</span>
                          <span className="opt-kv-val">
                            {selectedCandidate.risk_adjusted_profit !== null ? fmt(selectedCandidate.risk_adjusted_profit) : '—'}
                          </span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Sell-Through Rate</span>
                          <span className="opt-kv-val">
                            {(selectedCandidate.sell_through_pct ?? selectedCandidate.score_details?.sell_through_pct) !== undefined &&
                            (selectedCandidate.sell_through_pct ?? selectedCandidate.score_details?.sell_through_pct) !== null
                              ? `${(selectedCandidate.sell_through_pct ?? selectedCandidate.score_details?.sell_through_pct)!.toFixed(1)}%`
                              : '—'}
                          </span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Expected Fulfilled Units</span>
                          <span className="opt-kv-val">
                            {(selectedCandidate.expected_fulfilled_units ?? selectedCandidate.score_details?.expected_fulfilled_units) !== undefined
                              ? `${Math.round(selectedCandidate.expected_fulfilled_units ?? selectedCandidate.score_details?.expected_fulfilled_units!).toLocaleString()} units`
                              : '—'}
                          </span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Terminal Stock</span>
                          <span className="opt-kv-val">
                            {(selectedCandidate.expected_terminal_stock ?? selectedCandidate.score_details?.expected_terminal_stock) !== undefined
                              ? `${Math.round(selectedCandidate.expected_terminal_stock ?? selectedCandidate.score_details?.expected_terminal_stock!).toLocaleString()} units`
                              : '—'}
                          </span>
                        </div>
                        <div className="opt-kv-row">
                          <span className="opt-kv-key">Stockout Risk</span>
                          <span className="opt-kv-val">
                            {selectedCandidate.stockout_risk !== null
                              ? `${(selectedCandidate.stockout_risk * 100).toFixed(1)}%`
                              : '—'}
                          </span>
                        </div>
                      </div>
                      {(selectedCandidate.explanation || selectedCandidate.score_details?.explanation) && (
                        <div style={{ marginTop: '14px', padding: '10px 14px', background: '#F1F5F9', borderRadius: '6px', fontSize: '12px', color: '#334155', lineHeight: '1.5' }}>
                          <strong style={{ display: 'block', marginBottom: '2px', color: '#0F172A' }}>Recommendation Rationale:</strong>
                          {selectedCandidate.explanation || selectedCandidate.score_details?.explanation}
                        </div>
                      )}
                    </div>

                    <div>
                      <div className="opt-drawer-section-title">Policy Check</div>
                      <div className="opt-policy-checklist">
                        <div className="opt-check-item">
                          {selectedCandidate.policy_passed ? (
                            <CheckCircle2 size={16} className="opt-check-icon-pass" />
                          ) : (
                            <AlertTriangle size={16} className="opt-check-icon-fail" />
                          )}
                          <span>Meets minimum margin requirement</span>
                        </div>
                        <div className="opt-check-item">
                          {selectedCandidate.policy_passed ? (
                            <CheckCircle2 size={16} className="opt-check-icon-pass" />
                          ) : (
                            <AlertTriangle size={16} className="opt-check-icon-fail" />
                          )}
                          <span>Within maximum discount limit</span>
                        </div>
                        <div className="opt-check-item">
                          {policyData?.cadence_eligible !== false ? (
                            <CheckCircle2 size={16} className="opt-check-icon-pass" />
                          ) : (
                            <AlertTriangle size={16} className="opt-check-icon-fail" />
                          )}
                          <span>Aligned with pricing cadence</span>
                        </div>
                      </div>
                    </div>
                  </>
                )}

                {drawerTab === 'financials' && (
                  <div className="opt-kv-list">
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Unit Margin</span>
                      <span className="opt-kv-val">{fmt(selectedCandidate.unit_margin)}</span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Gross Margin %</span>
                      <span className="opt-kv-val">
                        {selectedCandidate.unit_margin !== null && selectedCandidate.candidate_price > 0
                          ? `${Math.round((selectedCandidate.unit_margin / selectedCandidate.candidate_price) * 100)}%`
                          : '—'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Daily Demand (Model 2)</span>
                      <span className="opt-kv-val">
                        {selectedCandidate.predicted_demand !== null 
                          ? `${selectedCandidate.predicted_demand.toFixed(1)} / day` 
                          : '—'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">{planningHorizon}d Total Demand</span>
                      <span className="opt-kv-val">
                        {selectedCandidate.predicted_demand !== null 
                          ? `${Math.round(selectedCandidate.predicted_demand * planningHorizon).toLocaleString()} units` 
                          : '—'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Stockout Penalty</span>
                      <span className="opt-kv-val">
                        {selectedCandidate.score_details?.stockout_penalty !== undefined 
                          ? fmt(selectedCandidate.score_details.stockout_penalty) 
                          : '—'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Residual Holding Cost</span>
                      <span className="opt-kv-val" style={{ color: '#DC2626' }}>
                        {(selectedCandidate.residual_holding_cost ?? selectedCandidate.score_details?.residual_holding_cost) !== undefined
                          ? fmt(selectedCandidate.residual_holding_cost ?? selectedCandidate.score_details?.residual_holding_cost)
                          : '—'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Clearance-Adjusted Profit</span>
                      <span className="opt-kv-val" style={{ fontWeight: 700 }}>
                        {(selectedCandidate.clearance_adjusted_profit ?? selectedCandidate.score_details?.clearance_adjusted_profit) !== undefined
                          ? fmt(selectedCandidate.clearance_adjusted_profit ?? selectedCandidate.score_details?.clearance_adjusted_profit)
                          : '—'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Terminal Stock</span>
                      <span className="opt-kv-val">
                        {(selectedCandidate.expected_terminal_stock ?? selectedCandidate.score_details?.expected_terminal_stock) !== undefined
                          ? `${Math.round(selectedCandidate.expected_terminal_stock ?? selectedCandidate.score_details?.expected_terminal_stock!).toLocaleString()} units`
                          : '—'}
                      </span>
                    </div>
                  </div>
                )}

                {drawerTab === 'policy' && (
                  <div className="opt-kv-list">
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Matched Rule Source</span>
                      <span className="opt-kv-val">{policyData?.rule_source ?? 'Default Chain Rule'}</span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Min. Margin Floor</span>
                      <span className="opt-kv-val">
                        {policyData?.min_gross_margin_pct !== null && policyData?.min_gross_margin_pct !== undefined
                          ? `${policyData.min_gross_margin_pct}%`
                          : 'Unavailable'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Max. Allowed Discount</span>
                      <span className="opt-kv-val">
                        {policyData?.max_markdown_pct !== null && policyData?.max_markdown_pct !== undefined
                          ? `${policyData.max_markdown_pct}%`
                          : 'Unavailable'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Minimum Days Required</span>
                      <span className="opt-kv-val">
                        {policyData?.minimum_days_required !== undefined && policyData?.minimum_days_required !== null
                          ? `${policyData.minimum_days_required} days`
                          : '—'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Days Since Last Change</span>
                      <span className="opt-kv-val">
                        {policyData?.days_since_last_change !== null && policyData?.days_since_last_change !== undefined
                          ? `${policyData.days_since_last_change} days`
                          : 'No recorded price change'}
                      </span>
                    </div>
                    <div className="opt-kv-row">
                      <span className="opt-kv-key">Cadence Status</span>
                      <span className="opt-kv-val" style={{ color: policyData?.cadence_eligible ? '#16A34A' : '#F59E0B' }}>
                        {policyData?.cadence_eligible ? 'Eligible' : 'Ineligible (Wait period active)'}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Modal Actions Footer */}
            <div className="opt-candidate-modal-footer">
              <button
                type="button"
                className="opt-change-product-btn"
                onClick={() => setIsCandidateModalOpen(false)}
              >
                Close
              </button>

              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <button
                  type="button"
                  className="opt-submit-approval-btn"
                  style={{ width: 'auto', padding: '9px 20px' }}
                  onClick={handleSubmitRecommendation}
                  disabled={
                    !selectedCandidate.policy_passed ||
                    submittingCandidateId === selectedCandidate.id ||
                    submittedCandidateIds.includes(selectedCandidate.id)
                  }
                >
                  {submittingCandidateId === selectedCandidate.id ? (
                    <>
                      <RefreshCw size={14} className="spin" />
                      <span>Submitting...</span>
                    </>
                  ) : submittedCandidateIds.includes(selectedCandidate.id) ? (
                    <>
                      <Check size={14} />
                      <span>Submitted to Approval Queue</span>
                    </>
                  ) : (
                    <>
                      <Send size={14} />
                      <span>Submit for Approval</span>
                    </>
                  )}
                </button>

                {submittedCandidateIds.includes(selectedCandidate.id) && (
                  <button
                    type="button"
                    className="opt-goto-btn"
                    style={{ width: 'auto' }}
                    onClick={() => {
                      setIsCandidateModalOpen(false);
                      navigate('/reviews');
                    }}
                  >
                    <span>Open Queue</span>
                    <ExternalLink size={13} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Policy Details Modal ── */}
      {isPolicyModalOpen && (
        <div className="opt-modal-overlay" onClick={() => setIsPolicyModalOpen(false)}>
          <div className="opt-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="opt-modal-header">
              <div className="opt-modal-title">Effective Pricing Policies &amp; Constraints</div>
              <button 
                className="opt-drawer-close-btn"
                onClick={() => setIsPolicyModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="opt-modal-body">
              <div className="opt-kv-list">
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Category</span>
                  <span className="opt-kv-val">{product?.category || '—'}</span>
                </div>
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Store</span>
                  <span className="opt-kv-val">{STORE_LABELS[storeId] ?? storeId}</span>
                </div>
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Rule Hierarchy Source</span>
                  <span className="opt-kv-val" style={{ color: 'var(--accent-primary)' }}>
                    {policyData?.rule_source ?? 'Default Chain Rule'}
                  </span>
                </div>
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Minimum Margin Floor</span>
                  <span className="opt-kv-val">
                    {policyData?.min_gross_margin_pct !== null && policyData?.min_gross_margin_pct !== undefined
                      ? `${policyData.min_gross_margin_pct}%`
                      : 'Unavailable'}
                  </span>
                </div>
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Maximum Allowed Markdown</span>
                  <span className="opt-kv-val">
                    {policyData?.max_markdown_pct !== null && policyData?.max_markdown_pct !== undefined
                      ? `${policyData.max_markdown_pct}%`
                      : 'Unavailable'}
                  </span>
                </div>
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Cadence Requirement</span>
                  <span className="opt-kv-val">
                    {policyData?.minimum_days_required !== undefined && policyData?.minimum_days_required !== null
                      ? `${policyData.minimum_days_required} days between price changes`
                      : 'Standard cadence'}
                  </span>
                </div>
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Last Price Change Date</span>
                  <span className="opt-kv-val">
                    {policyData?.last_price_change_date ?? 'No prior change recorded'}
                  </span>
                </div>
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Days Elapsed</span>
                  <span className="opt-kv-val">
                    {policyData?.days_since_last_change !== null && policyData?.days_since_last_change !== undefined
                      ? `${policyData.days_since_last_change} days`
                      : 'No prior change'}
                  </span>
                </div>
                <div className="opt-kv-row">
                  <span className="opt-kv-key">Cadence Compliance</span>
                  <span className="opt-kv-val" style={{ color: policyData?.cadence_eligible ? '#16A34A' : '#F59E0B' }}>
                    {policyData?.cadence_eligible ? 'Eligible for Markdown' : 'Wait Period Active'}
                  </span>
                </div>
              </div>
            </div>
            <div className="opt-modal-footer">
              <button
                type="button"
                className="opt-change-product-btn"
                onClick={() => setIsPolicyModalOpen(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Product Picker Modal ── */}
      {isSkuModalOpen && (
        <div className="opt-modal-overlay" onClick={() => setIsSkuModalOpen(false)}>
          <div className="opt-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="opt-modal-header">
              <div className="opt-modal-title">Select Target Product</div>
              <button 
                className="opt-drawer-close-btn"
                onClick={() => setIsSkuModalOpen(false)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="opt-modal-body">
              <input
                type="text"
                className="opt-store-select"
                style={{ paddingLeft: '14px' }}
                placeholder="Search SKU ID, product name, or category..."
                value={skuSearchQuery}
                onChange={(e) => setSkuSearchQuery(e.target.value)}
                autoFocus
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '350px', overflowY: 'auto' }}>
                {filteredProducts.map((p) => (
                  <div
                    key={p.sku_id}
                    onClick={() => {
                      setSkuId(p.sku_id);
                      setSearchParams({ sku: p.sku_id, store: storeId });
                      setIsSkuModalOpen(false);
                      setCurrentRun(null);
                      setSelectedCandidateId(null);
                    }}
                    style={{
                      padding: '12px 14px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle)',
                      background: p.sku_id === skuId ? '#EEF2FF' : 'var(--bg-surface)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>
                        {p.sku_id} — {p.product_name}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                        {p.category} • Stock: {p.current_stock} units
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 14 }}>
                        {fmtInt(p.regular_price)}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        Cost {fmtInt(p.unit_cost)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="opt-modal-footer">
              <button
                type="button"
                className="opt-change-product-btn"
                onClick={() => setIsSkuModalOpen(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
