#!/usr/bin/env bash
# ==============================================================================
# deploy_frontend.sh — Build and deploy the frontend SPA to production.
#
# Builds the Vite+React frontend with VITE_BASE_PATH=/linguaseeker, asserts
# the bundle actually references the subpath assets (a bare `bun run build`
# without the base path ships a white screen: HTML 200, /assets/*.js 404),
# uploads dist/ to the production server via LFTP reverse mirror, then
# smoke-checks the live site with a browser User-Agent (the server's
# block_bots.rule 403s curl's default UA).
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
#
#   # Skip the post-upload live smoke check (e.g. offline):
#   ./scripts/deploy/deploy_frontend.sh --no-smoke
# ==============================================================================
set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Defaults ─────────────────────────────────────────────────────────────
VITE_BASE_PATH="${VITE_BASE_PATH:-/linguaseeker}"
BUILD_ONLY=0
SMOKE=1
DEPLOY_URL="${DEPLOY_URL:-https://genemed.tech${VITE_BASE_PATH}/}"
SMOKE_UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"

usage() {
  cat <<'USAGE'
Usage: scripts/deploy/deploy_frontend.sh [options]

Options:
  --build-only        Build only (still asserts the bundle base path)
  --no-smoke          Skip the post-upload live smoke check
  -h, --help          Show this help

Environment variables:
  FTP_HOST            Production server hostname/IP (default: from alias)
  FTP_USER            FTP user (default: ftp)
  FTP_PASSWORD        FTP password (required if FTP_HOST is set)
  VITE_BASE_PATH      Vite base path (default: /linguaseeker)
  DEPLOY_URL          Public URL for the smoke check (default:
                      https://genemed.tech$VITE_BASE_PATH/)

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
    --no-smoke)
      SMOKE=0
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

# ── Assert bundle base path (white-screen guard) ─────────────────────────
# 2026-09-03 incident: a bundle built without VITE_BASE_PATH referenced
# /assets/*.js at the site root — HTML 200, every asset 404, blank page.
INDEX_HTML="$REPO_ROOT/frontend/dist/index.html"
if ! grep -q "src=\"${VITE_BASE_PATH}/assets/" "$INDEX_HTML"; then
  echo "ERROR: dist/index.html does not reference ${VITE_BASE_PATH}/assets/ —" >&2
  echo "       the bundle was built with the wrong base path and would ship a" >&2
  echo "       white screen. Check VITE_BASE_PATH / frontend/.env.production." >&2
  exit 1
fi
echo "✓ Bundle references ${VITE_BASE_PATH}/assets/ correctly"

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

# ── Live smoke check ──────────────────────────────────────────────────────
# Fetch the deployed index.html with a browser UA (the server's
# block_bots.rule 403s curl's default UA) and verify every referenced
# bundle asset returns HTTP 200.
if [[ "$SMOKE" -eq 1 ]]; then
  echo "━━━ Smoke check: ${DEPLOY_URL} ━━━"
  if ! html="$(curl -fsSk -A "$SMOKE_UA" --max-time 30 "$DEPLOY_URL")"; then
    echo "✗ ERROR: cannot fetch ${DEPLOY_URL} — site unreachable" >&2
    echo "       The server's block_bots.rule also 403s non-browser UAs and" >&2
    echo "       temporarily bans IPs that hammer the site; verify in a real" >&2
    echo "       browser, or rerun later / from another network." >&2
    exit 1
  fi
  origin="$(sed -E 's#(^[a-z]+://[^/]+).*$#\1#' <<<"$DEPLOY_URL")"
  failed=0
  while IFS= read -r asset; do
    case "$asset" in
      "$VITE_BASE_PATH"/*)
        # Absolute path under the base — resolve against the site origin,
        # exactly like the browser does for `src="/linguaseeker/assets/..."`.
        asset_url="${origin}${asset}"
        ;;
      /*)
        # Absolute path OUTSIDE the base — base-path regression: the browser
        # will request it from the site root where it 404s (2026-09-03
        # white screen). Fail loudly instead of silently resolving under base.
        echo "✗ asset not under VITE_BASE_PATH: ${asset}" >&2
        echo "       (deployed bundle was built without the subpath base)" >&2
        failed=1
        continue
        ;;
      http://*|https://*)
        # Fully-qualified external URL (e.g. OSS-hosted favicon) — skip.
        continue
        ;;
      *)
        # Relative path — resolve against the deployed page URL.
        asset_url="${DEPLOY_URL%/}/${asset}"
        ;;
    esac
    status="$(curl -sk -A "$SMOKE_UA" -o /dev/null -w '%{http_code}' --max-time 30 "$asset_url")"
    if [[ "$status" != "200" ]]; then
      echo "✗ ${status} ${asset_url}" >&2
      failed=1
    else
      echo "  200 ${asset_url}"
    fi
  done < <(grep -oE '(src|href)="[^"]+\.js["]?|(src|href)="[^"]+\.css"' <<<"$html" \
           | sed -E 's/^(src|href)="//; s/"$//' | sort -u)
  if [[ "$failed" -ne 0 ]]; then
    echo "✗ ERROR: deployed page references assets that do not resolve." >&2
    echo "       Check nginx location mapping / VITE_BASE_PATH consistency." >&2
    exit 1
  fi
  echo "✓ Live smoke check passed"
fi

echo "✓ Deploy complete"
