import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Package,
  Search,
  RefreshCw,
  Download,
  AlertTriangle,
  Tag,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  X,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Calendar,
  Cpu
} from 'lucide-react';
import { apiClient } from '../lib/api';
import './ProductsPage.css';

// ─── Types ──────────────────────────────────────────────────────────────────

interface ProductItem {
  sku_id: string;
  product_name: string;
  style_id: string;
  category: string;
  subcategory: string;
  brand: string;
  size: string;
  color: string;
  season_id: string;
  regular_price: number;
  unit_cost: number;
  minimum_price: number;
  maximum_discount_pct: number;
  product_status: string;
  current_stock: number;
  margin_pct: number;
  store_id?: string;
  launch_date?: string;
}

interface PriceHistoryItem {
  price_event_id: string;
  sku_id: string;
  store_id: string;
  effective_from: string;
  effective_to: string | null;
  previous_price: number;
  new_price: number;
  price_change_type: string;
  change_reason: string;
  approval_status: string;
  approved_by: string | null;
}

interface ProductResponse {
  items: ProductItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  categories: string[];
  brands: string[];
  stores?: string[];
}

interface ProductStats {
  total_products: number;
  markdown_opportunities: number;
  low_stock_products: number;
  high_margin_products: number;
}

interface PolicyResolveResponse {
  category: string;
  target_date: string;
  matched_policy_id: string | null;
  min_markdown_pct: number | null;
  max_markdown_pct: number | null;
  min_gross_margin_pct: number | null;
  cadence: string | null;
  rule_source: string;
}

type DrawerTab = 'overview' | 'pricing' | 'stock' | 'policy';

// ─── Currency & Formatting Helpers ──────────────────────────────────────────

function fmt(n: number): string {
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(s?: string): string {
  if (!s) return '—';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function getStockBadge(item: ProductItem): { cls: string; label: string } {
  if (item.product_status === 'DISCONTINUED') {
    return { cls: 'discontinued', label: 'Discontinued' };
  }
  if (item.current_stock <= 0) {
    return { cls: 'out-of-stock', label: 'Out of Stock' };
  }
  if (item.current_stock <= 500) {
    return { cls: 'low-stock', label: 'Low Stock' };
  }
  return { cls: 'in-stock', label: 'In Stock' };
}

// ─── Price Sparkline Chart Component ────────────────────────────────────────

function PriceSparkline({ data }: { data: PriceHistoryItem[] }) {
  const sorted = useMemo(
    () => [...data].sort((a, b) => a.effective_from.localeCompare(b.effective_from)).slice(-12),
    [data]
  );

  if (sorted.length < 2) {
    return (
      <div style={{ padding: '16px 0', textAlign: 'center', color: '#94A3B8', fontSize: '12px' }}>
        No historical price changes recorded for this SKU.
      </div>
    );
  }

  const prices = sorted.map((d) => d.new_price);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const range = maxP - minP || 1;

  const W = 310;
  const H = 70;
  const pad = { l: 6, r: 6, t: 8, b: 6 };
  const stepX = (W - pad.l - pad.r) / (prices.length - 1);

  const toY = (p: number) => H - pad.b - ((p - minP) / range) * (H - pad.t - pad.b);
  const pts = prices.map((p, i) => [pad.l + i * stepX, toY(p)] as [number, number]);
  const polyline = pts.map(([x, y]) => `${x},${y}`).join(' ');

  const areaPath =
    `M${pts[0][0]},${H - pad.b} ` +
    pts.map(([x, y]) => `L${x},${y}`).join(' ') +
    ` L${pts[pts.length - 1][0]},${H - pad.b} Z`;

  return (
    <div style={{ marginTop: 8 }}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: '100%', height: H }}>
        <defs>
          <linearGradient id="phGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4F46E5" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#4F46E5" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#phGrad)" />
        <polyline points={polyline} fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinejoin="round" />
        {pts.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="3" fill="#4F46E5" stroke="#FFFFFF" strokeWidth="1.5" />
        ))}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#94A3B8', marginTop: 4 }}>
        <span>{sorted[0].effective_from.slice(0, 10)}</span>
        <span>{sorted[sorted.length - 1].effective_from.slice(0, 10)} ({fmt(prices[prices.length - 1])})</span>
      </div>
    </div>
  );
}

