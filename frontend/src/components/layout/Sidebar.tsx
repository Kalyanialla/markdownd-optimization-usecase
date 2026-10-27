import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  Target,
  ShieldCheck,
  History,
  BarChart2,
  ChevronRight,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../lib/api';
import './Sidebar.css';

interface NavItem {
  name: string;
  path: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  showBadge?: boolean;
}

const navItems: NavItem[] = [
  { name: 'Overview', path: '/dashboard', icon: LayoutDashboard },
  { name: 'Product Inventory', path: '/products', icon: Package },
  { name: 'Markdown Optimizer', path: '/optimize', icon: Target },
  { name: 'Approval Queue', path: '/reviews', icon: ShieldCheck, showBadge: true },
  { name: 'Audit Trail', path: '/audit', icon: History },
];

export const Sidebar: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  const [pendingCount, setPendingCount] = useState<number>(0);

  useEffect(() => {
    let mounted = true;
    const fetchPendingCount = async () => {
      try {
        const res = await apiClient<{ pending_approvals: number }>('/dashboard/summary');
        if (mounted && res && typeof res.pending_approvals === 'number') {
          setPendingCount(res.pending_approvals);
        }
      } catch {
        // Retain existing count on network error
      }
    };
    fetchPendingCount();
    const interval = setInterval(fetchPendingCount, 15000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const getInitials = (name?: string, email?: string) => {
    if (name) {
      const parts = name.split(' ');
      if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      return name.slice(0, 2).toUpperCase();
    }
    if (email) return email.slice(0, 2).toUpperCase();
    return 'AD';
  };

  return (
    <>
      {isOpen && <div className="sidebar-backdrop" onClick={onClose} />}
      <aside className={`industrial-sidebar ${isOpen ? 'open' : ''}`}>
        {/* Brand Header matching mockup */}
        <div className="sidebar-brand-header">
          <div className="brand-logo-icon">
            <BarChart2 size={20} />
          </div>
          <div className="brand-titles">
            <h1 className="brand-name">Markdown Optimizer</h1>
            <p className="brand-subtitle">Pricing & Governance</p>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `nav-link ${isActive ? 'active' : ''}`
                }
              >
                <Icon size={18} className="nav-icon" />
                <span className="nav-text">{item.name}</span>
                {item.showBadge && pendingCount > 0 && (
                  <span className="nav-badge-pill">{pendingCount}</span>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Sidebar Footer with System Online and User Card */}
        <div className="sidebar-footer">
          {/* System Online Status */}
          <div className="system-status-box">
            <div className="system-status-indicator" />
            <div className="system-status-text">
              <span className="system-status-label">System Online</span>
              <span className="system-status-sub">All services operational</span>
            </div>
          </div>

          {/* User Account Card */}
          <div className="user-account-card">
            <div className="user-account-avatar">
              {getInitials(user?.full_name, user?.email)}
            </div>
            <div className="user-account-info">
              <span className="user-account-name">{user?.full_name || user?.email || 'admin'}</span>
              <span className="user-account-role">Administrator</span>
            </div>
            <ChevronRight size={16} className="user-account-chevron" />
          </div>
        </div>
      </aside>
    </>
  );
};
