#!/usr/bin/env bash
# ==============================================================================
# sync_neo4j.sh — Build / rebuild the Neo4j knowledge-graph baseline from
# PostgreSQL terminology tables. Safe to run repeatedly (idempotent).
#
# What it does (in order):
#   1. Ensure Neo4j read-path indexes exist
#      (calls scripts/ensure_neo4j_indexes.py)
#   2. Seed terminology baseline nodes + edges from PostgreSQL
#      (calls scripts/seed_neo4j_terminology.py)
#   3. (Optional, --with-literature) Backfill literature evidence graph
#      (calls scripts/backfill_neo4j_literature.py)
#
# Usage:
#   # Basic: terminology only (~90k nodes, fast)
#   bash scripts/sync_neo4j.sh
#
#   # Full: terminology + literature evidence backfill
#   bash scripts/sync_neo4j.sh --with-literature
#
#   # Custom batch size, clear existing nodes first
#   bash scripts/sync_neo4j.sh --clear --batch-size 2000
#
#   # Include variant entities (4M+ rows, very slow)
#   bash scripts/sync_neo4j.sh --include-variants
#
#   # Dry-run: print commands without executing
#   bash scripts/sync_neo4j.sh --dry-run
#
# Connection config is read from the backend layered config
# (backend/config/ + ENVIRONMENT env var) — the same source the FastAPI
# app uses. Set ENVIRONMENT=production to target the production Neo4j.
# ==============================================================================
set -euo pipefail

# ── options ───────────────────────────────────────────────────────────────
WITH_LITERATURE=0
CLEAR=0
INCLUDE_VARIANTS=0
DRY_RUN=0
BATCH_SIZE=1000
LITERATURE_LIMIT=0
LITERATURE_RUN_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-literature)    WITH_LITERATURE=1; shift ;;
    --clear)              CLEAR=1;          shift ;;
    --include-variants)   INCLUDE_VARIANTS=1; shift ;;
    --dry-run)            DRY_RUN=1;        shift ;;
    --batch-size)         BATCH_SIZE="$2";  shift 2 ;;
    --literature-limit)   LITERATURE_LIMIT="$2"; shift 2 ;;
    --run-id)             LITERATURE_RUN_ID="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^# ===/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "ERROR: unknown arg: $1" >&2
      echo "Usage: $0 [--with-literature] [--clear] [--include-variants] [--dry-run] [--batch-size N] [--literature-limit N] [--run-id UUID]" >&2
      exit 1
      ;;
  esac
done

# ── paths ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

ENVIRONMENT="${ENVIRONMENT:-development}"
LOG_FILE="$LOG_DIR/neo4j_sync_$(date +%Y%m%d_%H%M%S).log"

# ── helpers ───────────────────────────────────────────────────────────────
run() {
  echo "→ $*"
  if [[ $DRY_RUN -eq 1 ]]; then
    return 0
  fi
  "$@"
}

step() {
  echo
  echo "──────────────────────────────────────────"
  echo " $1"
  echo "──────────────────────────────────────────"
}

# ── main ──────────────────────────────────────────────────────────────────
echo "Neo4j sync — environment: $ENVIRONMENT"
echo "Log file: $LOG_FILE"
echo "Batch size: $BATCH_SIZE"
echo "Clear before seed: $CLEAR"
echo "Include variants: $INCLUDE_VARIANTS"
echo "Backfill literature: $WITH_LITERATURE"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "  *** DRY RUN — no commands will execute ***"
fi

# Tee all output to the log file (dry-run or not).
exec > >(tee -a "$LOG_FILE") 2>&1

step "Step 1/3 — Ensure Neo4j indexes"
run uv run --project "$BACKEND_DIR" \
  python "$SCRIPT_DIR/ensure_neo4j_indexes.py"

step "Step 2/3 — Seed terminology baseline"
seed_args=(
  --batch-size "$BATCH_SIZE"
)
if [[ $CLEAR -eq 1 ]]; then
  seed_args+=(--clear)
fi
if [[ $INCLUDE_VARIANTS -eq 1 ]]; then
  seed_args+=(--include-variants)
fi
run uv run --project "$BACKEND_DIR" \
  python "$SCRIPT_DIR/seed_neo4j_terminology.py" "${seed_args[@]}"

if [[ $WITH_LITERATURE -eq 1 ]]; then
  step "Step 3/3 — Backfill literature evidence"
  lit_args=()
  if [[ $LITERATURE_RUN_ID ]]; then
    lit_args+=(--run-id "$LITERATURE_RUN_ID")
  fi
  if [[ $LITERATURE_LIMIT -gt 0 ]]; then
    lit_args+=(--limit "$LITERATURE_LIMIT")
  fi
  lit_args+=(--batch-size "$BATCH_SIZE")
  run uv run --project "$BACKEND_DIR" \
    python "$SCRIPT_DIR/backfill_neo4j_literature.py" "${lit_args[@]}"
else
  step "Step 3/3 — Skip literature backfill (use --with-literature to enable)"
fi

step "Done"
echo "Neo4j sync finished successfully."
echo "Environment: $ENVIRONMENT"
echo "Log: $LOG_FILE"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "(dry run — no changes were applied)"
fi
