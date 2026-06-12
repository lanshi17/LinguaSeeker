import type { LoginRequest, LoginResponse, RegisterRequest } from "../types/auth";

// Backend auth routes not yet implemented — calls real API client.
// The static API key is injected server-side by middleware.ts from
// the API_KEY env var (never exposed to the browser bundle).

export async function login(body: LoginRequest): Promise<LoginResponse> {
  void body;
  // TODO: Replace with real POST /auth/login once backend auth is implemented.
  // For now, return an empty token — X-API-Key is sent independently.
  return { access_token: "", token_type: "bearer" };
}

export async function register(body: RegisterRequest): Promise<void> {
  void body;
  // TODO: Replace with real POST /auth/register once backend auth is implemented.
}
