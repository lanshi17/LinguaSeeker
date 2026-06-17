/**
 * Next.js middleware — session auth guard + API key injection.
 *
 * Two responsibilities:
 * 1. Session-based auth guard for dashboard routes — redirects unauthenticated
 *    users to /login.  Session is an HMAC-signed cookie set by /api/auth/login.
 * 2. Backend API key injection for /api/v1/* proxy routes — the X-API-Key
 *    header is injected server-side so the key never reaches the browser.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import crypto from "node:crypto";

const SESSION_COOKIE = "ce_session";
const PUBLIC_PATHS = ["/login", "/register", "/api/auth/login", "/api/auth/logout", "/health"];

function isValidSession(token: string | undefined): boolean {
  if (!token) return false;

  const sessionSecret =
    process.env.SESSION_SECRET || process.env.ADMIN_PASSWORD || process.env.API_KEY;
  if (!sessionSecret) return false;

  const [payload, signature] = token.split(".");
  if (!payload || !signature) return false;

  const expected = crypto
    .createHmac("sha256", sessionSecret)
    .update(payload)
    .digest("base64url");

  // Constant-time comparison
  const sigBuf = Buffer.from(signature);
  const expBuf = Buffer.from(expected);
  if (sigBuf.length !== expBuf.length) return false;
  if (!crypto.timingSafeEqual(sigBuf, expBuf)) return false;

  // Check expiry
  try {
    const data = JSON.parse(
      Buffer.from(payload, "base64url").toString("utf-8"),
    ) as { exp: number };
    return data.exp > Math.floor(Date.now() / 1000);
  } catch {
    return false;
  }
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  // ── Auth guard for dashboard routes ──────────────────────────────────
  const isPublicPath = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
  const isApiProxy = pathname.startsWith("/api/v1/");
  const isStaticAsset =
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/static/") ||
    pathname.startsWith("/favicon") ||
    /\.(png|jpg|jpeg|gif|svg|ico|woff2?|ttf|css|js)$/i.test(pathname);

  if (!isPublicPath && !isApiProxy && !isStaticAsset) {
    const sessionToken = request.cookies.get(SESSION_COOKIE)?.value;
    const authEnabled =
      !!process.env.ADMIN_PASSWORD || !!process.env.API_KEY;

    if (authEnabled && !isValidSession(sessionToken)) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("next", pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  // ── API key injection for proxied backend routes ─────────────────────
  if (isApiProxy) {
    const apiKey = process.env.API_KEY;

    // Only inject when the key is configured
    if (!apiKey) {
      return NextResponse.next();
    }

    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("X-API-Key", apiKey);

    return NextResponse.next({
      request: { headers: requestHeaders },
    });
  }

  return NextResponse.next();
}

export const config = {
  // Match all paths except Next.js internals and static files
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
