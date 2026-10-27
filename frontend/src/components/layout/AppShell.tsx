import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import './AppShell.css';

export const AppShell: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="industrial-appshell">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="appshell-main">
        <TopBar onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <main className="appshell-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
