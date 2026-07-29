#!/usr/bin/env bash
# ==============================================================================
# sync_dev_to_prod.sh — Incremental one-way-preserving data sync (dev -> prod).
#
# Semantics (confirmed with maintainer):
#   * dev is the authoritative source; prod-only rows are NEVER deleted.
#   * Rows are upserted by UUID primary key:
#       - tables WITH updated_at  -> ON CONFLICT DO UPDATE only when the incoming
#         row is newer (existing.updated_at < EXCLUDED.updated_at). This makes the
#         merge safe in both directions: a locally-newer prod edit survives.
#       - append-only tables WITHOUT updated_at -> ON CONFLICT DO NOTHING
#         (rows are immutable audit/log records; only brand-new rows are added).
#   * Runtime-local tables are excluded entirely (see EXCLUDED below).
#
# Two phases, run on two machines with a file bundle in between:
#   1. `export` on the DEV box   -> writes CSV bundle + MANIFEST
#   2. transfer the bundle to the PROD box (scp / rsync / docker cp)
#   3. `import` on the PROD box  -> upserts the bundle
#
# Connection uses standard libpq env vars (PGHOST/PGPORT/PGUSER/PGPASSWORD/
# PGDATABASE) or the matching flags. The prod postgres port is published on
# 127.0.0.1:5432, so `import` can run straight from the host with a psql client
# (\copy is client-side, no need to copy CSVs into the container).
#
# IMPORTANT: the import role must be able to run `SET session_replication_role`
# (superuser). The `lingua_seeker` role qualifies in this deployment.
#
# Usage:
#   Export (on dev):
#     PGHOST=127.0.0.1 PGPORT=5432 PGUSER=lingua_seeker PGPASSWORD=... \
#     PGDATABASE=dev_lingua_seeker \
#       scripts/sync_dev_to_prod.sh export --since '2026-07-28 00:00:00+00' --out ./sync_bundle
#
#   Import (on prod):
#     PGHOST=127.0.0.1 PGPORT=5432 PGUSER=lingua_seeker PGPASSWORD=... \
#     PGDATABASE=lingua_seeker \
#       scripts/sync_dev_to_prod.sh import --in ./sync_bundle
#
# On first sync, use the prod-restore dump timestamp as --since. Each export
# prints the timestamp to pass as --since next time (written into MANIFEST too).
# ==============================================================================
set -euo pipefail

SCHEMA="${SYNC_SCHEMA:-lingua_seeker}"

# Business tables in parent-first order (import order is cosmetic because FK
# checks are disabled during load, but keep it readable). Format: "table:ts_col".
# ts_col is the incremental filter column used at export time.
#
# EXCLUDED (runtime-local, never synced):
#   pipeline_jobs, pipeline_run_states, document_processing_cache,
#   alembic_version, frontend_search_index
TABLES=(
  "users:updated_at"
  "source_documents:updated_at"
  "processing_runs:created_at"            # no updated_at; treated as insert-once
  "source_document_identifiers:updated_at"
  "literature_profiles:updated_at"
  "normalized_entities:updated_at"
  "entity_merge_events:merged_at"         # append-only audit
  "run_evidence_items:updated_at"
  "evidence_entity_bindings:updated_at"
  "canonical_evidence_items:updated_at"
  "terminology_entries:updated_at"
  "terminology_aliases:updated_at"
  "terminology_relationships:updated_at"
  "terminology_embeddings:updated_at"
  "review_audit_events:created_at"        # append-only audit
  "chat_sessions:updated_at"
  "chat_messages:created_at"              # append-only
  "document_annotations:updated_at"
)

die() { echo "ERROR: $*" >&2; exit 1; }

# ── export ────────────────────────────────────────────────────────────────
cmd_export() {
  local since="" out=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --since) since="$2"; shift 2 ;;
      --out)   out="$2";   shift 2 ;;
      *) die "unknown export arg: $1" ;;
    esac
  done
  [[ -n "$since" ]] || die "--since required (e.g. '2026-07-28 00:00:00+00')"
  [[ -n "$out"   ]] || die "--out required (bundle directory)"
  mkdir -p "$out"

  # Capture the dev clock at start; this becomes the next --since. Rows written
  # during the export re-sync next time (idempotent upsert), so no data is lost.
  local next_since
  next_since="$(psql -tAX -c "SELECT now()")" || die "cannot connect to dev DB"

  echo "Exporting rows changed after: $since"
  local entry table ts_col
  for entry in "${TABLES[@]}"; do
    table="${entry%%:*}"; ts_col="${entry##*:}"
    echo "  -> ${table} (by ${ts_col})"
    psql -X -v ON_ERROR_STOP=1 -c \
      "\copy (SELECT * FROM ${SCHEMA}.${table} WHERE ${ts_col} > '${since}') TO '${out}/${table}.csv' WITH (FORMAT csv, HEADER true)"
  done

  {
    echo "schema=${SCHEMA}"
    echo "exported_from_since=${since}"
    echo "next_since=${next_since}"
  } > "${out}/MANIFEST"

  echo
  echo "Bundle written to: ${out}"
  echo "NEXT TIME run with:  --since '${next_since}'"
  echo "Transfer the bundle to the prod host, then run: import --in <bundle>"
}

