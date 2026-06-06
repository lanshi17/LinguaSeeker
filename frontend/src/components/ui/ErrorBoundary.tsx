"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional fallback UI. Receives the error and a reset callback. */
  fallback?: ReactNode;
  /** Called when an error is caught. Useful for logging. */
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Catches rendering errors in its subtree and displays a fallback UI
 * instead of white-screening the entire page.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <DataDrivenComponent />
 *   </ErrorBoundary>
 */
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
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            Something went wrong.
          </p>
          {this.state.error && (
            <p className="mt-1 text-xs text-red-600">
              {this.state.error.message}
            </p>
          )}
          <button
            onClick={this.reset}
            className="mt-3 cursor-pointer text-sm font-medium text-red-700 underline hover:text-red-900"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
