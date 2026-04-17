import { Outlet, Link, useLocation } from 'react-router-dom';

export const AppShell: React.FC = () => {
  const location = useLocation();

  return (
    <div>
      <header className="no-print" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <h1 style={{ fontWeight: 800, letterSpacing: 0.2, margin: 0, fontSize: 16 }}>Multi-ACMG</h1>
            <div className="muted" style={{ fontSize: 12 }}>
              Frontend MVP
            </div>
          </div>
          <nav aria-label="Primary" style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
            <Link
              to="/tasks/agent-create"
              aria-current={location.pathname.startsWith('/tasks') ? 'page' : undefined}
              style={{ opacity: location.pathname.startsWith('/tasks') ? 1 : 0.8 }}
            >
              Task
            </Link>
            <Link
              to="/graph"
              aria-current={location.pathname.startsWith('/graph') ? 'page' : undefined}
              style={{ opacity: location.pathname.startsWith('/graph') ? 1 : 0.8 }}
            >
              Graph
            </Link>
            <Link
              to="/login"
              aria-current={location.pathname === '/login' ? 'page' : undefined}
              style={{ opacity: location.pathname === '/login' ? 1 : 0.8 }}
            >
              Login
            </Link>
          </nav>
        </div>
      </header>
      <main className="container" id="main">
        <Outlet />
      </main>
    </div>
  );
};
