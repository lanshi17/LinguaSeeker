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
  if (!error.response) {
    return new ApiError(0, "Network error — please check your connection.");
  }

  const { status, statusText, data } = error.response;
  const backendMessage =
    data?.detail ?? data?.message ?? statusText ?? "Unknown error";

  return new ApiError(status, `Request failed: ${backendMessage}`, backendMessage);
}
