/**
 * API configuration.
 *
 * Centralizes all API-related settings. The apiClient and
 * useBackendHealth hook import from here instead of reading
 * process.env directly.
 */

import type { ApiConfig } from "./types";

export const apiConfig: ApiConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1",
  timeout: Number(process.env.NEXT_PUBLIC_API_TIMEOUT) || 30_000,
  healthEndpoint: process.env.NEXT_PUBLIC_HEALTH_ENDPOINT ?? "/health",
  healthPollInterval:
    Number(process.env.NEXT_PUBLIC_HEALTH_POLL_INTERVAL) || 30_000,
};
