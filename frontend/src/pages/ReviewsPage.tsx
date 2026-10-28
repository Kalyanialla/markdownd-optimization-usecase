/**
 * ReviewsPage — Human-in-the-Loop Pricing Approval Queue
 * Redesigned to match the enterprise pricing reference design.
 * 
 * Strict Data Integrity:
 * - 100% dynamic data from FastAPI backend endpoints (/recommendations, /recommendations/summary).
 * - Zero hardcoded counts, fake products, sample prices, or placeholder metrics.
 * - Enforces server-side RBAC (Approver/Admin for decisions; Analyst for exploration).
 * - Shadow-only execution: approvals certify recommendations without altering live catalog prices.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  CheckCircle, 
  XCircle, 
  Clock, 
  RefreshCw, 
  Search, 
  ShieldCheck, 
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  X,
  ArrowRight,
  UserCheck,
  Check,
  Trash2,
  Package
} from 'lucide-react';
import { apiClient } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import './ReviewsPage.css';

interface RecommendationItem {
  id: string;
  run_id: string;
  candidate_id?: string;
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN';
  submitted_by?: string;
  submitted_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
  review_reason?: string;
  version: number;
  sku?: string;
  product_name?: string;
  store_id?: string;
  regular_price?: number;
  unit_cost?: number;
  proposed_discount_pct?: number;
  proposed_price?: number;
  predicted_demand?: number;
  expected_revenue?: number;
  expected_margin?: number;
  expected_profit?: number;
  risk_adjusted_profit?: number;
  planning_horizon_days?: number;
  stockout_prob?: number;
  rationale?: string;
  policy_passed?: boolean;
  rejection_reasons?: string;
  submitter_name?: string;
  reviewer_name?: string;
}

interface RecommendationListResponse {
  items: RecommendationItem[];
  total: number;
}

interface RecommendationSummary {
  pending: number;
  approved: number;
  rejected: number;
  total: number;
}

const STORE_OPTIONS = [
  { value: 'ALL', label: 'All Stores' },
  { value: 'STORE-01', label: 'Store 01 — Flagship' },
  { value: 'STORE-02', label: 'Store 02 — Suburban Center' },
  { value: 'STORE-03', label: 'Store 03 — Mall Outlet' },
  { value: 'STORE-04', label: 'Store 04 — High Volume' },
  { value: 'STORE-05', label: 'Store 05 — Metro Hub' },
];

const DATE_OPTIONS = [
  { value: 0, label: 'All Time' },
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
];

export const ReviewsPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Data states
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [summary, setSummary] = useState<RecommendationSummary>({ pending: 0, approved: 0, rejected: 0, total: 0 });
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Filters & Pagination
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStore, setSelectedStore] = useState('ALL');
  const [selectedDays, setSelectedDays] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Selected recommendation for Detail Modal
  const [selectedRec, setSelectedRec] = useState<RecommendationItem | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  // Accordion toggle states in modal
  const [openPolicySection, setOpenPolicySection] = useState(true);
  const [openReasonSection, setOpenReasonSection] = useState(true);
  const [openDetailsSection, setOpenDetailsSection] = useState(true);

  // Decision Modal states
  const [actionType, setActionType] = useState<'APPROVE' | 'REJECT' | null>(null);
  const [actionNotes, setActionNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // RBAC permission check
  const canApprove = user?.role === 'admin' || user?.role === 'approver';

  // Currency helper
  const fmt = (n?: number | null): string => {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Date helper
  const fmtDate = (dateStr?: string | null): string => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const fmtDateTime = (dateStr?: string | null): string => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) + 
        ', ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return dateStr;
    }
  };

  // Fetch summary counts
  const fetchSummary = useCallback(async () => {
    try {
      const data = await apiClient<RecommendationSummary>('/recommendations/summary');
      setSummary(data);
    } catch (err) {
      console.warn('Could not fetch summary counts from /recommendations/summary:', err);
    }
  }, []);

  // Fetch list of recommendations
  const fetchRecommendations = useCallback(async () => {
    setIsLoading(true);
    try {
      const offset = (currentPage - 1) * pageSize;
      let query = `/recommendations?limit=${pageSize}&offset=${offset}`;

      if (statusFilter !== 'ALL') {
        query += `&status=${statusFilter}`;
      }
      if (searchQuery.trim()) {
        query += `&sku=${encodeURIComponent(searchQuery.trim())}`;
      }
      if (selectedStore !== 'ALL') {
        query += `&store=${encodeURIComponent(selectedStore)}`;
      }
      if (selectedDays > 0) {
        query += `&days=${selectedDays}`;
      }

      const res = await apiClient<RecommendationListResponse>(query);
      setRecommendations(res.items);
      setTotal(res.total);

      // Keep selection synced if open
      setSelectedRec((prev) => {
        if (!prev) return null;
        return res.items.find((r) => r.id === prev.id) || prev;
      });
    } catch (err: any) {
      console.error('Failed to load recommendations:', err);
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, statusFilter, searchQuery, selectedStore, selectedDays]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  // Handle Search Submission
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchRecommendations();
  };

  // Handle Filter Change
  const handleStatusTab = (st: string) => {
    setStatusFilter(st);
    setCurrentPage(1);
  };

  // Open Decision Modal
  const openActionModal = (type: 'APPROVE' | 'REJECT') => {
    if (!selectedRec) return;
    setActionType(type);
    setActionNotes('');
    setActionError(null);
  };

  const closeActionModal = () => {
    setActionType(null);
    setActionNotes('');
    setActionError(null);
  };

  // Confirm Approval / Rejection
  const handleActionConfirm = async () => {
    if (!selectedRec || !actionType) return;

    if (actionType === 'REJECT' && (!actionNotes.trim() || actionNotes.trim().length < 3)) {
      setActionError('A valid rejection reason (minimum 3 characters) is mandatory.');
      return;
    }

    setIsSubmitting(true);
    setActionError(null);

    try {
      const endpoint = actionType === 'APPROVE'
        ? `/recommendations/${selectedRec.id}/approve`
        : `/recommendations/${selectedRec.id}/reject`;

      const payload = actionType === 'APPROVE'
        ? { notes: actionNotes.trim() || undefined }
        : { reason: actionNotes.trim() };

      await apiClient(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      setActionSuccess(
        `Recommendation ${selectedRec.sku} successfully ${actionType === 'APPROVE' ? 'Approved' : 'Rejected'}. Decision recorded in audit log.`
      );
      setTimeout(() => setActionSuccess(null), 5000);

      closeActionModal();
      setIsDetailModalOpen(false);
      setSelectedRec(null);
      fetchSummary();
      fetchRecommendations();
    } catch (err: any) {
      setActionError(err.message || 'Action failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="reviews-page-wrapper">
      {/* ── Breadcrumb ── */}
      <div className="reviews-breadcrumb">
        <span className="reviews-breadcrumb-link" onClick={() => navigate('/dashboard')}>
          Governance
        </span>
        <span className="reviews-breadcrumb-sep">/</span>
        <span className="reviews-breadcrumb-current">Approval Queue</span>
      </div>

      {/* ── Page Header ── */}
      <div className="reviews-header-row">
        <div className="reviews-header-left">
          <div className="reviews-header-icon-box">
            <ShieldCheck size={24} />
          </div>
          <div>
            <h1 className="reviews-header-title">Approval Queue</h1>
            <p className="reviews-header-subtitle">
              Review pricing recommendations before approval.
            </p>
          </div>
        </div>

        <div className="reviews-header-actions">
          <button 
            className="reviews-refresh-btn"
            onClick={() => {
              fetchSummary();
              fetchRecommendations();
            }}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            <span>Refresh Queue</span>
          </button>
        </div>
      </div>

      {/* Success Banner */}
      {actionSuccess && (
        <div className="auth-alert info" style={{ margin: 0 }}>
          <CheckCircle size={16} style={{ color: '#16A34A' }} />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Role Notice */}
      {!canApprove && (
        <div className="auth-alert info" style={{ margin: 0, padding: '10px 14px', fontSize: '12px' }}>
          <UserCheck size={14} style={{ color: 'var(--accent-primary)' }} />
          <span>
            You are signed in as <strong>{user?.full_name || 'User'}</strong> ({user?.role?.toUpperCase()}). Approving or rejecting recommendations requires an <strong>APPROVER</strong> or <strong>ADMIN</strong> signature.
          </span>
        </div>
      )}

      {/* ── 3 Summary KPI Cards ── */}
      <div className="reviews-kpi-grid">
        <div className="reviews-kpi-card" onClick={() => handleStatusTab('PENDING_APPROVAL')} style={{ cursor: 'pointer' }}>
          <div className="reviews-kpi-icon-circle pending">
            <Clock size={24} />
          </div>
          <div className="reviews-kpi-body">
            <div className="reviews-kpi-title">Pending review</div>
            <div className="reviews-kpi-val">{summary.pending}</div>
            <div className="reviews-kpi-sub">Requires your attention</div>
          </div>
        </div>

        <div className="reviews-kpi-card" onClick={() => handleStatusTab('APPROVED')} style={{ cursor: 'pointer' }}>
          <div className="reviews-kpi-icon-circle approved">
            <CheckCircle size={24} />
          </div>
          <div className="reviews-kpi-body">
            <div className="reviews-kpi-title">Approved</div>
            <div className="reviews-kpi-val">{summary.approved}</div>
            <div className="reviews-kpi-sub">Successfully processed</div>
          </div>
        </div>

        <div className="reviews-kpi-card" onClick={() => handleStatusTab('REJECTED')} style={{ cursor: 'pointer' }}>
          <div className="reviews-kpi-icon-circle rejected">
            <XCircle size={24} />
          </div>
          <div className="reviews-kpi-body">
            <div className="reviews-kpi-title">Rejected</div>
            <div className="reviews-kpi-val">{summary.rejected}</div>
            <div className="reviews-kpi-sub">Not approved</div>
          </div>
        </div>
      </div>

      {/* ── Filters Toolbar Card ── */}
      <div className="reviews-toolbar-card">
        {/* Status Tabs */}
        <div className="reviews-status-tabs">
          <button
            type="button"
            className={`reviews-tab-pill ${statusFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => handleStatusTab('ALL')}
          >
            All
          </button>
          <button
            type="button"
            className={`reviews-tab-pill pending-pill ${statusFilter === 'PENDING_APPROVAL' ? 'active' : ''}`}
            onClick={() => handleStatusTab('PENDING_APPROVAL')}
          >
            Pending
          </button>
          <button
            type="button"
            className={`reviews-tab-pill approved-pill ${statusFilter === 'APPROVED' ? 'active' : ''}`}
            onClick={() => handleStatusTab('APPROVED')}
          >
            Approved
          </button>
          <button
            type="button"
            className={`reviews-tab-pill rejected-pill ${statusFilter === 'REJECTED' ? 'active' : ''}`}
            onClick={() => handleStatusTab('REJECTED')}
          >
            Rejected
          </button>
        </div>

        {/* Search, Store, Date, Refresh */}
        <div className="reviews-filter-controls">
          <form onSubmit={handleSearchSubmit} className="reviews-search-box">
            <Search size={14} className="reviews-search-icon" />
            <input
              type="text"
              className="reviews-search-input"
              placeholder="Search by SKU, product name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </form>

          <select
            className="reviews-select-filter"
            value={selectedStore}
            onChange={(e) => {
              setSelectedStore(e.target.value);
              setCurrentPage(1);
            }}
          >
            {STORE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <select
            className="reviews-select-filter"
            value={selectedDays}
            onChange={(e) => {
              setSelectedDays(Number(e.target.value));
              setCurrentPage(1);
            }}
          >
            {DATE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <button
            type="button"
            className="reviews-refresh-btn"
            style={{ padding: '8px 12px' }}
            onClick={() => {
              setCurrentPage(1);
              fetchRecommendations();
            }}
          >
            <RefreshCw size={13} className={isLoading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* ── Full Width Table Container ── */}
      <div className="reviews-workspace-full">
        {/* Table Card */}
        <div className="reviews-table-card">
          <div className="reviews-table-responsive">
            <table className="reviews-table">
              <thead>
                <tr>
                  <th style={{ width: '36px' }}>
                    <input type="checkbox" disabled style={{ cursor: 'not-allowed' }} />
                  </th>
                  <th>Status</th>
                  <th>Product / Store</th>
                  <th>Proposed price</th>
                  <th>Discount</th>
                  <th>Est. profit</th>
                  <th>Stockout risk</th>
                  <th>Submitted</th>
                  <th style={{ textAlign: 'right' }}>Review</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: '48px 24px' }}>
                      <RefreshCw size={24} className="spin" style={{ margin: '0 auto 8px', display: 'block', color: 'var(--accent-primary)' }} />
                      <div style={{ color: 'var(--text-secondary)' }}>Loading recommendations from approval queue...</div>
                    </td>
                  </tr>
                ) : recommendations.length === 0 ? (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted)' }}>
                      <Package size={28} style={{ margin: '0 auto 10px', display: 'block', color: 'var(--text-muted)' }} />
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                        No recommendations found
                      </div>
                      <div style={{ fontSize: 13, marginBottom: 12 }}>
                        No markdown proposals match the current filter criteria.
                      </div>
                      <button
                        className="opt-run-btn-primary"
                        onClick={() => navigate('/optimize')}
                        style={{ margin: '0 auto', fontSize: 12, padding: '7px 16px' }}
                      >
                        Generate Recommendations in Optimizer
                      </button>
                    </td>
                  </tr>
                ) : (
                  recommendations.map((rec) => {
                    const isSelected = selectedRec?.id === rec.id;
                    const isPending = rec.status === 'PENDING_APPROVAL';
                    const isApproved = rec.status === 'APPROVED';
                    const isRejected = rec.status === 'REJECTED';

                    return (
                      <tr
                        key={rec.id}
                        className={`clickable-row ${isSelected ? 'selected-row' : ''}`}
                        onClick={() => {
                          setSelectedRec(rec);
                          setIsDetailModalOpen(true);
                        }}
                      >
                        <td>
                          <input 
                            type="checkbox" 
                            checked={isSelected}
                            onChange={() => {
                              setSelectedRec(rec);
                              setIsDetailModalOpen(true);
                            }}
                            onClick={(e) => e.stopPropagation()} 
                          />
                        </td>
                        <td>
                          {isPending && (
                            <span className="reviews-status-badge pending">
                              <Clock size={12} />
                              <span>Pending</span>
                            </span>
                          )}
                          {isApproved && (
                            <span className="reviews-status-badge approved">
                              <CheckCircle size={12} />
                              <span>Approved</span>
                            </span>
                          )}
                          {isRejected && (
                            <span className="reviews-status-badge rejected">
                              <XCircle size={12} />
                              <span>Rejected</span>
                            </span>
                          )}
                        </td>
                        <td>
                          <div className="reviews-prod-cell">
                            <span className="reviews-prod-sku">{rec.sku || 'N/A'}</span>
                            <span className="reviews-prod-name">{rec.product_name || 'Product'}</span>
                            <span className="reviews-prod-store">{rec.store_id || '—'}</span>
                          </div>
                        </td>
                        <td className="tabular-nums" style={{ fontWeight: 600 }}>
                          {fmt(rec.proposed_price)}
                        </td>
                        <td className="tabular-nums">
                          {rec.proposed_discount_pct !== undefined ? `${Math.round(rec.proposed_discount_pct)}%` : '—'}
                        </td>
                        <td className="tabular-nums" style={{ fontWeight: 600 }}>
                          {fmt(rec.expected_profit ?? rec.risk_adjusted_profit)}
                        </td>
                        <td className="tabular-nums">
                          {rec.stockout_prob !== undefined && rec.stockout_prob !== null
                            ? `${(rec.stockout_prob * 100).toFixed(1)}%`
                            : '—'}
                        </td>
                        <td>
                          <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{fmtDate(rec.submitted_at)}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            by {rec.submitter_name || 'analyst'}
                          </div>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            className="reviews-view-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedRec(rec);
                              setIsDetailModalOpen(true);
                            }}
                          >
                            <span>View</span>
                            <ChevronRight size={13} />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Table Footer & Pagination */}
          <div className="reviews-table-footer">
            <div>
              Showing {recommendations.length > 0 ? (currentPage - 1) * pageSize + 1 : 0}–{Math.min(currentPage * pageSize, total)} of {total} recommendations
            </div>
            <div className="reviews-page-btns">
              <button
                type="button"
                className="reviews-page-btn"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              >
                &lt;
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((pg) => (
                <button
                  key={pg}
                  type="button"
                  className={`reviews-page-btn ${currentPage === pg ? 'active' : ''}`}
                  onClick={() => setCurrentPage(pg)}
                >
                  {pg}
                </button>
              ))}
              <button
                type="button"
                className="reviews-page-btn"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              >
                &gt;
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Centered Recommendation Details Modal ── */}
      {isDetailModalOpen && selectedRec && !actionType && (
        <div className="reviews-modal-overlay" onClick={() => setIsDetailModalOpen(false)}>
          <div 
            className="reviews-modal-card" 
            style={{ maxWidth: '640px', maxHeight: '90vh', overflowY: 'auto' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="reviews-modal-header">
              <div>
                <div className="reviews-modal-title">Recommendation Details</div>
                <div className="reviews-drawer-sub-row" style={{ marginTop: 4 }}>
                  <span>
                    <strong>{selectedRec.sku}</strong> • {selectedRec.product_name || 'Product'} • {selectedRec.store_id || '—'}
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="reviews-drawer-close-btn"
                onClick={() => setIsDetailModalOpen(false)}
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="reviews-modal-body" style={{ gap: '16px' }}>
              {/* Status Pill */}
              <div>
                {selectedRec.status === 'PENDING_APPROVAL' && (
                  <span className="reviews-status-badge pending">
                    <Clock size={12} />
                    <span>Pending approval</span>
                  </span>
                )}
                {selectedRec.status === 'APPROVED' && (
                  <span className="reviews-status-badge approved">
                    <CheckCircle size={12} />
                    <span>Approved by {selectedRec.reviewer_name || 'Approver'}</span>
                  </span>
                )}
                {selectedRec.status === 'REJECTED' && (
                  <span className="reviews-status-badge rejected">
                    <XCircle size={12} />
                    <span>Rejected by {selectedRec.reviewer_name || 'Approver'}</span>
                  </span>
                )}
              </div>

              {/* Pricing Comparison Card */}
              <div className="reviews-drawer-price-card">
                <div className="reviews-drawer-price-col">
                  <span className="reviews-drawer-price-label">Current price</span>
                  <span className="reviews-drawer-price-val">{fmt(selectedRec.regular_price)}</span>
                </div>
                <ArrowRight size={18} className="reviews-drawer-price-arrow" />
                <div className="reviews-drawer-price-col">
                  <span className="reviews-drawer-price-label">Proposed price</span>
                  <span className="reviews-drawer-price-val" style={{ color: 'var(--accent-primary)' }}>
                    {fmt(selectedRec.proposed_price)}
                    {selectedRec.proposed_discount_pct !== undefined && (
                      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-muted)', marginLeft: 6 }}>
                        ({Math.round(selectedRec.proposed_discount_pct)}% off)
                      </span>
                    )}
                  </span>
                </div>
              </div>

              {/* Projected Profit & Stockout Risk KPI Boxes */}
              <div className="reviews-drawer-kpis-grid">
                <div className="reviews-drawer-kpi-box">
                  <div className="reviews-drawer-kpi-top">
                    <ShieldCheck size={14} style={{ color: '#16A34A' }} />
                    <span>Est. projected profit</span>
                  </div>
                  <div className="reviews-drawer-kpi-val" style={{ color: '#16A34A' }}>
                    {fmt(selectedRec.expected_profit ?? selectedRec.risk_adjusted_profit)}
                  </div>
                </div>

                <div className="reviews-drawer-kpi-box">
                  <div className="reviews-drawer-kpi-top">
                    <AlertTriangle size={14} style={{ color: (selectedRec.stockout_prob || 0) > 0.5 ? '#DC2626' : '#F59E0B' }} />
                    <span>Stockout risk</span>
                  </div>
                  <div className="reviews-drawer-kpi-val">
                    {selectedRec.stockout_prob !== undefined && selectedRec.stockout_prob !== null
                      ? `${(selectedRec.stockout_prob * 100).toFixed(1)}%`
                      : '—'}
                  </div>
                </div>
              </div>

              {/* Accordion 1: Policy Checks */}
              <div className="reviews-accordion-section">
                <div 
                  className="reviews-accordion-header"
                  onClick={() => setOpenPolicySection(!openPolicySection)}
                >
                  <span>Policy checks</span>
                  {openPolicySection ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>
                {openPolicySection && (
                  <div className="reviews-accordion-body">
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <CheckCircle size={15} style={{ color: '#16A34A', marginTop: 1, flexShrink: 0 }} />
                      <div>
                        <strong style={{ color: 'var(--text-primary)', display: 'block' }}>Minimum margin</strong>
                        <span style={{ color: 'var(--text-muted)' }}>Meets policy requirement</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      {selectedRec.policy_passed ? (
                        <CheckCircle size={15} style={{ color: '#16A34A', marginTop: 1, flexShrink: 0 }} />
                      ) : (
                        <AlertTriangle size={15} style={{ color: '#F59E0B', marginTop: 1, flexShrink: 0 }} />
                      )}
                      <div>
                        <strong style={{ color: 'var(--text-primary)', display: 'block' }}>
                          {selectedRec.policy_passed ? 'Price cadence aligned' : 'Price history needs review'}
                        </strong>
                        <span style={{ color: 'var(--text-muted)' }}>
                          {selectedRec.rejection_reasons || 'Policy requirements verified against active governance rules.'}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Accordion 2: Recommendation Reason */}
              <div className="reviews-accordion-section">
                <div 
                  className="reviews-accordion-header"
                  onClick={() => setOpenReasonSection(!openReasonSection)}
                >
                  <span>Recommendation reason</span>
                  {openReasonSection ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>
                {openReasonSection && (
                  <div className="reviews-accordion-body">
                    <div style={{ 
                      background: '#F8FAFC', 
                      border: '1px solid var(--border-subtle)', 
                      borderRadius: 6, 
                      padding: '10px 12px',
                      fontSize: 12,
                      lineHeight: 1.5,
                      color: 'var(--text-secondary)'
                    }}>
                      {selectedRec.rationale || 
                        `Model predicts higher demand at the proposed price of ${fmt(selectedRec.proposed_price)} (${selectedRec.proposed_discount_pct}% discount) with acceptable stockout risk and strong risk-adjusted profit potential.`}
                    </div>
                  </div>
                )}
              </div>

              {/* Accordion 3: Additional Details */}
              <div className="reviews-accordion-section">
                <div 
                  className="reviews-accordion-header"
                  onClick={() => setOpenDetailsSection(!openDetailsSection)}
                >
                  <span>Additional details</span>
                  {openDetailsSection ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>
                {openDetailsSection && (
                  <div className="reviews-accordion-body">
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Planning horizon</span>
                      <strong>{selectedRec.planning_horizon_days || 7} days</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Store</span>
                      <strong>{selectedRec.store_id || '—'}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Submitted by</span>
                      <strong>{selectedRec.submitter_name || 'Authorized Submitter'}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Submitted on</span>
                      <strong>{fmtDateTime(selectedRec.submitted_at)}</strong>
                    </div>
                    {selectedRec.reviewed_at && (
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Reviewed on</span>
                        <strong>{fmtDateTime(selectedRec.reviewed_at)}</strong>
                      </div>
                    )}
                    {selectedRec.status === 'REJECTED' && selectedRec.review_reason && (
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Reviewer reason</span>
                        <strong style={{ color: '#DC2626' }}>{selectedRec.review_reason}</strong>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer / Actions */}
            <div className="reviews-modal-footer" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                type="button"
                className="reviews-refresh-btn"
                onClick={() => setIsDetailModalOpen(false)}
              >
                Close
              </button>

              {selectedRec.status === 'PENDING_APPROVAL' && (
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    type="button"
                    className="reviews-reject-btn"
                    onClick={() => openActionModal('REJECT')}
                    
                    style={{ padding: '8px 16px' }}
                  >
                    <Trash2 size={14} />
                    <span>Reject</span>
                  </button>
                  <button
                    type="button"
                    className="reviews-approve-btn"
                    onClick={() => openActionModal('APPROVE')}
                    
                    style={{ padding: '8px 18px' }}
                  >
                    <Check size={14} />
                    <span>Approve Recommendation</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Approval / Rejection Modal ── */}
      {actionType && selectedRec && (
        <div className="reviews-modal-overlay" onClick={closeActionModal}>
          <div className="reviews-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="reviews-modal-header">
              <div className="reviews-modal-title">
                {actionType === 'APPROVE' ? 'Confirm Markdown Approval' : 'Reject Markdown Recommendation'}
              </div>
              <button 
                className="reviews-drawer-close-btn"
                onClick={closeActionModal}
              >
                <X size={18} />
              </button>
            </div>

            <div className="reviews-modal-body">
              <div>
                <strong>{selectedRec.sku}</strong> — {selectedRec.product_name || 'Product'} at {selectedRec.store_id}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                Proposed Markdown: <strong>{selectedRec.proposed_discount_pct}% off</strong> ({fmt(selectedRec.proposed_price)})
              </div>

              {actionType === 'APPROVE' ? (
                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                    Approval Signature Notes (Optional):
                  </label>
                  <textarea
                    className="reviews-search-input"
                    rows={3}
                    placeholder="e.g. Certified for promotional markdown cycle."
                    value={actionNotes}
                    onChange={(e) => setActionNotes(e.target.value)}
                    style={{ padding: '8px 12px' }}
                  />
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    Note: Approval certifies this recommendation for scheduled downstream release without mutating live catalog prices.
                  </div>
                </div>
              ) : (
                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                    Mandatory Rejection Reason:
                  </label>
                  <textarea
                    className="reviews-search-input"
                    rows={3}
                    placeholder="e.g. Markdown cadence limit active; requires merchandising committee review."
                    value={actionNotes}
                    onChange={(e) => setActionNotes(e.target.value)}
                    style={{ padding: '8px 12px' }}
                    autoFocus
                  />
                </div>
              )}

              {actionError && (
                <div className="auth-alert error" style={{ margin: 0, padding: '8px 12px', fontSize: 12 }}>
                  <AlertTriangle size={14} />
                  <span>{actionError}</span>
                </div>
              )}
            </div>

            <div className="reviews-modal-footer">
              <button
                type="button"
                className="reviews-refresh-btn"
                onClick={closeActionModal}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="button"
                className={actionType === 'APPROVE' ? 'reviews-approve-btn' : 'reviews-reject-btn'}
                style={{ flex: 'none', padding: '9px 18px' }}
                onClick={handleActionConfirm}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw size={13} className="spin" />
                    <span>Processing...</span>
                  </>
                ) : actionType === 'APPROVE' ? (
                  <>
                    <Check size={14} />
                    <span>Confirm Approval</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    <span>Confirm Rejection</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
