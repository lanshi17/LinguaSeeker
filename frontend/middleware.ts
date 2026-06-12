/**
 * Next.js middleware that injects the backend API key into proxied requests.
 *
 * The backend requires X-API-Key for protected routes.  This key MUST NOT
 * be exposed in the browser bundle (NEXT_PUBLIC_* vars are client-visible).
 * Instead, the key lives in a server-only API_KEY env var and is injected
 * here — middleware runs exclusively on the server, even during CSR navigations.
 *
 * Requests matching /api/v1/* are rewritten to the backend origin by
 * next.config.ts.  This middleware runs before the rewrite, so the injected
 * header travels all the way to the backend.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest): NextResponse {
  const apiKey = process.env.API_KEY;

  // Only inject when the key is configured (auth disabled when empty).
  if (!apiKey) {
    return NextResponse.next();
  }

  // Clone the request with the X-API-Key header injected.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("X-API-Key", apiKey);

  return NextResponse.next({
    request: { headers: requestHeaders },
  });
}

export const config = {
  // Only intercept API proxy routes — skip static assets, pages, etc.
  matcher: "/api/v1/:path*",
};
