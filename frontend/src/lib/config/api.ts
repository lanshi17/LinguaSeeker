/**
 * API configuration.
 *
 * Centralizes API-related settings consumed by the shared API
 * client, infrastructure hooks, and feature service helpers.
 */

import type { ApiConfig } from "./types";

const baseUrl = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const timeout = Number(import.meta.env.VITE_API_TIMEOUT) || 30_000;
const healthEndpoint = import.meta.env.VITE_HEALTH_ENDPOINT || "/health";
const healthPollInterval =
  Number(import.meta.env.VITE_HEALTH_POLL_INTERVAL) || 30_000;

export const apiConfig: ApiConfig = {
  baseUrl,
  timeout,
  healthEndpoint,
  healthPollInterval,
};
