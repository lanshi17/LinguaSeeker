/**
 * Application-level configuration.
 *
 * Reads NEXT_PUBLIC_* env vars into a typed object.
 * Values come from the layered .env files (see .env, .env.development,
 * .env.production, .env.local) with the standard Next.js priority:
 *
 *   .env < .env.development/.env.production < .env.local < OS env vars
 */

import type { AppConfig, FeatureFlags } from "./types";

export const appConfig: AppConfig = {
  name: process.env.NEXT_PUBLIC_APP_NAME ?? "Cross Evidence",
  version: process.env.NEXT_PUBLIC_APP_VERSION ?? "0.0.0",
  environment:
    process.env.NODE_ENV === "production" ? "production" : "development",
  debug: process.env.NEXT_PUBLIC_DEBUG === "true",
};

export const featureFlags: FeatureFlags = {
  enableChat: process.env.NEXT_PUBLIC_ENABLE_CHAT !== "false",
  enableGraph: process.env.NEXT_PUBLIC_ENABLE_GRAPH !== "false",
};
