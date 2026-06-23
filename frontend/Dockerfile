# syntax=docker/dockerfile:1.7
# ────────────────────────────────────────────────────────────────────
# Stage 1: build the Vite SPA with bun.
#   The build-time API base URL is baked into the bundle via VITE_*.
#   Everything injected through ARG must be non-secret: it ships to the
#   browser. Real secrets (API_KEY) stay on the nginx server below.
# ────────────────────────────────────────────────────────────────────
FROM oven/bun:1.1-alpine AS builder

WORKDIR /app

# Subpath mount point (e.g. /linguaseeker). The built index.html references
# /<base>/assets/... and API/health URLs derive from import.meta.env.BASE_URL,
# so the runtime nginx only needs to proxy <base>/api/ → backend.
ARG VITE_BASE_PATH=/
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
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
# BASE_PATH must match the build-time VITE_BASE_PATH (SPA asset/API URLs
# are baked into the bundle relative to the Vite base).
ENV BACKEND_URL=http://backend:8000 \
    API_KEY="" \
    FRONTEND_MAX_BODY=200m \
    BASE_PATH=""

EXPOSE 80

# nginx official image already has a sane entrypoint that runs scripts
# in /docker-entrypoint.d/ before starting nginx, so we just rely on it.
