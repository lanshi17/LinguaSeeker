#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DB_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ROOT_DIR=$(CDPATH= cd -- "$DB_DIR/.." && pwd)
COMPOSE_FILE="$DB_DIR/podman-compose.yml"
DEFAULT_ENV_FILE="$DB_DIR/config/.env"
ROOT_ENV_LOCAL="$ROOT_DIR/.env.local"
SQL_SEED_FILE="$DB_DIR/sql/seed_data.sql"
SQL_CLEANUP_FILE="$DB_DIR/sql/cleanup_orphan_records.sql"
DEFAULT_BACKUP_DIR="$ROOT_DIR/backups"

log() {
  printf '%s\n' "$*"
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

resolve_path() {
  local p="$1"
  if [[ "$p" = /* ]]; then
    printf '%s\n' "$p"
  else
    printf '%s\n' "$ROOT_DIR/$p"
  fi
}

load_env() {
  if [[ -f "$DEFAULT_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$DEFAULT_ENV_FILE"
    set +a
  fi

  if [[ -f "$ROOT_ENV_LOCAL" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ROOT_ENV_LOCAL"
    set +a
  fi

  if [[ -n "${ENV_FILE:-}" ]]; then
    local env_override
    env_override=$(resolve_path "$ENV_FILE")
    [[ -f "$env_override" ]] || die "ENV_FILE does not exist: $env_override"
    set -a
    # shellcheck disable=SC1090
    source "$env_override"
    set +a
  fi
}

compose() {
  require_cmd podman-compose
  podman-compose -f "$COMPOSE_FILE" "$@"
}

postgres_env_required() {
  : "${POSTGRES_HOST:?POSTGRES_HOST is required}"
  : "${POSTGRES_PORT:?POSTGRES_PORT is required}"
  : "${POSTGRES_DB:?POSTGRES_DB is required}"
  : "${POSTGRES_USER:?POSTGRES_USER is required}"
  : "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
}

with_search_path() {
  local schema="${POSTGRES_SCHEMA:-public}"
  if [[ -n "$schema" && "$schema" != "public" ]]; then
    export PGOPTIONS="-c search_path=$schema"
  else
    unset PGOPTIONS || true
  fi
}

cmd_up() {
  compose up -d "$@"
}

cmd_down() {
  compose down "$@"
}

cmd_restart() {
  if [[ "$#" -gt 0 ]]; then
    compose restart "$@"
  else
    compose restart
  fi
}

cmd_ps() {
  compose ps
}

cmd_logs() {
  if [[ "$#" -eq 0 ]]; then
    compose logs --tail 200
  else
    compose logs --tail 200 "$@"
  fi
}

cmd_init() {
  load_env
  require_cmd uv

  ENV_FILE="${ENV_FILE:-.env.local}" uv run python -c "from src.infrastructure.postgres import initialize_schema; initialize_schema(); print('schema-initialized')"

  if [[ -f "$SQL_SEED_FILE" ]]; then
    postgres_env_required
    require_cmd psql
    with_search_path
    export PGPASSWORD="$POSTGRES_PASSWORD"
    psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$SQL_SEED_FILE"
    log "seed-applied"
  else
    warn "seed file not found, skipped: $SQL_SEED_FILE"
  fi
}

check_postgres() {
  if podman exec acmg_postgres pg_isready -U "${POSTGRES_USER:-acmg_user}" -d "${POSTGRES_DB:-acmg_ps3}" >/dev/null 2>&1; then
    log "[ok] postgres"
    return 0
  fi
  log "[fail] postgres"
  return 1
}

check_redis() {
  if [[ -z "${REDIS_PASSWORD:-}" ]]; then
    warn "REDIS_PASSWORD is empty"
    log "[fail] redis"
    return 1
  fi
  if podman exec acmg_redis redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q 'PONG'; then
    log "[ok] redis"
    return 0
  fi
  log "[fail] redis"
  return 1
}

check_minio() {
  if curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; then
    log "[ok] minio"
    return 0
  fi
  log "[fail] minio"
  return 1
}

check_qdrant() {
  local use_tls="${QDRANT_ENABLE_TLS:-${QDRANT_USE_TLS:-false}}"
  local protocol="http"
  local curl_args=(-fsS)
  if [[ "${use_tls,,}" == "true" || "$use_tls" == "1" ]]; then
    protocol="https"
    curl_args=(-k -fsS)
  fi

  if curl "${curl_args[@]}" "$protocol://127.0.0.1:${QDRANT_PORT:-6333}/healthz" | grep -q 'healthz check passed'; then
    log "[ok] qdrant"
    return 0
  fi
  log "[fail] qdrant"
  return 1
}

check_neo4j() {
  local auth="${NEO4J_AUTH:-}"
  local user="${auth%%/*}"
  local pass="${auth#*/}"

  if [[ -z "$auth" || "$user" == "$auth" || -z "$pass" ]]; then
    warn "NEO4J_AUTH is missing or invalid (expect user/password)"
    log "[fail] neo4j"
    return 1
  fi

  if curl -fsS -u "$user:$pass" -H "Content-Type: application/json" \
      -d '{"statements":[{"statement":"RETURN 1 as result"}]}' \
      http://127.0.0.1:7474/db/neo4j/tx/commit | grep -q 'result'; then
    log "[ok] neo4j"
    return 0
  fi

  log "[fail] neo4j"
  return 1
}

cmd_check() {
  load_env
  local failed=0

  compose ps || true
  echo

  check_postgres || failed=1
  check_redis || failed=1
  check_minio || failed=1
  check_qdrant || failed=1
  check_neo4j || failed=1

  if [[ "$failed" -ne 0 ]]; then
    die "one or more checks failed"
  fi

  log "all checks passed"
}

cmd_reset() {
  local confirm="${1:-}"
  [[ "$confirm" == "--yes" ]] || die "reset requires explicit confirmation: dbctl.sh reset --yes"

  compose down -v --remove-orphans
  rm -rf "$DB_DIR/minio/data"/*
  mkdir -p "$DB_DIR/minio/data"
  compose up -d
  cmd_init
}

cmd_backup() {
  load_env
  postgres_env_required

  local out_dir="${1:-$DEFAULT_BACKUP_DIR}"
  mkdir -p "$out_dir"

  local ts
  ts=$(date '+%Y%m%d_%H%M%S')
  local backup_file="$out_dir/pg_backup_${POSTGRES_DB}_${ts}.dump"
  local schema="${POSTGRES_SCHEMA:-public}"

  if command -v podman >/dev/null 2>&1 && podman ps --format '{{.Names}}' | grep -qx 'acmg_postgres'; then
    podman exec -e "PGPASSWORD=$POSTGRES_PASSWORD" acmg_postgres \
      pg_dump -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -n "$schema" -F c "$POSTGRES_DB" > "$backup_file"
  else
    require_cmd pg_dump
    export PGPASSWORD="$POSTGRES_PASSWORD"
    with_search_path
    pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -n "$schema" -F c -f "$backup_file" "$POSTGRES_DB"
  fi

  log "backup created: $backup_file"
}

cmd_cleanup() {
  load_env
  postgres_env_required
  require_cmd psql
  [[ -f "$SQL_CLEANUP_FILE" ]] || die "cleanup SQL not found: $SQL_CLEANUP_FILE"

  export PGPASSWORD="$POSTGRES_PASSWORD"
  with_search_path
  psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$SQL_CLEANUP_FILE"
  log "cleanup SQL executed"
}

usage() {
  cat <<USAGE
Usage: $(basename "$0") <command> [args]

Commands:
  up [service...]       Start all or selected services
  down [args...]        Stop services (passes args to podman-compose down)
  restart [service...]  Restart all or selected services
  ps                    Show service status
  logs [service...]     Show recent logs
  init                  Initialize/upgrade PostgreSQL schema and seed data
  check                 Run unified health checks for all services
  reset --yes           Destructive reset: down -v, wipe minio data, up, init
  backup [dir]          Create PostgreSQL backup dump (default: ./backups)
  cleanup               Run SQL cleanup script

Env loading order:
  1) database/config/.env
  2) .env.local (if exists)
  3) ENV_FILE (if set, highest priority)
USAGE
}

main() {
  local cmd="${1:-}"
  if [[ -z "$cmd" || "$cmd" == "-h" || "$cmd" == "--help" ]]; then
    usage
    exit 0
  fi
  shift || true

  case "$cmd" in
    up) cmd_up "$@" ;;
    down) cmd_down "$@" ;;
    restart) cmd_restart "$@" ;;
    ps) cmd_ps ;;
    logs) cmd_logs "$@" ;;
    init) cmd_init ;;
    check) cmd_check ;;
    reset) cmd_reset "$@" ;;
    backup) cmd_backup "$@" ;;
    cleanup) cmd_cleanup ;;
    *)
      usage
      die "unknown command: $cmd"
      ;;
  esac
}

main "$@"
