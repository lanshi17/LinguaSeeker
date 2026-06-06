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
   * Relative path ("/api/v1") → goes through Next.js proxy.
   * Absolute URL ("http://host:port/api/v1") → direct connection.
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
