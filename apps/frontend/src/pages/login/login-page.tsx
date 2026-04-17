import { Link } from 'react-router-dom';

export const LoginPage: React.FC = () => {
  return (
    <div className="panel">
      <div className="panel-header">
        <div style={{ fontWeight: 800 }}>Login</div>
      </div>
      <div className="panel-body">
        <div className="muted">
          Backend authentication endpoints are not available in the current OpenAPI contract.
        </div>
        <div style={{ marginTop: 12 }}>
          <Link to="/tasks/agent-create">Continue to MVP flow</Link>
        </div>
        <div style={{ marginTop: 8 }} className="muted">
          Need an account? <Link to="/register">Register</Link>
        </div>
      </div>
    </div>
  );
};
