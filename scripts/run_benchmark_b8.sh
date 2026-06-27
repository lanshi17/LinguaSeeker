#!/usr/bin/env bash
set -euo pipefail

# Unset stale POSTGRES_PASSWORD to let YAML config load the correct one
unset POSTGRES_PASSWORD

cd /data/[redacted-user]/Projects/01_ACMG_Lingua
export PYTHONPATH=.

exec backend/.venv/bin/python -m benchmark.layer3.evaluate \
    --base-url http://localhost:8000 \
    --concurrency 1 \
    --extraction-mode b8 \
    --extraction-profile none \
    --no-preprocessed \
    --api-key "[redacted-api-key]" \
    "$@"
