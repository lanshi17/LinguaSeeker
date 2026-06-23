#!/usr/bin/env bash
# ── E2E Docker Test ──────────────────────────────────────────────────
# Tests each model container sequentially (8GB VRAM constraint).
# Usage: bash tests/test_e2e_docker.sh
# Prerequisites: Docker, NVIDIA Container Toolkit, model weights linked
# -------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_BASE="-f docker-compose.model-server.yml"
COMPOSE_E2E="-f docker-compose.e2e.yml"
COMPOSE="$COMPOSE_BASE $COMPOSE_E2E"
PASSED=0
FAILED=0

log()  { echo -e "\033[1;34m[E2E]\033[0m $*"; }
pass() { echo -e "\033[1;32m[PASS]\033[0m $*"; PASSED=$((PASSED + 1)); }
fail() { echo -e "\033[1;31m[FAIL]\033[0m $*"; FAILED=$((FAILED + 1)); }

wait_for_health() {
    local name=$1 port=$2 max_wait=${3:-180}
    log "Waiting for $name on :$port (max ${max_wait}s)..."
    for i in $(seq 1 "$max_wait"); do
        if curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
            pass "$name health check OK (${i}s)"
            return 0
        fi
        sleep 1
    done
    fail "$name health check TIMEOUT after ${max_wait}s"
    return 1
}

cleanup() {
    log "Stopping containers..."
    docker-compose $COMPOSE down --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

# ── Test 1: Embedding Container ─────────────────────────────────────
log "=== Test 1: model-embedding ==="
docker-compose $COMPOSE up -d model-embedding
if wait_for_health "embedding" 8002 300; then
    # Test /v1/embeddings endpoint
    RESP=$(curl -sf -X POST http://localhost:8002/v1/embeddings \
        -H "Content-Type: application/json" \
        -d '{"input": ["hello world", "test document"], "model": "test"}' 2>&1)
    if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['data'])==2; assert len(d['data'][0]['embedding'])>0" 2>/dev/null; then
        pass "embedding /v1/embeddings returns 2 vectors"
    else
        fail "embedding /v1/embeddings response invalid: $RESP"
    fi
fi
docker-compose $COMPOSE stop model-embedding 2>/dev/null
docker-compose $COMPOSE rm -f model-embedding 2>/dev/null

# ── Test 2: Rerank Container ────────────────────────────────────────
log "=== Test 2: model-rerank ==="
docker-compose $COMPOSE up -d model-rerank
if wait_for_health "rerank" 8003 300; then
    RESP=$(curl -sf -X POST http://localhost:8003/v1/rerank \
        -H "Content-Type: application/json" \
        -d '{"query": "machine learning", "documents": ["deep learning tutorial", "cooking recipe"], "model": "test"}' 2>&1)
    if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['results'])==2; assert 'relevance_score' in d['results'][0]" 2>/dev/null; then
        pass "rerank /v1/rerank returns 2 scored results"
    else
        fail "rerank /v1/rerank response invalid: $RESP"
    fi
fi
docker-compose $COMPOSE stop model-rerank 2>/dev/null
docker-compose $COMPOSE rm -f model-rerank 2>/dev/null

# ── Test 3: Doc-Parse Container ─────────────────────────────────────
log "=== Test 3: model-doc-parse ==="
docker-compose $COMPOSE up -d model-doc-parse
if wait_for_health "doc-parse" 8004 600; then
    # Create a minimal PDF for testing
    PDF_FILE=$(mktemp /tmp/test_XXXXXX.pdf)
    python3 -c "
import struct
pdf = b'%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R/Contents 4 0 R>>endobj\n4 0 obj<</Length 44>>stream\nBT /F1 1 Tf (Hello World) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000206 00000 n \ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n300\n%%EOF'
with open('$PDF_FILE', 'wb') as f:
    f.write(pdf)
"
    RESP=$(curl -sf -X POST http://localhost:8004/file_parse \
        -F "file=@$PDF_FILE" 2>&1)
    rm -f "$PDF_FILE"
    if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='completed'" 2>/dev/null; then
        pass "doc-parse /file_parse returns completed status"
    else
        fail "doc-parse /file_parse response invalid: $RESP"
    fi
fi
docker-compose $COMPOSE stop model-doc-parse 2>/dev/null
docker-compose $COMPOSE rm -f model-doc-parse 2>/dev/null

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo -e "  E2E Results: \033[1;32m${PASSED} passed\033[0m, \033[1;31m${FAILED} failed\033[0m"
echo "============================================"
exit $FAILED
