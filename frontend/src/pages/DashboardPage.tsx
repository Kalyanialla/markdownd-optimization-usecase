import React, { useState, useEffect } from 'react';
import { 
  Target, 
  Clock, 
  ShieldCheck, 
  TrendingUp, 
  Play, 
  RefreshCw, 
  Calendar, 
  ArrowRight, 
  ChevronRight, 
  Package, 
  Check, 
  Send, 
  X, 
  FileText,
  AlertTriangle 
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { apiClient } from '../lib/api';
import './DashboardPage.css';

interface DashboardMetrics {
  total_runs: number;
  total_candidates: number;
  pending_approvals: number;
  approved_recommendations: number;
  rejected_recommendations: number;
  total_skus_tracked: number;
  active_policies_count: number;
  models_healthy: boolean;
  models_status: Record<string, any>;
  recent_events: Array<{
    id: string;
    actor_email?: string;
    actor_name?: string;
    event_type: string;
    entity_type: string;
    entity_id: string;
    details_json?: any;
    created_at: string;
  }>;
  approved_revenue_impact: number;
  approved_profit_impact: number;
}

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchDashboardMetrics = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient<DashboardMetrics>('/dashboard/summary');
      setMetrics(data);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err?.message || 'Unable to connect to optimization server.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardMetrics();
  }, []);

  const formatLastUpdated = (date: Date) => {
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    }) + ' ' + date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatActivityDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      }) + ' ' + d.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoString;
    }
  };

  const formatRelativeTime = (isoString: string) => {
    try {
      const now = new Date().getTime();
      const past = new Date(isoString).getTime();
      const diffMs = Math.max(0, now - past);
      const diffMins = Math.floor(diffMs / 60000);
      if (diffMins < 60) return `${Math.max(1, diffMins)}m ago`;
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    } catch {
      return '';
    }
  };

  const getEventTitle = (eventType: string) => {
    switch (eventType) {
      case 'RECOMMENDATION_APPROVED':
        return 'Recommendation Approved';
      case 'RECOMMENDATION_SUBMITTED':
        return 'Recommendation Submitted';
      case 'OPTIMIZATION_RUN_COMPLETED':
      case 'OPTIMIZATION_RUN':
        return 'Optimization Run Completed';
      case 'RECOMMENDATION_REJECTED':
        return 'Recommendation Rejected';
      case 'POLICY_EVALUATED':
      case 'POLICY_APPLIED':
        return 'Policy Evaluated';
      default:
        return eventType.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
    }
  };

  const getEventDetails = (ev: DashboardMetrics['recent_events'][0]) => {
    if (ev.details_json) {
      try {
        const d = typeof ev.details_json === 'string' ? JSON.parse(ev.details_json) : ev.details_json;
        const parts = [];
        if (d.sku || d.sku_id) parts.push(d.sku || d.sku_id);
        if (d.store_id || d.store) parts.push(d.store_id || d.store);
        if (d.discount_pct !== undefined) {
          parts.push(`${d.discount_pct}% discount`);
        } else if (d.markdown_percent !== undefined) {
          parts.push(`${d.markdown_percent}% discount`);
        } else if (d.horizon_days) {
          parts.push(`${d.horizon_days}-day horizon`);
        } else if (d.reason) {
          parts.push(d.reason);
        }
        if (parts.length > 0) return parts.join(' • ');
      } catch {
        // Fallback below
      }
    }
    return `${ev.entity_type} • ID: ${ev.entity_id ? ev.entity_id.slice(0, 8) : 'N/A'}`;
  };

  const getEventIcon = (eventType: string) => {
    if (eventType.includes('APPROVED')) {
      return (
        <div className="activity-icon-circle approved">
          <Check size={16} />
        </div>
      );
    }
    if (eventType.includes('SUBMITTED')) {
      return (
        <div className="activity-icon-circle submitted">
          <Send size={15} />
        </div>
      );
    }
    if (eventType.includes('REJECTED')) {
      return (
        <div className="activity-icon-circle rejected">
          <X size={16} />
        </div>
      );
    }
    if (eventType.includes('RUN')) {
      return (
        <div className="activity-icon-circle completed">
          <Clock size={16} />
        </div>
      );
    }
    return (
      <div className="activity-icon-circle evaluated">
        <FileText size={15} />
      </div>
    );
  };

  return (
    <div className="executive-overview-container">
      {/* Header matching exact layout */}
      <div className="executive-header">
        <div className="executive-title-area">
          <h1 className="executive-title">Executive Overview</h1>
          <p className="executive-subtitle">Track markdown performance, approvals and overall impact.</p>
        </div>

        <div className="executive-actions">
          <div className="last-updated-badge">
            <Calendar size={14} className="last-updated-icon" />
            <span>Last updated {formatLastUpdated(lastUpdated)}</span>
          </div>

          <button 
            className="btn-run-optimization"
            onClick={() => navigate('/optimize')}
            title="Start new markdown optimization"
          >
            <Play size={14} fill="currentColor" />
            <span>Run Optimization</span>
          </button>

          <button 
            className="btn-refresh-overview"
            onClick={fetchDashboardMetrics}
            disabled={isLoading}
            title="Reload live business telemetry"
          >
            <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error Notice */}
      {error && (
        <div className="status-banner error" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
          <button 
            onClick={fetchDashboardMetrics}
            style={{ background: 'transparent', border: '1px solid currentColor', color: 'inherit', padding: '2px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' }}
          >
            Retry
          </button>
        </div>
      )}

      {/* 4 KPI Cards Grid */}
      <div className="kpi-cards-grid">
        {/* KPI 1: Optimization Runs */}
        <Link to="/optimize" className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon-circle indigo">
              <Target size={18} />
            </div>
            <span className="kpi-title">Optimization Runs</span>
          </div>
          <div className="kpi-value">
            {isLoading ? '—' : metrics?.total_runs ?? 0}
          </div>
          <div className="kpi-footer">
            <span className="kpi-subtext trend-up">
              {metrics?.total_runs ? `${metrics.total_runs} total runs executed` : '0 runs executed'}
            </span>
            <div className="kpi-arrow-link">
              <ArrowRight size={16} />
            </div>
          </div>
        </Link>

        {/* KPI 2: Pending Approvals */}
        <Link to="/reviews" className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon-circle amber">
              <Clock size={18} />
            </div>
            <span className="kpi-title">Pending Approvals</span>
          </div>
          <div className="kpi-value">
            {isLoading ? '—' : metrics?.pending_approvals ?? 0}
          </div>
          <div className="kpi-footer">
            <span className="kpi-subtext trend-warning">
              <span className="priority-dot"></span>
              {metrics?.pending_approvals ? `${metrics.pending_approvals} high priority` : '0 high priority'}
            </span>
            <div className="kpi-arrow-link">
              <ArrowRight size={16} />
            </div>
          </div>
        </Link>

        {/* KPI 3: Approved Recommendations */}
        <Link to="/audit" className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon-circle green">
              <ShieldCheck size={18} />
            </div>
            <span className="kpi-title">Approved Recommendations</span>
          </div>
          <div className="kpi-value">
            {isLoading ? '—' : metrics?.approved_recommendations ?? 0}
          </div>
          <div className="kpi-footer">
            <span className="kpi-subtext trend-up">
              {metrics?.approved_recommendations ? `${metrics.approved_recommendations} active approved` : '0 active approved'}
            </span>
            <div className="kpi-arrow-link">
              <ArrowRight size={16} />
            </div>
          </div>
        </Link>

        {/* KPI 4: Projected Financial Impact */}
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon-circle indigo">
              <TrendingUp size={18} />
            </div>
            <span className="kpi-title">Projected Financial Impact</span>
          </div>
          <div className="kpi-value">
            ${isLoading ? '0.00' : (metrics?.approved_profit_impact ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="kpi-footer">
            <span className="kpi-subtext muted">
              Estimated (7-day horizon)
            </span>
            <div className="kpi-arrow-link">
              <ArrowRight size={16} />
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Next Steps & Recent Activity */}
      <div className="two-column-layout">
        {/* Left Column: Next Steps */}
        <div className="next-steps-card">
          <h2 className="section-card-title">Next Steps</h2>
          <p className="section-card-subtitle">Quick access to key workflows</p>

          <div className="next-steps-list">
            <Link to="/products" className="next-step-item">
              <div className="next-step-left">
                <div className="next-step-icon-box">
                  <Package size={20} />
                </div>
                <div className="next-step-content">
                  <div className="next-step-title">Product Inventory</div>
                  <div className="next-step-desc">View products, prices and stock levels</div>
                </div>
              </div>
              <ChevronRight size={18} className="next-step-chevron" />
            </Link>

            <Link to="/optimize" className="next-step-item">
              <div className="next-step-left">
                <div className="next-step-icon-box">
                  <Target size={20} />
                </div>
                <div className="next-step-content">
                  <div className="next-step-title">Markdown Optimizer</div>
                  <div className="next-step-desc">Run optimization and review candidates</div>
                </div>
              </div>
              <ChevronRight size={18} className="next-step-chevron" />
            </Link>

            <Link to="/reviews" className="next-step-item">
              <div className="next-step-left">
                <div className="next-step-icon-box">
                  <ShieldCheck size={20} />
                </div>
                <div className="next-step-content">
                  <div className="next-step-title">Approval Queue</div>
                  <div className="next-step-desc">Review and approve pending recommendations</div>
                </div>
              </div>
              <ChevronRight size={18} className="next-step-chevron" />
            </Link>
          </div>
        </div>

        {/* Right Column: Recent Activity */}
        <div className="recent-activity-card">
          <div className="recent-activity-header">
            <div>
              <h2 className="section-card-title">Recent Activity</h2>
              <p className="section-card-subtitle">Latest audit events across the platform</p>
            </div>
            <Link to="/audit" className="view-all-link">
              <span>View all</span>
              <ArrowRight size={14} />
            </Link>
          </div>

          <div className="recent-activity-list">
            {isLoading ? (
              <div style={{ textAlign: 'center', padding: '32px', color: '#94A3B8', fontSize: '13px' }}>
                <RefreshCw size={20} className="spin" style={{ margin: '0 auto 8px', display: 'block', color: '#4F46E5' }} />
                Loading recent activity...
              </div>
            ) : !metrics?.recent_events?.length ? (
              <div style={{ textAlign: 'center', padding: '32px', color: '#94A3B8', fontSize: '13px' }}>
                No audit events recorded yet. Run an optimization to generate live audit records.
              </div>
            ) : (
              metrics.recent_events.slice(0, 5).map((ev) => (
                <div key={ev.id} className="recent-activity-item">
                  <div className="activity-left">
                    {getEventIcon(ev.event_type)}
                    <div className="activity-content">
                      <div className="activity-title">{getEventTitle(ev.event_type)}</div>
                      <div className="activity-meta">{getEventDetails(ev)}</div>
                    </div>
                  </div>
                  <div className="activity-time-block">
                    <div className="activity-date">{formatActivityDate(ev.created_at)}</div>
                    <div className="activity-relative-time">{formatRelativeTime(ev.created_at)}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Bottom Banner: Smarter Markdown Decisions Flow */}
      <div className="smarter-decisions-banner">
        <div className="banner-left">
          <div className="banner-icon-circle">
            <Target size={22} />
          </div>
          <div className="banner-text-block">
            <h3 className="banner-title">Smarter Markdown Decisions</h3>
            <p className="banner-subtitle">
              Leverage AI-powered insights, policy controls and human oversight to maximize profit while managing stockout risk.
            </p>
          </div>
        </div>

        <div className="workflow-steps">
          <div className="workflow-step">
            <div className="workflow-step-icon">
              <Target size={18} />
            </div>
            <span className="workflow-step-name">1. Optimize</span>
            <span className="workflow-step-action">Run analysis</span>
          </div>

          <div className="workflow-step-arrow">→</div>

          <div className="workflow-step-step workflow-step">
            <div className="workflow-step-icon">
              <FileText size={18} />
            </div>
            <span className="workflow-step-name">2. Review</span>
            <span className="workflow-step-action">Check candidates</span>
          </div>

          <div className="workflow-step-arrow">→</div>

          <div className="workflow-step-step workflow-step">
            <div className="workflow-step-icon">
              <ShieldCheck size={18} />
            </div>
            <span className="workflow-step-name">3. Approve</span>
            <span className="workflow-step-action">Finalize decision</span>
          </div>
        </div>
      </div>
    </div>
  );
};
