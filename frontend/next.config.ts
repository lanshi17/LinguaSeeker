import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Prevent MIME-type sniffing
          { key: "X-Content-Type-Options", value: "nosniff" },
          // Prevent clickjacking
          { key: "X-Frame-Options", value: "DENY" },
          // Control referrer information leakage
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Restrict browser features (camera, mic, geolocation, etc.)
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), bluetooth=()",
          },
          // Content Security Policy — restrictive baseline
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; " +
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'; " +
              "style-src 'self' 'unsafe-inline'; " +
              "img-src 'self' data: blob:; " +
              "font-src 'self' data:; " +
              "connect-src 'self'; " +
              "frame-ancestors 'none'; " +
              "base-uri 'self'; " +
              "form-action 'self'",
          },
          // Legacy XSS protection header (redundant with CSP but harmless)
          { key: "X-XSS-Protection", value: "1; mode=block" },
        ],
      },
    ];
  },

  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://localhost:8000/api/v1/:path*",
      },
      {
        source: "/health",
        destination: "http://localhost:8000/health",
      },
    ];
  },
};

export default nextConfig;
