#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
KEEP_DAYS="${KEEP_DAYS:-7}"
KEEP_LATEST="${KEEP_LATEST:-3}"

TMP_DIR="$ROOT_DIR/tmp"
if [ -d "$TMP_DIR" ]; then
  find "$TMP_DIR" -type f -mtime "+$KEEP_DAYS" -print -delete
  find "$TMP_DIR" -type d -empty -delete
fi

python "$ROOT_DIR/scripts/purge_old_outputs.py" --path "$ROOT_DIR/demo_output" --keep-latest "$KEEP_LATEST"

echo "Temp cleaned (keep_days=$KEEP_DAYS, keep_latest=$KEEP_LATEST)."