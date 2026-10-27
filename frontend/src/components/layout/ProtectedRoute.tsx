import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import type { UserRole } from '../../types/auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: 'var(--bg-base)',
        color: 'var(--text-secondary)',
        fontFamily: 'var(--font-mono)',
        gap: '16px'
      }}>
        <div style={{
          width: '32px',
          height: '32px',
          border: '2px solid var(--border-prominent)',
          borderTopColor: 'var(--accent-lime)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite'
        }} />
        <span style={{ fontSize: '12px', letterSpacing: '0.05em' }}>VERIFYING CREDENTIALS...</span>
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '64px 20px',
        textAlign: 'center'
      }}>
        <div style={{
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          backgroundColor: 'var(--accent-coral-dim)',
          border: '1px solid rgba(255, 107, 107, 0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '16px',
          color: 'var(--accent-coral)'
        }}>
          <ShieldAlert size={28} />
        </div>
        <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>
          RESTRICTED ROLE ACCESS
        </h2>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '440px', fontSize: '13px', lineHeight: 1.6 }}>
          This section requires privileged permissions ({allowedRoles.join(', ')}). Your current active role is{' '}
          <code style={{ color: 'var(--accent-lime)', fontFamily: 'var(--font-mono)' }}>{user.role}</code>.
        </p>
      </div>
    );
  }

  return <>{children}</>;
};
