/**
 * API configuration.
 *
 * Centralizes API-related settings consumed by the shared API
 * client, infrastructure hooks, and feature service helpers.
 */

import type { ApiConfig } from "./types";

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";

// In production, baseUrl MUST be relative so requests pass through
// middleware.ts (which injects X-API-Key from server-only API_KEY).
if (
  process.env.NODE_ENV === "production" &&
  /^https?:\/\//.test(baseUrl)
) {
  console.warn(
    `[config] NEXT_PUBLIC_API_BASE_URL="${baseUrl}" is absolute — ` +
      "requests will bypass middleware.ts and X-API-Key will not be " +
      "injected. Protected routes will 401.",
  );
}

export const apiConfig: ApiConfig = {
  baseUrl,
  timeout: Number(process.env.NEXT_PUBLIC_API_TIMEOUT) || 30_000,
  healthEndpoint: process.env.NEXT_PUBLIC_HEALTH_ENDPOINT || "/health",
  healthPollInterval:
    Number(process.env.NEXT_PUBLIC_HEALTH_POLL_INTERVAL) || 30_000,
};
