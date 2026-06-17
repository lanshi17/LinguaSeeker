"""Security headers middleware for FastAPI.

Adds defense-in-depth HTTP security headers to all responses:
- Strict-Transport-Security (HSTS)
- X-Content-Type-Options
- X-Frame-Options
- Content-Security-Policy
- Referrer-Policy
- Permissions-Policy
- X-XSS-Protection (legacy, for older browsers)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related HTTP headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Prevent clickjacking
        response.headers.setdefault("X-Frame-Options", "DENY")

        # Control referrer information leakage
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # Restrict browser features (camera, mic, geolocation, etc.)
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), bluetooth=()",
        )

        # Content Security Policy — restrictive by default
        # Backend is an API, so we can use a very strict policy
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )

        # Legacy XSS protection header (mostly redundant with CSP, but harmless)
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")

        return response


class SecurityHeadersMiddlewareHSTS(SecurityHeadersMiddleware):
    """Security headers plus HTTP Strict Transport Security (HSTS).

    Use this variant in production behind TLS.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await super().dispatch(request, call_next)
        # HSTS: 1 year, include subdomains, allow preload
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains; preload",
        )
        return response
