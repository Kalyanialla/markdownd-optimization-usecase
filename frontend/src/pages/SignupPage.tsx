import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Terminal, Eye, EyeOff, AlertCircle, ArrowRight, ShieldCheck, Info } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../lib/api';
import './Auth.css';

export const SignupPage: React.FC = () => {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!fullName || !email || !password || !confirmPassword) {
      setErrorMessage('All registration fields are required.');
      return;
    }

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match. Please verify and retype.');
      return;
    }

    setIsLoading(true);
    try {
      await signup({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
      });
      navigate('/dashboard', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to register operator account. Please verify details.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <motion.div
        className="auth-card"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: 'easeOut' }}
      >
        <div className="auth-header">
          <div className="auth-badge">
            <Terminal size={14} />
            <span>OPERATOR ENROLLMENT</span>
          </div>
          <h2 className="auth-title">Create Account</h2>
          <p className="auth-subtitle">
            Register your operator profile for markdown policy formulation and optimization runs.
          </p>
        </div>

        <div className="auth-alert info" style={{ marginBottom: '16px' }}>
          <Info size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>
            First registered user bootstraps safely as System Administrator. Subsequent operators default to Analyst.
          </span>
        </div>

        {errorMessage && (
          <motion.div
            className="auth-alert error"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            style={{ marginBottom: '16px' }}
          >
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{errorMessage}</span>
          </motion.div>
        )}

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="name-input">
              Full Legal Name
            </label>
            <input
              id="name-input"
              type="text"
              autoComplete="name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alex Vance"
              className="form-input"
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="email-input">
              Enterprise Work Email
            </label>
            <input
              id="email-input"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex.vance@enterprise-retail.com"
              className="form-input"
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password-input">
              Master Password (Min 8 Characters)
            </label>
            <div className="input-wrapper">
              <input
                id="password-input"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="form-input"
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

          <div className="form-group">
            <label className="form-label" htmlFor="confirm-password-input">
              Confirm Master Password
            </label>
            <input
              id="confirm-password-input"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••••••"
              className="form-input"
              disabled={isLoading}
            />
          </div>

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={isLoading}
          >
            {isLoading ? (
              <span>REGISTERING IDENTITY...</span>
            ) : (
              <>
                <span>REGISTER OPERATOR ACCOUNT</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        <div className="auth-footer">
          Already registered in the system?
          <Link to="/login">Sign In Here</Link>
        </div>

        <div className="security-note">
          <ShieldCheck size={13} />
          <span>Role privileges enforced exclusively by server-side advisory locks</span>
        </div>
      </motion.div>
    </div>
  );
};
