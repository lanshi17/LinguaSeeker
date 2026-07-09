import { apiClient } from "@/lib/api/client";
import type {
  AuthAccount,
  AuthResponse,
  LoginRequest,
  LogoutResponse,
} from "../types/auth";

export async function getAuthMe(): Promise<AuthAccount> {
  const { data } = await apiClient.get<AuthAccount>("/auth/me");
  return data;
}

export async function login(body: LoginRequest): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>("/auth/login", body);
  return data;
}

export async function logout(): Promise<LogoutResponse> {
  const { data } = await apiClient.post<LogoutResponse>("/auth/logout");
  return data;
}
