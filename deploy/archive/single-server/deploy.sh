#!/bin/bash
# ============================================================================
# Lingua Seeker — Single-Server Deploy Script (CentOS 7.9 + GPU)
# ============================================================================
# Run on the target server as root or sudo-capable user.
#
# Prerequisites:
#   1. Docker CE 20.10+ installed
#   2. Docker Hub access to pull the private backend image
#   3. NVIDIA Container Toolkit installed (nvidia-ctk runtime --verify)
#
# Usage:
#   chmod +x deploy.sh && ./deploy.sh
# ============================================================================
set -euo pipefail

DEPLOY_DIR="/opt/lingua-seeker"
COMPOSE_FILE="deploy/compose/single-server/docker-compose.yml"

echo "=========================================="
echo "  Lingua Seeker — Single-Server Deploy"
echo "=========================================="

# ── 1. Check prerequisites ────────────────────────────────────────────────
echo "[1/5] Checking prerequisites..."

if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not installed. Install Docker CE 20.10+ first."
    exit 1
fi

if ! docker info 2>&1 | grep -q "Runtimes.*nvidia"; then
    echo "WARNING: NVIDIA runtime not detected in Docker."
    echo "  Install nvidia-container-toolkit and run:"
    echo "  sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
    echo ""
    read -p "Continue anyway? (y/N): " yn
    [[ "$yn" =~ ^[Yy] ]] || exit 1
fi

echo "  Backend image: ${BACKEND_IMAGE:-docker.io/lanshi47/lingua-seeker-backend}:${IMAGE_TAG:-latest}"

# ── 2. Prepare directories ────────────────────────────────────────────────
echo "[2/5] Preparing directories..."
sudo mkdir -p "$DEPLOY_DIR"/{config/environments,config/vault}
sudo chown -R "$(whoami):$(whoami)" "$DEPLOY_DIR"

# ── 3. Copy compose + env ─────────────────────────────────────────────────
echo "[3/5] Copying compose files..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR"/docker-compose.yml "$DEPLOY_DIR"/docker-compose.yml

if [ ! -f "$DEPLOY_DIR/.env" ]; then
    cp "$SCRIPT_DIR"/.env.example "$DEPLOY_DIR"/.env
    echo "  Created .env from template — EDIT IT NOW:"
    echo "    vi $DEPLOY_DIR/.env"
    echo ""
    read -p "Done editing .env? (y/N): " yn
    [[ "$yn" =~ ^[Yy] ]] || { echo "Aborted."; exit 1; }
else
    echo "  .env already exists, keeping current."
fi

# ── 4. Prepare config files ───────────────────────────────────────────────
echo "[4/5] Preparing config files..."

# Production environment config
if [ ! -f "$DEPLOY_DIR/config/environments/production.yaml" ]; then
    cat > "$DEPLOY_DIR/config/environments/production.yaml" <<'YAML'
environment: "production"
debug: false
cors_origins: "https://furong.genemed.tech"

fast_llm:
  base_url: "https://linxi.chat/v1"

reasoning_llm:
  base_url: "https://linxi.chat/v1"

chat_llm:
  base_url: "https://api.siliconflow.cn"

translation_llm:
  local_base_url: "http://host.docker.internal:59062/api"
  local_target_lang: "en"
  local_timeout: 120
  base_url: "https://api.siliconflow.cn"

embedding:
  base_url: "http://host.docker.internal:32949"
  api_style: "simple"

rerank:
  base_url: "http://host.docker.internal:35001"
  api_style: "simple"

mineru:
  local_parse_url: "http://host.docker.internal:44321"

postgres:
  host: "postgres"
  db: "lingua_seeker"
  schema: "lingua_seeker"

redis:
  host: "redis"

unpaywall:
  email: "[redacted-email]"

network:
  proxy: ""
  no_proxy: "cn,ncbi.nlm.nih.gov,nlm.nih.gov,unpaywall.org,localhost,127.0.0.1"

doc_parse_model_id: "opendatalab/MinerU2.5-Pro-2604-1.2B"
YAML
    echo "  Created config/environments/production.yaml"
fi

# Vault config (secrets)
if [ ! -f "$DEPLOY_DIR/config/vault/production.yaml" ]; then
    echo ""
    echo "  NOTE: config/vault/production.yaml is MISSING."
    echo "  Create it with your secrets:"
    echo "    vi $DEPLOY_DIR/config/vault/production.yaml"
    echo ""
    echo "  Required fields: postgres.password, redis.password,"
    echo "  fast_llm.api_key, reasoning_llm.api_key, etc."
    read -p "Done creating vault? (y/N): " yn
    [[ "$yn" =~ ^[Yy] ]] || { echo "Aborted."; exit 1; }
fi

sudo chmod 600 "$DEPLOY_DIR/config/vault/production.yaml" 2>/dev/null || true

# ── 5. Start services ─────────────────────────────────────────────────────
echo "[5/5] Starting services..."
cd "$DEPLOY_DIR"
docker-compose --env-file .env pull
docker-compose --env-file .env up -d

# ── Health check ──────────────────────────────────────────────────────────
echo ""
echo "Waiting for backend to become healthy..."

if curl -fsS --retry 30 --retry-delay 5 --retry-all-errors \
    "http://127.0.0.1:8000/health" &>/dev/null; then
    echo "  ✓ backend"
else
    echo "  ✗ backend (check logs: docker logs lingua-backend)"
fi

echo ""
echo "=========================================="
echo "  Deployment complete!"
echo "=========================================="
echo ""
echo "  Backend API:  http://$(hostname -I | awk '{print $1}'):8000"
echo "  Health check: curl http://localhost:8000/health"
echo ""
echo "  Logs:         docker-compose logs -f"
echo "  Stop:         docker-compose down"
echo "  Restart:      docker-compose restart"
echo ""
