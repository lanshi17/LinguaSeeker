#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -f "$ROOT_DIR/.env.local" ]; then
  set -a
  . "$ROOT_DIR/.env.local"
  set +a
fi

: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_PORT:?POSTGRES_PORT is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

OUT_DIR="${1:-$ROOT_DIR/backups}"
mkdir -p "$OUT_DIR"

TS=$(date "+%Y%m%d_%H%M%S")
BACKUP_FILE="$OUT_DIR/pg_backup_${POSTGRES_DB}_${TS}.dump"

export PGPASSWORD="$POSTGRES_PASSWORD"

pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -F c -f "$BACKUP_FILE" "$POSTGRES_DB"

echo "Backup created: $BACKUP_FILE"