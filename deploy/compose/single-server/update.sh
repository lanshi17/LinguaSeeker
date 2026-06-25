#!/bin/bash
# ============================================================================
# Incremental Update Script — code-only changes (no dependency rebuild)
# ============================================================================
# Run ON the target CentOS server. Syncs changed source from GPFS, builds
# thin overlay images, restarts affected services.
#
# Usage:
#   ./update.sh backend          # update backend only
#   ./update.sh all              # update everything
# ============================================================================
set -euo pipefail

DEPLOY_DIR="/opt/lingua-seeker"
GPFS_DIR="/gpfs/hpc/home/lijc/[redacted-user]/Projects/lingua_seeker_backend"
REPO_DIR="${GPFS_DIR}/repo"   # rsync your repo here, or adjust path

update_backend() {
    echo "=== Updating backend ==="

    # 1. Sync changed source code
    rsync -avz --delete \
      --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
      --exclude='docker-artifacts' --exclude='**/target' \
      "$REPO_DIR/backend/" "$DEPLOY_DIR/backend/"

    rsync -avz \
      "$REPO_DIR/libs/config-loader/" "$DEPLOY_DIR/libs/config-loader/"

    # 2. Build thin overlay (seconds, not minutes)
    cd "$DEPLOY_DIR"
    docker build -t lingua-seeker-backend:local \
      -f deploy/compose/single-server/patch-backend.Dockerfile . 2>&1 | tail -5

    # 3. Restart
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
