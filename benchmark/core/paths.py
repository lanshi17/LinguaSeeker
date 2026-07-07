"""Centralized filesystem roots for the benchmark suite.

Imported by every layer (datasets, runners, analysis) so that ground-truth
and report locations stay in one place. Phase 4 of the 2026-06-18
framework refactor (see
``docs/active/2026-06-18-benchmark-framework-refactor-plan.md``) flipped
these constants from the legacy ``benchmark/layer3/`` layout to
``benchmark/data/``; they remain stable for downstream code.
"""
from __future__ import annotations

from pathlib import Path

__all__ = [
    "BENCHMARK_ROOT",
    "DATA_ROOT",
    "GROUND_TRUTH_ROOT",
    "GROUND_TRUTH_UNIFIED_ROOT",
    "GROUND_TRUTH_CLINGEN_ROOT",
    "GROUND_TRUTH_CLINVAR_FUSED_ROOT",
    "GROUND_TRUTH_RETT_ROOT",
    "REPORTS_ROOT",
    "INPUTS_ROOT",
    "RAW_PDF_ROOT",
    "PAPER_ROOT",
    "PAPER_MANIFESTS_ROOT",
    "PAPER_REPORTS_ROOT",
    "PAPER_GROUND_TRUTH_ROOT",
]


BENCHMARK_ROOT: Path = Path(__file__).resolve().parent.parent
"""Directory ``benchmark/`` (one level above ``core/``)."""

DATA_ROOT: Path = BENCHMARK_ROOT / "data"
"""Top-level data root that holds ``ground_truth/``, ``inputs/``, ``reports/``."""

GROUND_TRUTH_UNIFIED_ROOT: Path = DATA_ROOT / "ground_truth" / "unified"
"""Unified gold-standard ground-truth root (150 entries).

Default benchmark dataset since 2026-06-25. Subtree contains
``manifest.json`` plus one ``gs_NNN/`` directory per evaluated entry
(``source.md``, ``expected.json``, etc.).  Each entry carries
``source_dataset`` and ``original_entry_id`` for provenance.
"""

GROUND_TRUTH_ROOT: Path = GROUND_TRUTH_UNIFIED_ROOT
"""Default ground-truth root — points to the unified dataset.

Legacy datasets (clingen, clinvar_fused, rett) are still accessible via
their dedicated ``GROUND_TRUTH_*_ROOT`` constants but are no longer the
default.
"""

GROUND_TRUTH_CLINGEN_ROOT: Path = DATA_ROOT / "ground_truth" / "clingen"
"""ClinGen ground-truth root (legacy, 34 entries).

.. deprecated::
    Use :data:`GROUND_TRUTH_ROOT` (unified) for new evaluations.
"""

GROUND_TRUTH_CLINVAR_FUSED_ROOT: Path = DATA_ROOT / "ground_truth" / "clinvar_fused"
"""ClinVar fused ground-truth root."""

GROUND_TRUTH_RETT_ROOT: Path = DATA_ROOT / "ground_truth" / "rett"
"""Rett ground-truth root."""

REPORTS_ROOT: Path = DATA_ROOT / "reports"
"""Per-report output root, second-level bucketed:

* ``reports/eval/``           - end-to-end evaluation reports
* ``reports/reconcile/``      - reconcile ablations & case studies
* ``reports/baseline/``       - LLM baseline reports & summary tables
* ``reports/traceability/``   - traceability metric reports
* ``reports/benchmark_b/``    - multilingual pilot Phase 2 outputs
* ``reports/curation/``       - dataset curation / readiness / inventory
* ``reports/paper/``          - paper-specific tables & rescue manifests
* ``reports/diagnostics/``    - diagnose_* outputs
* ``reports/clinvar_fused/``  - fused-dataset eval reports
* ``reports/pipeline_e2e/``   - HTTP pipeline benchmark runs
"""

INPUTS_ROOT: Path = DATA_ROOT / "inputs"
"""PDF / markdown inputs to runners.

Subdirs:

* ``inputs/pipeline/``                — pipeline_e2e manifest + case-report PDFs
* ``inputs/literature_acquisition/``  — provider configs, query lists, downloads
"""

RAW_PDF_ROOT: Path = INPUTS_ROOT / "literature_acquisition" / "downloads"
"""Raw downloaded PDFs directory used by literature acquisition runners."""

PAPER_ROOT: Path = BENCHMARK_ROOT / "paper"
"""Consolidated paper artifacts root.

Single source of truth for all benchmark paper-related data:
manifests, reports, ground truth, and analysis scripts.
"""

PAPER_MANIFESTS_ROOT: Path = PAPER_ROOT / "manifests"
"""Rett manifests (JSON, CSV, JSONL) for paper experiments."""

PAPER_REPORTS_ROOT: Path = PAPER_ROOT / "reports"
"""Timestamped paper reports and figure packs."""

PAPER_GROUND_TRUTH_ROOT: Path = PAPER_ROOT / "ground_truth"
"""Rett ground truth entries for paper evaluation."""