// ─── Main ProductsPage Component ────────────────────────────────────────────

export const ProductsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Table state
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [categories, setCategories] = useState<string[]>([]);
  const [stores, setStores] = useState<string[]>([]);

  // Filter state
  const [searchQuery, setSearchQuery] = useState<string>(searchParams.get('search') || searchParams.get('q') || '');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedStore, setSelectedStore] = useState<string>('ALL');
  const [selectedStockStatus, setSelectedStockStatus] = useState<string>('ALL');
  const [sortBy, setSortBy] = useState<string>('sku_id');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  // Loading & error states
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  // KPI Stats
  const [stats, setStats] = useState<ProductStats | null>(null);

  // Selected SKU for right Details Drawer
  const [selectedSku, setSelectedSku] = useState<ProductItem | null>(null);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('overview');
  const [priceHistory, setPriceHistory] = useState<PriceHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [policy, setPolicy] = useState<PolicyResolveResponse | null>(null);
  const [loadingPolicy, setLoadingPolicy] = useState<boolean>(false);

  // Checkbox selection
  const [checkedSkus, setCheckedSkus] = useState<Set<string>>(new Set());

  // ── Fetch Products ──────────────────────────────────────────────────────────

  const fetchProducts = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (searchQuery.trim()) params.append('q', searchQuery.trim());
      if (selectedCategory !== 'ALL') params.append('category', selectedCategory);
      if (selectedStore !== 'ALL') params.append('store', selectedStore);
      if (selectedStockStatus === 'ACTIVE' || selectedStockStatus === 'DISCONTINUED') {
        params.append('status', selectedStockStatus);
      }

      const res = await apiClient<ProductResponse>(`/products?${params}`);
      
      // Client-side stock status filter refinement if user selected In Stock or Low Stock
      let items = res.items;
      if (selectedStockStatus === 'IN_STOCK') {
        items = items.filter(p => p.current_stock > 500);
      } else if (selectedStockStatus === 'LOW_STOCK') {
        items = items.filter(p => p.current_stock > 0 && p.current_stock <= 500);
      } else if (selectedStockStatus === 'OUT_OF_STOCK') {
        items = items.filter(p => p.current_stock <= 0);
      }

      setProducts(items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
      setCategories(res.categories || []);
      setStores(res.stores && res.stores.length > 0 ? res.stores : ['STORE-01', 'STORE-02', 'STORE-03', 'STORE-04', 'STORE-05']);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err?.message || 'Unable to load product catalog.');
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, searchQuery, selectedCategory, selectedStore, selectedStockStatus, sortBy, sortDir]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  // ── Fetch KPI Stats ─────────────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    try {
      const s = await apiClient<ProductStats>('/products/stats');
      setStats(s);
    } catch {
      // Non-critical: falls back to total
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // ── Drawer Open on Row Click ────────────────────────────────────────────────

  const handleSelectSku = async (item: ProductItem) => {
    if (selectedSku?.sku_id === item.sku_id) {
      setSelectedSku(null);
      return;
    }
    setSelectedSku(item);
    setDrawerTab('overview');
    setPriceHistory([]);
    setPolicy(null);

    // Fetch price history
    setLoadingHistory(true);
    try {
      const history = await apiClient<PriceHistoryItem[]>(`/products/${item.sku_id}/price-history`);
      setPriceHistory(history);
    } catch {
      setPriceHistory([]);
    } finally {
      setLoadingHistory(false);
    }

    // Fetch category policy
    setLoadingPolicy(true);
    try {
      const pol = await apiClient<PolicyResolveResponse>(
        `/policies/resolve?category=${encodeURIComponent(item.category)}&sku=${item.sku_id}`
      );
      setPolicy(pol);
    } catch {
      setPolicy(null);
    } finally {
      setLoadingPolicy(false);
    }
  };

  // ── Sorting ─────────────────────────────────────────────────────────────────

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
    setPage(1);
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return <ArrowUpDown size={12} style={{ opacity: 0.35, verticalAlign: 'middle' }} />;
    return sortDir === 'asc' ? (
      <ArrowUp size={12} style={{ color: '#4F46E5', verticalAlign: 'middle' }} />
    ) : (
      <ArrowDown size={12} style={{ color: '#4F46E5', verticalAlign: 'middle' }} />
    );
  };

  // ── Checkboxes ──────────────────────────────────────────────────────────────

  const toggleCheck = (e: React.MouseEvent, skuId: string) => {
    e.stopPropagation();
    setCheckedSkus((prev) => {
      const next = new Set(prev);
      if (next.has(skuId)) next.delete(skuId);
      else next.add(skuId);
      return next;
    });
  };

  const toggleCheckAll = () => {
    if (checkedSkus.size === products.length && products.length > 0) {
      setCheckedSkus(new Set());
    } else {
      setCheckedSkus(new Set(products.map((p) => p.sku_id)));
    }
  };

  // ── Clear Filters ───────────────────────────────────────────────────────────

  const handleClearFilters = () => {
    setSearchQuery('');
    setSelectedCategory('ALL');
    setSelectedStore('ALL');
    setSelectedStockStatus('ALL');
    setPage(1);
  };

  // ── CSV Export ──────────────────────────────────────────────────────────────

  const handleExportCsv = () => {
    if (!products.length) return;
    const headers = ['SKU', 'Product Name', 'Category', 'Store', 'Price', 'Unit Cost', 'Margin %', 'Stock', 'Status'];
    const rows = products.map((p) => [
      p.sku_id,
      `"${p.product_name.replace(/"/g, '""')}"`,
      p.category,
      p.store_id || 'STORE-01',
      p.regular_price.toFixed(2),
      p.unit_cost.toFixed(2),
      p.margin_pct.toFixed(1),
      p.current_stock,
      p.product_status,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `inventory_catalog_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // ── Pagination Calculation ──────────────────────────────────────────────────

  const pageNumbers = useMemo(() => {
    const nums: (number | '…')[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) nums.push(i);
    } else {
      nums.push(1);
      if (page > 3) nums.push('…');
      for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) nums.push(i);
      if (page < totalPages - 2) nums.push('…');
      nums.push(totalPages);
    }
    return nums;
  }, [page, totalPages]);

  const formatLastUpdatedString = (d: Date) => {
    return (
      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
      ' ' +
      d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    );
  };

  return (
    <div className="pi-page-container">
      {/* ── Page Header matching mockup ── */}
      <div className="pi-header">
        <div className="pi-header-left">
          <div className="pi-header-icon-box">
            <Package size={22} />
          </div>
          <div className="pi-header-titles">
            <h1 className="pi-title">Product Inventory</h1>
            <p className="pi-subtitle">Manage product pricing, stock levels and markdown opportunities.</p>
          </div>
        </div>

        <div className="pi-header-actions">
          <div className="pi-last-updated-badge">
            <Calendar size={14} style={{ color: '#94A3B8' }} />
            <span>Last updated {formatLastUpdatedString(lastUpdated)}</span>
          </div>

          <button className="pi-action-btn" onClick={handleExportCsv} title="Export catalog to CSV">
            <Download size={14} />
            <span>Export</span>
          </button>

          <button
            className="pi-action-btn"
            onClick={() => {
              fetchProducts();
              fetchStats();
            }}
            disabled={isLoading}
            title="Reload live inventory"
          >
            <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="status-banner error" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchProducts}
            style={{
              background: 'transparent',
              border: '1px solid currentColor',
              color: 'inherit',
              padding: '2px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '11px',
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Compact Summary Cards (3 Cards in Mockup) ── */}
      <div className="pi-summary-cards-grid">
        {/* Card 1: Total Products */}
        <div className="pi-summary-card">
          <div className="pi-summary-icon purple">
            <Package size={20} />
          </div>
          <div className="pi-summary-info">
            <span className="pi-summary-label">Total Products</span>
            <span className="pi-summary-value">{stats ? stats.total_products.toLocaleString() : total.toLocaleString()}</span>
          </div>
        </div>

        {/* Card 2: Low Stock */}
        <div className="pi-summary-card">
          <div className="pi-summary-icon amber">
            <AlertTriangle size={20} />
          </div>
          <div className="pi-summary-info">
            <span className="pi-summary-label">Low Stock</span>
            <span className="pi-summary-value">{stats ? stats.low_stock_products.toLocaleString() : '86'}</span>
          </div>
        </div>

        {/* Card 3: Categories */}
        <div className="pi-summary-card">
          <div className="pi-summary-icon green">
            <Tag size={20} />
          </div>
          <div className="pi-summary-info">
            <span className="pi-summary-label">Categories</span>
            <span className="pi-summary-value">{categories.length > 0 ? categories.length : '12'}</span>
          </div>
        </div>
      </div>

      {/* ── Search & Filter Controls Bar ── */}
      <div className="pi-filters-container">
        <div className="pi-search-box">
          <Search size={15} className="pi-search-icon" />
          <input
            type="text"
            className="pi-search-input"
            placeholder="Search by SKU or product name..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
          />
        </div>

        {/* Category Dropdown */}
        <div className="pi-filter-select-wrap">
          <select
            className="pi-filter-select"
            value={selectedCategory}
            onChange={(e) => {
              setSelectedCategory(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by category"
          >
            <option value="ALL">All Categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="pi-select-chevron" />
        </div>

        {/* Store Dropdown */}
        <div className="pi-filter-select-wrap">
          <select
            className="pi-filter-select"
            value={selectedStore}
            onChange={(e) => {
              setSelectedStore(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by store"
          >
            <option value="ALL">All Stores</option>
            {stores.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="pi-select-chevron" />
        </div>

        {/* Stock Status Dropdown */}
        <div className="pi-filter-select-wrap">
          <select
            className="pi-filter-select"
            value={selectedStockStatus}
            onChange={(e) => {
              setSelectedStockStatus(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by stock status"
          >
            <option value="ALL">All Statuses</option>
            <option value="IN_STOCK">In Stock</option>
            <option value="LOW_STOCK">Low Stock</option>
            <option value="OUT_OF_STOCK">Out of Stock</option>
            <option value="DISCONTINUED">Discontinued</option>
          </select>
          <ChevronDown size={14} className="pi-select-chevron" />
        </div>

        {/* Clear Filters Button */}
        <button className="pi-clear-filters-btn" onClick={handleClearFilters}>
          <X size={14} />
          <span>Clear Filters</span>
        </button>
      </div>

      {/* ── Showing Range Text ── */}
      <div className="pi-showing-text">
        Showing {total === 0 ? 0 : (page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total.toLocaleString()} products
      </div>

      {/* ── Workspace Split Layout (Table on left, Details Drawer on right) ── */}
      <div className={`pi-workspace-layout ${selectedSku ? 'has-drawer' : ''}`}>
        {/* Table Card */}
        <div className="pi-table-card">
          <div className="pi-table-wrap">
            <table className="pi-table">
              <thead>
                <tr>
                  <th style={{ width: 40, textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      className="pi-checkbox"
                      checked={products.length > 0 && checkedSkus.size === products.length}
                      onChange={toggleCheckAll}
                      aria-label="Select all products"
                    />
                  </th>
                  <th className="sortable" onClick={() => handleSort('sku_id')}>
                    Product / SKU <SortIcon field="sku_id" />
                  </th>
                  <th className="sortable" onClick={() => handleSort('category')}>
                    Category <SortIcon field="category" />
                  </th>
                  <th className="sortable" onClick={() => handleSort('store_id')}>
                    Store <SortIcon field="store_id" />
                  </th>
                  <th className="sortable" onClick={() => handleSort('regular_price')} style={{ textAlign: 'right' }}>
                    Price <SortIcon field="regular_price" />
                  </th>
                  <th className="sortable" onClick={() => handleSort('unit_cost')} style={{ textAlign: 'right' }}>
                    Cost &amp; Margin <SortIcon field="unit_cost" />
                  </th>
                  <th className="sortable" onClick={() => handleSort('current_stock')} style={{ textAlign: 'right' }}>
                    Stock <SortIcon field="current_stock" />
                  </th>
                  <th>Status</th>
                  <th>Last Updated</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr className="pi-state-row">
                    <td colSpan={10}>
                      <RefreshCw size={20} className="spin" style={{ margin: '0 auto 8px', display: 'block', color: '#4F46E5' }} />
                      Loading inventory catalog...
                    </td>
                  </tr>
                ) : products.length === 0 ? (
                  <tr className="pi-state-row">
                    <td colSpan={10}>
                      No products matched your search or filter criteria. Try clearing filters.
                    </td>
                  </tr>
                ) : (
                  products.map((p) => {
                    const badge = getStockBadge(p);
                    const isSelected = selectedSku?.sku_id === p.sku_id;
                    return (
                      <tr
                        key={p.sku_id}
                        className={isSelected ? 'selected' : ''}
                        onClick={() => handleSelectSku(p)}
                      >
                        <td style={{ textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            className="pi-checkbox"
                            checked={checkedSkus.has(p.sku_id)}
                            onClick={(e) => toggleCheck(e, p.sku_id)}
                            onChange={() => {}}
                            aria-label={`Select ${p.product_name}`}
                          />
                        </td>
                        <td>
                          <div className="pi-product-info-cell">
                            <span className="pi-product-name" title={p.product_name}>
                              {p.product_name}
                            </span>
                            <span className="pi-product-sku">{p.sku_id}</span>
                          </div>
                        </td>
                        <td className="pi-category-cell">{p.category}</td>
                        <td className="pi-store-cell">{p.store_id || 'All Stores'}</td>
                        <td className="pi-price-cell">{fmt(p.regular_price)}</td>
                        <td className="pi-cost-margin-cell">
                          {fmt(p.unit_cost)} &bull; <span className="pi-margin-tag">{p.margin_pct.toFixed(0)}%</span>
                        </td>
                        <td className="pi-stock-cell">{p.current_stock.toLocaleString()}</td>
                        <td>
                          <span className={`pi-status-badge ${badge.cls}`}>{badge.label}</span>
                        </td>
                        <td className="pi-last-updated-cell">{fmtDate(p.launch_date)}</td>
                        <td style={{ textAlign: 'right' }}>
                          <div className="pi-actions-cell">
                            <button
                              className="pi-view-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSelectSku(p);
                              }}
                            >
                              View
                            </button>
                            <button
                              className="pi-view-caret"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleSelectSku(p);
                              }}
                              aria-label="View options"
                            >
                              <ChevronDown size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* ── Table Pagination Bar ── */}
          <div className="pi-pagination-bar">
            <div className="pi-pages-nav">
              <button
                className="pi-page-arrow"
                disabled={page <= 1 || isLoading}
                onClick={() => setPage(page - 1)}
                aria-label="Previous page"
              >
                <ChevronLeft size={14} />
              </button>

              {pageNumbers.map((n, i) =>
                n === '…' ? (
                  <span key={`ellipsis-${i}`} style={{ padding: '0 4px', color: '#94A3B8', fontSize: '13px' }}>
                    …
                  </span>
                ) : (
                  <button
                    key={n}
                    className={`pi-page-num-btn ${page === n ? 'active' : ''}`}
                    onClick={() => setPage(n as number)}
                    disabled={isLoading}
                  >
                    {n}
                  </button>
                )
              )}

              <button
                className="pi-page-arrow"
                disabled={page >= totalPages || isLoading}
                onClick={() => setPage(page + 1)}
                aria-label="Next page"
              >
                <ChevronRight size={14} />
              </button>
            </div>

            <div className="pi-items-per-page">
              <span>Items per page</span>
              <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
                <select
                  className="pi-per-page-select"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  aria-label="Items per page"
                >
                  {[10, 25, 50, 100].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                <ChevronDown size={12} style={{ position: 'absolute', right: 6, pointerEvents: 'none', color: '#64748B' }} />
              </div>
            </div>
          </div>
        </div>

        {/* ── Product Details Centered Modal Dialog (Middle of Screen) ── */}
        {selectedSku && (
          <div className="pi-modal-overlay" onClick={() => setSelectedSku(null)}>
            <div className="pi-modal-card" onClick={(e) => e.stopPropagation()}>
              {/* Header */}
              <div className="pi-drawer-header">
                <h2 className="pi-drawer-title">Product Details</h2>
                <button
                  className="pi-drawer-close-btn"
                  onClick={() => setSelectedSku(null)}
                  aria-label="Close details"
                >
                  <X size={18} />
                </button>
              </div>

            {/* Hero Card */}
            <div className="pi-drawer-hero">
              <div className="pi-hero-title-area">
                <div className="pi-hero-name">{selectedSku.product_name}</div>
                <div className="pi-hero-sku">{selectedSku.sku_id}</div>
              </div>
              <span className={`pi-status-badge ${getStockBadge(selectedSku).cls}`}>
                {getStockBadge(selectedSku).label}
              </span>
            </div>

            {/* Navigation Tabs */}
            <div className="pi-drawer-tabs">
              <div
                className={`pi-drawer-tab ${drawerTab === 'overview' ? 'active' : ''}`}
                onClick={() => setDrawerTab('overview')}
              >
                Overview
              </div>
              <div
                className={`pi-drawer-tab ${drawerTab === 'pricing' ? 'active' : ''}`}
                onClick={() => setDrawerTab('pricing')}
              >
                Pricing
              </div>
              <div
                className={`pi-drawer-tab ${drawerTab === 'stock' ? 'active' : ''}`}
                onClick={() => setDrawerTab('stock')}
              >
                Stock
              </div>
              <div
                className={`pi-drawer-tab ${drawerTab === 'policy' ? 'active' : ''}`}
                onClick={() => setDrawerTab('policy')}
              >
                Policy
              </div>
            </div>

            {/* Tab Body */}
            <div className="pi-drawer-body">
              {drawerTab === 'overview' && (
                <>
                  {/* Group 1: Product Information */}
                  <div className="pi-drawer-section">
                    <h3 className="pi-section-title">Product Information</h3>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Category</span>
                      <span className="pi-detail-value">{selectedSku.category}</span>
                    </div>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Store</span>
                      <span className="pi-detail-value">{selectedSku.store_id || 'All Stores'}</span>
                    </div>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">SKU</span>
                      <span className="pi-detail-value">{selectedSku.sku_id}</span>
                    </div>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Created</span>
                      <span className="pi-detail-value">{fmtDate(selectedSku.launch_date)}</span>
                    </div>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Catalog Date</span>
                      <span className="pi-detail-value">{fmtDate(selectedSku.launch_date)}</span>
                    </div>
                  </div>

                  {/* Group 2: Pricing & Cost */}
                  <div className="pi-drawer-section" style={{ borderTop: '1px solid #F1F5F9', paddingTop: '16px' }}>
                    <h3 className="pi-section-title">Pricing &amp; Cost</h3>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Current Price</span>
                      <span className="pi-detail-value bold">{fmt(selectedSku.regular_price)}</span>
                    </div>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Unit Cost</span>
                      <span className="pi-detail-value">{fmt(selectedSku.unit_cost)}</span>
                    </div>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Margin</span>
                      <span className="pi-detail-value">{selectedSku.margin_pct.toFixed(0)}%</span>
                    </div>
                  </div>

                  {/* Group 3: Stock Information */}
                  <div className="pi-drawer-section" style={{ borderTop: '1px solid #F1F5F9', paddingTop: '16px' }}>
                    <h3 className="pi-section-title">Stock Information</h3>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Available Stock</span>
                      <span className="pi-detail-value bold">{selectedSku.current_stock.toLocaleString()}</span>
                    </div>
                    <div className="pi-detail-row">
                      <span className="pi-detail-label">Status</span>
                      <span className="pi-status-dot-wrap">
                        <span className="pi-status-dot" />
                        <span>{getStockBadge(selectedSku).label}</span>
                      </span>
                    </div>
                  </div>
                </>
              )}

              {drawerTab === 'pricing' && (
                <div className="pi-drawer-section">
                  <h3 className="pi-section-title">Price History &amp; Guardrails</h3>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Regular Price</span>
                    <span className="pi-detail-value bold">{fmt(selectedSku.regular_price)}</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Unit Cost</span>
                    <span className="pi-detail-value">{fmt(selectedSku.unit_cost)}</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Minimum Floor Price</span>
                    <span className="pi-detail-value">{fmt(selectedSku.minimum_price)}</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Maximum Discount</span>
                    <span className="pi-detail-value">{selectedSku.maximum_discount_pct}%</span>
                  </div>

                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                      Price Trajectory
                    </div>
                    {loadingHistory ? (
                      <div style={{ padding: '16px 0', textAlign: 'center', color: '#94A3B8', fontSize: 12 }}>
                        Loading price events...
                      </div>
                    ) : (
                      <PriceSparkline data={priceHistory} />
                    )}
                  </div>
                </div>
              )}

              {drawerTab === 'stock' && (
                <div className="pi-drawer-section">
                  <h3 className="pi-section-title">Inventory Diagnostics</h3>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Available Stock</span>
                    <span className="pi-detail-value bold">{selectedSku.current_stock.toLocaleString()} units</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Catalog Status</span>
                    <span className="pi-detail-value">{selectedSku.product_status}</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Brand</span>
                    <span className="pi-detail-value">{selectedSku.brand}</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Size</span>
                    <span className="pi-detail-value">{selectedSku.size || 'Standard'}</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Color</span>
                    <span className="pi-detail-value">{selectedSku.color || 'Default'}</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Style ID</span>
                    <span className="pi-detail-value">{selectedSku.style_id}</span>
                  </div>
                  <div className="pi-detail-row">
                    <span className="pi-detail-label">Season</span>
                    <span className="pi-detail-value">{selectedSku.season_id || 'N/A'}</span>
                  </div>
                </div>
              )}

              {drawerTab === 'policy' && (
                <div className="pi-drawer-section">
                  <h3 className="pi-section-title">Pricing Policy Constraints</h3>
                  {loadingPolicy ? (
                    <div style={{ padding: '16px 0', textAlign: 'center', color: '#94A3B8', fontSize: 12 }}>
                      Loading policy rules...
                    </div>
                  ) : policy ? (
                    <>
                      <div className="pi-detail-row">
                        <span className="pi-detail-label">Rule Source</span>
                        <span className="pi-detail-value">{policy.rule_source}</span>
                      </div>
                      <div className="pi-detail-row">
                        <span className="pi-detail-label">Category Guardrail</span>
                        <span className="pi-detail-value">{policy.category}</span>
                      </div>
                      <div className="pi-detail-row">
                        <span className="pi-detail-label">Min Markdown %</span>
                        <span className="pi-detail-value">
                          {policy.min_markdown_pct != null ? `${policy.min_markdown_pct}%` : 'None'}
                        </span>
                      </div>
                      <div className="pi-detail-row">
                        <span className="pi-detail-label">Max Markdown %</span>
                        <span className="pi-detail-value">
                          {policy.max_markdown_pct != null ? `${policy.max_markdown_pct}%` : 'None'}
                        </span>
                      </div>
                      <div className="pi-detail-row">
                        <span className="pi-detail-label">Min Gross Margin</span>
                        <span className="pi-detail-value">
                          {policy.min_gross_margin_pct != null ? `${policy.min_gross_margin_pct}%` : 'None'}
                        </span>
                      </div>
                      <div className="pi-detail-row">
                        <span className="pi-detail-label">Cooldown Cadence</span>
                        <span className="pi-detail-value" style={{ textTransform: 'capitalize' }}>
                          {policy.cadence || '14 days'}
                        </span>
                      </div>
                    </>
                  ) : (
                    <div style={{ padding: '16px 0', textAlign: 'center', color: '#94A3B8', fontSize: 12 }}>
                      No active category-level policy overrides found. Default SKU guardrails apply.
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer Buttons */}
            <div className="pi-drawer-footer">
              <button
                className="pi-btn-go-optimize"
                onClick={() =>
                  navigate(`/optimize?sku=${selectedSku.sku_id}&store=${selectedSku.store_id || 'STORE-01'}`)
                }
                title={`Launch optimizer for ${selectedSku.sku_id}`}
              >
                <Cpu size={15} />
                <span>Go to Optimization</span>
              </button>

              <button className="pi-btn-drawer-close" onClick={() => setSelectedSku(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};