#!/usr/bin/env bash
# ==============================================================================
# deploy_frontend.sh — Build and deploy the frontend SPA to production.
#
# Builds the Vite+React frontend with VITE_BASE_PATH=/linguaseeker, then
# uploads the dist/ to the production server via LFTP reverse mirror.
#
# Usage (run from anywhere inside the repo):
#   # Use the shell alias (reads credentials from ~/.zshrc / ~/.bashrc):
#   ./scripts/deploy/deploy_frontend.sh
#
#   # Or override via env vars (avoids hardcoded alias):
#   FTP_HOST=47.239.135.59 FTP_USER=ftp FTP_PASSWORD='...' \
#     ./scripts/deploy/deploy_frontend.sh
#
#   # Build only, skip upload:
#   ./scripts/deploy/deploy_frontend.sh --build-only
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Defaults ─────────────────────────────────────────────────────────────
VITE_BASE_PATH="${VITE_BASE_PATH:-/linguaseeker}"
BUILD_ONLY=0

usage() {
  cat <<'USAGE'
Usage: scripts/deploy/deploy_frontend.sh [options]

Options:
  --build-only        Build only, skip FTP upload
  -h, --help          Show this help

Environment variables:
  FTP_HOST            Production server hostname/IP (default: from alias)
  FTP_USER            FTP user (default: ftp)
  FTP_PASSWORD        FTP password (required if FTP_HOST is set)
  VITE_BASE_PATH      Vite base path (default: /linguaseeker)

The script falls back to the shell `deploy` alias for credentials when
FTP_HOST is not explicitly set. The alias is defined in ~/.zshrc as:

  alias deploy='lftp -u ... 47.239.135.59 -e "mirror -R ./dist/ /linguaseeker/"'
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-only)
      BUILD_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# ── Resolve FTP credentials (only needed for deploy) ────────────────────
if [[ "$BUILD_ONLY" -eq 0 ]]; then
  if [[ -n "${FTP_HOST:-}" ]]; then
    DEPLOY_HOST="$FTP_HOST"
    DEPLOY_USER="${FTP_USER:-ftp}"
    DEPLOY_PASSWORD="${FTP_PASSWORD:?FTP_PASSWORD must be set when FTP_HOST is provided}"
  else
    # Try current shell alias first (works in bash/zsh)
    if alias deploy &>/dev/null; then
      ALIAS_CMD="$(alias deploy)"
    else
      # Parse alias from shell config files directly.
      # Sourcing .zshrc from bash is fragile — zsh syntax breaks bash.
      for rc in ~/.zshrc ~/.bashrc ~/.bash_profile ~/.profile; do
        [[ -f "$rc" ]] || continue
        ALIAS_CMD="$(grep -m1 -E '^alias deploy=' "$rc" 2>/dev/null)"
        [[ -n "$ALIAS_CMD" ]] && break
      done
    fi

    if [[ -z "${ALIAS_CMD:-}" ]]; then
      echo "ERROR: no deploy alias found and FTP_HOST not set." >&2
      echo "Either:" >&2
      echo "  1. Set FTP_HOST/FTP_USER/FTP_PASSWORD env vars" >&2
      echo "  2. Define a deploy alias in ~/.zshrc or ~/.bashrc" >&2
      exit 1
    fi

    if [[ $ALIAS_CMD =~ lftp[[:space:]]+-u[[:space:]]+([^,]+),([^[:space:]]+)[[:space:]]+([^[:space:]]+) ]]; then
      DEPLOY_USER="${BASH_REMATCH[1]}"
      DEPLOY_PASSWORD="${BASH_REMATCH[2]}"
      DEPLOY_HOST="${BASH_REMATCH[3]%%[\"\$]*}"
    else
      echo "ERROR: cannot parse deploy alias: $ALIAS_CMD" >&2
      echo "Set FTP_HOST/FTP_USER/FTP_PASSWORD env vars instead." >&2
      exit 1
    fi
  fi
fi

# ── Build ────────────────────────────────────────────────────────────────
echo "━━━ Building frontend with VITE_BASE_PATH=${VITE_BASE_PATH} ━━━"
cd "$REPO_ROOT/frontend"

VITE_BASE_PATH="$VITE_BASE_PATH" bun run build

echo "✓ Build complete"

if [[ "$BUILD_ONLY" -eq 1 ]]; then
  echo "  dist/: $REPO_ROOT/frontend/dist/"
  echo "  (--build-only, skipping upload)"
  exit 0
fi

# ── Deploy ───────────────────────────────────────────────────────────────
echo "━━━ Deploying to ${DEPLOY_HOST} as ${DEPLOY_USER} ━━━"
echo "  source:  frontend/dist/"
echo "  target:  /linguaseeker/"

lftp \
  -u "$DEPLOY_USER","$DEPLOY_PASSWORD" \
  "$DEPLOY_HOST" \
  -e "mirror -R '$REPO_ROOT/frontend/dist/' /linguaseeker/; bye"

echo "✓ Deploy complete"
