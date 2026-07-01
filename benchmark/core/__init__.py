"""Shared benchmark primitives.

Re-exports the contracts, matching algorithms, aggregates, paths, and
pipeline client previously living inside ``benchmark.layer3.evaluate``.
The split landed in the 2026-06-18 framework refactor; see
``docs/active/2026-06-18-benchmark-framework-refactor-plan.md`` for the
target tree.

Stable imports for downstream code:

    from benchmark.core import (
        FieldMatch, EntryMetrics,
        compare_evidence, fuzzy_match_value, normalize_comparison_text,
        compute_aggregate_metrics,
        GROUND_TRUTH_ROOT, REPORTS_ROOT,
    )
"""
from __future__ import annotations

from benchmark.core.aggregate import compute_aggregate_metrics
from benchmark.core.contracts import EntryMetrics, FieldMatch
from benchmark.core.matching import (
    article_supported_expected_evidence,
    compare_evidence,
    fuzzy_match_value,
    mark_expected_fields_missing,
    normalize_comparison_text,
    prepare_extracted_items,
)
from benchmark.core.paths import (
    BENCHMARK_ROOT,
    GROUND_TRUTH_CLINGEN_ROOT,
    GROUND_TRUTH_ROOT,
    GROUND_TRUTH_UNIFIED_ROOT,
    RAW_PDF_ROOT,
    REPORTS_ROOT,
)
from benchmark.core.pdf import markdown_to_pdf_bytes, sanitize_for_pdf
from benchmark.core.pipeline_client import (
    MAX_POLL_ATTEMPTS,
    POLL_INTERVAL_S,
    QUEUED_STATUSES,
    TERMINAL_STATUSES,
    compare_entity_standardization,
    compare_track_consistency,
    evaluate_one,
    load_proxy,
    preflight_database_connection,
    run_evaluation,
    submit_and_poll,
)

# Transitional aliases (drop after Phase 6 of the refactor):
GROUND_TRUTH_DIR = GROUND_TRUTH_ROOT
REPORTS_DIR = REPORTS_ROOT


__all__ = [
    # contracts
    "FieldMatch",
    "EntryMetrics",
    # matching
    "compare_evidence",
    "article_supported_expected_evidence",
    "fuzzy_match_value",
    "mark_expected_fields_missing",
    "normalize_comparison_text",
    "prepare_extracted_items",
    # aggregate
    "compute_aggregate_metrics",
    # paths
    "BENCHMARK_ROOT",
    "GROUND_TRUTH_ROOT",
    "GROUND_TRUTH_UNIFIED_ROOT",
    "GROUND_TRUTH_CLINGEN_ROOT",
    "GROUND_TRUTH_DIR",
    "REPORTS_ROOT",
    "REPORTS_DIR",
    "RAW_PDF_ROOT",
    # pdf
    "markdown_to_pdf_bytes",
    "sanitize_for_pdf",
    # pipeline client
    "POLL_INTERVAL_S",
    "MAX_POLL_ATTEMPTS",
    "QUEUED_STATUSES",
    "TERMINAL_STATUSES",
    "preflight_database_connection",
    "compare_entity_standardization",
    "compare_track_consistency",
    "submit_and_poll",
    "evaluate_one",
    "load_proxy",
    "run_evaluation",
]
