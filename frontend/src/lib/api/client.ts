/**
 * Shared Axios instance used by every feature service layer.
 *
 * Auth is handled by the backend via session cookie or X-API-Key header;
 * no client-side token management is required.
 */

import axios from "axios";
import type { AxiosResponse } from "axios";
import { normalizeError } from "./error";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const timeout = Number(import.meta.env.VITE_API_TIMEOUT) || 30_000;
const apiKey = import.meta.env.VITE_API_KEY || "";

export const apiClient = axios.create({
  baseURL,
  timeout,
  headers: {
    "Content-Type": "application/json",
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  },
});

// Normalize errors into ApiError for consistent handling downstream.
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => Promise.reject(normalizeError(error)),
);
