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

const SESSION_COOKIE = "ce_session";
const PUBLIC_PATHS = ["/login", "/register", "/api/auth/login", "/api/auth/logout", "/health"];

async function isValidSession(token: string | undefined): Promise<boolean> {
  if (!token) return false;

  const sessionSecret =
    process.env.SESSION_SECRET || process.env.ADMIN_PASSWORD || process.env.API_KEY;
  if (!sessionSecret) return false;

  const [payload, signature] = token.split(".");
  if (!payload || !signature) return false;

  try {
    const encoder = new TextEncoder();
    const keyData = encoder.encode(sessionSecret);
    const key = await crypto.subtle.importKey(
      "raw",
      keyData,
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );

    const signatureBytes = await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(payload)
    );

    const bytes = new Uint8Array(signatureBytes);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const expected = btoa(binary)
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=/g, "");

    if (signature.length !== expected.length) return false;
    let result = 0;
    for (let i = 0; i < signature.length; i++) {
      result |= signature.charCodeAt(i) ^ expected.charCodeAt(i);
    }
    if (result !== 0) return false;

    const data = JSON.parse(
      atob(payload.replace(/-/g, "+").replace(/_/g, "/"))
    ) as { exp: number };
    return data.exp > Math.floor(Date.now() / 1000);
  } catch {
    return false;
  }
}

export async function middleware(request: NextRequest): Promise<NextResponse> {
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

    if (authEnabled && !(await isValidSession(sessionToken))) {
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
