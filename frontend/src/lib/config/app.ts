/**
 * Application-level configuration.
 *
 * Reads VITE_* env vars into a typed object.
 * Values come from the layered .env files (see .env, .env.development,
 * .env.production, .env.local) with the standard Vite priority:
 *
 *   .env < .env.development/.env.production < .env.local < OS env vars
 */

import type { AppConfig, FeatureFlags } from "./types";

export const appConfig: AppConfig = {
  name: import.meta.env.VITE_APP_NAME ?? "Lingua Seeker",
  version: import.meta.env.VITE_APP_VERSION ?? "0.0.0",
  environment: import.meta.env.PROD ? "production" : "development",
  debug: import.meta.env.VITE_DEBUG === "true",
};

export const featureFlags: FeatureFlags = {
  enableChat: import.meta.env.VITE_ENABLE_CHAT !== "false",
  enableGraph: import.meta.env.VITE_ENABLE_GRAPH !== "false",
};
