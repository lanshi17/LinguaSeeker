/**
 * Layout Component
 */
import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { Home, Network } from 'lucide-react';
import { ApiStatus } from '../../debug/ApiStatus/ApiStatus';
import './Layout.css';

export const Layout: React.FC = () => {
  const location = useLocation();
  const isHome = location.pathname === '/';

  // Full screen layout for home page, no navigation
  if (isHome) {
    return <Outlet />;
  }

  return (
    <div className="layout">
      {/* Sidebar navigation */}
      <nav className="sidebar">
        <Link to="/" className="logo">
          <span className="logo-icon">🔬</span>
          <span className="logo-text">Multi-ACMG</span>
        </Link>
        
        <div className="nav-links">
          <Link 
            to="/" 
            className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
          >
            <Home size={18} />
            <span>Home</span>
          </Link>
          <Link 
            to="/graph" 
            className={`nav-link ${location.pathname === '/graph' ? 'active' : ''}`}
          >
            <Network size={18} />
            <span>Graph</span>
          </Link>
        </div>
        
        <div className="nav-footer">
          <ApiStatus />
        </div>
      </nav>

      {/* Main content area */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
};
