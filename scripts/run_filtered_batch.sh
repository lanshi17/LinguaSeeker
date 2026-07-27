#!/bin/bash
# ============================================================================
# 批量处理 filtered 目录下的所有 PDF 文献
# 使用 mimo 模型配置通过 pipeline API 处理
#
# Usage:
#   bash scripts/run_filtered_batch.sh [--dry-run] [--concurrency N]
# ============================================================================

set -euo pipefail

# ── 配置 ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

INPUT_DIR="${PROJECT_ROOT}/benchmark/runners/downloads/filtered"
STATE_FILE="${PROJECT_ROOT}/data/filtered_batch_state.jsonl"
LOG_FILE="${PROJECT_ROOT}/logs/filtered_batch_$(date +%Y%m%d_%H%M%S).log"
VAULT_FILE="${PROJECT_ROOT}/backend/config/vault/batch_mimo.yaml"

# 模型配置
MIMO_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
MIMO_API_KEY="tp-cmltonm3l77iv1h7zkmr679c2ar5p2shpdsyoktpbc5sxguv"
FAST_MODEL="mimo-v2.5"
REASON_MODEL="mimo-v2.5-pro"

# 默认参数
CONCURRENCY=2
SUBMIT_SPACING=8.0
POLL_INTERVAL=30.0
EXTRACTION_PROFILE="none"
EXTRACTION_MODE="broad"

# ── 解析参数 ──────────────────────────────────────────────────────────────
DRY_RUN=""
for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN="--dry-run"
            ;;
        --concurrency=*)
            CONCURRENCY="${arg#*=}"
            ;;
        --concurrency)
            shift
            CONCURRENCY="${1:-$CONCURRENCY}"
            ;;
    esac
done

# ── 前置检查 ──────────────────────────────────────────────────────────────
if [ ! -d "$INPUT_DIR" ]; then
    echo "ERROR: Input directory not found: $INPUT_DIR"
    exit 1
fi

PDF_COUNT=$(find "$INPUT_DIR" -name "*.pdf" -type f | wc -l)
echo "============================================"
echo "  批量处理 filtered 文献"
echo "============================================"
echo "  输入目录: $INPUT_DIR"
echo "  PDF 数量: $PDF_COUNT"
echo "  并发数:   $CONCURRENCY"
echo "  模型:     $FAST_MODEL / $REASON_MODEL"
echo "  API:      $MIMO_BASE_URL"
echo "============================================"

if [ "$PDF_COUNT" -eq 0 ]; then
    echo "No PDF files found. Exiting."
    exit 0
fi

# ── 创建临时 vault 配置 ──────────────────────────────────────────────────
echo "[1/3] Creating temporary vault config: $VAULT_FILE"
mkdir -p "$(dirname "$VAULT_FILE")"

cat > "$VAULT_FILE" << EOF
# Temporary vault for batch processing with mimo models
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

session_signing_key: "batch-temp-key-$(openssl rand -hex 16)"

# LLM API Keys - 使用 mimo 模型
fast_llm:
  api_key: "${MIMO_API_KEY}"
  base_url: "${MIMO_BASE_URL}"
  model: "${FAST_MODEL}"

reasoning_llm:
  api_key: "${MIMO_API_KEY}"
  base_url: "${MIMO_BASE_URL}"
  model: "${REASON_MODEL}"

chat_llm:
  api_key: "${MIMO_API_KEY}"
  base_url: "${MIMO_BASE_URL}"
  model: "${FAST_MODEL}"

translation_llm:
  remote_base_url: "${MIMO_BASE_URL}"
  remote_api_key: "${MIMO_API_KEY}"
  remote_model: "${FAST_MODEL}"

# 数据库配置 - 使用开发环境数据库
api_key: "batch-temp-key"
EOF

echo "  Vault config created."

# ── 创建日志目录 ──────────────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"

# ── 启动后端 ──────────────────────────────────────────────────────────────
echo "[2/3] Starting backend with mimo configuration..."

# 设置环境变量
export ENVIRONMENT="development"
export FAST_LLM_BASE_URL="${MIMO_BASE_URL}"
export FAST_LLM_API_KEY="${MIMO_API_KEY}"
export FAST_LLM_MODEL="${FAST_MODEL}"
export REASONING_LLM_BASE_URL="${MIMO_BASE_URL}"
export REASONING_LLM_API_KEY="${MIMO_API_KEY}"
export REASONING_LLM_MODEL="${REASON_MODEL}"
export CHAT_LLM_BASE_URL="${MIMO_BASE_URL}"
export CHAT_LLM_API_KEY="${MIMO_API_KEY}"
export CHAT_LLM_MODEL="${FAST_MODEL}"

# 启动后端（后台运行）
cd "$PROJECT_ROOT/backend"
BACKEND_PID_FILE="${PROJECT_ROOT}/data/batch_backend.pid"

if [ -f "$BACKEND_PID_FILE" ]; then
    OLD_PID=$(cat "$BACKEND_PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "  Stopping existing backend (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
fi

echo "  Starting backend server..."
nohup uv run uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    > "${PROJECT_ROOT}/logs/batch_backend.log" 2>&1 &

BACKEND_PID=$!
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"
echo "  Backend started (PID: $BACKEND_PID)"

# 等待后端启动
echo "  Waiting for backend to be ready..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  Backend is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Backend failed to start within 30 seconds."
        echo "Check logs: ${PROJECT_ROOT}/logs/batch_backend.log"
        exit 1
    fi
    sleep 1
done

# ── 运行批处理 ────────────────────────────────────────────────────────────
echo "[3/3] Starting batch processing..."
echo ""

cd "$PROJECT_ROOT"

uv --project backend run python scripts/run_document_batch.py \
    --input-dir "$INPUT_DIR" \
    --base-url http://127.0.0.1:8000 \
    --api-key "batch-temp-key" \
    --state "$STATE_FILE" \
    --log-file "$LOG_FILE" \
    --concurrency "$CONCURRENCY" \
    --submit-spacing "$SUBMIT_SPACING" \
    --poll-interval "$POLL_INTERVAL" \
    --extraction-profile "$EXTRACTION_PROFILE" \
    --extraction-mode "$EXTRACTION_MODE" \
    --extensions ".pdf" \
    --retry-failed \
    $DRY_RUN

BATCH_EXIT_CODE=$?

# ── 清理 ──────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
if [ $BATCH_EXIT_CODE -eq 0 ]; then
    echo "  Batch processing completed successfully!"
else
    echo "  Batch processing finished with exit code: $BATCH_EXIT_CODE"
fi
echo "  State file: $STATE_FILE"
echo "  Log file:   $LOG_FILE"
echo "============================================"

# 询问是否停止后端
echo ""
read -p "Stop the backend server? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "$BACKEND_PID_FILE" ]; then
        kill "$(cat "$BACKEND_PID_FILE")" 2>/dev/null || true
        rm -f "$BACKEND_PID_FILE"
        echo "Backend stopped."
    fi
else
    echo "Backend still running (PID: $(cat "$BACKEND_PID_FILE" 2>/dev/null || echo 'unknown'))"
fi

exit $BATCH_EXIT_CODE
