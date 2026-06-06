/**
 * API configuration.
 *
 * Centralizes API-related settings consumed by useBackendHealth
 * and other infrastructure hooks. The apiClient hardcodes its
 * own baseURL to avoid Turbopack module-caching issues with
 * NEXT_PUBLIC_* inlining.
 */

import type { ApiConfig } from "./types";

export const apiConfig: ApiConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1",
  timeout: Number(process.env.NEXT_PUBLIC_API_TIMEOUT) || 30_000,
  healthEndpoint: process.env.NEXT_PUBLIC_HEALTH_ENDPOINT || "/health",
  healthPollInterval:
    Number(process.env.NEXT_PUBLIC_HEALTH_POLL_INTERVAL) || 30_000,
};
