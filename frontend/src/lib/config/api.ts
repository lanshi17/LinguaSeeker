/**
 * API configuration.
 *
 * Centralizes all API-related settings. The apiClient and
 * useBackendHealth hook import from here instead of reading
 * process.env directly.
 */

import type { ApiConfig } from "./types";

// Resolve base URL: prefer env var, fall back to relative proxy path.
// The "||" fallback ensures "/api/v1" even when the env var is an empty string.
const resolvedBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";

export const apiConfig: ApiConfig = {
  baseUrl: resolvedBaseUrl,
  timeout: Number(process.env.NEXT_PUBLIC_API_TIMEOUT) || 30_000,
  healthEndpoint: process.env.NEXT_PUBLIC_HEALTH_ENDPOINT || "/health",
  healthPollInterval:
    Number(process.env.NEXT_PUBLIC_HEALTH_POLL_INTERVAL) || 30_000,
};

// Temporary debug — check browser console. Remove after confirming.
if (typeof window !== "undefined") {
  // eslint-disable-next-line no-console
  console.warn(
    "[apiConfig] baseUrl =",
    resolvedBaseUrl,
    "| raw env =",
    process.env.NEXT_PUBLIC_API_BASE_URL,
  );
}
