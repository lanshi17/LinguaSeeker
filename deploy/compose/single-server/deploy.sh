#!/bin/bash
# ============================================================================
# Lingua Seeker — Single-Server Deploy Script (CentOS 7.9 + GPU)
# ============================================================================
# Run on the target server as root or sudo-capable user.
#
# Prerequisites:
#   1. Docker CE 20.10+ installed
#   2. NVIDIA Container Toolkit installed (nvidia-ctk runtime --verify)
#   3. Images loaded: docker load -i lingua-all-images.tar
#   4. Model weights downloaded to /opt/lingua-seeker-data/models/
#
# Usage:
#   chmod +x deploy.sh && ./deploy.sh
# ============================================================================
set -euo pipefail

DEPLOY_DIR="/opt/lingua-seeker"
MODEL_DIR="/opt/lingua-seeker-data/models"
COMPOSE_FILE="deploy/compose/single-server/docker-compose.yml"

echo "=========================================="
echo "  Lingua Seeker — Single-Server Deploy"
echo "=========================================="

# ── 1. Check prerequisites ────────────────────────────────────────────────
echo "[1/7] Checking prerequisites..."

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

for img in lingua-seeker-backend:local lingua-embedding:local lingua-rerank:local lingua-vlm:local lingua-doc-parse:local; do
    if ! docker image inspect "$img" &>/dev/null; then
        echo "ERROR: Image $img not found. Run: docker load -i lingua-all-images.tar"
        exit 1
    fi
    echo "  ✓ $img"
done

# ── 2. Prepare directories ────────────────────────────────────────────────
echo "[2/7] Preparing directories..."
sudo mkdir -p "$DEPLOY_DIR"/{config/environments,config/vault}
sudo mkdir -p "$MODEL_DIR"/{embedding,rerank,vlm}
sudo chown -R "$(whoami):$(whoami)" "$DEPLOY_DIR"

# ── 3. Copy compose + env ─────────────────────────────────────────────────
echo "[3/7] Copying compose files..."
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
echo "[4/7] Preparing config files..."

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
  base_url: "https://api.siliconflow.cn"

embedding:
  base_url: "http://model-embedding:8002/v1"

rerank:
  base_url: "http://model-rerank:8003/v1"

postgres:
  host: "postgres"
  db: "lingua_seeker"
  schema: "lingua_seeker"

redis:
  host: "redis"

unpaywall:
  email: "yhvguk@stu.hunau.edu.cn"

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

# ── 5. Check model weights ────────────────────────────────────────────────
echo "[5/7] Checking model weights..."
for model in \
    "embedding/Qwen--Qwen3-Embedding-0.6B" \
    "rerank/BAAI--bge-reranker-v2-m3" \
    "vlm/opendatalab--MinerU2.5-Pro-2604-1.2B"; do
    if [ -d "$MODEL_DIR/$model" ] && [ "$(ls -A "$MODEL_DIR/$model" 2>/dev/null)" ]; then
        echo "  ✓ $model"
    else
        echo "  ✗ MISSING: $MODEL_DIR/$model"
        echo "    Download with:"
        echo "      huggingface-cli download Qwen/Qwen3-Embedding-0.6B --local-dir $MODEL_DIR/embedding/Qwen--Qwen3-Embedding-0.6B"
        echo "      huggingface-cli download BAAI/bge-reranker-v2-m3 --local-dir $MODEL_DIR/rerank/BAAI--bge-reranker-v2-m3"
        echo "      huggingface-cli download opendatalab/MinerU2.5-Pro-2604-1.2B --local-dir $MODEL_DIR/vlm/opendatalab--MinerU2.5-Pro-2604-1.2B"
        echo ""
        read -p "Continue without this model? (y/N): " yn
        [[ "$yn" =~ ^[Yy] ]] || exit 1
    fi
done

# ── 6. Start services ─────────────────────────────────────────────────────
echo "[6/7] Starting services..."
cd "$DEPLOY_DIR"
docker-compose --env-file .env up -d

# ── 7. Health check ───────────────────────────────────────────────────────
echo "[7/7] Waiting for services to become healthy..."
echo "  (this may take 2-5 minutes for model loading)"

SERVICES=(
    "backend:8000/health"
    "embedding:8002/health"
    "rerank:8003/health"
    "vlm:8004/health"
    "doc-parse:8005/health"
)

for entry in "${SERVICES[@]}"; do
    name="${entry%%:*}"
    url="http://127.0.0.1:${entry#*:}"
    echo -n "  Waiting for $name..."
    for i in $(seq 1 60); do
        if curl -fsS "$url" &>/dev/null; then
            echo " OK"
            break
        fi
        sleep 5
        [ $i -eq 60 ] && echo " TIMEOUT (check logs: docker logs lingua-model-$name)"
    done
done

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
