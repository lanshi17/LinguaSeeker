#!/usr/bin/env bash
# ── ACMG-Lingua Backend — Development Server ──────────────────────────────
# Starts uvicorn with hot-reload, excluding files that change during pipeline
# execution (logs, temp data, migrations) so that editing state_persistence
# or running a pipeline doesn't kill in-flight requests.
#
# Usage:
#   ./scripts/start_backend_dev.sh          # default port 8000
#   ./scripts/start_backend_dev.sh --port 8001
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/../backend"

exec uv run uvicorn app.main:app \
    --reload \
    --reload-dir src \
    --reload-dir app \
    --reload-exclude "logs/*" \
    --reload-exclude "*.log" \
    --reload-exclude "__pycache__" \
    --reload-exclude ".venv" \
    --reload-exclude "database/migrations/*" \
    --reload-exclude "*.pyc" \
    --timeout-graceful-shutdown 120 \
    "$@"
