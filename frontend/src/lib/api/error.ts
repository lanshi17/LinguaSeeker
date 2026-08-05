/**
 * Standardized API error handling.
 *
 * All feature service layers normalize Axios errors into ApiError
 * before surfacing them to hooks and components.
 */

import { AxiosError } from "axios";

/** Structured error returned by the backend. */
interface BackendErrorResponse {
  detail?: string;
  message?: string;
  error?: {
    code?: string;
    message?: string;
  };
}

/** Normalized error thrown by the API client interceptors and service functions. */
export class ApiError extends Error {
  readonly status: number;
  readonly backendMessage: string;

  constructor(status: number, message: string, backendMessage?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.backendMessage = backendMessage ?? message;
  }
}

/**
 * Convert an AxiosError into a normalized ApiError.
 *
 * Network failures (no response) get status 0.
 * Responses without a structured body use the HTTP status text.
 */
export function normalizeError(error: AxiosError<BackendErrorResponse>): ApiError {
  if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
    return new ApiError(0, "Request timed out — please try again.");
  }

  if (!error.response) {
    return new ApiError(0, "Network error — please check your connection.");
  }

  const { status, statusText, data } = error.response;
  const backendMessage =
    data?.error?.message ??
    data?.detail ??
    data?.message ??
    statusText ??
    "Unknown error";

  return new ApiError(status, `Request failed: ${backendMessage}`, backendMessage);
}

/**
 * Extract a human-readable message from an unknown error value.
 *
 * Handles ApiError (duck-typed for bundler compatibility), plain Error
 * objects, and string errors.  Returns `fallback` when nothing matches.
 */
export function extractErrorMessage(err: unknown, fallback = "An unexpected error occurred"): string {
  if (err && typeof err === "object" && "backendMessage" in err) {
    const msg = String((err as { backendMessage: unknown }).backendMessage);
    if (msg) return msg;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
