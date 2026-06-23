#!/bin/bash
# ============================================================================
# Incremental Update Script — code-only changes (no dependency rebuild)
# ============================================================================
# Run ON the target CentOS server. Syncs changed source from GPFS, builds
# thin overlay images, restarts affected services.
#
# Usage:
#   ./update.sh backend          # update backend only
#   ./update.sh model-server     # update all 4 model-server containers
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

update_model_server() {
    echo "=== Updating model-server ==="

    # 1. Sync changed source code
    rsync -avz --delete \
      --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
      "$REPO_DIR/services/model-server/" "$DEPLOY_DIR/services/model-server/"

    # 2. Build thin overlays for each service
    cd "$DEPLOY_DIR"
    for svc in embedding rerank vlm doc-parse; do
        echo "  Patching lingua-${svc}..."
        docker build -t "lingua-${svc}:local" \
          --build-arg "BASE_IMAGE=lingua-${svc}:local" \
          -f deploy/compose/single-server/patch-model-server.Dockerfile . 2>&1 | tail -3
    done

    # 3. Restart
    docker-compose up -d model-embedding model-rerank model-vlm model-doc-parse
    echo "  ✓ model-server updated"
}

# ── Main ───────────────────────────────────────────────────────────────────
cd "$DEPLOY_DIR"

case "${1:-all}" in
    backend)
        update_backend
        ;;
    model-server|model)
        update_model_server
        ;;
    all)
        update_backend
        update_model_server
        ;;
    *)
        echo "Usage: $0 {backend|model-server|all}"
        exit 1
        ;;
esac

echo ""
echo "=== Health check ==="
for svc in backend:8000 model-embedding:8002 model-rerank:8003 model-vlm:8004 model-doc-parse:8005; do
    name="${svc%%:*}"
    port="${svc#*:}"
    if curl -fsS "http://localhost:${port}/health" &>/dev/null; then
        echo "  ✓ $name"
    else
        echo "  ✗ $name (still starting? check: docker logs lingua-${name#model-})"
    fi
done
