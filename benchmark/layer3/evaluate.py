"""DEPRECATED: this module is a transitional shim.

The contents previously living in ``benchmark.layer3.evaluate`` were split
into ``benchmark.core`` during the 2026-06-18 framework refactor (see
``docs/active/2026-06-18-benchmark-framework-refactor-plan.md``).

All public symbols are re-exported here for one-release backward
compatibility. New code MUST import from ``benchmark.core``; this shim
will be removed in Phase 6 of the refactor.
"""
from __future__ import annotations

import warnings
import asyncio  # noqa: F401  - re-exported for legacy `evaluate.asyncio.run` callsites

from benchmark.core.aggregate import (  # noqa: F401
    _false_positive_count,
    _over_extraction_count,
    compute_aggregate_metrics,
)
from benchmark.core.contracts import EntryMetrics, FieldMatch  # noqa: F401
from benchmark.core.matching import (  # noqa: F401
    compare_evidence,
    fuzzy_match_value,
    mark_expected_fields_missing,
    normalize_comparison_text,
)
from benchmark.core.paths import (  # noqa: F401
    GROUND_TRUTH_ROOT as GROUND_TRUTH_DIR,
    REPORTS_ROOT as REPORTS_DIR,
)
from benchmark.core.pdf import (  # noqa: F401
    _sanitize_for_pdf,
    markdown_to_pdf_bytes,
)
from benchmark.core.pipeline_client import (  # noqa: F401
    MAX_POLL_ATTEMPTS,
    POLL_INTERVAL_S,
    TERMINAL_STATUSES,
    compare_entity_standardization,
    compare_track_consistency,
    evaluate_one,
    load_proxy,
    preflight_database_connection,
    run_evaluation,
    submit_and_poll,
)


warnings.warn(
    "benchmark.layer3.evaluate is deprecated; import from benchmark.core instead.",
    DeprecationWarning,
    stacklevel=2,
)


if __name__ == "__main__":  # pragma: no cover - CLI parity with the old entry point
    import argparse
    import asyncio
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--entries", nargs="+", default=None, help="Specific entry IDs to evaluate")
    parser.add_argument(
        "--ground-truth-root",
        type=Path,
        default=GROUND_TRUTH_DIR,
        help="Ground truth root (default: unified dataset)",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=None,
        help="Shard index for batch execution (requires --shard-size)",
    )
    parser.add_argument(
        "--shard-size",
        type=int,
        default=None,
        help="Number of entries per shard (requires --shard-index)",
    )
    parser.add_argument(
        "--no-preprocessed",
        action="store_true",
        default=False,
        help="Force re-extraction through the pipeline, ignoring cached preprocessed results",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for X-API-Key header authentication",
    )
    parser.add_argument(
        "--extraction-profile",
        default="none",
        help="Extraction field profile (none, dataset_d_publication)",
    )
    args = parser.parse_args()
    asyncio.run(
        run_evaluation(
            args.base_url,
            args.concurrency,
            args.limit,
            args.entries,
            ground_truth_root=args.ground_truth_root,
            force_reextract=args.no_preprocessed,
            api_key=args.api_key,
            extraction_profile=args.extraction_profile,
            shard_index=args.shard_index,
            shard_size=args.shard_size,
        )
    )
