export type AuthAccountType = "public" | "user";

export interface AuthAccount {
  authenticated: boolean;
  account_type: AuthAccountType;
  user_id: string | null;
  username: string | null;
  display_name: string | null;
}

export interface AuthResponse {
  success: boolean;
  account: AuthAccount;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LogoutResponse {
  success: boolean;
}
