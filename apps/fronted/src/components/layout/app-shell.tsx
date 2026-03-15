import { Outlet, Link, useLocation } from 'react-router-dom';

export const AppShell: React.FC = () => {
  const location = useLocation();

  return (
    <div>
      <header className="no-print" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <div style={{ fontWeight: 800, letterSpacing: 0.2 }}>Multi-ACMG</div>
            <div className="muted" style={{ fontSize: 12 }}>
              Frontend MVP
            </div>
          </div>
          <nav style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
            <Link to="/tasks/new" style={{ opacity: location.pathname.startsWith('/tasks') ? 1 : 0.8 }}>
              Task
            </Link>
            <Link to="/login" style={{ opacity: location.pathname === '/login' ? 1 : 0.8 }}>
              Login
            </Link>
          </nav>
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </div>
  );
};
