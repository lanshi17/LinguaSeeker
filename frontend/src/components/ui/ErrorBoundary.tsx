
import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.props.onError?.(error, info);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={{
          borderRadius: 8,
          border: "1px solid #fecaca",
          backgroundColor: "#fef2f2",
          padding: 24,
          textAlign: "center",
        }}>
          <p style={{ fontSize: 14, fontWeight: 500, color: "#991b1b" }}>
            Something went wrong.
          </p>
          {this.state.error && (
            <p style={{ marginTop: 4, fontSize: 12, color: "#dc2626" }}>
              {this.state.error.message}
            </p>
          )}
          <button
            onClick={this.reset}
            style={{
              marginTop: 12,
              cursor: "pointer",
              fontSize: 14,
              fontWeight: 500,
              color: "#b91c1c",
              textDecoration: "underline",
              background: "none",
              border: "none",
            }}
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
