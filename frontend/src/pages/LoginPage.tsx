import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Sparkles, Lock, Mail, Eye, EyeOff, AlertCircle, ArrowRight, 
  TrendingUp, ShieldCheck, Zap, CheckCircle2 
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../lib/api';
import './Auth.css';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!email || !password) {
      setErrorMessage('Please enter both your corporate email and password.');
      return;
    }

    setIsLoading(true);
    try {
      await login({ email, password });
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Authentication failed. Please verify credentials or server connectivity.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="split-auth-container">
      {/* LEFT COLUMN: Hero Showcase */}
      <div className="auth-hero-pane">
        <div className="hero-gradient-orb orb-1" />
        <div className="hero-gradient-orb orb-2" />
        <div className="hero-grid-pattern" />

        <div className="hero-content">
          <div className="hero-brand">
            <div className="hero-brand-icon">
              <Sparkles size={24} />
            </div>
            <div className="hero-brand-name">Markdown Optimizer</div>
          </div>

          <div className="hero-headline-block">
            <div className="hero-pill">
              <Zap size={14} className="hero-pill-icon" />
              <span>Next-Gen Markdown Intelligence</span>
            </div>
            <h1 className="hero-title">
              Autonomous Markdown Pricing & Inventory Clearance.
            </h1>
            <p className="hero-description">
              Harness predictive machine learning to discover optimal clearance discounts, protect gross margins, and eliminate dead stock across every retail channel.
            </p>
          </div>

          {/* Metric Feature Cards */}
          <div className="hero-feature-cards">
            <div className="feature-stat-card">
              <div className="feature-stat-header">
                <span className="stat-label">Clearance Lift</span>
                <TrendingUp size={16} className="stat-icon-green" />
              </div>
              <div className="stat-value">+24.8%</div>
              <div className="stat-caption">Average Sell-Through Rate</div>
            </div>

            <div className="feature-stat-card">
              <div className="feature-stat-header">
                <span className="stat-label">Margin Guard</span>
                <ShieldCheck size={16} className="stat-icon-indigo" />
              </div>
              <div className="stat-value">100%</div>
              <div className="stat-caption">Automated Policy Enforcement</div>
            </div>
          </div>

          {/* Trust bullet footer */}
          <div className="hero-trust-footer">
            <div className="trust-item">
              <CheckCircle2 size={16} className="trust-check" />
              <span>Multi-Store Elasticity Engine</span>
            </div>
            <div className="trust-item">
              <CheckCircle2 size={16} className="trust-check" />
              <span>Immutable Governance & Audit Trails</span>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT COLUMN: Interactive Form */}
      <div className="auth-form-pane">
        <motion.div 
          className="form-wrapper-card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
        >
          <div className="form-header-area">
            <h2 className="form-main-title">Sign in to console</h2>
            <p className="form-sub-title">Enter your credentials to manage inventory and pricing optimizations.</p>
          </div>

          {errorMessage && (
            <motion.div
              className="auth-alert error"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <AlertCircle size={16} className="auth-alert-icon" />
              <span>{errorMessage}</span>
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="email-input">
                Corporate Email
              </label>
              <div className="input-wrapper">
                <Mail size={16} className="input-lead-icon" />
                <input
                  id="email-input"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@enterprise.com"
                  className="form-input with-lead-icon"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="form-group">
              <div className="form-label-row">
                <label className="form-label" htmlFor="password-input">
                  Password
                </label>
              </div>
              <div className="input-wrapper">
                <Lock size={16} className="input-lead-icon" />
                <input
                  id="password-input"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="form-input with-lead-icon with-trail-icon"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={isLoading}
            >
              {isLoading ? (
                <span className="btn-loading-text">Verifying credentials...</span>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          <div className="auth-footer">
            Don't have an operator account?
            <Link to="/signup" className="auth-footer-link">Register here</Link>
          </div>

          <div className="security-note">
            <ShieldCheck size={14} className="security-note-icon" />
            <span>256-bit AES encryption &bull; SOC2 Certified Infrastructure</span>
          </div>
        </motion.div>
      </div>
    </div>
  );
};
