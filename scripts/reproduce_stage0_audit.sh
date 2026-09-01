#!/usr/bin/env bash
## Reproduce the Stage-0 source-visibility and provenance audit without network access.
## This wrapper sets PYTHONPATH to the repository root so that
## `benchmark.experiments.acmg_multilingual.cli` resolves whether the caller
## runs from the worktree root, from backend/, or from any other directory.
## It intentionally isolates the frozen Stage-0 check from the optional
## live-extraction probe (which loads src.core.*) so that the audit does not
## require model credentials or publisher access.

set -euo pipefail

## Resolve the real script location (follows the gim worktree's symlink to
## ../01_ACMG_Lingua/scripts).  readlink -f is GNU-specific and available on
## this host.
SCRIPT_REAL="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_REAL")" && pwd)"

# When run from the GIM worktree, scripts/ is a symlink to ../01_ACMG_Lingua/scripts.
# Walk up until a directory containing benchmark/experiments/acmg_multilingual exists.
REPO_ROOT="$SCRIPT_DIR"
while [[ ! -d "$REPO_ROOT/benchmark/experiments/acmg_multilingual" ]]; do
  PARENT="$(dirname "$REPO_ROOT")"
  if [[ "$PARENT" == "$REPO_ROOT" ]]; then
    echo "error: cannot locate benchmark/experiments/acmg_multilingual from $SCRIPT_DIR" >&2
    exit 1
  fi
  REPO_ROOT="$PARENT"
done
# If we landed in 01_ACMG_Lingua but the frozen ledger lives only in the GIM
# worktree, prefer the worktree that actually contains reviewed/ sources.
if [[ ! -d "$REPO_ROOT/benchmark/experiments/acmg_multilingual/reviewed" ]]; then
  GIM_ROOT="/data/yangzs/Projects/01_ACMG_Lingua-gim"
  if [[ -d "$GIM_ROOT/benchmark/experiments/acmg_multilingual/reviewed" ]]; then
    REPO_ROOT="$GIM_ROOT"
  fi
fi

BENCHMARK_ROOT="$REPO_ROOT/benchmark"
LEDGER_ROOT="$BENCHMARK_ROOT/experiments/acmg_multilingual"
REPORT_PATH="${1:-/tmp/stage0-audit-receipt.json}"

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "Repo root: $REPO_ROOT" >&2
echo "Benchmark root: $LEDGER_ROOT" >&2
echo "Report: $REPORT_PATH" >&2

uv --directory "$REPO_ROOT/backend" run --locked --all-groups \
  --module benchmark.experiments.acmg_multilingual.cli \
  check-evidence-item-coverage \
  --facts "$LEDGER_ROOT/evidence_item_coverage_facts.json" \
  --cases "$LEDGER_ROOT/direct_inference_cases.json" \
  --reviewed-root "$LEDGER_ROOT/reviewed" \
  --report "$REPORT_PATH"

echo "Verification receipt written to $REPORT_PATH" >&2
# Print a short human-readable summary (the checker already prints one line).
python3 -c "import json,pathlib; p=pathlib.Path('$REPORT_PATH'); j=json.load(open(p)); print(json.dumps({k:j[k] for k in ('field_anchor_checks','increment_summary','artifact_state','direct_inference_inventory') if k in j}, indent=2, ensure_ascii=False))" 2>&1 | head -n 80
