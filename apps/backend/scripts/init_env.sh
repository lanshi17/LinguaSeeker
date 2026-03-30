#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ ! -f "$ROOT_DIR/.env.local" ]; then
  if [ -f "$ROOT_DIR/database/.env.example" ]; then
    cp "$ROOT_DIR/database/.env.example" "$ROOT_DIR/.env.local"
    echo "Created .env.local from .env.example"
  else
    echo "Missing .env.example; create .env.local manually" >&2
  fi
fi

mkdir -p \
  "$ROOT_DIR/logs" \
  "$ROOT_DIR/tmp" \
  "$ROOT_DIR/tmp/mineru_downloads" \
  "$ROOT_DIR/demo_output"

echo "Directories ensured."