import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Menu, Search, Bell, ChevronDown, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import './TopBar.css';

export const TopBar: React.FC<{ onToggleSidebar: () => void }> = ({ onToggleSidebar }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/products?search=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

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
    <header className="industrial-topbar">
      <div className="topbar-left">
        <button
          className="sidebar-toggle-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle navigation menu"
        >
          <Menu size={18} />
        </button>

        {/* Search bar matching mockup */}
        <form className="topbar-search-form" onSubmit={handleSearch}>
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search SKUs, stores, or categories..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </form>
      </div>

      <div className="topbar-right">
        {/* Notification Bell */}
        <button className="notification-btn" aria-label="Notifications" title="Notifications">
          <Bell size={18} />
          <span className="notification-dot" />
        </button>

        {/* User Profile Pill with Dropdown */}
        <div className="user-profile-wrapper">
          <button 
            className="user-profile-pill"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            aria-expanded={dropdownOpen}
          >
            <div className="user-avatar-initial">
              {getInitials(user?.full_name, user?.email)}
            </div>
            <span className="user-display-name">
              {user?.full_name ? user.full_name.split(' ')[0].toLowerCase() : (user?.email ? user.email.split('@')[0] : 'admin')}
            </span>
            <ChevronDown size={14} className="user-chevron" />
          </button>

          {dropdownOpen && (
            <div className="user-dropdown-menu">
              <div className="dropdown-header">
                <div className="dropdown-name">{user?.full_name || 'Administrator'}</div>
                <div className="dropdown-email">{user?.email || 'admin@retail.internal'}</div>
                <div className="dropdown-role">{user?.role || 'MERCHANDISER'}</div>
              </div>
              <div className="dropdown-divider" />
              <button 
                className="dropdown-item signout"
                onClick={() => {
                  setDropdownOpen(false);
                  logout();
                }}
              >
                <LogOut size={14} />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
