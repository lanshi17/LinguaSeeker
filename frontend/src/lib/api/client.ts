/**
 * Shared Axios instance used by every feature service layer.
 *
 * Auth: sends browser cookies for the public/personal account session.
 *
 * The API base URL follows the SPA mount point (import.meta.env.BASE_URL,
 * set from the Vite `base` config): mounted at /linguaseeker it resolves to
 * "/linguaseeker/api/v1", at root to "/api/v1". Override with
 * VITE_API_BASE_URL only when the API lives on a different origin.
 */

import axios from "axios";
import type { AxiosResponse } from "axios";
import { normalizeError } from "./error";
import { createResponseCacheAdapter } from "./responseCache";

const baseURL =
  import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL}api/v1`;
const timeout = Number(import.meta.env.VITE_API_TIMEOUT) || 30_000;

export const apiClient = axios.create({
  baseURL,
  timeout,
  withCredentials: true,
  adapter: createResponseCacheAdapter(axios.getAdapter(axios.defaults.adapter)),
  headers: {
    "Content-Type": "application/json",
  },
});

// Normalize errors into ApiError for consistent handling downstream.
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => Promise.reject(normalizeError(error)),
);
