/**
 * Typed configuration interfaces.
 *
 * These mirror the NEXT_PUBLIC_* environment variables defined in
 * the layered .env files.  Access via the appConfig / apiConfig
 * singletons — never read process.env directly outside this module.
 */

export interface AppConfig {
  /** Application display name. */
  name: string;
  /** Semantic version string. */
  version: string;
  /** Current environment: "development" | "production". */
  environment: "development" | "production";
  /** Enable verbose logging and dev tools. */
  debug: boolean;
}

export interface ApiConfig {
  /**
   * Base URL for API requests.
   *
   * MUST be a relative path ("/api/v1") in production so that requests
   * pass through Next.js middleware.ts, which injects the server-side
   * X-API-Key header.  An absolute URL bypasses middleware and protected
   * routes will 401.
   */
  baseUrl: string;
  /** Request timeout in milliseconds. */
  timeout: number;
  /** Health check endpoint path (relative to baseUrl's origin). */
  healthEndpoint: string;
  /** Health check polling interval in milliseconds. */
  healthPollInterval: number;
}

export interface FeatureFlags {
  /** Enable the chat / SSE streaming feature. */
  enableChat: boolean;
  /** Enable the knowledge graph explorer. */
  enableGraph: boolean;
}
