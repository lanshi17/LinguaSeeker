import type { LoginRequest, LoginResponse, RegisterRequest } from "../types/auth";

// Backend auth routes not yet implemented — stubbed for frontend development.
// Replace with real apiClient calls once POST /auth/login and /auth/register exist.

export async function login(body: LoginRequest): Promise<LoginResponse> {
  // TODO: Replace with real apiClient call once POST /auth/login exists.
  void body;
  return { access_token: "dev-stub-token", token_type: "bearer" };
}

export async function register(body: RegisterRequest): Promise<void> {
  // TODO: Replace with real apiClient call once POST /auth/register exists.
  void body;
}
