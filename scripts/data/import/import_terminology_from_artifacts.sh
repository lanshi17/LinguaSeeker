#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Import terminology data from artifacts export into lingua_seeker database.
#
# Usage:
#   ./scripts/data/import/import_terminology_from_artifacts.sh [OPTIONS]
#
# Options:
#   --host HOST         PostgreSQL host (default: 127.0.0.1)
#   --port PORT         PostgreSQL port (default: 5432)
#   --db NAME           Database name (default: lingua_seeker)
#   --user NAME         Database user (default: lingua_seeker)
#   --password PASS     Database password (or set PGPASSWORD env var)
#   --artifact-dir DIR  Path to artifact directory
#   --skip-truncate     Don't truncate existing terminology tables before import
#   --dry-run           Show what would be done without executing
#   --help              Show this help
#
# Examples:
#   # Import to local dev database (default)
#   ./scripts/data/import/import_terminology_from_artifacts.sh \
#     --password "$PGPASSWORD" --db dev_lingua_seeker
#
#   # Import to production server via SSH tunnel
#   ssh -L 5433:postgres-server:5432 deploy@your-server
#   ./scripts/data/import/import_terminology_from_artifacts.sh \
#     --port 5433 --db lingua_seeker --password "$PGPASSWORD"
#
#   # Import to remote server directly
#   ./scripts/data/import/import_terminology_from_artifacts.sh \
#     --host postgres-server --db lingua_seeker --password "$PGPASSWORD"
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────
HOST="127.0.0.1"
PORT="5432"
DB="lingua_seeker"
USER="lingua_seeker"
PASSWORD="${PGPASSWORD:-}"
ARTIFACT_DIR=""
SKIP_TRUNCATE=false
DRY_RUN=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DEFAULT_ARTIFACT_DIR="$PROJECT_ROOT/artifacts/terminology_export_20260628"

# ── Parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --host)       HOST="$2"; shift 2 ;;
    --port)       PORT="$2"; shift 2 ;;
    --db)         DB="$2"; shift 2 ;;
    --user)       USER="$2"; shift 2 ;;
    --password)   PASSWORD="$2"; shift 2 ;;
    --artifact-dir) ARTIFACT_DIR="$2"; shift 2 ;;
    --skip-truncate) SKIP_TRunCATE=true; shift ;;
    --dry-run)    DRY_RUN=true; shift ;;
    --help)
      sed -n '2,/^# ──/{ /^# ──/d; s/^# \?//p; }' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Resolve artifact directory ──────────────────────────────────────────────
if [[ -z "$ARTIFACT_DIR" ]]; then
  ARTIFACT_DIR="$DEFAULT_ARTIFACT_DIR"
fi

if [[ ! -d "$ARTIFACT_DIR" ]]; then
  echo "ERROR: Artifact directory not found: $ARTIFACT_DIR"
  exit 1
fi

GZ_FILES=(
  "terminology_entries.csv.gz"
  "terminology_aliases.csv.gz"
  "terminology_relationships.csv.gz"
  "terminology_embeddings.csv.gz"
)

for f in "${GZ_FILES[@]}"; do
  if [[ ! -f "$ARTIFACT_DIR/$f" ]]; then
    echo "ERROR: Missing file: $ARTIFACT_DIR/$f"
    exit 1
  fi
done

# ── Build psql command ──────────────────────────────────────────────────────
export PGPASSWORD="$PASSWORD"
PSQL="psql -h $HOST -p $PORT -U $USER -d $DB -v ON_ERROR_STOP=1"

# ── Preflight checks ───────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════════"
echo "  Terminology Import — artifacts → $DB"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "  Source:  $ARTIFACT_DIR"
echo "  Target:  $USER@$HOST:$PORT/$DB (schema: lingua_seeker)"
echo ""

# Test connection
if ! $PSQL -c "SELECT 1" &>/dev/null; then
  echo "ERROR: Cannot connect to $USER@$HOST:$PORT/$DB"
  exit 1
fi
echo "  ✓ Connection OK"

