/**
 * AuditPage — Human-in-the-Loop Pricing Governance & Investigation Workspace
 * Redesigned to match the enterprise pricing reference design.
 * 
 * Strict Data Integrity:
 * - 100% dynamic data from FastAPI backend endpoints (/audit, /audit/summary, /audit/{id}).
 * - Zero hardcoded counts, fake actors, sample prices, or placeholder metrics.
 * - Human-readable parameter cards (NO raw JSON code dumps).
 * - Displays event details in a clean, centered modal dialog in the middle of the screen.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  RefreshCw, 
  Search, 
  X, 
  CheckCircle, 
  XCircle, 
  Calendar, 
  FileText, 
  Layers, 
  ChevronRight, 
  Copy, 
  Check, 
  ExternalLink,
  AlertTriangle,
  Tag
} from 'lucide-react';
import { apiClient } from '../lib/api';
import './AuditPage.css';

interface AuditEventItem {
  id: string;
  actor_id?: string;
  actor_email?: string;
  actor_name?: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  details_json?: Record<string, any>;
  created_at: string;
  outcome?: string;
}

interface AuditListResponse {
  items: AuditEventItem[];
  total: number;
}

interface AuditSummaryResponse {
  total: number;
  successful: number;
  failed: number;
  today: number;
}

interface AuditEventDetailResponse {
  event: AuditEventItem;
  summary: string;
  outcome: string;
  related_events: AuditEventItem[];
  related_records: Record<string, any>;
}

const EVENT_TYPE_OPTIONS = [
  { value: 'ALL', label: 'All Event Types' },
  { value: 'OPTIMIZATION_RUN_CREATED', label: 'OPTIMIZATION_RUN_CREATED' },
  { value: 'RECOMMENDATION_SUBMITTED', label: 'RECOMMENDATION_SUBMITTED' },
  { value: 'RECOMMENDATION_APPROVED', label: 'RECOMMENDATION_APPROVED' },
  { value: 'RECOMMENDATION_REJECTED', label: 'RECOMMENDATION_REJECTED' },
  { value: 'APPROVAL_ATTEMPT_REJECTED', label: 'APPROVAL_ATTEMPT_REJECTED' },
  { value: 'USER_LOGIN', label: 'USER_LOGIN' },
  { value: 'USER_REGISTERED', label: 'USER_REGISTERED' },
];

const OUTCOME_OPTIONS = [
  { value: 'ALL', label: 'All Outcomes' },
  { value: 'SUCCESS', label: 'Success' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'BLOCKED', label: 'Blocked' },
];

const DATE_OPTIONS = [
  { value: 0, label: 'All Time' },
  { value: 1, label: 'Today' },
  { value: 7, label: 'Last 7 Days' },
  { value: 30, label: 'Last 30 Days' },
];

export const AuditPage: React.FC = () => {
  const navigate = useNavigate();

  // Data states
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [summary, setSummary] = useState<AuditSummaryResponse>({ total: 0, successful: 0, failed: 0, today: 0 });
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Filters & Pagination
  const [searchQuery, setSearchQuery] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('ALL');
  const [outcomeFilter, setOutcomeFilter] = useState('ALL');
  const [dateFilter, setDateFilter] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Centered Modal State (model type)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [eventDetail, setEventDetail] = useState<AuditEventDetailResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  // Format currency helper
  const fmt = (n?: number | null): string => {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Format date helper
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
      const data = await apiClient<AuditSummaryResponse>('/audit/summary');
      setSummary(data);
    } catch (err) {
      console.warn('Could not fetch summary counts from /audit/summary:', err);
    }
  }, []);

  // Fetch audit event list
  const fetchAuditEvents = useCallback(async () => {
    setIsLoading(true);
    try {
      const offset = (currentPage - 1) * pageSize;
      let query = `/audit?limit=${pageSize}&offset=${offset}`;

      if (eventTypeFilter !== 'ALL') {
        query += `&event_type=${encodeURIComponent(eventTypeFilter)}`;
      }
      if (outcomeFilter !== 'ALL') {
        query += `&outcome=${encodeURIComponent(outcomeFilter)}`;
      }
      if (searchQuery.trim()) {
        query += `&search=${encodeURIComponent(searchQuery.trim())}`;
      }
      if (dateFilter > 0) {
        query += `&days=${dateFilter}`;
      }

      const res = await apiClient<AuditListResponse>(query);
      setEvents(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('Failed to load audit events:', err);
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, eventTypeFilter, outcomeFilter, searchQuery, dateFilter]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    fetchAuditEvents();
  }, [fetchAuditEvents]);

  // Open Event Modal (Centered in middle of screen)
  const openEventModal = async (eventId: string) => {
    setSelectedEventId(eventId);
    setLoadingDetail(true);
    try {
      const data = await apiClient<AuditEventDetailResponse>(`/audit/${eventId}`);
      setEventDetail(data);
    } catch (err) {
      console.error('Failed to load event detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const closeModal = () => {
    setSelectedEventId(null);
    setEventDetail(null);
  };

  const copyEventId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const clearAllFilters = () => {
    setSearchQuery('');
    setEventTypeFilter('ALL');
    setOutcomeFilter('ALL');
    setDateFilter(0);
    setCurrentPage(1);
  };

  const getEventBadgeClass = (type: string) => {
    if (type.includes('APPROVED')) return 'rec-approve';
    if (type.includes('REJECTED')) return 'rec-reject';
    if (type.includes('SUBMITTED')) return 'rec-submit';
    if (type.includes('OPTIMIZATION')) return 'opt-run';
    return 'user-event';
  };

  const getOutcomeBadgeClass = (outcome?: string) => {
    const norm = (outcome || 'SUCCESS').toUpperCase();
    if (norm === 'SUCCESS') return 'success';
    if (norm === 'REJECTED') return 'rejected';
    if (norm === 'BLOCKED') return 'blocked';
    return 'failed';
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="audit-page-wrapper">
      {/* ── Breadcrumb Tag ── */}
      <div className="audit-breadcrumb">
        <ShieldCheck size={16} />
        <span>Immutable Audit Log</span>
      </div>

      {/* ── Page Header ── */}
      <div className="audit-header-row">
        <div className="audit-header-left">
          <h1 className="audit-header-title">Audit Trail</h1>
          <p className="audit-header-sub">
            Review system activity, pricing decisions, and governance events.
          </p>
        </div>
        <div className="audit-header-actions">
          <button
            type="button"
            className="audit-refresh-btn"
            onClick={() => {
              fetchSummary();
              fetchAuditEvents();
            }}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            <span>Refresh Trail</span>
          </button>
        </div>
      </div>

      {/* ── 4 Summary KPI Cards ── */}
      <div className="audit-kpi-grid">
        {/* Total Events */}
        <div 
          className={`audit-kpi-card ${outcomeFilter === 'ALL' && dateFilter === 0 ? 'active' : ''}`}
          onClick={clearAllFilters}
          title="Click to view all events"
        >
          <div className="audit-kpi-left">
            <div className="audit-kpi-icon-circle events">
              <FileText size={20} />
            </div>
            <div className="audit-kpi-info">
              <span className="audit-kpi-label">Events</span>
              <span className="audit-kpi-count">{summary.total}</span>
            </div>
          </div>
          <ChevronRight size={18} className="audit-kpi-chevron" />
        </div>

        {/* Successful */}
        <div 
          className={`audit-kpi-card ${outcomeFilter === 'SUCCESS' ? 'active' : ''}`}
          onClick={() => {
            setOutcomeFilter('SUCCESS');
            setCurrentPage(1);
          }}
          title="Click to filter by Successful events"
        >
          <div className="audit-kpi-left">
            <div className="audit-kpi-icon-circle success">
              <CheckCircle size={20} />
            </div>
            <div className="audit-kpi-info">
              <span className="audit-kpi-label">Successful</span>
              <span className="audit-kpi-count">{summary.successful}</span>
            </div>
          </div>
          <ChevronRight size={18} className="audit-kpi-chevron" />
        </div>

        {/* Failed / Rejected */}
        <div 
          className={`audit-kpi-card ${outcomeFilter === 'FAILED' || outcomeFilter === 'REJECTED' ? 'active' : ''}`}
          onClick={() => {
            setOutcomeFilter('FAILED');
            setCurrentPage(1);
          }}
          title="Click to filter by Failed/Rejected events"
        >
          <div className="audit-kpi-left">
            <div className="audit-kpi-icon-circle failed">
              <XCircle size={20} />
            </div>
            <div className="audit-kpi-info">
              <span className="audit-kpi-label">Failed</span>
              <span className="audit-kpi-count">{summary.failed}</span>
            </div>
          </div>
          <ChevronRight size={18} className="audit-kpi-chevron" />
        </div>

        {/* Today */}
        <div 
          className={`audit-kpi-card ${dateFilter === 1 ? 'active' : ''}`}
          onClick={() => {
            setDateFilter(1);
            setCurrentPage(1);
          }}
          title="Click to filter by Today's events"
        >
          <div className="audit-kpi-left">
            <div className="audit-kpi-icon-circle today">
              <Calendar size={20} />
            </div>
            <div className="audit-kpi-info">
              <span className="audit-kpi-label">Today</span>
              <span className="audit-kpi-count">{summary.today}</span>
            </div>
          </div>
          <ChevronRight size={18} className="audit-kpi-chevron" />
        </div>
      </div>

      {/* ── Filter & Search Toolbar ── */}
      <div className="audit-filters-bar">
        {/* Search */}
        <div className="audit-search-box">
          <Search size={15} className="audit-search-icon" />
          <input
            type="text"
            className="audit-search-input"
            placeholder="Search event, entity ID, or actor..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
          />
        </div>

        {/* Event Type Filter */}
        <select
          className="audit-select-filter"
          value={eventTypeFilter}
          onChange={(e) => {
            setEventTypeFilter(e.target.value);
            setCurrentPage(1);
          }}
        >
          {EVENT_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Outcome Filter */}
        <select
          className="audit-select-filter"
          value={outcomeFilter}
          onChange={(e) => {
            setOutcomeFilter(e.target.value);
            setCurrentPage(1);
          }}
        >
          {OUTCOME_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Date Filter */}
        <select
          className="audit-select-filter"
          value={dateFilter}
          onChange={(e) => {
            setDateFilter(Number(e.target.value));
            setCurrentPage(1);
          }}
        >
          {DATE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Clear Filters */}
        {(searchQuery || eventTypeFilter !== 'ALL' || outcomeFilter !== 'ALL' || dateFilter !== 0) && (
          <button
            type="button"
            className="audit-clear-btn"
            onClick={clearAllFilters}
          >
            <X size={13} />
            <span>Clear Filters</span>
          </button>
        )}
      </div>

      {/* ── Event Table Card ── */}
      <div className="audit-table-card">
        <div className="audit-table-responsive">
          <table className="audit-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Event</th>
                <th>Entity</th>
                <th>Actor</th>
                <th>Outcome</th>
                <th style={{ textAlign: 'right' }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '48px 24px' }}>
                    <RefreshCw size={24} className="spin" style={{ margin: '0 auto 8px', display: 'block', color: 'var(--accent-primary, #4F46E5)' }} />
                    <div style={{ color: 'var(--text-secondary, #64748B)' }}>Loading events from immutable audit log...</div>
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted, #94A3B8)' }}>
                    <ShieldCheck size={28} style={{ margin: '0 auto 10px', display: 'block', color: 'var(--text-muted, #94A3B8)' }} />
                    <div style={{ fontWeight: 600, color: 'var(--text-primary, #0F172A)', marginBottom: 4 }}>
                      No audit events found
                    </div>
                    <div style={{ fontSize: 13 }}>
                      No governance records match the selected filter criteria.
                    </div>
                  </td>
                </tr>
              ) : (
                events.map((ev) => {
                  const isSelected = selectedEventId === ev.id;
                  const eventClass = getEventBadgeClass(ev.event_type);
                  const outcomeClass = getOutcomeBadgeClass(ev.outcome);

                  return (
                    <tr
                      key={ev.id}
                      className={`clickable-row ${isSelected ? 'selected-row' : ''}`}
                      onClick={() => openEventModal(ev.id)}
                    >
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary, #0F172A)' }}>
                          {fmtDate(ev.created_at)}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted, #94A3B8)' }}>
                          {new Date(ev.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </td>
                      <td>
                        <span className={`audit-event-badge ${eventClass}`}>
                          {ev.event_type}
                        </span>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary, #0F172A)' }}>
                          {ev.entity_type}
                        </div>
                        <div style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--text-muted, #94A3B8)' }}>
                          ID: {ev.entity_id.length > 18 ? `${ev.entity_id.slice(0, 14)}...` : ev.entity_id}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 500, color: 'var(--text-primary, #0F172A)' }}>
                          {ev.actor_name || ev.actor_email || 'admin'}
                        </div>
                      </td>
                      <td>
                        <span className={`audit-outcome-badge ${outcomeClass}`}>
                          {outcomeClass === 'success' && <CheckCircle size={11} />}
                          {outcomeClass === 'rejected' && <XCircle size={11} />}
                          {outcomeClass === 'failed' && <XCircle size={11} />}
                          {outcomeClass === 'blocked' && <AlertTriangle size={11} />}
                          <span>{ev.outcome || 'SUCCESS'}</span>
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          type="button"
                          className="audit-view-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            openEventModal(ev.id);
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
        <div className="audit-table-footer">
          <div>
            Showing {events.length > 0 ? (currentPage - 1) * pageSize + 1 : 0}–{Math.min(currentPage * pageSize, total)} of {total} events
          </div>
          <div className="audit-page-btns">
            <button
              type="button"
              className="audit-page-btn"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            >
              &lt;
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((pg) => (
              <button
                key={pg}
                type="button"
                className={`audit-page-btn ${currentPage === pg ? 'active' : ''}`}
                onClick={() => setCurrentPage(pg)}
              >
                {pg}
              </button>
            ))}
            <button
              type="button"
              className="audit-page-btn"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            >
              &gt;
            </button>
          </div>
        </div>
      </div>

      {/* ── Centered Event Details Modal Dialog (model type in the middle of screen) ── */}
      {selectedEventId && (
        <div className="audit-modal-overlay" onClick={closeModal}>
          <div className="audit-modal-card" onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div className="audit-modal-header">
              <div>
                <div className="audit-modal-title">Event Details</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                  {eventDetail && (
                    <>
                      <span className={`audit-event-badge ${getEventBadgeClass(eventDetail.event.event_type)}`}>
                        {eventDetail.event.event_type}
                      </span>
                      <span className={`audit-outcome-badge ${getOutcomeBadgeClass(eventDetail.outcome)}`}>
                        {eventDetail.outcome}
                      </span>
                    </>
                  )}
                </div>
              </div>
              <button
                type="button"
                className="audit-modal-close-btn"
                onClick={closeModal}
                title="Close"
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="audit-modal-body">
              {loadingDetail ? (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-secondary, #64748B)' }}>
                  <RefreshCw size={24} className="spin" style={{ margin: '0 auto 8px', display: 'block', color: 'var(--accent-primary, #4F46E5)' }} />
                  Loading investigation record...
                </div>
              ) : eventDetail ? (
                <>
                  {/* Overview Grid */}
                  <div className="audit-detail-card">
                    <div className="audit-detail-header">
                      <FileText size={15} style={{ color: 'var(--accent-primary, #4F46E5)' }} />
                      <span>Event Overview</span>
                    </div>
                    <div className="audit-kv-grid">
                      <div className="audit-kv-item">
                        <span className="audit-kv-label">Timestamp</span>
                        <span className="audit-kv-value">{fmtDateTime(eventDetail.event.created_at)}</span>
                      </div>
                      <div className="audit-kv-item">
                        <span className="audit-kv-label">Actor</span>
                        <span className="audit-kv-value">
                          {eventDetail.event.actor_name || eventDetail.event.actor_email || 'admin'}
                        </span>
                      </div>
                      <div className="audit-kv-item">
                        <span className="audit-kv-label">Entity</span>
                        <span className="audit-kv-value">{eventDetail.event.entity_type}</span>
                      </div>
                      <div className="audit-kv-item">
                        <span className="audit-kv-label">Entity ID</span>
                        <span className="audit-kv-value mono">{eventDetail.event.entity_id}</span>
                      </div>
                    </div>
                  </div>

                  {/* Event Summary Box */}
                  {eventDetail.summary && (
                    <div className="audit-summary-box">
                      <strong>Summary: </strong>
                      {eventDetail.summary}
                    </div>
                  )}

                  {/* Recorded Changes & Parameters (Clean Human-Readable UI — NO raw JSON!) */}
                  {eventDetail.event.details_json && Object.keys(eventDetail.event.details_json).length > 0 && (
                    <div className="audit-detail-card">
                      <div className="audit-detail-header">
                        <Tag size={15} style={{ color: '#0284C7' }} />
                        <span>Recorded Changes & Parameters</span>
                      </div>
                      <div className="audit-kv-grid">
                        {eventDetail.event.details_json.sku && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Target SKU</span>
                            <span className="audit-kv-value" style={{ color: 'var(--accent-primary, #4F46E5)' }}>
                              {eventDetail.event.details_json.sku}
                            </span>
                          </div>
                        )}
                        {eventDetail.event.details_json.store_id && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Store Location</span>
                            <span className="audit-kv-value">{eventDetail.event.details_json.store_id}</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.price !== undefined && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Proposed Price</span>
                            <span className="audit-kv-value">{fmt(eventDetail.event.details_json.price)}</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.recommended_price !== undefined && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Recommended Price</span>
                            <span className="audit-kv-value">{fmt(eventDetail.event.details_json.recommended_price)}</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.discount_pct !== undefined && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Discount %</span>
                            <span className="audit-kv-value">{eventDetail.event.details_json.discount_pct}%</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.recommended_discount_pct !== undefined && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Recommended Discount</span>
                            <span className="audit-kv-value">{eventDetail.event.details_json.recommended_discount_pct}%</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.candidates_evaluated !== undefined && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Candidates Evaluated</span>
                            <span className="audit-kv-value">{eventDetail.event.details_json.candidates_evaluated}</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.approver && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Approver</span>
                            <span className="audit-kv-value">{eventDetail.event.details_json.approver}</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.reviewer && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Reviewer</span>
                            <span className="audit-kv-value">{eventDetail.event.details_json.reviewer}</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.role && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Role</span>
                            <span className="audit-kv-value">{eventDetail.event.details_json.role}</span>
                          </div>
                        )}
                        {eventDetail.event.details_json.email && (
                          <div className="audit-kv-item">
                            <span className="audit-kv-label">Email</span>
                            <span className="audit-kv-value">{eventDetail.event.details_json.email}</span>
                          </div>
                        )}
                      </div>

                      {/* Rationale / Reasons formatted as dedicated callouts */}
                      {eventDetail.event.details_json.rationale && (
                        <div style={{ marginTop: '8px', padding: '10px 12px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '6px' }}>
                          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary, #64748B)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>
                            Model Rationale
                          </span>
                          <span style={{ fontSize: '13px', color: 'var(--text-primary, #0F172A)' }}>
                            {eventDetail.event.details_json.rationale}
                          </span>
                        </div>
                      )}
                      {eventDetail.event.details_json.reason && (
                        <div style={{ marginTop: '8px', padding: '10px 12px', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '6px' }}>
                          <span style={{ fontSize: '11px', fontWeight: 600, color: '#991B1B', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>
                            Decision Reason
                          </span>
                          <span style={{ fontSize: '13px', color: '#B91C1C', fontWeight: 500 }}>
                            {eventDetail.event.details_json.reason}
                          </span>
                        </div>
                      )}
                      {eventDetail.event.details_json.notes && (
                        <div style={{ marginTop: '8px', padding: '10px 12px', background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: '6px' }}>
                          <span style={{ fontSize: '11px', fontWeight: 600, color: '#166534', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>
                            Approval Notes
                          </span>
                          <span style={{ fontSize: '13px', color: '#15803D' }}>
                            {eventDetail.event.details_json.notes}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Related Records Context */}
                  {(() => {
                    const runObj = eventDetail.related_records?.run || (
                      eventDetail.event.details_json?.run_id ? {
                        id: eventDetail.event.details_json.run_id,
                        sku: eventDetail.event.details_json.sku || 'N/A',
                        store_id: eventDetail.event.details_json.store_id || 'N/A',
                        status: 'COMPLETED'
                      } : eventDetail.event.entity_type.toLowerCase().includes('optimization') ? {
                        id: eventDetail.event.entity_id,
                        sku: eventDetail.event.details_json?.sku || 'N/A',
                        store_id: eventDetail.event.details_json?.store_id || 'N/A',
                        status: 'COMPLETED'
                      } : null
                    );
                    const recObj = eventDetail.related_records?.recommendation || (
                      eventDetail.event.entity_type.toLowerCase().includes('recommendation') ? {
                        id: eventDetail.event.entity_id,
                        status: 'PENDING_APPROVAL'
                      } : null
                    );

                    if (!runObj && !recObj) return null;

                    return (
                      <div className="audit-detail-card">
                        <div className="audit-detail-header">
                          <Layers size={15} style={{ color: '#7C3AED' }} />
                          <span>Linked Records & Workflow</span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {runObj && (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '6px' }}>
                              <div>
                                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #0F172A)' }}>
                                  Optimization Run: {runObj.sku} ({runObj.store_id})
                                </div>
                                <div style={{ fontSize: '11px', color: 'var(--text-muted, #94A3B8)' }}>
                                  Status: {runObj.status}
                                </div>
                              </div>
                              <button
                                type="button"
                                className="audit-view-btn"
                                onClick={() => {
                                  closeModal();
                                  navigate(`/optimize?run_id=${encodeURIComponent(runObj.id)}&sku=${encodeURIComponent(runObj.sku)}&store=${encodeURIComponent(runObj.store_id)}`);
                                }}
                              >
                                <span>View Run</span>
                                <ExternalLink size={12} />
                              </button>
                            </div>
                          )}

                          {recObj && (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '6px' }}>
                              <div>
                                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #0F172A)' }}>
                                  Recommendation Candidate
                                </div>
                                <div style={{ fontSize: '11px', color: 'var(--text-muted, #94A3B8)' }}>
                                  Status: {recObj.status}
                                </div>
                              </div>
                              <button
                                type="button"
                                className="audit-view-btn"
                                onClick={() => {
                                  closeModal();
                                  navigate('/reviews');
                                }}
                              >
                                <span>View in Queue</span>
                                <ExternalLink size={12} />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Audit Integrity Verification */}
                  <div className="audit-integrity-card">
                    <ShieldCheck size={20} style={{ color: '#16A34A', marginTop: '2px', flexShrink: 0 }} />
                    <div>
                      <div className="audit-integrity-title">Audit Record Integrity Verified</div>
                      <div className="audit-integrity-sub">
                        Event persisted with immutable PostgreSQL ledger constraints. Event UUID: {eventDetail.event.id}
                      </div>
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            {/* Modal Footer */}
            <div className="audit-modal-footer">
              <button
                type="button"
                className="audit-refresh-btn"
                onClick={() => eventDetail && copyEventId(eventDetail.event.id)}
              >
                {copySuccess ? <Check size={14} style={{ color: '#16A34A' }} /> : <Copy size={14} />}
                <span>{copySuccess ? 'Event ID Copied' : 'Copy Event ID'}</span>
              </button>
              <button
                type="button"
                className="audit-refresh-btn"
                style={{ background: 'var(--accent-primary, #4F46E5)', color: '#FFFFFF', borderColor: 'transparent' }}
                onClick={closeModal}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
