# syntax=docker/dockerfile:1.7
# ────────────────────────────────────────────────────────────────────
# Stage 1: build the Vite SPA with bun.
#   The build-time API base URL is baked into the bundle via VITE_*.
#   Everything injected through ARG must be non-secret: it ships to the
#   browser. Real secrets (API_KEY) stay on the nginx server below.
# ────────────────────────────────────────────────────────────────────
FROM oven/bun:1.1-alpine AS builder

WORKDIR /app

# Same-origin in production: the bundled SPA hits /api/v1 on its own host,
# the runtime nginx proxies that prefix to the backend server.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV NODE_ENV=production

COPY package.json bun.lock* bun.lockb* ./
RUN bun install --frozen-lockfile

COPY . .
RUN bun run build

# ────────────────────────────────────────────────────────────────────
# Stage 2: nginx serves dist/ and reverse-proxies /api/v1 + /health
#   to the backend server. The shared X-API-Key is injected here so it
#   never ships to the browser.
# ────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# envsubst lives in gettext; we need it to template nginx.conf at boot.
RUN apk add --no-cache gettext

COPY --from=builder /app/dist /usr/share/nginx/html
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker/entrypoint.sh /docker-entrypoint.d/40-render-conf.sh
RUN chmod +x /docker-entrypoint.d/40-render-conf.sh

# Defaults — override at deploy time via -e or compose `environment:`.
ENV BACKEND_URL=http://backend:8000 \
    API_KEY="" \
    FRONTEND_MAX_BODY=200m

EXPOSE 80

# nginx official image already has a sane entrypoint that runs scripts
# in /docker-entrypoint.d/ before starting nginx, so we just rely on it.
