#!/usr/bin/env bash
# Robust benchmark runner with shard support
# Usage: ./run_benchmark_shard.sh <shard_index> <shard_size>
#        ./run_benchmark_shard.sh          # no shard, full run
set -euo pipefail

unset POSTGRES_PASSWORD
cd /data/yangzs/Projects/01_ACMG_Lingua
export PYTHONPATH=.

SHARD_ARGS=""
if [ $# -ge 2 ]; then
    SHARD_ARGS="--shard-index $1 --shard-size $2"
    LOG="/tmp/benchmark_shard_${1}_of_${2}.log"
else
    LOG="/tmp/benchmark_full.log"
fi

echo "Starting benchmark at $(date)" | tee "$LOG"
echo "Shard args: ${SHARD_ARGS:-none}" | tee -a "$LOG"

exec backend/.venv/bin/python -m benchmark.layer3.evaluate \
    --base-url http://localhost:8000 \
    --concurrency 1 \
    --extraction-mode b8 \
    --extraction-profile none \
    --no-preprocessed \
    --api-key "11a0a544bdeba461aba12b33d3dda55105ffa5daa52126f8" \
    $SHARD_ARGS \
    2>&1 | tee -a "$LOG"
