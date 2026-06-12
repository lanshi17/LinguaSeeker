/**
 * API configuration.
 *
 * Centralizes API-related settings consumed by the shared API
 * client, infrastructure hooks, and feature service helpers.
 */

import type { ApiConfig } from "./types";

export const apiConfig: ApiConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1",
  timeout: Number(process.env.NEXT_PUBLIC_API_TIMEOUT) || 30_000,
  healthEndpoint: process.env.NEXT_PUBLIC_HEALTH_ENDPOINT || "/health",
  healthPollInterval:
    Number(process.env.NEXT_PUBLIC_HEALTH_POLL_INTERVAL) || 30_000,
  apiKey: process.env.NEXT_PUBLIC_API_KEY || "",
};
