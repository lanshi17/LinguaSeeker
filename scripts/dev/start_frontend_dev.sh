#!/usr/bin/env bash
# ── CrossEvidence Frontend — Development Server ─────────────────────────────
# Starts the Vite dev server with hot-module replacement.
# The dev server proxies /api/v1/* and /health to the backend (default :8000).
#
# Usage:
#   ./scripts/start_frontend_dev.sh              # default port 3000
#   ./scripts/start_frontend_dev.sh --port 3001  # custom port
#   ./scripts/start_frontend_dev.sh --host       # expose on LAN
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/../../frontend"

exec bun run dev "$@"
