import { useState, useEffect, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

interface AuthGuardProps {
  children: ReactNode;
}

interface AuthMeResponse {
  authenticated: boolean;
  email: string | null;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const [status, setStatus] = useState<"loading" | "authenticated" | "unauthenticated">("loading");
  const location = useLocation();

  useEffect(() => {
    fetch("/api/v1/auth/me")
      .then((res) => res.json() as Promise<AuthMeResponse>)
      .then((data) => {
        setStatus(data.authenticated ? "authenticated" : "unauthenticated");
      })
      .catch(() => setStatus("unauthenticated"));
  }, []);

  if (status === "loading") {
    return null; // or a spinner
  }

  if (status === "unauthenticated") {
    const params = new URLSearchParams({ next: location.pathname });
    return <Navigate to={`/login?${params}`} replace />;
  }

  return <>{children}</>;
}
