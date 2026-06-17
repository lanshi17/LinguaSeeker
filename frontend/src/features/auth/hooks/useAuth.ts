"use client";

import { useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { login as loginApi, register as registerApi } from "../services/auth";
import type { LoginRequest, RegisterRequest, AuthUser } from "../types/auth";

/**
 * Authentication hook.
 *
 * Manages login/logout state. Token is persisted in localStorage.
 * Does NOT use a global auth store — auth state is lightweight enough
 * to live in this hook and be consumed via React context if needed later.
 */
export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(() => {
    if (typeof window === "undefined") return null;
    const token = localStorage.getItem("access_token");
    const email = localStorage.getItem("auth_email");
    return token && email ? { email } : null;
  });

  const loginMutation = useMutation({
    mutationFn: (body: LoginRequest) => loginApi(body),
    onSuccess: (data, variables) => {
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("auth_email", variables.email);
      setUser({ email: variables.email });
    },
  });

  const registerMutation = useMutation({
    mutationFn: (body: RegisterRequest) => registerApi(body),
  });

  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Ignore — cookie will expire eventually
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("auth_email");
    setUser(null);
  }, []);

  return {
    user,
    isAuthenticated: user !== null,
    login: loginMutation.mutateAsync,
    register: registerMutation.mutateAsync,
    logout,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,
    loginError: loginMutation.error,
    registerError: registerMutation.error,
  };
}
