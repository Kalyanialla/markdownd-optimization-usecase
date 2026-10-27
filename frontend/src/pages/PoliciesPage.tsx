import React, { useState, useEffect } from 'react';
import { 
  RefreshCw, 
  Sliders, 
  Layers, 
  AlertTriangle
} from 'lucide-react';
import { apiClient } from '../lib/api';
import './Pages.css';

interface PolicyItem {
  policy_id: string;
  category: string;
  min_markdown_pct: number;
  max_markdown_pct: number;
  allowed_steps: number[];
  min_gross_margin_pct: number;
  max_markdown_frequency_days: number;
  cadence: string;
  effective_start: string;
  effective_end: string;
  is_active: boolean;
}

interface PolicyResolveResponse {
  category: string;
  target_date: string;
  matched_policy_id?: string;
  min_markdown_pct?: number;
  max_markdown_pct?: number;
  allowed_steps: number[];
  min_gross_margin_pct?: number;
  cadence?: string;
  rule_source: string;
}

export const PoliciesPage: React.FC = () => {
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Simulator state
  const [simCategory, setSimCategory] = useState('TShirt');
  const [simSku, setSimSku] = useState('');
  const [simStore, setSimStore] = useState('');
  const [simDate, setSimDate] = useState('2024-06-30');
  const [simResult, setSimResult] = useState<PolicyResolveResponse | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  const fetchPolicies = async () => {
    setIsLoading(true);
    try {
      const data = await apiClient<PolicyItem[]>('/policies');
      setPolicies(data);
    } catch (err: any) {
      console.error('Failed to load policies:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
    handleSimulate();
  }, []);

  const handleSimulate = async () => {
    setIsSimulating(true);
    setSimError(null);
    try {
      let query = `/policies/resolve?category=${encodeURIComponent(simCategory)}&date=${encodeURIComponent(simDate)}`;
      if (simSku.trim()) query += `&sku=${encodeURIComponent(simSku.trim())}`;
      if (simStore.trim()) query += `&store=${encodeURIComponent(simStore.trim())}`;

      const res = await apiClient<PolicyResolveResponse>(query);
      setSimResult(res);
    } catch (err: any) {
      setSimError(err.message || 'Resolution failed');
      setSimResult(null);
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div className="page-title-block">
          <div className="page-tag">
            <span className="tabular-nums">05</span> // POLICY MATRIX & GUARDRAILS
          </div>
          <h1 className="page-title">Pricing Policies & Guardrails</h1>
          <p className="page-description">
            Inspect active policy bounds, minimum margins, maximum discount caps, and cadence holdouts enforced by the deterministic pricing engine.
          </p>
        </div>
        <div className="page-actions">
          <button 
            className="action-btn secondary-btn"
            onClick={fetchPolicies}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            <span>Reload Policies</span>
          </button>
        </div>
      </div>

      {/* Policy Hierarchy Resolution Simulator */}
      <div style={{
        background: 'var(--card-bg, #0f172a)',
        border: '1px solid var(--border-color, #334155)',
        borderRadius: '10px',
        padding: '1.5rem',
        marginBottom: '2rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
          <Layers size={18} style={{ color: '#38bdf8' }} />
          <h2 style={{ margin: 0, fontSize: '1.05rem', color: '#f8fafc' }}>
            Strict Hierarchy Precedence Simulator (SKU &gt; STORE &gt; CATEGORY &gt; CHAIN)
          </h2>
        </div>
        <p style={{ margin: '0 0 1.25rem 0', fontSize: '0.82rem', color: '#94a3b8' }}>
          Enter a category, evaluation date, and optional SKU or store overrides to inspect deterministic policy selection and guardrail constraints.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', alignItems: 'end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.4rem' }}>
              Category
            </label>
            <select
              value={simCategory}
              onChange={(e) => setSimCategory(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem',
                fontSize: '0.85rem',
                borderRadius: '6px',
                border: '1px solid #334155',
                background: '#090d16',
                color: '#f8fafc',
                outline: 'none',
              }}
            >
              <option value="TShirt">TShirt</option>
              <option value="Jeans">Jeans</option>
              <option value="Dress">Dress</option>
              <option value="Jacket">Jacket</option>
              <option value="Activewear">Activewear</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.4rem' }}>
              Evaluation Date
            </label>
            <input
              type="date"
              value={simDate}
              onChange={(e) => setSimDate(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem',
                fontSize: '0.85rem',
                borderRadius: '6px',
                border: '1px solid #334155',
                background: '#090d16',
                color: '#f8fafc',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.4rem' }}>
              SKU Override (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. SKU-0071"
              value={simSku}
              onChange={(e) => setSimSku(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem',
                fontSize: '0.85rem',
                borderRadius: '6px',
                border: '1px solid #334155',
                background: '#090d16',
                color: '#f8fafc',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.4rem' }}>
              Store Override (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. STORE-04"
              value={simStore}
              onChange={(e) => setSimStore(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem',
                fontSize: '0.85rem',
                borderRadius: '6px',
                border: '1px solid #334155',
                background: '#090d16',
                color: '#f8fafc',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div>
            <button
              onClick={handleSimulate}
              disabled={isSimulating}
              className="action-btn primary-btn"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {isSimulating ? <RefreshCw size={14} className="spin" /> : <Sliders size={14} />}
              <span>Resolve Policy</span>
            </button>
          </div>
        </div>

        {simError && (
          <div className="status-banner error" style={{ marginTop: '1rem' }}>
            <AlertTriangle size={15} />
            <span>{simError}</span>
          </div>
        )}

        {simResult && (
          <div style={{
            marginTop: '1.25rem',
            padding: '1rem',
            borderRadius: '8px',
            background: 'rgba(56, 189, 248, 0.08)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem'
          }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Matched Policy ID</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#38bdf8' }}>{simResult.matched_policy_id}</div>
              <div style={{ fontSize: '0.75rem', color: '#4ade80', marginTop: '2px' }}>{simResult.rule_source}</div>
            </div>

            <div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Allowed Markdown Steps</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc' }}>
                {simResult.allowed_steps.map((s) => `${s}%`).join(', ')}
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Margin &amp; Discount Guardrails</div>
              <div style={{ fontSize: '0.85rem', color: '#f8fafc' }}>
                Min Margin: <strong style={{ color: '#4ade80' }}>{simResult.min_gross_margin_pct}%</strong>
              </div>
              <div style={{ fontSize: '0.85rem', color: '#f8fafc' }}>
                Max Markdown: <strong style={{ color: '#f87171' }}>{simResult.max_markdown_pct}%</strong>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Execution Cadence</div>
              <div style={{ fontSize: '0.85rem', color: '#e2e8f0' }}>{simResult.cadence}</div>
            </div>
          </div>
        )}
      </div>

      {/* Enterprise Policy Store Catalog */}
      <div className="section-header" style={{ marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem', color: '#f8fafc', margin: 0 }}>Enterprise Policy Store</h2>
        <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
          {policies.length} Total Policies ({policies.filter(p => p.is_active).length} Active)
        </span>
      </div>

      <div className="industrial-table-container">
        <table className="industrial-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Policy ID</th>
              <th>Hierarchy Scope</th>
              <th>Allowed Discount Steps</th>
              <th>Max Discount Cap</th>
              <th>Min Margin Guardrail</th>
              <th>Price Change Cadence</th>
              <th>Effective Window</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '3rem' }}>
                  <RefreshCw size={24} className="spin" style={{ margin: '0 auto 0.75rem', display: 'block', color: '#38bdf8' }} />
                  Loading pricing policies...
                </td>
              </tr>
            ) : policies.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>
                  No policies found in enterprise catalog.
                </td>
              </tr>
            ) : (
              policies.map((p) => (
                <tr key={p.policy_id}>
                  <td>
                    <span 
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        background: p.is_active ? 'rgba(34, 197, 94, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                        color: p.is_active ? '#4ade80' : '#94a3b8',
                        border: `1px solid ${p.is_active ? 'rgba(34, 197, 94, 0.3)' : 'rgba(148, 163, 184, 0.3)'}`
                      }}
                    >
                      {p.is_active ? 'ACTIVE' : 'RETIRED'}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700, color: '#38bdf8' }}>{p.policy_id}</td>
                  <td style={{ fontWeight: 600, color: '#f8fafc' }}>{p.category}</td>
                  <td>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
                      {p.allowed_steps.map((st) => (
                        <span key={st} style={{
                          padding: '1px 5px',
                          fontSize: '0.72rem',
                          borderRadius: '3px',
                          background: 'rgba(255, 255, 255, 0.05)',
                          color: '#cbd5e1'
                        }}>
                          {st}%
                        </span>
                      ))}
                    </div>
                  </td>
                  <td style={{ fontWeight: 600, color: '#f87171' }}>{p.max_markdown_pct}%</td>
                  <td style={{ fontWeight: 600, color: '#4ade80' }}>{p.min_gross_margin_pct}%</td>
                  <td style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{p.cadence}</td>
                  <td style={{ fontSize: '0.78rem', color: '#64748b' }}>
                    {p.effective_start} &rarr; {p.effective_end}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
