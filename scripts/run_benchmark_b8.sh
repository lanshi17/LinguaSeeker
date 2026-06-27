#!/usr/bin/env bash
set -euo pipefail

# Unset stale POSTGRES_PASSWORD to let YAML config load the correct one
unset POSTGRES_PASSWORD

cd /data/yangzs/Projects/01_ACMG_Lingua
export PYTHONPATH=.

exec backend/.venv/bin/python -m benchmark.layer3.evaluate \
    --base-url http://localhost:8000 \
    --concurrency 1 \
    --extraction-mode b8 \
    --extraction-profile none \
    --no-preprocessed \
    --api-key "11a0a544bdeba461aba12b33d3dda55105ffa5daa52126f8" \
    "$@"