# Check tables exist
TABLE_COUNT=$($PSQL -tAc "
  SELECT count(*) FROM information_schema.tables
  WHERE table_schema='lingua_seeker'
    AND table_name IN ('terminology_entries','terminology_aliases',
                       'terminology_relationships','terminology_embeddings')
")
if [[ "$TABLE_COUNT" -ne 4 ]]; then
  echo "ERROR: Expected 4 terminology tables, found $TABLE_COUNT."
  echo "  Run migrations first: uv run alembic -c database/alembic.ini upgrade head"
  exit 1
fi
echo "  ✓ All 4 terminology tables exist"

# Show current row counts
echo ""
echo "  Current row counts:"
for tbl in terminology_entries terminology_aliases terminology_relationships terminology_embeddings; do
  cnt=$($PSQL -tAc "SELECT count(*) FROM lingua_seeker.$tbl")
  printf "    %-35s %'10d\n" "$tbl" "$cnt"
done

echo ""
echo "  Artifact row counts:"
declare -A EXPECTED=(
  [terminology_entries]=4224483
  [terminology_aliases]=15222469
  [terminology_relationships]=4135386
  [terminology_embeddings]=94311
)
for tbl in terminology_entries terminology_aliases terminology_relationships terminology_embeddings; do
  printf "    %-35s %'10d\n" "$tbl" "${EXPECTED[$tbl]}"
done

# ── Dry run exit ────────────────────────────────────────────────────────────
if $DRY_RUN; then
  echo ""
  echo "  [DRY RUN] No changes made."
  exit 0
fi

# ── Confirm ─────────────────────────────────────────────────────────────────
echo ""
if ! $SKIP_TRUNCATE; then
  read -rp "  Truncate existing terminology data and import? [y/N] " confirm
else
  read -rp "  Append to existing terminology data? [y/N] " confirm
fi
if [[ "$confirm" != [yY] ]]; then
  echo "  Aborted."
  exit 0
fi

# ── Import ──────────────────────────────────────────────────────────────────
echo ""
echo "  Starting import..."
SECONDS=0

IMPORT_ORDER=(
  "terminology_entries"
  "terminology_aliases"
  "terminology_relationships"
  "terminology_embeddings"
)

for tbl in "${IMPORT_ORDER[@]}"; do
  gz_file="$ARTIFACT_DIR/${tbl}.csv.gz"
  echo ""
  echo "  ── $tbl ─────────────────────────────────────────"

  if ! $SKIP_TRUNCATE; then
    echo "    Truncating..."
    $PSQL -c "TRUNCATE lingua_seeker.$tbl CASCADE" 2>/dev/null || true
  fi

  echo "    Importing from ${tbl}.csv.gz ..."
  row_start=$SECONDS

  # Pipe gzipped CSV directly into psql \copy — no temp files on disk
  zcat "$gz_file" | $PSQL -c "\copy lingua_seeker.$tbl FROM STDIN WITH CSV HEADER"

  elapsed=$(( SECONDS - row_start ))
  imported=$($PSQL -tAc "SELECT count(*) FROM lingua_seeker.$tbl")
  echo "    ✓ Imported $imported rows in ${elapsed}s"
done

# ── Post-import: ANALYZE ────────────────────────────────────────────────────
echo ""
echo "  Running ANALYZE on terminology tables..."
$PSQL -c "ANALYZE lingua_seeker.terminology_entries" &>/dev/null
$PSQL -c "ANALYZE lingua_seeker.terminology_aliases" &>/dev/null
$PSQL -c "ANALYZE lingua_seeker.terminology_relationships" &>/dev/null
$PSQL -c "ANALYZE lingua_seeker.terminology_embeddings" &>/dev/null
echo "  ✓ Statistics updated"

# ── Summary ─────────────────────────────────────────────────────────────────
total_time=$SECONDS
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Import complete in ${total_time}s"
echo ""
for tbl in terminology_entries terminology_aliases terminology_relationships terminology_embeddings; do
  cnt=$($PSQL -tAc "SELECT count(*) FROM lingua_seeker.$tbl")
  printf "    %-35s %'10d\n" "$tbl" "$cnt"
done
echo ""
echo "  ⚠ terminology_embeddings contains metadata only (no vectors)."
echo "  To regenerate vector embeddings, run:"
echo "    uv run python scripts/data/import/import_terminology.py \\"
echo "      --terminology-root database/terminology_database \\"
echo "      --version 2026.05 --generate-embeddings"
echo "═══════════════════════════════════════════════════════════════════"
