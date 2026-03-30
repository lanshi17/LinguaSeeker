#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LOG_DIR="$ROOT_DIR/logs"
KEEP_DAYS="${KEEP_DAYS:-7}"

if [ -d "$LOG_DIR" ]; then
  find "$LOG_DIR" -type f -mtime "+$KEEP_DAYS" -print -delete
fi

echo "Logs cleaned (keep_days=$KEEP_DAYS)."