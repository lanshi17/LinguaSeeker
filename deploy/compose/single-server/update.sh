#!/bin/bash
# ============================================================================
# Incremental Update Script — pull pre-built container image
# ============================================================================
# Run ON the target CentOS server. Pulls the configured backend image and
# restarts affected services. Source code is not required on the server.
#
# Usage:
#   ./update.sh backend          # update backend only
#   ./update.sh all              # update everything
# ============================================================================
set -euo pipefail

DEPLOY_DIR="/opt/lingua-seeker"

update_backend() {
    echo "=== Updating backend ==="

    cd "$DEPLOY_DIR"
    docker-compose --env-file .env pull backend
    docker-compose up -d backend
    echo "  ✓ backend updated"
}

# ── Main ───────────────────────────────────────────────────────────────────
cd "$DEPLOY_DIR"

case "${1:-all}" in
    backend)
        update_backend
        ;;
    all)
        update_backend
        ;;
    *)
        echo "Usage: $0 {backend|all}"
        exit 1
        ;;
esac

echo ""
echo "=== Health check ==="
if curl -fsS "http://localhost:8000/health" &>/dev/null; then
    echo "  ✓ backend"
else
    echo "  ✗ backend (check logs: docker logs lingua-backend)"
fi
