#!/usr/bin/env bash
# Run all 6 shards sequentially for DB injection
# This script runs the benchmark for all 150 entries in 6 shards of 25
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Starting full benchmark run for DB injection ==="
echo "Start time: $(date)"
echo ""

for shard in 0 1 2 3 4 5; do
    echo "--- Starting shard $shard at $(date) ---"
    bash "$SCRIPT_DIR/run_benchmark_shard.sh" "$shard" 25
    echo "--- Shard $shard completed at $(date) ---"
    echo ""
done

echo "=== All shards complete at $(date) ==="
echo ""
echo "Verifying DB counts:"
PGPASSWORD='haMSxtBGKNzgzEDwySsSkJYazwBysTAe' psql -h 127.0.0.1 -U lingua_seeker -d dev_lingua_seeker -c "
SELECT 'source_documents' as tbl, count(*) FROM source_documents
UNION ALL SELECT 'processing_runs', count(*) FROM processing_runs
UNION ALL SELECT 'canonical_evidence_items', count(*) FROM canonical_evidence_items
UNION ALL SELECT 'run_evidence_items', count(*) FROM run_evidence_items
UNION ALL SELECT 'literature_profiles', count(*) FROM literature_profiles
UNION ALL SELECT 'frontend_search_index', count(*) FROM frontend_search_index
ORDER BY 1;"
