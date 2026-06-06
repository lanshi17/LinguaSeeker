import { apiClient } from "@/lib/api/client";
import type { LoginRequest, LoginResponse, RegisterRequest } from "../types/auth";

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login", body);
  return data;
}

export async function register(body: RegisterRequest): Promise<void> {
  await apiClient.post("/auth/register", body);
}
