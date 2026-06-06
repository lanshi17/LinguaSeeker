/** POST /auth/login request body. */
export interface LoginRequest {
  email: string;
  password: string;
}

/** POST /auth/login response body. */
export interface LoginResponse {
  access_token: string;
  token_type: string;
}

/** POST /auth/register request body. */
export interface RegisterRequest {
  email: string;
  password: string;
  password_confirm: string;
}

/** Current authenticated user state. */
export interface AuthUser {
  email: string;
}
