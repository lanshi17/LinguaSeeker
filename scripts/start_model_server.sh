#!/usr/bin/env bash
# ── ACMG-Lingua Model Server ─────────────────────────────────────────────
# Starts the model server (embedding, rerank, VLM) on port 8001 by default.
# Models are lazy-loaded on first request; embedding, rerank, and VLM share
# a single GPU sequentially.
#
# Usage:
#   ./scripts/start_model_server.sh              # default port 8001
#   ./scripts/start_model_server.sh --port 8002  # custom port
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/../backend/services/model-server"

exec uv run python main.py "$@"
