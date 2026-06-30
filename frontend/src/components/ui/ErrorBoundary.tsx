
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
          border: "1px solid var(--color-error-border)",
          backgroundColor: "var(--color-error-bg)",
          padding: 24,
          textAlign: "center",
        }}>
          <p style={{ fontSize: 14, fontWeight: 500, color: "var(--color-error-text)" }}>
            Something went wrong.
          </p>
          {this.state.error && (
            <p style={{ marginTop: 4, fontSize: 12, color: "var(--color-error-text)" }}>
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
              color: "var(--color-error-text)",
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
