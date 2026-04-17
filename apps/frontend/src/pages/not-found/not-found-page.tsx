import { Link, useLocation } from 'react-router-dom';

export const NotFoundPage: React.FC = () => {
  const location = useLocation();

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h1 className="panel-title" style={{ margin: 0, fontSize: 18 }}>
            Page not found
          </h1>
          <div className="muted" style={{ marginTop: 6 }}>
            No route matches <code>{location.pathname}</code>
          </div>
        </div>
      </div>
      <div className="panel-body">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <Link to="/tasks/agent-create">Go to Task</Link>
          <Link to="/graph">Go to Graph</Link>
          <Link to="/login">Go to Login</Link>
        </div>
      </div>
    </div>
  );
};