# ── import ──────────────────────────────────────────────────────────────────
cmd_import() {
  local in=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --in) in="$2"; shift 2 ;;
      *) die "unknown import arg: $1" ;;
    esac
  done
  [[ -n "$in" ]] || die "--in required (bundle directory)"
  [[ -f "${in}/MANIFEST" ]] || die "no MANIFEST in ${in}; is it a valid bundle?"

  # Build one transactional psql script: disable FK checks, define a generic
  # upsert helper, then stage+upsert each table's CSV.
  local sql; sql="$(mktemp)"
  trap 'rm -f "$sql"' EXIT

  {
    echo "\\set ON_ERROR_STOP on"
    echo "BEGIN;"
    echo "SET LOCAL session_replication_role = replica;  -- bypass FK during bulk load"
    cat <<'PLPGSQL'
CREATE FUNCTION pg_temp._sync_upsert(target regclass, staging regclass)
RETURNS bigint LANGUAGE plpgsql AS $fn$
DECLARE
  pk_names  text[];
  all_names text[];
  pk_list   text;
  col_list  text;
  set_list  text;
  stmt      text;
  n         bigint;
BEGIN
  SELECT array_agg(a.attname ORDER BY k.ord) INTO pk_names
  FROM pg_index i
  JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON true
  JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
  WHERE i.indrelid = target AND i.indisprimary;

  SELECT array_agg(attname ORDER BY attnum) INTO all_names
  FROM pg_attribute
  WHERE attrelid = target AND attnum > 0 AND NOT attisdropped;

  SELECT string_agg(quote_ident(c), ', ') INTO pk_list  FROM unnest(pk_names)  AS c;
  SELECT string_agg(quote_ident(c), ', ') INTO col_list FROM unnest(all_names) AS c;
  SELECT string_agg(format('%I = EXCLUDED.%I', c, c), ', ') INTO set_list
  FROM unnest(all_names) AS c WHERE c <> ALL (pk_names);

  IF 'updated_at' = ANY (all_names) THEN
    stmt := format(
      'INSERT INTO %s AS tgt (%s) SELECT %s FROM %s '
      'ON CONFLICT (%s) DO UPDATE SET %s WHERE tgt.updated_at < EXCLUDED.updated_at',
      target::text, col_list, col_list, staging::text, pk_list, set_list);
  ELSE
    stmt := format(
      'INSERT INTO %s (%s) SELECT %s FROM %s ON CONFLICT (%s) DO NOTHING',
      target::text, col_list, col_list, staging::text, pk_list);
  END IF;

  EXECUTE stmt;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$fn$;
PLPGSQL

    local entry table
    for entry in "${TABLES[@]}"; do
      table="${entry%%:*}"
      [[ -f "${in}/${table}.csv" ]] || { echo "\\echo 'skip ${table} (no csv)'"; continue; }
      echo "CREATE TEMP TABLE _stg_${table} (LIKE ${SCHEMA}.${table} INCLUDING DEFAULTS) ON COMMIT DROP;"
      echo "\\copy _stg_${table} FROM '${in}/${table}.csv' WITH (FORMAT csv, HEADER true)"
      echo "\\echo upsert ${table}:"
      echo "SELECT _sync_upsert('${SCHEMA}.${table}'::regclass, '_stg_${table}'::regclass) AS rows_written;"
    done

    echo "COMMIT;"
  } > "$sql"

  echo "Importing bundle: ${in}"
  psql -X -f "$sql"
  echo
  echo "Import complete."
  echo "NOTE: session_replication_role=replica also skipped user triggers. If"
  echo "      frontend_search_index is trigger-maintained, rebuild it now."
}

# ── dispatch ──────────────────────────────────────────────────────────────
[[ $# -ge 1 ]] || die "usage: $0 {export|import} [args]"
mode="$1"; shift
case "$mode" in
  export) cmd_export "$@" ;;
  import) cmd_import "$@" ;;
  *) die "unknown mode: $mode (expected export|import)" ;;
esac
