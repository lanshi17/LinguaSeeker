import { Link } from 'react-router-dom';

export const RegisterPage: React.FC = () => {
  return (
    <div className="panel">
      <div className="panel-header">
        <div style={{ fontWeight: 800 }}>Register</div>
      </div>
      <div className="panel-body">
        <div className="muted">
          Registration/email verification is blocked until backend auth endpoints are added.
        </div>
        <div style={{ marginTop: 12 }}>
          <Link to="/tasks/agent-create">Continue to MVP flow</Link>
        </div>
        <div style={{ marginTop: 8 }} className="muted">
          Already have an account? <Link to="/login">Login</Link>
        </div>
      </div>
    </div>
  );
};
