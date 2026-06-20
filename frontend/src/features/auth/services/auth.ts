import type { LoginRequest, LoginResponse, RegisterRequest } from "../types/auth";

// Frontend session auth — validates password against ADMIN_PASSWORD / API_KEY
// server-side via /api/v1/auth/login and sets an HttpOnly session cookie.
// Auth is handled by the backend via session cookie.
// TODO: Replace with real backend user auth when available.

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const res = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: body.password }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Login failed");
  }

  return { access_token: "session", token_type: "bearer" };
}

export async function register(body: RegisterRequest): Promise<void> {
  void body;
  // TODO: Replace with real POST /auth/register once backend auth is implemented.
  throw new Error("Registration not available in single-user mode");
}
