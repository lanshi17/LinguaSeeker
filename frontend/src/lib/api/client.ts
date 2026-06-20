/**
 * Shared Axios instance used by every feature service layer.
 *
 * Configuration comes from @/lib/config (layered .env files).
 * Auth is handled by the backend via session cookie or X-API-Key header;
 * no client-side token management is required.
 */

import axios from "axios";
import type { AxiosResponse } from "axios";
import { apiConfig } from "../config";
import { normalizeError } from "./error";

export const apiClient = axios.create({
  baseURL: apiConfig.baseUrl,
  timeout: apiConfig.timeout,
  headers: {
    "Content-Type": "application/json",
  },
});

// Normalize errors into ApiError for consistent handling downstream.
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => Promise.reject(normalizeError(error)),
);
