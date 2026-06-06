/**
 * Shared Axios instance used by every feature service layer.
 *
 * Configuration comes from @/lib/config (layered .env files).
 * - Request interceptor injects the auth token from localStorage.
 * - Response interceptor normalizes errors into ApiError and redirects
 *   to /login on 401 (with a guard to prevent duplicate navigations).
 */

import axios from "axios";
import type { InternalAxiosRequestConfig, AxiosResponse } from "axios";
import { apiConfig } from "@/lib/config";
import { normalizeError } from "./error";

/** Guard against concurrent 401s each triggering a navigation. */
let isRedirectingToLogin = false;

export const apiClient = axios.create({
  baseURL: apiConfig.baseUrl,
  timeout: apiConfig.timeout,
  headers: {
    "Content-Type": "application/json",
  },
});

// --------------- Request interceptor ---------------

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// --------------- Response interceptor ---------------

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    // Redirect to login on 401 (client-side only, once).
    if (typeof window !== "undefined" && error.response?.status === 401) {
      if (!isRedirectingToLogin) {
        isRedirectingToLogin = true;
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }
    }

    // Normalize to ApiError for consistent handling downstream.
    return Promise.reject(normalizeError(error));
  },
);
