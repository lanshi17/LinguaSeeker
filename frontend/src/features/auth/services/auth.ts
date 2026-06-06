import type { LoginRequest, LoginResponse, RegisterRequest } from "../types/auth";

// Backend auth routes not yet implemented — stubbed for frontend development.
// Replace with real apiClient calls once POST /auth/login and /auth/register exist.

export async function login(_body: LoginRequest): Promise<LoginResponse> {
  return { access_token: "dev-stub-token", token_type: "bearer" };
}

export async function register(_body: RegisterRequest): Promise<void> {
  // no-op
}
