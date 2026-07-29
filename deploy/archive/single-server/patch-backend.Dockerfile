# ── Backend Code Patch — thin overlay on existing image ──────────────
# Use when only Python source code changed (no dependency changes).
# Build ON the target server (no uv/Rust needed, just Docker).
#
#   docker build -t lingua-seeker-backend:local \
#     -f deploy/compose/single-server/patch-backend.Dockerfile .
# -------------------------------------------------------------------
FROM lingua-seeker-backend:local

# Only copies changed source files — one thin layer (~MB)
COPY backend/ /app/

USER deploy
